#!/bin/bash
# MCP Redaction Server - Production Installation Script
# Supports Ubuntu 20.04+, RHEL 8+, CentOS 8+
# Version: 2.0.0

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/mcp-redaction"
SERVICE_USER="mcp"
SERVICE_NAME="mcp-redaction"
STATE_FILE="/tmp/mcp-install-state.conf"
SECRETS_FILE="/root/.mcp-secrets"
REPO_URL="https://github.com/sunkencity999/redaction-compliance-MCP.git"

# Logging
LOG_FILE="/var/log/mcp-install.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

# Functions
print_header() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  MCP Redaction & Compliance Server - Production Installer     ║${NC}"
    echo -e "${BLUE}║  Version 2.0.0                                                 ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}\n"
}

log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

save_state() {
    local key=$1
    local value=$2
    mkdir -p "$(dirname "$STATE_FILE")"
    echo "${key}=${value}" >> "$STATE_FILE"
}

load_state() {
    if [ -f "$STATE_FILE" ]; then
        source "$STATE_FILE"
    fi
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run as root (use sudo)"
        exit 1
    fi
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
        log_info "Detected OS: $PRETTY_NAME"
    else
        log_error "Cannot detect OS version"
        exit 1
    fi
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing_deps=()
    
    # Check Python 3.9+
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    else
        PY_VER=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if (( $(echo "$PY_VER < 3.9" | bc -l) )); then
            log_warn "Python $PY_VER detected, need 3.9+. Will attempt to install."
            missing_deps+=("python3.11")
        fi
    fi
    
    # Check for required commands
    for cmd in git curl systemctl; do
        if ! command -v $cmd &> /dev/null; then
            missing_deps+=($cmd)
        fi
    done
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_warn "Missing dependencies: ${missing_deps[*]}"
        install_dependencies "${missing_deps[@]}"
    else
        log_info "All prerequisites met"
    fi
}

install_dependencies() {
    log_info "Installing system dependencies..."
    
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        apt-get update -qq
        apt-get install -y python3.11 python3.11-venv python3-pip git curl redis-server bc jq
        systemctl enable redis-server
        systemctl start redis-server
    elif [[ "$OS" == "rhel" ]] || [[ "$OS" == "centos" ]] || [[ "$OS" == "rocky" ]]; then
        yum install -y python3.11 python3-pip git curl redis bc jq
        systemctl enable redis
        systemctl start redis
    else
        log_error "Unsupported OS: $OS"
        exit 1
    fi
    
    log_info "Dependencies installed successfully"
}

create_service_user() {
    if id "$SERVICE_USER" &>/dev/null; then
        log_info "Service user '$SERVICE_USER' already exists"
    else
        log_info "Creating service user '$SERVICE_USER'..."
        useradd -r -s /bin/false -d "$INSTALL_DIR" -c "MCP Redaction Service" "$SERVICE_USER"
    fi
}

download_repository() {
    if [ -d "$INSTALL_DIR" ]; then
        log_warn "Install directory already exists"
        read -p "Remove and re-install? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
        else
            log_info "Using existing installation"
            return
        fi
    fi
    
    log_info "Cloning repository from GitHub..."
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    log_info "Repository downloaded to $INSTALL_DIR"
}

setup_virtualenv() {
    log_info "Setting up Python virtual environment..."
    
    cd "$INSTALL_DIR"
    sudo -u "$SERVICE_USER" python3.11 -m venv .venv
    sudo -u "$SERVICE_USER" .venv/bin/pip install --upgrade pip
    sudo -u "$SERVICE_USER" .venv/bin/pip install -r requirements.txt
    
    log_info "Virtual environment created and dependencies installed"
}

generate_secrets() {
    log_info "Generating cryptographic secrets..."
    
    # Generate secrets
    MCP_TOKEN_SALT=$(openssl rand -base64 32)
    MCP_ENCRYPTION_KEY=$(openssl rand -base64 32)
    
    # Save to secure location
    cat > "$SECRETS_FILE" <<EOF
# MCP Redaction Server Secrets
# Generated: $(date)
# KEEP THIS FILE SECURE - DO NOT SHARE

MCP_TOKEN_SALT="$MCP_TOKEN_SALT"
MCP_ENCRYPTION_KEY="$MCP_ENCRYPTION_KEY"
EOF
    
    chmod 600 "$SECRETS_FILE"
    
    echo -e "\n${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  IMPORTANT: Secrets Generated and Saved${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "Location: ${YELLOW}$SECRETS_FILE${NC}"
    echo -e "\n${RED}⚠ BACKUP THIS FILE IMMEDIATELY ⚠${NC}"
    echo -e "Store in password manager or secure vault.\n"
    echo -e "MCP_TOKEN_SALT: ${YELLOW}${MCP_TOKEN_SALT}${NC}"
    echo -e "MCP_ENCRYPTION_KEY: ${YELLOW}${MCP_ENCRYPTION_KEY}${NC}\n"
    
    read -p "Press ENTER after you have securely backed up these secrets..."
    
    save_state "SECRETS_GENERATED" "true"
}

