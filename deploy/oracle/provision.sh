#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu 24.04 Oracle Cloud Always Free VM
# (VM.Standard.A1.Flex, 2 OCPU / 12GB). Run as the default `ubuntu` user;
# it uses sudo where needed. Mirrors nixpacks.toml's [phases.setup]/[install]/
# [build] so the runtime matches Railway's build as closely as possible.
set -euo pipefail

REPO_URL="${NEXADESK_REPO_URL:?Set NEXADESK_REPO_URL to your git remote, e.g. git@github.com:you/nexa_desk.git}"
INSTALL_DIR=/opt/nexadesk

echo "==> Installing system packages (Python 3.12, ffmpeg, build tools, Caddy)"
sudo apt-get update
sudo apt-get install -y \
  python3.12 python3.12-venv python3-pip \
  ffmpeg git curl \
  build-essential libssl-dev libffi-dev \
  debian-keyring debian-archive-keyring apt-transport-https

# Caddy's official repo (gives auto-HTTPS reverse proxying for free)
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update
sudo apt-get install -y caddy

echo "==> Cloning repo"
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER":"$USER" "$INSTALL_DIR"
git clone "$REPO_URL" "$INSTALL_DIR/app"

echo "==> Creating venv and installing dependencies"
python3.12 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$INSTALL_DIR/app/requirements.txt"

echo "==> Baking tiktoken cache (avoids a first-request fetch from Azure blob storage)"
export TIKTOKEN_CACHE_DIR="$INSTALL_DIR/app/.tiktoken_cache"
python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

echo "==> Opening host firewall for 80/443 (Security List in the OCI console still needs the same rules)"
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || true

cat <<EOF

Done. Next steps:
  1. Create $INSTALL_DIR/app/.env with production secrets (see .env.example).
  2. Install the systemd unit and Caddyfile from deploy/oracle/ (see README.md).
  3. Point api.nexadesk.site's DNS A record at this VM's public IP.
EOF
