#!/usr/bin/env bash
# ==============================================================================
# Sisi Stack: Standalone Xray VLESS + TCP + Reality Installer
# Supports: Ubuntu 20.04 / 22.04 / 24.04 LTS (x86_64)
# Bypasses strict DPI / Censorship via TLS 1.3 Reality masquerading
# ==============================================================================

set -e

if [ "$(id -u)" -ne 0 ]; then
  echo "Error: This script must be run as root. (Use sudo bash scripts/setup_xray.sh)"
  exit 1
fi

echo "=========================================================="
echo "  🚀 Installing & Configuring Xray VLESS + TCP + Reality..."
echo "=========================================================="

# 1. Install Xray-core via official script
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 2. Generate UUID & X25519 Keys
UUID=$(xray uuid)
X25519_OUTPUT=$(xray x25519)
PRIVATE_KEY=$(echo "$X25519_OUTPUT" | grep -iE 'PrivateKey:' | awk '{print $NF}')
PUBLIC_KEY=$(echo "$X25519_OUTPUT" | grep -iE 'Password \(PublicKey\):|PublicKey:' | awk '{print $NF}')
SHORT_ID=$(openssl rand -hex 4)
SERVER_IP=$(curl -s -4 ifconfig.me || hostname -I | awk '{print $1}')

mkdir -p /usr/local/etc/xray

cat << EOF > /usr/local/etc/xray/config.json
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${UUID}",
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "www.speedtest.net:443",
          "xver": 0,
          "serverNames": [
            "www.speedtest.net",
            "speedtest.net"
          ],
          "privateKey": "${PRIVATE_KEY}",
          "shortIds": [
            "${SHORT_ID}"
          ]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "tag": "direct"
    },
    {
      "protocol": "blackhole",
      "tag": "blocked"
    }
  ]
}
EOF

# 3. Enable & Restart Service
systemctl daemon-reload
systemctl enable xray
systemctl restart xray

VLESS_LINK="vless://${UUID}@${SERVER_IP}:443?security=reality&encryption=none&pbk=${PUBLIC_KEY}&headerType=none&fp=chrome&spx=%2F&type=tcp&flow=xtls-rprx-vision&sni=www.speedtest.net&sid=${SHORT_ID}#Sisi-VPS-Reality"

echo ""
echo "=========================================================="
echo "  🎉 Xray VLESS Reality Setup Completed Successfully!"
echo "=========================================================="
echo "Import Link (Copy & Paste into v2rayNG / Streisand / v2rayN):"
echo ""
echo "$VLESS_LINK"
echo ""
echo "=========================================================="
