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

configure_firewall() {
    log_info "Configuring firewall..."
    
    if command -v ufw &> /dev/null; then
        ufw allow 8019/tcp comment 'MCP Redaction Server'
        log_info "UFW firewall rule added for port 8019"
    elif command -v firewall-cmd &> /dev/null; then
        firewall-cmd --permanent --add-port=8019/tcp
        firewall-cmd --reload
        log_info "firewalld rule added for port 8019"
    else
        log_warn "No firewall detected. Manually open port 8019 if needed."
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

print_success() {
    echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                                ║${NC}"
    echo -e "${GREEN}║  ✓ MCP Redaction Server Installed Successfully!               ║${NC}"
    echo -e "${GREEN}║                                                                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo -e "${BLUE}Service Status:${NC}"
    systemctl status "$SERVICE_NAME" --no-pager | head -10
    
    echo -e "\n${BLUE}Quick Reference:${NC}"
    echo "  Service URL:     http://$(hostname):8019"
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
    
    echo -e "\n${BLUE}Next Steps:${NC}"
    echo "  1. Test the API:  curl http://localhost:8019/health"
    echo "  2. Run demo:      cd $INSTALL_DIR && python3 mcp_redaction/demo_client.py"
    echo "  3. Review docs:   cat $INSTALL_DIR/README.md"
    echo "  4. Configure TLS: Setup reverse proxy (NGINX/HAProxy) with certificates"
    
    echo -e "\n${RED}⚠ IMPORTANT SECURITY NOTES:${NC}"
    echo "  • Backup secrets file: $SECRETS_FILE"
    echo "  • Setup TLS/HTTPS before production use"
    echo "  • Configure mTLS for client authentication"
    echo "  • Review and customize policy: $INSTALL_DIR/mcp_redaction/sample_policies/default.yaml"
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
    configure_firewall
    
    echo
    read -p "Run test suite? (recommended) (Y/n): " run_tests_choice
    if [[ ! $run_tests_choice =~ ^[Nn]$ ]]; then
        run_tests
    fi
    
    start_service
    health_check
    
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
