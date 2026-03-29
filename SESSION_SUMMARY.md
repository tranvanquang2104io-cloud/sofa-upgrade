# Sofa Flow – Deployment & Ops Notes (session recap)

## Docker Compose (production)
- Use prod stack with env file:  
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
  ```
- Port mapping to avoid conflicts: host `90:80` (HTTP), `9443:443` (HTTPS).
- Required env: `POSTGRES_PASSWORD`, `SECRET_KEY`, `POSTGRES_DB`, `POSTGRES_USER`, `APP_VERSION`.

## Nginx (inside container)
- HTTP redirects to HTTPS port 9443:
  ```nginx
  server { listen 80; server_name _; return 301 https://$host:9443$request_uri; }
  ```
- HTTPS serves the app and proxies to Gunicorn on `app:5000` with self‑signed/real cert:
  ```nginx
  server {
      listen 443 ssl http2;
      server_name _;
      ssl_certificate     /etc/letsencrypt/live/ip-self/fullchain.pem;
      ssl_certificate_key /etc/letsencrypt/live/ip-self/privkey.pem;
      location / { proxy_pass http://sofa_app; }
      location /static/  { alias /app/static/;  expires 30d; }
      location /uploads/ { alias /app/uploads/; expires 7d; }
  }
  ```
- Mount certs from host: `- /etc/letsencrypt:/etc/letsencrypt:ro`.

## Self-signed certificate tied to host IP (no domain)
```bash
IP=$(hostname -I | awk '{print $1}')
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout privkey.pem -out fullchain.pem \
  -subj "/CN=${IP}" \
  -addext "subjectAltName=IP:${IP}"
sudo mkdir -p /etc/letsencrypt/live/ip-self
sudo mv fullchain.pem /etc/letsencrypt/live/ip-self/
sudo mv privkey.pem   /etc/letsencrypt/live/ip-self/
```
Access app at `https://<IP>:9443/admin/login` (browser will warn self-signed).

## Database checks
- List DBs: `docker exec -it sofa-flow-prod-db-1 psql -U sofa_user -l`
- List tables: `docker exec -it sofa-flow-prod-db-1 psql -U sofa_user -d sofa_flow -c "\dt"`
- Quick query example:  
  `docker exec -it sofa-flow-prod-db-1 psql -U sofa_user -d sofa_flow -c "SELECT count(*) FROM users;"`

## Master admin account
- Reset/create login inside app container:  
  ```bash
  docker exec -it sofa-flow-prod-app-1 sh -c "python - <<'PY'
  from app import create_app
  from app.config.database import db
  from app.models.models import MasterAdmin
  app = create_app('production')
  with app.app_context():
      admin = MasterAdmin.query.filter_by(username='masteradmin').first()
      if not admin:
          admin = MasterAdmin(username='masteradmin', email='admin@sofaflow.local', full_name='Master Administrator')
          db.session.add(admin)
      admin.is_active = True
      admin.set_password('NewStrongPass@2024')  # change after login
      db.session.commit()
      print('Reset masteradmin')
  PY"
  ```
- Login URL: `/admin/login` via HTTPS port 9443.

## Common issues resolved
- Session not persisted over HTTP in production: caused by `SESSION_COOKIE_SECURE=True`; use HTTPS (above) or temporarily set `SESSION_COOKIE_SECURE=false`.
- Port conflicts on host: change compose port mappings instead of container ports (e.g., `90:80`, `9443:443`).
- Missing `POSTGRES_PASSWORD`: supply via `.env.prod` or shell `export POSTGRES_PASSWORD=...` before running compose.
- Stopping accidental dev DB: `docker stop sofa-flow-dev-db-1` (or `docker compose -p sofa-flow-dev down`).

## Useful log commands
- App: `docker logs -f sofa-flow-prod-app-1`
- Nginx: `docker logs -f sofa-flow-prod-nginx-1`
- Check port bindings: `docker ps | grep sofa-flow-prod-nginx`

