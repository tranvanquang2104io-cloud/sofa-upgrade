# -*- coding: utf-8 -*-
"""Đề nghị mua hàng (Purchase Requisition, PR) — tài liệu CRUD.

PR là nhu cầu mua nội bộ, tạo tay (không phụ thuộc mức tồn) hoặc điền sẵn từ đề
xuất tự động. Sau khi duyệt → chuyển thành một/nhiều Đơn mua hàng (PO) gộp theo
nhà cung cấp.
"""
from datetime import date, datetime
from decimal import Decimal

from app.config.database import db
from app.services.services import ProductionPlanService
from app.services.procurement_service import ProcurementService


class RequisitionService:
    def _gen_pr_number(self, company_id):
        from app.models.models import PurchaseRequisition
        n = PurchaseRequisition.query.filter_by(company_id=company_id).count() + 1
        return f"PR-{datetime.now():%y%m}-{n:04d}"

    def suggest_lines(self, company_id):
        """Gợi ý dòng vật tư (điền sẵn PR) từ đề xuất tự động (nhu cầu − tồn + min)."""
        data = ProductionPlanService().purchase_suggestions(company_id)
        out = []
        for grp in data['groups']:
            for ln in grp['lines']:
                out.append({'material_id': str(ln['material'].id), 'material': ln['material'],
                            'quantity': ln['suggested'], 'unit': ln['unit']})
        return out

    def create_pr(self, company_id, header, lines):
        from app.models.models import PurchaseRequisition
        pr = PurchaseRequisition(
            company_id=company_id, pr_number=self._gen_pr_number(company_id),
            status=PurchaseRequisition.STATUS_DRAFT,
            store_id=header.get('store_id') or None,
            request_date=header.get('request_date') or date.today(),
            expected_date=header.get('expected_date') or None,
            title=header.get('title') or None, notes=header.get('notes') or None)
        db.session.add(pr); db.session.flush()
        self._replace_lines(pr, lines)
        db.session.commit()
        return pr

    def update_pr(self, pr, header, lines):
        if not pr.can_edit():
            raise ValueError("PR đã gửi/duyệt/hủy — không sửa được.")
        pr.store_id = header.get('store_id') or None
        pr.request_date = header.get('request_date') or pr.request_date
        pr.expected_date = header.get('expected_date') or None
        pr.title = header.get('title') or None
        pr.notes = header.get('notes') or None
        self._replace_lines(pr, lines)
        db.session.commit()
        return pr

    def _replace_lines(self, pr, lines):
        from app.models.models import PurchaseRequisitionLine, Material
        pr.lines.clear()   # delete-orphan removes old lines
        db.session.flush()
        for ln in lines:
            mid = ln.get('material_id')
            if not mid:
                continue
            m = Material.query.get(mid)
            if m is None or str(m.company_id) != str(pr.company_id):
                continue
            pr.lines.append(PurchaseRequisitionLine(
                material_id=m.id,
                quantity=Decimal(str(ln.get('quantity') or 0)),
                unit=ln.get('unit') or (m.unit.name if m.unit else None),
                notes=ln.get('notes') or None))
        db.session.flush()

    def transition(self, pr, action):
        tr = pr.TRANSITIONS.get(action)
        if not tr or pr.status not in tr[0]:
            raise ValueError(f'Không thể "{action}" khi PR ở trạng thái "{pr.status}"')
        pr.status = tr[1]
        db.session.commit()
        return pr

    def convert_to_pos(self, pr):
        """PR đã duyệt → tạo PO nháp gộp theo nhà cung cấp; đánh dấu PR 'converted'."""
        from app.models.models import PurchaseOrder, PurchaseOrderLine, Material
        if not pr.can_convert():
            raise ValueError("Chỉ tạo PO từ PR đã được duyệt.")
        if not pr.lines:
            raise ValueError("PR chưa có dòng vật tư nào.")
        groups = {}
        for ln in pr.lines:
            m = ln.material or Material.query.get(ln.material_id)
            key = str(m.supplier_id) if (m and m.supplier_id) else '__none__'
            groups.setdefault(key, []).append((ln, m))
        proc = ProcurementService()
        created = []
        for key, items in groups.items():
            supplier_id = None if key == '__none__' else items[0][1].supplier_id
            po = PurchaseOrder(company_id=pr.company_id, pr_id=pr.id, store_id=pr.store_id,
                               supplier_id=supplier_id, po_number=proc._gen_po_number(pr.company_id),
                               status=PurchaseOrder.STATUS_DRAFT, order_date=date.today(),
                               vat_rate=Decimal('0'))
            db.session.add(po); db.session.flush()
            for ln, m in items:
                qty = Decimal(str(ln.quantity or 0))
                price = Decimal(str(m.unit_price or 0)) if m else Decimal('0')
                db.session.add(PurchaseOrderLine(
                    po_id=po.id, material_id=ln.material_id, quantity_ordered=qty, unit=ln.unit,
                    unit_price=price, line_total=(qty * price).quantize(Decimal('1'))))
            db.session.flush()
            po.recompute_totals()
            created.append(po)
        pr.status = pr.STATUS_CONVERTED
        db.session.commit()
        return created

    def list_prs(self, company_id, status=None):
        from app.models.models import PurchaseRequisition
        q = PurchaseRequisition.query.filter_by(company_id=company_id)
        if status:
            q = q.filter_by(status=status)
        return q.order_by(PurchaseRequisition.created_at.desc()).all()

    def get_pr(self, company_id, pr_id):
        from app.models.models import PurchaseRequisition
        pr = PurchaseRequisition.query.get(pr_id)
        return pr if pr and str(pr.company_id) == str(company_id) else None
