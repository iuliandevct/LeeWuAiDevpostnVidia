#!/usr/bin/env bash
# ==============================================================================
# Cloudflare Tunnel Setup & Service Manager for leewuai.ro
# ==============================================================================
set -e

TUNNEL_TOKEN="$1"

echo "=== LeeWu AI - Cloudflare Tunnel Setup ==="

# 1. Check or install cloudflared
if ! command -v cloudflared &> /dev/null; then
    echo "Downloading official cloudflared binary..."
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
    echo "Installed cloudflared version: $(cloudflared --version)"
else
    echo "cloudflared already installed: $(cloudflared --version)"
fi

# 2. If token is provided, install as service
if [ -n "$TUNNEL_TOKEN" ]; then
    echo "Configuring cloudflared system service with provided token..."
    cloudflared service install "$TUNNEL_TOKEN"
    systemctl daemon-reload
    systemctl enable --now cloudflared
    echo "Cloudflare Tunnel service installed and active!"
    systemctl status cloudflared --no-pager
else
    echo ""
    echo "Usage with Cloudflare Zero Trust Token:"
    echo "  sudo ./setup_tunnel.sh <TUNNEL_TOKEN>"
    echo ""
    echo "Or manual run using config.yml:"
    echo "  cloudflared tunnel --config ./config.yml run"
fi
