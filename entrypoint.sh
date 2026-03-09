#!/bin/sh
# Entrypoint script: chạy trước khi khởi động Flask
# 1. Tạo master admin nếu chưa có
# 2. Khởi động app

set -e

echo "[entrypoint] Initializing master admin..."
PYTHONPATH=/app python /app/scripts/create_master_admin.py

echo "[entrypoint] Starting application..."
exec "$@"