configure_siem() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  SIEM Integration Configuration                                ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo "Select SIEM platform:"
    echo "1) Splunk (HTTP Event Collector)"
    echo "2) Elasticsearch / ELK Stack"
    echo "3) Datadog Logs"
    echo "4) Syslog (Traditional SIEM)"
    echo "5) None (Local logs only)"
    echo
    read -p "Choice [1-5] (default: 1): " siem_choice
    siem_choice=${siem_choice:-1}
    
    case $siem_choice in
        1)
            SIEM_TYPE="splunk"
            read -p "Splunk HEC URL (e.g., https://splunk.example.com:8088): " SPLUNK_HEC_URL
            read -p "Splunk HEC Token: " SPLUNK_HEC_TOKEN
            save_state "SIEM_TYPE" "$SIEM_TYPE"
            save_state "SPLUNK_HEC_URL" "$SPLUNK_HEC_URL"
            save_state "SPLUNK_HEC_TOKEN" "$SPLUNK_HEC_TOKEN"
            log_info "Splunk SIEM configured"
            ;;
        2)
            SIEM_TYPE="elasticsearch"
            read -p "Elasticsearch URL (e.g., https://es.example.com:9200): " ELASTICSEARCH_URL
            read -p "Elasticsearch API Key (press ENTER if none): " ELASTICSEARCH_API_KEY
            read -p "Index name (default: mcp-audit): " ELASTICSEARCH_INDEX
            ELASTICSEARCH_INDEX=${ELASTICSEARCH_INDEX:-mcp-audit}
            save_state "SIEM_TYPE" "$SIEM_TYPE"
            save_state "ELASTICSEARCH_URL" "$ELASTICSEARCH_URL"
            save_state "ELASTICSEARCH_API_KEY" "$ELASTICSEARCH_API_KEY"
            save_state "ELASTICSEARCH_INDEX" "$ELASTICSEARCH_INDEX"
            log_info "Elasticsearch SIEM configured"
            ;;
        3)
            SIEM_TYPE="datadog"
            read -p "Datadog API Key: " DATADOG_API_KEY
            read -p "Datadog Site (default: datadoghq.com): " DATADOG_SITE
            DATADOG_SITE=${DATADOG_SITE:-datadoghq.com}
            save_state "SIEM_TYPE" "$SIEM_TYPE"
            save_state "DATADOG_API_KEY" "$DATADOG_API_KEY"
            save_state "DATADOG_SITE" "$DATADOG_SITE"
            log_info "Datadog SIEM configured"
            ;;
        4)
            SIEM_TYPE="syslog"
            read -p "Syslog server hostname/IP: " SYSLOG_HOST
            read -p "Syslog port (default: 514): " SYSLOG_PORT
            SYSLOG_PORT=${SYSLOG_PORT:-514}
            save_state "SIEM_TYPE" "$SIEM_TYPE"
            save_state "SYSLOG_HOST" "$SYSLOG_HOST"
            save_state "SYSLOG_PORT" "$SYSLOG_PORT"
            log_info "Syslog SIEM configured"
            ;;
        5)
            SIEM_TYPE=""
            save_state "SIEM_TYPE" "none"
            log_info "SIEM integration skipped (local logs only)"
            ;;
        *)
            log_error "Invalid choice"
            configure_siem
            ;;
    esac
}

