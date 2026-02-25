# Deployment Guide for SofaFlow

## Overview
This guide covers deploying SofaFlow to production environments.

## Prerequisites

- Linux server (Ubuntu 20.04+ recommended)
- PostgreSQL 12+
- Python 3.8+
- Nginx
- Gunicorn
- Supervisor (for process management)

## Step 1: Server Setup

### Update System
```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### Install Dependencies
```bash
sudo apt-get install -y python3.11 python3.11-venv python3-pip
sudo apt-get install -y postgresql postgresql-contrib
sudo apt-get install -y nginx
sudo apt-get install -y supervisor
sudo apt-get install -y libreoffice  # For advanced PDF generation
```

## Step 2: Create Application User

```bash
sudo useradd -m -s /bin/bash sofaflow
sudo su - sofaflow
```

## Step 3: Clone Application

```bash
git clone <repository-url> sofaflow
cd sofaflow
```

## Step 4: Setup Python Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

## Step 5: Configure Database

### Create Database
```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE sofa_flow;
CREATE USER sofa_user WITH PASSWORD 'strong_password_here';
ALTER ROLE sofa_user SET client_encoding TO 'utf8';
ALTER ROLE sofa_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE sofa_user SET default_transaction_deferrable TO on;
ALTER ROLE sofa_user SET default_transaction_deferrable TO on;
GRANT ALL PRIVILEGES ON DATABASE sofa_flow TO sofa_user;
\q
```

### Initialize Database
```bash
export DATABASE_URL="postgresql://sofa_user:strong_password_here@localhost:5432/sofa_flow"
python init_db.py
```

## Step 6: Create Environment File

Create `.env` file in application directory:

```bash
cat > /home/sofaflow/sofaflow/.env << EOF
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=$(python -c 'import os; print(os.urandom(24).hex())')
DATABASE_URL=postgresql://sofa_user:strong_password_here@localhost:5432/sofa_flow
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
EOF
```

## Step 7: Configure Gunicorn

Create `/home/sofaflow/sofaflow/gunicorn_config.py`:

```python
import multiprocessing

bind = "127.0.0.1:5000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2
```

Test Gunicorn:
```bash
cd /home/sofaflow/sofaflow
source venv/bin/activate
gunicorn -c gunicorn_config.py wsgi:app
```

## Step 8: Configure Supervisor

Create `/etc/supervisor/conf.d/sofaflow.conf`:

```ini
[program:sofaflow]
process_name=%(program_name)s
command=/home/sofaflow/sofaflow/venv/bin/gunicorn -c /home/sofaflow/sofaflow/gunicorn_config.py wsgi:app
directory=/home/sofaflow/sofaflow
user=sofaflow
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/sofaflow.log
```

Activate Supervisor:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start sofaflow
```

Check status:
```bash
sudo supervisorctl status sofaflow
```

## Step 9: Configure Nginx

Create `/etc/nginx/sites-available/sofaflow`:

```nginx
upstream sofaflow {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Limit request body
    client_max_body_size 50M;

    # Logs
    access_log /var/log/nginx/sofaflow_access.log;
    error_log /var/log/nginx/sofaflow_error.log;

    # Proxy settings
    location / {
        proxy_pass http://sofaflow;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files
    location /static/ {
        alias /home/sofaflow/sofaflow/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Uploads
    location /uploads/ {
        alias /home/sofaflow/sofaflow/app/uploads/;
        expires 7d;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/sofaflow /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Step 10: Setup SSL with Let's Encrypt

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d your-domain.com
```

## Step 11: Setup Monitoring and Logging

### Logrotate Configuration

Create `/etc/logrotate.d/sofaflow`:

```
/var/log/sofaflow.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 sofaflow sofaflow
    sharedscripts
    postrotate
        /usr/lib/supervisor/supervisor-script.py reread >/dev/null 2>&1
    endscript
}
```

## Step 12: Backup Strategy

### Database Backup Script

Create `/home/sofaflow/backup_db.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/home/sofaflow/backups"
DB_NAME="sofa_flow"
DB_USER="sofa_user"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Create backup
pg_dump -U $DB_USER $DB_NAME | gzip > $BACKUP_DIR/sofa_flow_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "sofa_flow_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/sofa_flow_$DATE.sql.gz"
```

Add to crontab:
```bash
0 2 * * * /home/sofaflow/backup_db.sh
```

## Step 13: Performance Optimization

### Database Indexes
```sql
CREATE INDEX idx_order_company_id ON orders(company_id);
CREATE INDEX idx_order_customer_id ON orders(customer_id);
CREATE INDEX idx_customer_store_id ON customers(store_id);
CREATE INDEX idx_lifecycle_order_id ON lifecycle_statuses(order_id);
```

### Connection Pooling
In `app/config/config.py`:
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}
```

## Step 14: Monitoring

### System Monitoring
```bash
sudo apt-get install htop iotop
```

### Log Monitoring
```bash
sudo tail -f /var/log/sofaflow.log
```

## Production Checklist

- [ ] Database backups configured
- [ ] SSL certificate installed
- [ ] Security headers configured
- [ ] Rate limiting configured
- [ ] Monitoring and alerting set up
- [ ] Log rotation configured
- [ ] Database indexes created
- [ ] Connection pooling configured
- [ ] File permissions secured
- [ ] SSH key-based authentication enabled
- [ ] Firewall rules configured
- [ ] Regular security updates scheduled

## Troubleshooting

### Application won't start
```bash
sudo supervisorctl restart sofaflow
tail -f /var/log/sofaflow.log
```

### Database connection issues
```bash
sudo -u postgres psql sofa_flow
\dt  # List tables
```

### Nginx errors
```bash
sudo nginx -t
sudo tail -f /var/log/nginx/sofaflow_error.log
```

## Scaling Considerations

### Horizontal Scaling
- Use load balancer (HAProxy, AWS ALB)
- Run multiple Gunicorn instances
- Use shared database
- Store uploads in S3 or shared storage

### Vertical Scaling
- Increase server resources
- Optimize database queries
- Enable caching layer (Redis)

## Security Hardening

1. **Firewall**
   ```bash
   sudo ufw enable
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```

2. **Regular Updates**
   ```bash
   sudo apt-get install -y unattended-upgrades
   ```

3. **SSH Hardening**
   - Disable root login
   - Use SSH keys only
   - Change default port

4. **Database Security**
   - Use strong passwords
   - Regular backups
   - Enable replication

---

For more help, refer to the main README.md file.
