# -*- coding: utf-8 -*-
"""Feature 3 — Procurement loop: PR → PO → GR (đóng vòng cung ứng).

Khép vòng vận hành: KH sản xuất trừ kho → tồn thấp → đề xuất mua (PR) → tạo PO
gửi NCC → nhận hàng (GR) tăng tồn → tiếp tục sản xuất / bán hàng.
"""
from datetime import date, datetime
from decimal import Decimal

from app.config.database import db
from app.services.services import ProductionPlanService


class ProcurementService:
    """Đơn mua hàng (PurchaseOrder) và Nhập kho (GoodsReceipt)."""

    # ---- number generators ------------------------------------------------
    def _gen_po_number(self, company_id):
        from app.models.models import PurchaseOrder
        n = PurchaseOrder.query.filter_by(company_id=company_id).count() + 1
        return f"PO-{datetime.now():%y%m}-{n:04d}"

    def _gen_gr_number(self, company_id):
        from app.models.models import GoodsReceipt
        n = GoodsReceipt.query.filter_by(company_id=company_id).count() + 1
        return f"GR-{datetime.now():%y%m}-{n:04d}"

    # ---- PR → PO ----------------------------------------------------------
    def create_pos_from_suggestions(self, company_id, store_id=None):
        """Từ đề xuất mua hàng, tạo mỗi nhà cung cấp một PO nháp (vật tư chưa gán
        NCC gộp vào một PO riêng). Trả về danh sách PO vừa tạo."""
        from app.models.models import PurchaseOrder, PurchaseOrderLine
        data = ProductionPlanService().purchase_suggestions(company_id)
        created = []
        for grp in data['groups']:
            supplier = grp['supplier']
            po = PurchaseOrder(
                company_id=company_id, store_id=store_id,
                supplier_id=(supplier.id if supplier else None),
                po_number=self._gen_po_number(company_id),
                status=PurchaseOrder.STATUS_DRAFT, order_date=date.today(),
                vat_rate=Decimal('0'))
            db.session.add(po)
            db.session.flush()
            for ln in grp['lines']:
                m = ln['material']
                qty = Decimal(str(ln['suggested']))
                price = Decimal(str(ln['unit_price']))
                db.session.add(PurchaseOrderLine(
                    po_id=po.id, material_id=m.id, quantity_ordered=qty, unit=ln['unit'],
                    unit_price=price, line_total=(qty * price).quantize(Decimal('1'))))
            db.session.flush()
            po.recompute_totals()
            created.append(po)
        db.session.commit()
        return created

    def create_manual_po(self, company_id, supplier_id=None, store_id=None):
        from app.models.models import PurchaseOrder
        po = PurchaseOrder(company_id=company_id, supplier_id=supplier_id, store_id=store_id,
                           po_number=self._gen_po_number(company_id),
                           status=PurchaseOrder.STATUS_DRAFT, order_date=date.today(),
                           vat_rate=Decimal('0'))
        db.session.add(po); db.session.commit()
        return po

    # ---- PO editing -------------------------------------------------------
    def add_line(self, po, material_id, quantity, unit=None, unit_price=None):
        from app.models.models import PurchaseOrderLine, Material
        if not po.can_edit():
            raise ValueError("Đơn mua đã gửi/hủy — không sửa được dòng.")
        m = Material.query.get(material_id)
        if m is None or str(m.company_id) != str(po.company_id):
            raise ValueError("Vật tư không hợp lệ.")
        qty = Decimal(str(quantity or 0))
        if qty <= 0:
            raise ValueError("Số lượng phải > 0.")
        price = Decimal(str(unit_price)) if unit_price not in (None, '') else Decimal(str(m.unit_price or 0))
        db.session.add(PurchaseOrderLine(
            po_id=po.id, material_id=m.id, quantity_ordered=qty,
            unit=unit or (m.unit.name if m.unit else None), unit_price=price,
            line_total=(qty * price).quantize(Decimal('1'))))
        db.session.flush()
        po.recompute_totals()
        db.session.commit()
        return po

    def delete_line(self, po, line_id):
        from app.models.models import PurchaseOrderLine
        if not po.can_edit():
            raise ValueError("Đơn mua đã gửi/hủy — không sửa được dòng.")
        line = PurchaseOrderLine.query.get(line_id)
        if line and str(line.po_id) == str(po.id):
            db.session.delete(line); db.session.flush()
            po.recompute_totals()
            db.session.commit()
        return po

    def set_header(self, po, supplier_id=None, store_id=None, expected_date=None,
                   vat_rate=None, notes=None):
        if not po.can_edit():
            raise ValueError("Đơn mua đã gửi/hủy — không sửa được.")
        if supplier_id is not None:
            po.supplier_id = supplier_id or None
        if store_id is not None:
            po.store_id = store_id or None
        if expected_date is not None:
            po.expected_date = expected_date or None
        if vat_rate is not None:
            po.vat_rate = Decimal(str(vat_rate or 0))
        if notes is not None:
            po.notes = notes
        po.recompute_totals()
        db.session.commit()
        return po

    def transition(self, po, action):
        tr = po.TRANSITIONS.get(action)
        if not tr or po.status not in tr[0]:
            raise ValueError(f'Không thể "{action}" khi đơn mua ở trạng thái "{po.status}"')
        po.status = tr[1]
        db.session.commit()
        return po

    # ---- GR: nhận hàng, tăng tồn -----------------------------------------
    def receive(self, po, quantities, store_id=None, receipt_date=None, notes=None):
        """Nhận hàng theo PO. ``quantities`` = {po_line_id(str): qty}. Tạo phiếu
        nhập kho, **tăng MaterialStock**, cập nhật đã-nhận + trạng thái PO.
        Trả về (GoodsReceipt, warnings)."""
        from app.models.models import GoodsReceipt, GoodsReceiptLine, MaterialStock
        if not po.can_receive():
            raise ValueError("Chỉ nhập kho khi đơn mua đã gửi NCC và chưa nhập đủ.")
        target_store = store_id if store_id is not None else po.store_id

        gr = GoodsReceipt(company_id=po.company_id, po_id=po.id, store_id=target_store,
                          gr_number=self._gen_gr_number(po.company_id),
                          receipt_date=receipt_date or date.today(), notes=notes, is_posted=True)
        db.session.add(gr)
        db.session.flush()

        warnings = []
        any_received = False
        for line in po.lines:
            qty = Decimal(str(quantities.get(str(line.id), 0) or 0))
            if qty <= 0:
                continue
            if qty > line.outstanding:
                code = line.material.material_code if line.material else line.material_id
                warnings.append(f"{code}: nhận {qty} vượt số còn lại {line.outstanding}.")
            db.session.add(GoodsReceiptLine(
                gr_id=gr.id, po_line_id=line.id, material_id=line.material_id,
                quantity_received=qty, unit=line.unit))
            st = MaterialStock.query.filter_by(material_id=line.material_id, store_id=target_store).first()
            if st is None and target_store is not None:
                st = MaterialStock.query.filter_by(material_id=line.material_id, store_id=None).first()
            if st is None:
                st = MaterialStock(company_id=po.company_id, material_id=line.material_id,
                                   store_id=target_store, current_quantity=Decimal('0'))
                db.session.add(st)
            st.current_quantity = Decimal(str(st.current_quantity or 0)) + qty
            line.quantity_received = Decimal(str(line.quantity_received or 0)) + qty
            any_received = True

        if not any_received:
            db.session.rollback()
            raise ValueError("Chưa nhập số lượng nào để nhận.")

        po.sync_receipt_status()
        db.session.commit()
        return gr, warnings

    # ---- queries ----------------------------------------------------------
    def list_pos(self, company_id, status=None):
        from app.models.models import PurchaseOrder
        q = PurchaseOrder.query.filter_by(company_id=company_id)
        if status:
            q = q.filter_by(status=status)
        return q.order_by(PurchaseOrder.created_at.desc()).all()

    def get_po(self, company_id, po_id):
        from app.models.models import PurchaseOrder
        po = PurchaseOrder.query.get(po_id)
        return po if po and str(po.company_id) == str(company_id) else None