test_siem_connection() {
    if [ -z "$SIEM_TYPE" ] || [ "$SIEM_TYPE" == "none" ]; then
        return 0
    fi
    
    log_info "Testing SIEM connection..."
    
    case $SIEM_TYPE in
        splunk)
            if curl -k -s -o /dev/null -w "%{http_code}" "$SPLUNK_HEC_URL/services/collector/health" | grep -q "200\|401"; then
                log_info "Splunk HEC endpoint reachable"
            else
                log_warn "Cannot reach Splunk HEC. Check URL and firewall."
            fi
            ;;
        elasticsearch)
            if curl -k -s -o /dev/null -w "%{http_code}" "$ELASTICSEARCH_URL/_cluster/health" | grep -q "200"; then
                log_info "Elasticsearch cluster reachable"
            else
                log_warn "Cannot reach Elasticsearch. Check URL and firewall."
            fi
            ;;
        datadog)
            log_info "Datadog connection will be tested on first log"
            ;;
        syslog)
            if nc -zv "$SYSLOG_HOST" "$SYSLOG_PORT" 2>&1 | grep -q "succeeded\|open"; then
                log_info "Syslog server reachable"
            else
                log_warn "Cannot reach syslog server. Check hostname and firewall."
            fi
            ;;
    esac
}

create_env_file() {
    log_info "Creating environment configuration..."
    
    cat > "$INSTALL_DIR/.env" <<EOF
# MCP Redaction Server Environment Configuration
# Generated: $(date)

# Core Configuration
MCP_TOKEN_SALT="$MCP_TOKEN_SALT"
MCP_ENCRYPTION_KEY="$MCP_ENCRYPTION_KEY"
TOKEN_BACKEND=redis
REDIS_URL=redis://localhost:6379/0

# Transparent Proxy Mode (OpenAI, Claude, Gemini compatible)
PROXY_MODE_ENABLED=true
OPENAI_UPSTREAM_URL=https://api.openai.com/v1/chat/completions
CLAUDE_UPSTREAM_URL=https://api.anthropic.com/v1/messages
GEMINI_UPSTREAM_URL=https://generativelanguage.googleapis.com

# Trusted Callers for Detokenization
DETOKENIZE_TRUSTED_CALLERS=demo_client,openai-proxy,claude-proxy,gemini-proxy

# CORS Configuration (for browser-based apps)
CORS_ORIGINS=*

# Claim Verification (Claimify-based hallucination detection)
CLAIM_VERIFICATION_ENABLED=false
CLAIM_VERIFICATION_MODEL=gpt-4o-mini
CLAIM_VERIFICATION_LEVEL=standard
CLAIM_VERIFICATION_INLINE=true

# SIEM Configuration
EOF

    if [ "$SIEM_TYPE" != "none" ] && [ -n "$SIEM_TYPE" ]; then
        echo "SIEM_TYPE=$SIEM_TYPE" >> "$INSTALL_DIR/.env"
        echo "SIEM_BATCH_MODE=true" >> "$INSTALL_DIR/.env"
        echo "SIEM_BATCH_SIZE=100" >> "$INSTALL_DIR/.env"
        echo "SIEM_FLUSH_INTERVAL=5.0" >> "$INSTALL_DIR/.env"
        
        case $SIEM_TYPE in
            splunk)
                echo "SPLUNK_HEC_URL=\"$SPLUNK_HEC_URL\"" >> "$INSTALL_DIR/.env"
                echo "SPLUNK_HEC_TOKEN=\"$SPLUNK_HEC_TOKEN\"" >> "$INSTALL_DIR/.env"
                ;;
            elasticsearch)
                echo "ELASTICSEARCH_URL=\"$ELASTICSEARCH_URL\"" >> "$INSTALL_DIR/.env"
                [ -n "$ELASTICSEARCH_API_KEY" ] && echo "ELASTICSEARCH_API_KEY=\"$ELASTICSEARCH_API_KEY\"" >> "$INSTALL_DIR/.env"
                echo "ELASTICSEARCH_INDEX=\"$ELASTICSEARCH_INDEX\"" >> "$INSTALL_DIR/.env"
                ;;
            datadog)
                echo "DATADOG_API_KEY=\"$DATADOG_API_KEY\"" >> "$INSTALL_DIR/.env"
                echo "DATADOG_SITE=\"$DATADOG_SITE\"" >> "$INSTALL_DIR/.env"
                ;;
            syslog)
                echo "SYSLOG_HOST=\"$SYSLOG_HOST\"" >> "$INSTALL_DIR/.env"
                echo "SYSLOG_PORT=\"$SYSLOG_PORT\"" >> "$INSTALL_DIR/.env"
                ;;
        esac
    fi
    
    chmod 600 "$INSTALL_DIR/.env"
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
    
    log_info "Environment configuration created"
    log_info "✓ Transparent Proxy Mode ENABLED (OpenAI/Claude/Gemini compatible)"
}

