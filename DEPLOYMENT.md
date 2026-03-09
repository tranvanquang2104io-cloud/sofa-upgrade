# Deployment Guide

Production deployment for SofaFlow on Ubuntu 20.04+ using **Gunicorn + Nginx + Supervisor**.

## 1. Server Setup

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3.11 python3.11-venv python3-pip
sudo apt-get install -y postgresql postgresql-contrib
sudo apt-get install -y nginx supervisor
```

## 2. Create App User

```bash
sudo useradd -m -s /bin/bash sofaflow
sudo su - sofaflow
```

## 3. Deploy Application

```bash
git clone <repository-url> sofaflow
cd sofaflow
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

## 4. Configure Database

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE sofa_flow;
CREATE USER sofa_user WITH PASSWORD 'strong_password_here';
GRANT ALL PRIVILEGES ON DATABASE sofa_flow TO sofa_user;
\c sofa_flow
GRANT USAGE, CREATE ON SCHEMA public TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO sofa_user;
\q
```

```bash
export DATABASE_URL="postgresql+psycopg://sofa_user:strong_password_here@localhost:5432/sofa_flow"
python create_docx_templates.py
python seed_docx_templates.py
```

## 5. Environment File

Create `/home/sofaflow/sofaflow/.env`:

```ini
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=<generate with: python -c "import os; print(os.urandom(32).hex())">
DATABASE_URL=postgresql+psycopg://sofa_user:strong_password_here@localhost:5432/sofa_flow
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
```

## 6. Gunicorn

Create `/home/sofaflow/sofaflow/gunicorn_config.py`:

```python
import multiprocessing

bind            = "127.0.0.1:5000"
workers         = multiprocessing.cpu_count() * 2 + 1
worker_class    = "sync"
timeout         = 30
max_requests    = 1000
max_requests_jitter = 50
```

Test:
```bash
cd /home/sofaflow/sofaflow && source venv/bin/activate
gunicorn -c gunicorn_config.py wsgi:app
```

## 7. Supervisor

Create `/etc/supervisor/conf.d/sofaflow.conf`:

```ini
[program:sofaflow]
command=/home/sofaflow/sofaflow/venv/bin/gunicorn -c /home/sofaflow/sofaflow/gunicorn_config.py wsgi:app
directory=/home/sofaflow/sofaflow
user=sofaflow
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/sofaflow.log
```

```bash
sudo supervisorctl reread && sudo supervisorctl update
sudo supervisorctl start sofaflow
sudo supervisorctl status sofaflow
```

## 8. Nginx

Create `/etc/nginx/sites-available/sofaflow`:

```nginx
upstream sofaflow { server 127.0.0.1:5000; }

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    client_max_body_size 50M;
    access_log /var/log/nginx/sofaflow_access.log;
    error_log  /var/log/nginx/sofaflow_error.log;

    location / {
        proxy_pass http://sofaflow;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias   /home/sofaflow/sofaflow/app/static/;
        expires 30d;
    }

    location /uploads/ {
        alias   /home/sofaflow/sofaflow/app/uploads/;
        expires 7d;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/sofaflow /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

## 9. SSL (Let's Encrypt)

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot certonly --nginx -d your-domain.com
```

## 10. Database Backups

Create `/home/sofaflow/backup_db.sh`:

```bash
#!/bin/bash
DIR="/home/sofaflow/backups"
mkdir -p $DIR
pg_dump -U sofa_user sofa_flow | gzip > $DIR/sofa_flow_$(date +%Y%m%d_%H%M%S).sql.gz
find $DIR -name "*.sql.gz" -mtime +30 -delete
```

Add to crontab (`crontab -e`):
```
0 2 * * * /home/sofaflow/backup_db.sh
```

## 11. Firewall

```bash
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

## Production Checklist

- [ ] `FLASK_DEBUG=False` and strong `SECRET_KEY` set
- [ ] PostgreSQL user limited to `sofa_flow` database only
- [ ] SSL certificate installed and auto-renewing
- [ ] Supervisor configured to auto-restart on crash
- [ ] Nginx serving static files directly (not via Flask)
- [ ] Daily database backups with 30-day retention
- [ ] Log rotation configured (`/etc/logrotate.d/sofaflow`)
- [ ] Firewall rules in place
- [ ] Unattended security updates enabled

## Troubleshooting

| Symptom | Command |
|---------|---------|
| App not responding | `sudo supervisorctl restart sofaflow` |
| Check app logs | `sudo tail -f /var/log/sofaflow.log` |
| Nginx config error | `sudo nginx -t` |
| Nginx error log | `sudo tail -f /var/log/nginx/sofaflow_error.log` |
| DB connection issue | `psql -U sofa_user -d sofa_flow -c "\dt"` |
