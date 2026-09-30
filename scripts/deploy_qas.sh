#!/usr/bin/env bash
# Deploy nhánh main cua repo sofa-upgrade len QAS (103.57.220.46).
# Chay tu may dev (Git Bash) trong thu muc Q:/Projects/sofa-upgrade:
#     bash scripts/deploy_qas.sh [--force]
# Mac dinh: khong co commit moi -> bo qua (exit 10). --force = deploy lai du khong doi.
# KHONG BAO GIO dung script nay cho production.
set -euo pipefail

KEY="${SSH_KEY:-Q:/SERVERS/iNet/CS-Linux-20251105132714721.pem}"
HOST="${QAS_HOST:-root@103.57.220.46}"
DIR=/opt/apps/sofa-flow-qas
STAMP=$(date +%Y%m%d-%H%M%S)
FORCE="${1:-}"

sh() { ssh -i "$KEY" -o StrictHostKeyChecking=no "$HOST" "$@"; }

echo "== [1/7] Fetch main"
git fetch -q origin main
NEW=$(git rev-parse origin/main)
CUR=$(sh "cat $DIR/.deployed_sha 2>/dev/null || echo none")
echo "   deployed=$CUR  remote=$NEW"
if [ "$NEW" = "$CUR" ] && [ "$FORCE" != "--force" ]; then
  echo "   Khong co commit moi -> bo qua."
  exit 10
fi
git log --oneline "$CUR..$NEW" 2>/dev/null | head -20 || true

echo "== [2/7] Backup DB QAS"
sh "mkdir -p /opt/backups/qas && docker exec sofa-flow-qas-db-1 pg_dump -U sofa_user -d sofa_flow_qas | gzip > /opt/backups/qas/qas-$STAMP.sql.gz && ls -lh /opt/backups/qas/qas-$STAMP.sql.gz"
# giu 5 ban gan nhat
sh "ls -1t /opt/backups/qas/*.sql.gz | tail -n +6 | xargs -r rm -f"

echo "== [3/7] Ship code"
git archive "$NEW" -o "/tmp/qas-$STAMP.tar"
scp -q -i "$KEY" "/tmp/qas-$STAMP.tar" "$HOST:/tmp/"
sh "tar -xf /tmp/qas-$STAMP.tar -C $DIR && rm -f /tmp/qas-$STAMP.tar && echo $NEW > $DIR/.deployed_sha"
rm -f "/tmp/qas-$STAMP.tar"

echo "== [4/7] Build image"
VER="$(git show "$NEW:VERSION" | tr -d '[:space:]')-qas-${NEW:0:7}"
sh "cd $DIR && sed -i 's/^APP_VERSION=.*/APP_VERSION=$VER/' .env.qas && docker compose -f docker-compose.qas.yml --env-file .env.qas build app" 2>&1 | tail -5

echo "== [5/7] Migrate"
sh "cd $DIR && PW=\$(grep ^POSTGRES_PASSWORD= .env.qas | cut -d= -f2-) && docker run --rm --network sofa-flow-qas_default --entrypoint sh \
  -e DATABASE_URL=postgresql+psycopg://sofa_user:\$PW@db:5432/sofa_flow_qas -e PYTHONPATH=/app sofa-flow-qas:$VER \
  -c \"pip install -q 'alembic>=1.13'; cd /app && python -m alembic upgrade head\"" 2>&1 | tail -5

echo "== [6/7] Restart app + tai khoan test"
sh "cd $DIR && docker compose -f docker-compose.qas.yml --env-file .env.qas up -d app" 2>&1 | tail -3
sleep 10
sh "docker exec -e PYTHONIOENCODING=utf-8 sofa-flow-qas-app-1 sh -c 'PYTHONPATH=/app python /app/scripts/create_qas_test_accounts.py' >/dev/null && echo '   tai khoan test: OK'"

echo "== [7/7] Verify + don dep"
# giu lai image QAS hien tai + 1 ban truoc, xoa cac ban cu hon
sh "docker images --format '{{.Repository}}:{{.Tag}}' sofa-flow-qas | grep -v ':$VER\$' | tail -n +2 | xargs -r docker rmi -f >/dev/null 2>&1; docker image prune -f >/dev/null; docker builder prune -f --filter until=24h >/dev/null; df -h / | tail -1"
CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 25 https://qas-sofaflow.quangtv.com/auth/login || true)
echo "   https://qas-sofaflow.quangtv.com/auth/login -> $CODE"
[ "$CODE" = "200" ] || { echo "   LOI: app khong phan hoi 200"; sh "docker logs --tail 40 sofa-flow-qas-app-1"; exit 1; }
echo "DEPLOYED $VER ($NEW)"
