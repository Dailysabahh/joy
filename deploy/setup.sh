#!/usr/bin/env bash
# ============================================================
#  Joy + Closer Tech — Full Server Setup
#  Runs on Ubuntu 22.04 on AWS EC2
# ============================================================
set -e

APP_DIR="/opt/joy"
WEB_DIR="/var/www/closertech"
JOY_DOMAIN="joy.aicloser.tech"
ROOT_DOMAIN="aicloser.tech"

echo "============================================"
echo "  Closer Tech — Server Setup"
echo "  Joy Bot + Website"
echo "============================================"

# ── 1. System update ────────────────────────────────────────
echo "[1/9] Updating system..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3 python3-pip python3-venv nginx certbot python3-certbot-nginx ufw

# ── 2. Firewall ─────────────────────────────────────────────
echo "[2/9] Configuring firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# ── 3. Deploy Joy app ────────────────────────────────────────
echo "[3/9] Deploying Joy to $APP_DIR..."
if [ -d "$APP_DIR" ]; then
  echo "  Backing up existing..."
  mv "$APP_DIR" "${APP_DIR}_bak_$(date +%Y%m%d%H%M%S)"
fi
cp -r /tmp/joy "$APP_DIR"
chown -R ubuntu:ubuntu "$APP_DIR"
chmod +x "$APP_DIR/deploy/setup.sh"

# ── 4. Python virtualenv ─────────────────────────────────────
echo "[4/9] Installing Python dependencies..."
cd "$APP_DIR"
python3 -m venv venv
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
echo "  Done."

# ── 5. Deploy Closer Tech website ───────────────────────────
echo "[5/9] Deploying Closer Tech website to $WEB_DIR..."
mkdir -p "$WEB_DIR"
if [ -d "/tmp/closertech_site" ]; then
  cp -r /tmp/closertech_site/. "$WEB_DIR/"
  chown -R www-data:www-data "$WEB_DIR"
  echo "  Website deployed."
else
  echo "  No website files found at /tmp/closertech_site — skipping."
fi

# ── 6. Nginx (HTTP only first — before certbot) ─────────────
echo "[6/9] Configuring Nginx (HTTP)..."
cat > /etc/nginx/sites-available/closertech-http <<'NGINXHTTP'
server {
    listen 80;
    server_name joy.aicloser.tech aicloser.tech www.aicloser.tech;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 200 "OK"; }
}
NGINXHTTP

ln -sf /etc/nginx/sites-available/closertech-http /etc/nginx/sites-enabled/closertech-http
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ── 7. SSL Certificates ──────────────────────────────────────
echo "[7/9] Obtaining SSL certificates..."

# Certificate for joy.aicloser.tech
certbot certonly --nginx \
  -d "$JOY_DOMAIN" \
  --non-interactive \
  --agree-tos \
  --email olakunle@closertech.ai \
  --redirect 2>/dev/null || \
certbot certonly --standalone \
  -d "$JOY_DOMAIN" \
  --non-interactive \
  --agree-tos \
  --email olakunle@closertech.ai \
  --http-01-port 80

# Certificate for aicloser.tech + www
certbot certonly --nginx \
  -d "$ROOT_DOMAIN" -d "www.$ROOT_DOMAIN" \
  --non-interactive \
  --agree-tos \
  --email olakunle@closertech.ai \
  --redirect 2>/dev/null || \
certbot certonly --standalone \
  -d "$ROOT_DOMAIN" -d "www.$ROOT_DOMAIN" \
  --non-interactive \
  --agree-tos \
  --email olakunle@closertech.ai \
  --http-01-port 80

echo "  SSL certificates obtained."

# ── 8. Full Nginx config ─────────────────────────────────────
echo "[8/9] Installing full Nginx config..."
rm -f /etc/nginx/sites-enabled/closertech-http
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/closertech
ln -sf /etc/nginx/sites-available/closertech /etc/nginx/sites-enabled/closertech
nginx -t && systemctl reload nginx

# ── 9. Systemd service ──────────────────────────────────────
echo "[9/9] Installing Joy systemd service..."
cp "$APP_DIR/deploy/joy.service" /etc/systemd/system/joy.service
systemctl daemon-reload
systemctl enable joy
systemctl restart joy

echo ""
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
echo "  Joy bot:      https://$JOY_DOMAIN"
echo "  Website:      https://$ROOT_DOMAIN"
echo "  Admin panel:  https://$JOY_DOMAIN/admin"
echo "  Webhook URL:  https://$JOY_DOMAIN/webhook"
echo ""
echo "  Joy status:"
systemctl status joy --no-pager -l | tail -5
echo ""
