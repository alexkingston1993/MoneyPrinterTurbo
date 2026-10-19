#!/usr/bin/env bash
# ==============================================================================
# 1-Click Automated Deployment Script for Oracle Cloud Always Free Tier (ARM64)
# Configures: Python 3.11/12, FFmpeg, Ollama + Qwen2.5-7B, & Systemd Daemon
# ==============================================================================

set -e

echo "🚀 [1/6] Updating system and installing base dependencies..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git wget build-essential ffmpeg python3 python3-pip python3-venv jq

echo "🧠 [2/6] Installing Ollama (ARM64 Optimized)..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
    sudo systemctl daemon-reload
    sudo systemctl enable ollama
    sudo systemctl start ollama
    sleep 3
else
    echo "Ollama already installed."
fi

echo "📦 [3/6] Pulling Qwen 2.5 7B Instruct (Q4_K_M)..."
ollama pull qwen2.5:7b

echo "🐍 [4/6] Setting up Python Virtual Environment..."
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pytz yfinance

echo "⚙️ [5/6] Creating Systemd Background Service..."
SERVICE_FILE="/etc/systemd/system/moneyprinter-daemon.service"
CURRENT_USER=$(whoami)

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=MoneyPrinterTurbo Autonomous Live Market Daemon
After=network.target ollama.service

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python3 -m app.services.autonomous_scheduler
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable moneyprinter-daemon
sudo systemctl restart moneyprinter-daemon

echo "✅ [6/6] Deployment Complete!"
echo "------------------------------------------------------------------------"
echo "Status check:  sudo systemctl status moneyprinter-daemon"
echo "Live logs:     journalctl -u moneyprinter-daemon -f"
echo "Ollama check:  curl http://localhost:11434/api/tags"
echo "------------------------------------------------------------------------"
