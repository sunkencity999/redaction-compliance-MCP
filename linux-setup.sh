#!/bin/bash
# MCP Redaction Server - Linux Setup Script
# Creates systemd service for Linux systems

set -e

echo "🐧 Setting up MCP Redaction Server for Linux (systemd)..."

# Check if we're on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ This script is for Linux only"
    echo "   For macOS, use install_enhanced.sh"
    exit 1
fi

# Check if systemd is available
if ! command -v systemctl &> /dev/null; then
    echo "❌ systemd not found. This script requires systemd."
    exit 1
fi

# Set paths
INSTALL_DIR="/opt/mcp-redaction"
SERVICE_FILE="/etc/systemd/system/mcp-redaction.service"

echo ""
echo "📍 Installation directory: $INSTALL_DIR"
echo "📍 Service file: $SERVICE_FILE"
echo ""

# Check if install dir exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ Installation directory not found: $INSTALL_DIR"
    echo "   Please run the installer first"
    exit 1
fi

# Create systemd service file
echo "📝 Creating systemd service file..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=MCP Redaction & Compliance Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"

# Load environment from .env file
EnvironmentFile=$INSTALL_DIR/.env

# Start the server
ExecStart=$INSTALL_DIR/.venv/bin/uvicorn mcp_redaction.server:app --host 0.0.0.0 --port 8019 --workers 4

# Restart policy
Restart=always
RestartSec=10

# Logging
StandardOutput=append:$INSTALL_DIR/logs/stdout.log
StandardError=append:$INSTALL_DIR/logs/stderr.log

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service file created"
echo ""

# Reload systemd
echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "✅ Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Next Steps:"
echo ""
echo "  Start service:    sudo systemctl start mcp-redaction"
echo "  Stop service:     sudo systemctl stop mcp-redaction"
echo "  Enable on boot:   sudo systemctl enable mcp-redaction"
echo "  View status:      sudo systemctl status mcp-redaction"
echo "  View logs:        journalctl -u mcp-redaction -f"
echo ""
echo "  Or use the Linux scripts:"
echo "  ./linux-start.sh"
echo "  ./linux-stop.sh"
echo "  ./linux-status.sh"
echo "  ./linux-logs.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