create_systemd_service() {
    log_info "Creating systemd service..."
    
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=MCP Redaction & Compliance Server
Documentation=https://github.com/sunkencity999/redaction-compliance-MCP
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env

ExecStartPre=/bin/sleep 2
ExecStart=$INSTALL_DIR/.venv/bin/uvicorn mcp_redaction.server:app \\
    --host 0.0.0.0 \\
    --port 8019 \\
    --workers 4 \\
    --log-level info

Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_DIR/audit
ReadWritePaths=/var/log/$SERVICE_NAME

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF

    # Create directories
    mkdir -p "$INSTALL_DIR/audit"
    mkdir -p "/var/log/$SERVICE_NAME"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/audit"
    chown -R "$SERVICE_USER:$SERVICE_USER" "/var/log/$SERVICE_NAME"
    
    # Reload systemd
    systemctl daemon-reload
    
    log_info "Systemd service created"
}

setup_logrotate() {
    log_info "Configuring log rotation..."
    
    cat > "/etc/logrotate.d/$SERVICE_NAME" <<EOF
$INSTALL_DIR/audit/*.jsonl {
    daily
    rotate 90
    compress
    delaycompress
    notifempty
    create 0640 $SERVICE_USER $SERVICE_USER
    sharedscripts
    postrotate
        systemctl reload $SERVICE_NAME > /dev/null 2>&1 || true
    endscript
}

/var/log/$SERVICE_NAME/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 $SERVICE_USER $SERVICE_USER
}
EOF
    
    log_info "Log rotation configured (90 days for audit, 30 days for service logs)"
}

setup_nginx_proxy() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  NGINX Reverse Proxy Setup (Recommended for Production)       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    
    read -p "Setup NGINX reverse proxy with HTTPS? (recommended) (Y/n): " setup_nginx
    if [[ $setup_nginx =~ ^[Nn]$ ]]; then
        log_info "Skipping NGINX setup"
        save_state "NGINX_SETUP" "skipped"
        return 0
    fi
    
    log_info "Installing NGINX..."
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        apt-get install -y nginx certbot python3-certbot-nginx
    elif [[ "$OS" == "rhel" ]] || [[ "$OS" == "centos" ]] || [[ "$OS" == "rocky" ]]; then
        yum install -y nginx certbot python3-certbot-nginx
    fi
    
    read -p "Enter your server's public hostname (e.g., mcp.company.com): " SERVER_HOSTNAME
    save_state "SERVER_HOSTNAME" "$SERVER_HOSTNAME"
    
    echo
    echo "SSL Certificate Options:"
    echo "1) Let's Encrypt (free, auto-renewing, requires public DNS)"
    echo "2) Self-signed (for internal/testing)"
    echo "3) Skip SSL setup (I'll configure manually)"
    read -p "Choice [1-3]: " ssl_choice
    
    # Create NGINX config
    log_info "Creating NGINX configuration..."
    cat > "/etc/nginx/sites-available/mcp-redaction" <<EOF
# MCP Redaction Server - NGINX Reverse Proxy
upstream mcp_backend {
    server 127.0.0.1:8019;
    keepalive 32;
}

server {
    listen 80;
    server_name ${SERVER_HOSTNAME};
    
    # Redirect to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${SERVER_HOSTNAME};
    
    # SSL certificates (will be configured based on choice)
    ssl_certificate /etc/nginx/ssl/${SERVER_HOSTNAME}.crt;
    ssl_certificate_key /etc/nginx/ssl/${SERVER_HOSTNAME}.key;
    
    # SSL security settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Proxy settings
    location / {
        proxy_pass http://mcp_backend;
        proxy_http_version 1.1;
        
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Connection "";
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
    
    # Health check endpoint (no auth)
    location /health {
        proxy_pass http://mcp_backend;
        access_log off;
    }
    
    # Access log
    access_log /var/log/nginx/mcp-access.log;
    error_log /var/log/nginx/mcp-error.log;
}
EOF
    
    # Enable site
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        ln -sf /etc/nginx/sites-available/mcp-redaction /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default
    fi
    
    # Setup SSL based on choice
    case $ssl_choice in
        1)
            log_info "Setting up Let's Encrypt certificate..."
            mkdir -p /etc/nginx/ssl
            
            # Temporary HTTP server for ACME challenge
            sed -i 's/return 301/#return 301/' /etc/nginx/sites-available/mcp-redaction
            systemctl reload nginx
            
            if certbot --nginx -d "$SERVER_HOSTNAME" --non-interactive --agree-tos --email admin@"$SERVER_HOSTNAME" --redirect; then
                log_info "Let's Encrypt certificate installed successfully"
                # Certbot handles the SSL config
            else
                log_warn "Let's Encrypt failed. Falling back to self-signed certificate."
                setup_self_signed_cert
            fi
            ;;
        2)
            setup_self_signed_cert
            ;;
        3)
            log_warn "SSL setup skipped. Configure /etc/nginx/sites-available/mcp-redaction manually."
            setup_self_signed_cert  # Still create self-signed for testing
            ;;
    esac
    
    # Test NGINX config
    if nginx -t; then
        systemctl enable nginx
        systemctl restart nginx
        log_info "NGINX configured and started successfully"
    else
        log_error "NGINX configuration test failed"
        return 1
    fi
    
    save_state "NGINX_SETUP" "complete"
}

setup_self_signed_cert() {
    log_info "Generating self-signed certificate..."
    mkdir -p /etc/nginx/ssl
    
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "/etc/nginx/ssl/${SERVER_HOSTNAME}.key" \
        -out "/etc/nginx/ssl/${SERVER_HOSTNAME}.crt" \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=${SERVER_HOSTNAME}" \
        2>/dev/null
    
    log_info "Self-signed certificate created (valid for 365 days)"
    log_warn "⚠ Self-signed certificates should only be used for testing!"
}

configure_firewall() {
    log_info "Configuring firewall..."
    
    if [ "$NGINX_SETUP" == "complete" ] || [ "$NGINX_SETUP" == "skipped" ]; then
        # Open HTTPS if NGINX is setup
        if [ "$NGINX_SETUP" == "complete" ]; then
            if command -v ufw &> /dev/null; then
                ufw allow 443/tcp comment 'HTTPS for MCP'
                ufw allow 80/tcp comment 'HTTP redirect'
                # Don't expose 8019 directly
                log_info "UFW: Opened ports 80, 443 (NGINX)"
            elif command -v firewall-cmd &> /dev/null; then
                firewall-cmd --permanent --add-service=https
                firewall-cmd --permanent --add-service=http
                firewall-cmd --reload
                log_info "firewalld: Opened ports 80, 443"
            fi
        else
            # No NGINX, open 8019
            if command -v ufw &> /dev/null; then
                ufw allow 8019/tcp comment 'MCP Redaction Server'
                log_info "UFW firewall rule added for port 8019"
            elif command -v firewall-cmd &> /dev/null; then
                firewall-cmd --permanent --add-port=8019/tcp
                firewall-cmd --reload
                log_info "firewalld rule added for port 8019"
            fi
        fi
    else
        log_warn "No firewall detected. Manually configure firewall rules."
    fi
}

run_tests() {
    echo -e "\n${BLUE}Running test suite...${NC}"
    
    cd "$INSTALL_DIR"
    if sudo -u "$SERVICE_USER" .venv/bin/pytest tests/ -v --tb=short; then
        log_info "All tests passed ✓"
    else
        log_warn "Some tests failed. Review output above."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

start_service() {
    log_info "Starting MCP Redaction service..."
    
    systemctl enable "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"
    
    sleep 3
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_info "Service started successfully"
    else
        log_error "Service failed to start. Check logs:"
        echo "  journalctl -u $SERVICE_NAME -n 50"
        exit 1
    fi
}

health_check() {
    log_info "Running health check..."
    
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f http://localhost:8019/health > /dev/null 2>&1; then
            log_info "Health check passed ✓"
            return 0
        fi
        log_warn "Attempt $attempt/$max_attempts failed, retrying..."
        sleep 2
        ((attempt++))
    done
    
    log_error "Health check failed after $max_attempts attempts"
    return 1
}

install_client_sdk() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Python Client SDK Installation                                ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    
    log_info "Installing MCP Client SDK..."
    
    cd "$INSTALL_DIR"
    sudo -u "$SERVICE_USER" .venv/bin/pip install -e . --quiet
    
    log_info "Client SDK installed successfully"
}

create_integration_examples() {
    log_info "Creating integration examples..."
    
    local examples_dir="$INSTALL_DIR/examples"
    mkdir -p "$examples_dir"
    
    # Example 1: Basic usage
    cat > "$examples_dir/basic_example.py" <<'EOF'
#!/usr/bin/env python3
"""
Basic MCP Client Example
Demonstrates simple redact/detokenize workflow
"""

from mcp_client import MCPClient, MCPConfig

# Configure client
config = MCPConfig(
    server_url="https://mcp.yourcompany.com",  # Or http://localhost:8019 for testing
    caller="my-app",
    region="us"
)

mcp = MCPClient(config)

# Example user input (contains AWS key)
user_input = "My AWS key is AKIAIOSFODNN7EXAMPLE, can you help me debug this error?"

print("Original input:")
print(user_input)
print()

# Step 1: Redact sensitive data
try:
    sanitized, token_handle = mcp.redact(user_input)
    print("Sanitized (safe for LLM):")
    print(sanitized)
    print()
    
    # Step 2: Send sanitized version to LLM
    # llm_response = call_your_llm(sanitized)
    # For this example, simulate an LLM response
    llm_response = f"Based on your request about {sanitized}, here's what I found..."
    
    print("LLM Response:")
    print(llm_response)
    print()
    
    # Step 3: Detokenize (restore non-secrets)
    final_response = mcp.detokenize(
        llm_response,
        token_handle,
        allow_categories=["pii", "ops_sensitive"]  # NOT secrets!
    )
    
    print("Final response (detokenized):")
    print(final_response)
    
except Exception as e:
    print(f"Error: {e}")
EOF
    
    # Example 2: OpenAI integration
    cat > "$examples_dir/openai_integration.py" <<'EOF'
#!/usr/bin/env python3
"""
OpenAI Integration Example
Shows how to integrate MCP with OpenAI API
"""

from mcp_client import MCPClient, MCPConfig, MCPBlockedError
import os

# Requires: pip install openai
try:
    import openai
except ImportError:
    print("Please install openai: pip install openai")
    exit(1)

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configure MCP
mcp = MCPClient(MCPConfig(
    server_url=os.getenv("MCP_SERVER_URL", "https://mcp.yourcompany.com"),
    caller="openai-wrapper",
    region="us"
))

def safe_chat_completion(user_message: str, model="gpt-4") -> str:
    """
    Safely call OpenAI with automatic redaction/detokenization.
    """
    try:
        # Step 1: Redact with MCP
        sanitized, token_handle = mcp.redact(user_message)
        
        # Step 2: Call OpenAI with sanitized input
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": sanitized}
            ]
        )
        
        llm_output = response.choices[0].message.content
        
        # Step 3: Detokenize response
        final = mcp.detokenize(llm_output, token_handle)
        
        return final
        
    except MCPBlockedError as e:
        return f"❌ Request blocked by security policy: {e}"
    except Exception as e:
        return f"❌ Error: {e}"

# Example usage
if __name__ == "__main__":
    test_input = "My AWS key is AKIAIOSFODNN7EXAMPLE. Can you help me troubleshoot?"
    
    print("User input:", test_input)
    print()
    
    result = safe_chat_completion(test_input)
    print("Safe response:", result)
EOF
    
    # Example 3: Helper wrapper function
    cat > "$examples_dir/safe_llm_wrapper.py" <<'EOF'
#!/usr/bin/env python3
"""
Convenience Wrapper for Any LLM
Drop-in replacement that adds MCP protection
"""

from mcp_client import MCPClient, MCPConfig
import os

# Global MCP client
_mcp_client = None

def get_mcp_client():
    """Get or create MCP client singleton."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient(MCPConfig.from_env())
    return _mcp_client

def safe_llm_call(user_input: str, llm_function, **kwargs) -> str:
    """
    Wrapper that adds MCP protection to any LLM call.
    
    Args:
        user_input: User's message (may contain sensitive data)
        llm_function: Your LLM function that takes a string and returns a string
        **kwargs: Additional arguments to pass to llm_function
    
    Returns:
        Safe, detokenized response
    
    Example:
        def my_llm(text):
            return openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": text}]
            ).choices[0].message.content
        
        response = safe_llm_call("Help me with AKIAIOSFODNN...", my_llm)
    """
    mcp = get_mcp_client()
    
    # Use the built-in safe_llm_call method
    return mcp.safe_llm_call(
        user_input,
        llm_function,
        **kwargs
    )

# Example usage
if __name__ == "__main__":
    # Your existing LLM function
    def my_llm(text):
        # Simulate LLM response
        return f"I received: {text}"
    
    # Just wrap it!
    user_input = "My password is SuperSecret123, help me debug"
    safe_response = safe_llm_call(user_input, my_llm)
    print(safe_response)
EOF
    
    chmod +x "$examples_dir"/*.py
    chown -R "$SERVICE_USER:$SERVICE_USER" "$examples_dir"
    
    log_info "Integration examples created in $examples_dir"
}

print_success() {
    echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                                ║${NC}"
    echo -e "${GREEN}║  ✓ MCP Redaction Server Installed Successfully!               ║${NC}"
    echo -e "${GREEN}║                                                                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo -e "${BLUE}Service Status:${NC}"
    systemctl status "$SERVICE_NAME" --no-pager | head -10
    
    echo -e "\n${BLUE}API Access:${NC}"
    if [ "$NGINX_SETUP" == "complete" ]; then
        echo "  Public URL:      https://${SERVER_HOSTNAME}"
        echo "  Health check:    curl https://${SERVER_HOSTNAME}/health"
    else
        echo "  Local URL:       http://localhost:8019"
        echo "  Health check:    curl http://localhost:8019/health"
    fi
    
    echo -e "\n${BLUE}System Management:${NC}"
    echo "  Service status:  systemctl status $SERVICE_NAME"
    echo "  View logs:       journalctl -u $SERVICE_NAME -f"
    echo "  Audit logs:      tail -f $INSTALL_DIR/audit/audit.jsonl"
    echo "  Config file:     $INSTALL_DIR/.env"
    echo "  Secrets file:    $SECRETS_FILE"
    
    if [ "$SIEM_TYPE" != "none" ] && [ -n "$SIEM_TYPE" ]; then
        echo -e "\n${BLUE}SIEM Integration:${NC}"
        echo "  Platform: $SIEM_TYPE"
        echo "  Status:   Check SIEM platform for incoming logs"
    fi
    
    echo -e "\n${BLUE}🔄 Transparent Proxy Mode: ENABLED${NC}"
    echo "  Zero-code integration - just change your API base URL!"
    echo ""
    echo "  OpenAI:   openai.api_base = \"$([ "$NGINX_SETUP" == "complete" ] && echo "https://${SERVER_HOSTNAME}" || echo "http://localhost:8019")/v1\""
    echo "  Claude:   client = Anthropic(base_url=\"$([ "$NGINX_SETUP" == "complete" ] && echo "https://${SERVER_HOSTNAME}" || echo "http://localhost:8019")/v1/messages\")"
    echo "  Gemini:   genai.configure(client_options={\"api_endpoint\": \"$([ "$NGINX_SETUP" == "complete" ] && echo "https://${SERVER_HOSTNAME}" || echo "http://localhost:8019")/v1\"})"
    echo ""
    echo "  Your existing OpenAI/Claude/Gemini code works unchanged!"
    echo "  See TRANSPARENT_PROXY.md for complete guide"
    
    echo -e "\n${BLUE}Client SDK Integration (Alternative Method):${NC}"
    echo "  Python SDK:      Installed in $INSTALL_DIR/.venv"
    echo "  JavaScript SDK:  $INSTALL_DIR/mcp_client_js/"
    echo "  Examples:        $INSTALL_DIR/examples/"
    echo "    • basic_example.py        - Simple redact/detokenize"
    echo "    • openai_integration.py   - OpenAI wrapper"
    echo "    • safe_llm_wrapper.py     - Drop-in LLM protection"
    echo ""
    echo "  Test SDK:        cd $INSTALL_DIR && .venv/bin/python examples/basic_example.py"
    
    echo -e "\n${BLUE}Direct API Integration (Advanced):${NC}"
    cat <<'INTEGRATION'
  
  # Python SDK method:
  from mcp_client import MCPClient, MCPConfig
  
  mcp = MCPClient(MCPConfig(
      server_url="https://YOUR-HOSTNAME",
      caller="your-app-name"
  ))
  
  sanitized, handle = mcp.redact(user_input)
  llm_response = call_your_llm(sanitized)
  final = mcp.detokenize(llm_response, handle)
INTEGRATION
    
    echo -e "\n${BLUE}Next Steps:${NC}"
    echo "  1. Test API:      curl $([ "$NGINX_SETUP" == "complete" ] && echo "https://${SERVER_HOSTNAME}" || echo "http://localhost:8019")/health"
    echo "  2. Run examples:  cd $INSTALL_DIR/examples && .venv/bin/python basic_example.py"
    echo "  3. Integrate app: Copy mcp_client SDK to your application"
    echo "  4. Monitor SIEM:  Check $SIEM_TYPE for audit logs"
    
    echo -e "\n${RED}⚠ IMPORTANT SECURITY NOTES:${NC}"
    echo "  • Backup secrets file: $SECRETS_FILE"
    if [ "$NGINX_SETUP" != "complete" ]; then
        echo "  • ⚠ HTTPS not configured - DO NOT use in production without TLS!"
    fi
    echo "  • Add trusted callers to: $INSTALL_DIR/mcp_redaction/sample_policies/default.yaml"
    echo "  • Review and customize policy before production use"
    echo ""
}

uninstall() {
    echo -e "\n${RED}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  MCP Redaction Server - UNINSTALL                              ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo -e "${YELLOW}This will remove:${NC}"
    echo "  • Service: $SERVICE_NAME"
    echo "  • Installation: $INSTALL_DIR"
    echo "  • System user: $SERVICE_USER"
    echo "  • Audit logs: $INSTALL_DIR/audit/"
    echo ""
    echo -e "${RED}⚠ Secrets will NOT be removed from: $SECRETS_FILE${NC}"
    echo ""
    read -p "Are you SURE you want to uninstall? (type 'YES' to confirm): " confirm
    
    if [ "$confirm" != "YES" ]; then
        log_info "Uninstall cancelled"
        exit 0
    fi
    
    log_info "Stopping service..."
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    
    log_info "Removing service file..."
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload
    
    log_info "Removing installation directory..."
    rm -rf "$INSTALL_DIR"
    
    log_info "Removing log rotation config..."
    rm -f "/etc/logrotate.d/$SERVICE_NAME"
    
    log_info "Removing service user..."
    userdel "$SERVICE_USER" 2>/dev/null || true
    
    log_info "Removing state file..."
    rm -f "$STATE_FILE"
    
    echo -e "\n${GREEN}✓ MCP Redaction Server uninstalled successfully${NC}\n"
    echo -e "${YELLOW}Preserved:${NC}"
    echo "  • Secrets file: $SECRETS_FILE (delete manually if needed)"
    echo "  • Install log: $LOG_FILE"
    echo ""
}

main_menu() {
    print_header
    
    echo "1) Install MCP Redaction Server"
    echo "2) Uninstall MCP Redaction Server"
    echo "3) Exit"
    echo
    read -p "Select option [1-3]: " menu_choice
    
    case $menu_choice in
        1)
            install_full
            ;;
        2)
            uninstall
            ;;
        3)
            echo "Exiting..."
            exit 0
            ;;
        *)
            log_error "Invalid option"
            main_menu
            ;;
    esac
}

install_full() {
    log_info "Starting installation..."
    log_info "Log file: $LOG_FILE"
    
    load_state
    
    check_root
    detect_os
    check_prerequisites
    create_service_user
    download_repository
    setup_virtualenv
    
    if [ "$SECRETS_GENERATED" != "true" ]; then
        generate_secrets
    else
        log_info "Using existing secrets from previous run"
        source "$SECRETS_FILE"
    fi
    
    if [ -z "$SIEM_TYPE" ]; then
        configure_siem
    else
        log_info "Using existing SIEM configuration: $SIEM_TYPE"
    fi
    
    test_siem_connection
    create_env_file
    create_systemd_service
    setup_logrotate
    
    # Setup NGINX proxy (optional but recommended)
    if [ "$NGINX_SETUP" != "complete" ] && [ "$NGINX_SETUP" != "skipped" ]; then
        setup_nginx_proxy
    else
        log_info "Using existing NGINX configuration"
    fi
    
    configure_firewall
    
    echo
    read -p "Run test suite? (recommended) (Y/n): " run_tests_choice
    if [[ ! $run_tests_choice =~ ^[Nn]$ ]]; then
        run_tests
    fi
    
    start_service
    health_check
    
    # Install client SDK and create examples
    install_client_sdk
    create_integration_examples
    
    # Cleanup state file on success
    rm -f "$STATE_FILE"
    
    print_success
}

# Trap errors
trap 'log_error "Installation failed at line $LINENO. State saved for resume."; exit 1' ERR

# Main execution
if [ "$1" == "--uninstall" ]; then
    check_root
    uninstall
else
    main_menu
fi
