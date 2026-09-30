#!/usr/bin/env bash
# Xoa du lieu do bo test tu dong sinh ra tren QAS (ten/ma co 'AUTOTEST').
# Chi chay tren DB QAS. KHONG chay tren prod.
set -euo pipefail
KEY="${SSH_KEY:-Q:/SERVERS/iNet/CS-Linux-20251105132714721.pem}"
HOST="${QAS_HOST:-root@103.57.220.46}"
ssh -i "$KEY" "$HOST" "docker exec -i sofa-flow-qas-db-1 psql -U sofa_user -d sofa_flow_qas -v ON_ERROR_STOP=1" <<'SQL'
BEGIN;
CREATE TEMP TABLE t_orders AS
  SELECT o.id FROM orders o JOIN customers c ON c.id = o.customer_id
  WHERE o.title LIKE 'AUTOTEST%' OR c.name LIKE 'AUTOTEST%';
DELETE FROM documents        WHERE order_id IN (SELECT id FROM t_orders);
DELETE FROM payment_reports  WHERE order_id IN (SELECT id FROM t_orders);
DELETE FROM handover_records WHERE order_id IN (SELECT id FROM t_orders);
DELETE FROM contracts        WHERE order_id IN (SELECT id FROM t_orders);
DELETE FROM quotations       WHERE order_id IN (SELECT id FROM t_orders);
DELETE FROM lifecycle_statuses WHERE order_id IN (SELECT id FROM t_orders);
DELETE FROM orders           WHERE id IN (SELECT id FROM t_orders);
DELETE FROM customers        WHERE name LIKE 'AUTOTEST%';
COMMIT;
SQL
echo "Da don du lieu AUTOTEST tren QAS."
