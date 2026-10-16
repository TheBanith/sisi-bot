#!/usr/bin/env bash
# ==============================================================================
# Sisi Telegram Chatbot & 9Router AI Gateway - 1-Click Installer
# Supports: Ubuntu 22.04 LTS / 24.04 LTS (x86_64)
# ==============================================================================

set -e

if [ "$(id -u)" -ne 0 ]; then
  echo "Error: This script must be run as root. (Use sudo bash install.sh)"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "  🚀 Starting Sisi & 9Router Deployment on this VPS..."
echo "=========================================================="

# 1. Environment File Check
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
  else
    echo "Warning: .env file not found. Ensure .env is populated with your keys."
  fi
fi

# Load variables
set -a
[ -f .env ] && . .env
set +a

# 2. Swap Setup (Prevent OOM on 1GB RAM instances)
TOTAL_SWAP=$(free -m | awk '/^Swap:/ {print $2}')
if [ "$TOTAL_SWAP" -lt 1000 ]; then
  echo "-> Setting up 2GB Swap space..."
  if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "   Swap created and enabled."
  fi
else
  echo "-> Swap already sufficient (${TOTAL_SWAP}MB)."
fi

# 3. Install System Packages
echo "-> Updating system repositories and installing dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  curl wget git build-essential \
  python3 python3-pip python3-venv \
  ffmpeg privoxy lsb-release gnupg

# 4. Install Cloudflare WARP (for Geoblocking & Cloudflare unblocking)
if ! command -v warp-cli &> /dev/null; then
  echo "-> Installing Cloudflare WARP..."
  curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/cloudflare-client.list
  apt-get update -y
  apt-get install -y cloudflare-warp
fi

echo "-> Configuring Cloudflare WARP in Proxy Mode (port 40000)..."
systemctl enable --now warp-svc
warp-cli --accept-tos registration new || true
warp-cli --accept-tos mode proxy
warp-cli --accept-tos proxy port 40000
warp-cli --accept-tos connect || true

# 5. Configure Privoxy (HTTP-to-SOCKS5 bridge on port 40001)
echo "-> Configuring Privoxy on 127.0.0.1:40001..."
cp "$SCRIPT_DIR/config/privoxy.conf" /etc/privoxy/config
systemctl restart privoxy
systemctl enable privoxy

# 6. Install Node.js 20 LTS
NODE_MAJOR=0
if command -v node &> /dev/null; then
  NODE_MAJOR=$(node -v | cut -d'.' -f1 | tr -d 'v')
fi

if [ "$NODE_MAJOR" -lt 20 ]; then
  echo "-> Installing Node.js 20 LTS..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
echo "   Node.js version: $(node -v)"

# 7. Install 9Router
echo "-> Installing 9Router & Undici globally via npm..."
npm install -g 9router@latest undici
ln -sf /usr/bin/9router /usr/local/bin/9router 2>/dev/null || true
ln -sf /usr/local/bin/9router /usr/bin/9router 2>/dev/null || true

echo "-> Setting up SQLite native runtime for 9Router..."
mkdir -p /root/.9router/runtime
cd /root/.9router/runtime
if [ ! -d node_modules/better-sqlite3 ]; then
  npm init -y > /dev/null 2>&1
  npm install better-sqlite3@12.6.2 --build-from-source
fi
cd "$SCRIPT_DIR"

# 8. Deploy 9Router Proxy Preload & Systemd Service
echo "-> Configuring 9Router systemd service..."
cp "$SCRIPT_DIR/config/9router-proxy-preload.js" /root/9router-proxy-preload.js

cat << EOF > /root/.9router.env
INITIAL_PASSWORD=${NINE_ROUTER_PASSWORD:-m44332211}
NODE_OPTIONS=--require=/root/9router-proxy-preload.js
NODE_PATH=/usr/lib/node_modules:/usr/local/lib/node_modules
EOF

cp "$SCRIPT_DIR/systemd/9router.service" /etc/systemd/system/9router.service
systemctl daemon-reload
systemctl enable 9router
systemctl restart 9router
sleep 5

# 9. Deploy Sisi Bot Application
echo "-> Deploying Sisi Bot application to /root/sisi-bot..."
mkdir -p /root/sisi-bot
cp "$SCRIPT_DIR/bot.py" /root/sisi-bot/bot.py
cp "$SCRIPT_DIR/requirements.txt" /root/sisi-bot/requirements.txt
cp "$SCRIPT_DIR/setup_9router.py" /root/sisi-bot/setup_9router.py
[ -f .env ] && cp "$SCRIPT_DIR/.env" /root/sisi-bot/.env

echo "-> Building Python virtual environment..."
if [ ! -d /root/sisi-bot/venv ]; then
  python3 -m venv /root/sisi-bot/venv
fi

/root/sisi-bot/venv/bin/pip install --upgrade pip
/root/sisi-bot/venv/bin/pip install -r /root/sisi-bot/requirements.txt

# 10. Run 9Router Initial Configuration
echo "-> Configuring 9Router database, API keys, round-robin, and smart combo..."
cd /root/sisi-bot
/root/sisi-bot/venv/bin/python setup_9router.py || true
cd "$SCRIPT_DIR"

# 11. Deploy Sisi Bot Systemd Service
echo "-> Enabling and starting sisi-bot service..."
cp "$SCRIPT_DIR/systemd/sisi-bot.service" /etc/systemd/system/sisi-bot.service
systemctl daemon-reload
systemctl enable sisi-bot
systemctl restart sisi-bot
systemctl restart 9router
sleep 3

# 12. Verification & Summary
PUBLIC_IP=$(curl -s -4 ifconfig.me || hostname -I | awk '{print $1}')

echo ""
echo "=========================================================="
echo "  🎉 SISI & 9ROUTER DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "=========================================================="
echo ""
echo "🤖 Telegram Bot Status:"
systemctl is-active sisi-bot && echo "   sisi-bot: ACTIVE (Running)" || echo "   sisi-bot: FAILED"
systemctl is-active 9router && echo "   9router:  ACTIVE (Running)" || echo "   9router:  FAILED"
systemctl is-active privoxy && echo "   privoxy:  ACTIVE (Running)" || echo "   privoxy:  FAILED"
echo ""
echo "🌐 9Router Web Dashboard:"
echo "   URL:      http://${PUBLIC_IP}:20128/dashboard"
echo "   Password: ${NINE_ROUTER_PASSWORD:-m44332211}"
echo ""
echo "💬 Telegram Bot:"
echo "   Token:    ${TELEGRAM_BOT_TOKEN:0:15}..."
echo ""
echo "🛡️ Personal Anti-Censorship Proxy (VLESS Reality):"
echo "   Run anytime to setup personal proxy: sudo bash scripts/setup_xray.sh"
echo ""
echo "View logs anytime with:"
echo "   journalctl -f -u sisi-bot"
echo "   journalctl -f -u 9router"
echo "=========================================================="
