#!/bin/bash
# MCP Redaction Server - Enhanced Production Installation Script
# Supports: Ubuntu 20.04+, RHEL 8+, CentOS 8+, macOS 12+
# Version: 2.1.0
# Features: Graceful failure handling, resume capability, input validation, detailed logging

set -eE  # Exit on error and inherit ERR trap

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_VERSION="2.1.1"
INSTALL_DIR="/opt/mcp-redaction"
SERVICE_USER="mcp"
SERVICE_NAME="mcp-redaction"
STATE_FILE=""
SECRETS_FILE=""
REPO_URL="https://github.com/sunkencity999/redaction-compliance-MCP.git"

# Will be set after platform detection

# Logging
LOG_DIR="$(pwd)"
LOG_FILE="$LOG_DIR/mcp-install-$(date +%Y%m%d-%H%M%S).log"
SUMMARY_FILE="$LOG_DIR/mcp-install-summary.txt"

# Determine actual user (even if running with sudo)
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER="$SUDO_USER"
    ACTUAL_HOME=$(eval echo ~$SUDO_USER)
else
    ACTUAL_USER=$(whoami)
    ACTUAL_HOME="$HOME"
fi

# Platform detection
OS_TYPE=""  # linux or darwin
OS_DIST=""  # ubuntu, rhel, centos, macos, etc.
PACKAGE_MANAGER=""  # apt, yum, brew

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

# Dual logging - to file and console
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Log to file with full details
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
    
    # Console output with colors (no tee to avoid duplicates)
    case $level in
        INFO)
            echo -e "${GREEN}✓${NC} $message"
            ;;
        WARN)
            echo -e "${YELLOW}⚠${NC} $message"
            ;;
        ERROR)
            echo -e "${RED}✗${NC} $message"
            ;;
        STEP)
            echo -e "\n${BLUE}═══${NC} ${CYAN}$message${NC} ${BLUE}═══${NC}"
            ;;
        DEBUG)
            if [ "${DEBUG:-false}" == "true" ]; then
                echo -e "${CYAN}  ↳${NC} $message"
            fi
            echo "[$timestamp] [DEBUG] $message" >> "$LOG_FILE"
            ;;
    esac
}

log_info() {
    log INFO "$@"
}

log_warn() {
    log WARN "$@"
}

log_error() {
    log ERROR "$@"
}

log_step() {
    log STEP "$@"
}

log_debug() {
    log DEBUG "$@"
}

# ============================================================================
# STATE MANAGEMENT (Resume Capability)
# ============================================================================

save_state() {
    local key=$1
    local value=$2
    
    # Ensure STATE_FILE is set
    if [ -z "$STATE_FILE" ]; then
        log_warn "STATE_FILE not set yet, skipping state save"
        return 0
    fi
    
    # Create directory if needed
    mkdir -p "$(dirname "$STATE_FILE")" 2>/dev/null || true
    
    # Ensure we can write to state file
    if [ ! -w "$(dirname "$STATE_FILE")" ] && [ ! -w "$STATE_FILE" ]; then
        log_warn "Cannot write to state file: $STATE_FILE"
        return 0
    fi
    
    # Remove existing key if present
    if [ -f "$STATE_FILE" ]; then
        if [ "$OS_TYPE" == "darwin" ]; then
            sed -i '' "/^${key}=/d" "$STATE_FILE" 2>/dev/null || true
        else
            sed -i "/^${key}=/d" "$STATE_FILE" 2>/dev/null || true
        fi
    fi
    
    echo "${key}=${value}" >> "$STATE_FILE" 2>/dev/null || true
    log_debug "Saved state: $key=$value"
}

load_state() {
    if [ -f "$STATE_FILE" ]; then
        log_info "Found previous installation state - resuming from checkpoint"
        source "$STATE_FILE"
        log_debug "Loaded state from $STATE_FILE"
        return 0
    else
        log_debug "No previous state found - fresh installation"
        return 1
    fi
}

mark_step_complete() {
    local step=$1
    save_state "STEP_${step}" "complete"
    log_debug "Marked step complete: $step"
}

is_step_complete() {
    local step=$1
    local var_name="STEP_${step}"
    [ "${!var_name}" == "complete" ]
}

# ============================================================================
# ERROR HANDLING
# ============================================================================

error_handler() {
    local line_no=$1
    local last_command=$BASH_COMMAND
    
    log_error "Installation failed at line $line_no"
    log_error "Failed command: $last_command"
    log_error "Exit code: $?"
    
    echo -e "\n${RED}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  INSTALLATION FAILED                                           ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo -e "${YELLOW}Error Details:${NC}"
    echo "  Line: $line_no"
    echo "  Command: $last_command"
    echo ""
    echo -e "${YELLOW}Your progress has been saved.${NC}"
    echo "  State file: $STATE_FILE"
    echo "  Log file: $LOG_FILE"
    echo ""
    echo -e "${CYAN}To resume installation:${NC}"
    echo "  Simply run this script again - it will continue from where it left off"
    echo ""
    echo -e "${CYAN}For help:${NC}"
    echo "  Check the log file: cat $LOG_FILE"
    echo "  Run with debug: DEBUG=true sudo ./install_enhanced.sh"
    echo ""
    
    generate_summary "FAILED"
    exit 1
}

trap 'error_handler $LINENO' ERR

# ============================================================================
# INPUT VALIDATION
# ============================================================================

validate_url() {
    local url=$1
    if [[ ! "$url" =~ ^https?:// ]]; then
        return 1
    fi
    return 0
}

validate_hostname() {
    local hostname=$1
    # Basic hostname validation
    if [[ "$hostname" =~ ^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$ ]]; then
        return 0
    fi
    return 1
}

validate_port() {
    local port=$1
    if [[ "$port" =~ ^[0-9]+$ ]] && [ "$port" -ge 1 ] && [ "$port" -le 65535 ]; then
        return 0
    fi
    return 1
}

validate_email() {
    local email=$1
    if [[ "$email" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        return 0
    fi
    return 1
}

# Robust user input with validation and retry
prompt_with_validation() {
    local prompt=$1
    local validation_type=$2
    local default_value=$3
    local var_name=$4
    local max_attempts=3
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if [ -n "$default_value" ]; then
            read -p "$prompt [$default_value]: " user_input
            user_input=${user_input:-$default_value}
        else
            read -p "$prompt: " user_input
        fi
        
        # Validate based on type
        local valid=true
        case $validation_type in
            url)
                if ! validate_url "$user_input"; then
                    log_warn "Invalid URL format. Must start with http:// or https://"
                    valid=false
                fi
                ;;
            hostname)
                if ! validate_hostname "$user_input"; then
                    log_warn "Invalid hostname format"
                    valid=false
                fi
                ;;
            port)
                if ! validate_port "$user_input"; then
                    log_warn "Invalid port. Must be between 1 and 65535"
                    valid=false
                fi
                ;;
            email)
                if ! validate_email "$user_input"; then
                    log_warn "Invalid email format"
                    valid=false
                fi
                ;;
            nonempty)
                if [ -z "$user_input" ]; then
                    log_warn "Value cannot be empty"
                    valid=false
                fi
                ;;
            *)
                # No validation
                ;;
        esac
        
        if $valid; then
            eval "$var_name=\"$user_input\""
            save_state "$var_name" "$user_input"
            log_debug "Validated input for $var_name: $user_input"
            return 0
        fi
        
        ((attempt++))
        if [ $attempt -le $max_attempts ]; then
            log_warn "Attempt $attempt of $max_attempts. Please try again."
        fi
    done
    
    log_error "Failed to get valid input after $max_attempts attempts"
    return 1
}

# ============================================================================
# PLATFORM DETECTION
# ============================================================================

detect_platform() {
    log_step "Detecting Platform"
    
    # Detect OS type
    case "$(uname -s)" in
        Linux*)
            OS_TYPE="linux"
            log_info "Platform: Linux"
            ;;
        Darwin*)
            OS_TYPE="darwin"
            log_info "Platform: macOS"
            
            # macOS-specific checks
            if [ "$EUID" -eq 0 ] && [ -n "$SUDO_USER" ]; then
                log_error "Do NOT run this script with sudo on macOS!"
                log_error "Homebrew refuses to run as root for security reasons."
                log_error "Please run: ./install_enhanced.sh (without sudo)"
                exit 1
            fi
            ;;
        *)
            log_error "Unsupported operating system: $(uname -s)"
            log_error "This script supports Linux and macOS only"
            exit 1
            ;;
    esac
    
    # Set platform-specific paths
    if [ "$OS_TYPE" == "darwin" ]; then
        # macOS: Use user-specific locations
        STATE_FILE="$ACTUAL_HOME/.mcp-install-state.conf"
        SECRETS_FILE="$ACTUAL_HOME/.mcp-secrets"
        log_debug "macOS paths: STATE=$STATE_FILE, SECRETS=$SECRETS_FILE"
    else
        # Linux: Use system locations
        STATE_FILE="/tmp/mcp-install-state.conf"
        SECRETS_FILE="/root/.mcp-secrets"
    fi
    
    # Detect specific distribution
    if [ "$OS_TYPE" == "linux" ]; then
        if [ -f /etc/os-release ]; then
            source /etc/os-release
            OS_DIST=$ID
            OS_VERSION=$VERSION_ID
            log_info "Distribution: $PRETTY_NAME"
            log_debug "OS_DIST=$OS_DIST, VERSION=$OS_VERSION"
            
            case $OS_DIST in
                ubuntu|debian)
                    PACKAGE_MANAGER="apt"
                    ;;
                rhel|centos|rocky|almalinux|fedora)
                    PACKAGE_MANAGER="yum"
                    ;;
                *)
                    log_error "Unsupported Linux distribution: $OS_DIST"
                    exit 1
                    ;;
            esac
        else
            log_error "Cannot detect Linux distribution"
            exit 1
        fi
    elif [ "$OS_TYPE" == "darwin" ]; then
        OS_DIST="macos"
        OS_VERSION=$(sw_vers -productVersion)
        log_info "macOS Version: $OS_VERSION"
        PACKAGE_MANAGER="brew"
        
        # Check for Homebrew
        if ! command -v brew &> /dev/null; then
            log_warn "Homebrew not found. Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            
            if ! command -v brew &> /dev/null; then
                log_error "Failed to install Homebrew"
                exit 1
            fi
            log_info "Homebrew installed successfully"
        else
            log_info "Homebrew found: $(brew --version | head -1)"
        fi
    fi
    
    save_state "OS_TYPE" "$OS_TYPE"
    save_state "OS_DIST" "$OS_DIST"
    save_state "PACKAGE_MANAGER" "$PACKAGE_MANAGER"
    
    mark_step_complete "PLATFORM_DETECT"
}

# ============================================================================
# PREREQUISITES
# ============================================================================

check_prerequisites() {
    if is_step_complete "PREREQUISITES"; then
        log_info "Prerequisites already checked - skipping"
        return 0
    fi
    
    log_step "Checking Prerequisites"
    
    local missing_deps=()
    
    # Check Python
    log_debug "Checking for Python 3.9+"
    if command -v python3 &> /dev/null; then
        PY_VER=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || echo "0.0")
        log_info "Python found: $PY_VER"
        
        # Convert version to comparable number (e.g., 3.11 -> 311, 3.9 -> 309)
        PY_VER_NUM=$(echo "$PY_VER" | awk -F. '{printf "%d%02d", $1, $2}')
        REQUIRED_VER_NUM=309  # 3.9
        
        if [ "$PY_VER_NUM" -lt "$REQUIRED_VER_NUM" ]; then
            log_warn "Python $PY_VER is too old. Need Python 3.9+"
            missing_deps+=("python3")
        else
            log_debug "Python version check passed: $PY_VER >= 3.9"
        fi
    else
        log_warn "Python3 not found"
        missing_deps+=("python3")
    fi
    
    # Check Git
    if ! command -v git &> /dev/null; then
        log_warn "Git not found"
        missing_deps+=("git")
    else
        log_info "Git found: $(git --version)"
    fi
    
    # Check curl
    if ! command -v curl &> /dev/null; then
        log_warn "curl not found"
        missing_deps+=("curl")
    else
        log_info "curl found"
    fi
    
    # Platform-specific checks
    if [ "$OS_TYPE" == "linux" ]; then
        # Check systemd
        if ! command -v systemctl &> /dev/null; then
            log_error "systemd not found - required for service management"
            exit 1
        else
            log_info "systemd found"
        fi
    elif [ "$OS_TYPE" == "darwin" ]; then
        # macOS uses launchd instead of systemd
        log_info "macOS detected - will use launchd for service management"
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_warn "Missing dependencies: ${missing_deps[*]}"
        install_system_dependencies "${missing_deps[@]}"
    else
        log_info "All prerequisites met ✓"
    fi
    
    mark_step_complete "PREREQUISITES"
}

install_system_dependencies() {
    log_step "Installing System Dependencies"
    
    local deps=("$@")
    log_info "Installing: ${deps[*]}"
    
    case $PACKAGE_MANAGER in
        apt)
            log_debug "Updating package lists..."
            apt-get update -qq || {
                log_error "Failed to update package lists"
                return 1
            }
            
            log_debug "Installing packages via apt..."
            DEBIAN_FRONTEND=noninteractive apt-get install -y \
                python3.11 python3.11-venv python3-pip \
                git curl redis-server bc jq \
                build-essential libssl-dev libffi-dev python3-dev || {
                log_error "Failed to install packages with apt"
                return 1
            }
            
            log_info "Enabling Redis service..."
            systemctl enable redis-server
            systemctl start redis-server || log_warn "Redis may not have started"
            ;;
            
        yum)
            log_debug "Installing packages via yum..."
            yum install -y \
                python3.11 python3-pip \
                git curl redis bc jq \
                gcc openssl-devel bzip2-devel libffi-devel || {
                log_error "Failed to install packages with yum"
                return 1
            }
            
            log_info "Enabling Redis service..."
            systemctl enable redis
            systemctl start redis || log_warn "Redis may not have started"
            ;;
            
        brew)
            log_debug "Installing packages via Homebrew..."
            brew update || log_warn "Brew update failed"
            
            # Install packages individually to handle already-installed
            for pkg in python@3.11 git curl redis; do
                if brew list $pkg &>/dev/null; then
                    log_info "$pkg already installed"
                else
                    log_debug "Installing $pkg..."
                    brew install $pkg || log_warn "Failed to install $pkg"
                fi
            done
            
            log_info "Starting Redis service..."
            brew services start redis || log_warn "Redis may not have started"
            ;;
    esac
    
    log_info "System dependencies installed ✓"
}

# ============================================================================
# USER CREATION
# ============================================================================

create_service_user() {
    if is_step_complete "SERVICE_USER"; then
        log_info "Service user already created - skipping"
        return 0
    fi
    
    log_step "Creating Service User"
    
    if [ "$OS_TYPE" == "darwin" ]; then
        # macOS doesn't need a system user - will run as current user
        SERVICE_USER=$(whoami)
        log_info "macOS: Using current user '$SERVICE_USER' for service"
    else
        # Linux: Create dedicated service user
        if id "$SERVICE_USER" &>/dev/null; then
            log_info "Service user '$SERVICE_USER' already exists"
        else
            log_info "Creating service user '$SERVICE_USER'..."
            useradd -r -s /bin/false -d "$INSTALL_DIR" -c "MCP Redaction Service" "$SERVICE_USER" || {
                log_error "Failed to create service user"
                return 1
            }
            log_info "Service user created ✓"
        fi
    fi
    
    save_state "SERVICE_USER" "$SERVICE_USER"
    mark_step_complete "SERVICE_USER"
}

# ============================================================================
# REPOSITORY DOWNLOAD
# ============================================================================

download_repository() {
    if is_step_complete "REPOSITORY"; then
        log_info "Repository already downloaded - skipping"
        return 0
    fi
    
    log_step "Downloading Repository"
    
    if [ -d "$INSTALL_DIR" ]; then
        log_warn "Install directory already exists: $INSTALL_DIR"
        
        read -p "Remove and re-download? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Removing existing directory..."
            
            # On macOS, /opt typically requires sudo for write operations
            if [ "$OS_TYPE" == "darwin" ]; then
                log_info "macOS: Using elevated permissions to remove /opt directory"
                sudo rm -rf "$INSTALL_DIR" || {
                    log_error "Failed to remove directory. Try manually: sudo rm -rf $INSTALL_DIR"
                    return 1
                }
            else
                rm -rf "$INSTALL_DIR" || {
                    log_error "Failed to remove directory"
                    return 1
                }
            fi
        else
            log_info "Using existing installation directory"
            mark_step_complete "REPOSITORY"
            return 0
        fi
    fi
    
    log_info "Cloning from GitHub: $REPO_URL"
    log_debug "Target directory: $INSTALL_DIR"
    
    # On macOS, create /opt directory with sudo if needed
    if [ "$OS_TYPE" == "darwin" ] && [ ! -d "$(dirname "$INSTALL_DIR")" ]; then
        log_info "Creating /opt directory with elevated permissions..."
        sudo mkdir -p "$(dirname "$INSTALL_DIR")" || {
            log_error "Failed to create /opt directory"
            return 1
        }
    fi
    
    # Clone repository - use sudo on macOS for /opt
    if [ "$OS_TYPE" == "darwin" ]; then
        sudo git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" || {
            log_error "Failed to clone repository"
            log_error "Check internet connection and GitHub access"
            return 1
        }
        # Give current user ownership
        sudo chown -R "$ACTUAL_USER:staff" "$INSTALL_DIR"
        log_debug "Set ownership to $ACTUAL_USER:staff"
    else
        git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" || {
            log_error "Failed to clone repository"
            log_error "Check internet connection and GitHub access"
            return 1
        }
        # Set ownership on Linux
        chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
        log_debug "Set ownership to $SERVICE_USER"
    fi
    
    log_info "Repository downloaded ✓"
    
    mark_step_complete "REPOSITORY"
}

# ============================================================================
# PYTHON VIRTUAL ENVIRONMENT
# ============================================================================

setup_virtualenv() {
    if is_step_complete "VIRTUALENV"; then
        log_info "Virtual environment already set up - skipping"
        return 0
    fi
    
    log_step "Setting Up Python Virtual Environment"
    
    cd "$INSTALL_DIR" || {
        log_error "Cannot access install directory"
        return 1
    }
    
    # Determine Python command
    local python_cmd="python3.11"
    if ! command -v $python_cmd &> /dev/null; then
        python_cmd="python3"
        if ! command -v $python_cmd &> /dev/null; then
            log_error "No suitable Python found"
            return 1
        fi
    fi
    
    log_info "Using Python: $python_cmd ($(command -v $python_cmd || echo 'not found'))"
    log_debug "Python version: $($python_cmd --version)"
    
    # Create virtual environment
    log_info "Creating virtual environment..."
    if [ "$OS_TYPE" == "linux" ]; then
        sudo -u "$SERVICE_USER" $python_cmd -m venv .venv || {
            log_error "Failed to create virtual environment"
            return 1
        }
    else
        $python_cmd -m venv .venv || {
            log_error "Failed to create virtual environment"
            return 1
        }
    fi
    
    log_info "Installing Python dependencies..."
    
    if [ "$OS_TYPE" == "linux" ]; then
        sudo -u "$SERVICE_USER" .venv/bin/pip install --upgrade pip setuptools wheel >> "$LOG_FILE" 2>&1
        sudo -u "$SERVICE_USER" .venv/bin/pip install -r requirements.txt >> "$LOG_FILE" 2>&1 || {
            log_error "Failed to install Python dependencies"
            log_error "Check $LOG_FILE for details"
            return 1
        }
    else
        .venv/bin/pip install --upgrade pip setuptools wheel >> "$LOG_FILE" 2>&1
        .venv/bin/pip install -r requirements.txt >> "$LOG_FILE" 2>&1 || {
            log_error "Failed to install Python dependencies"
            log_error "Check $LOG_FILE for details"
            return 1
        }
    fi
    
    log_info "Virtual environment ready ✓"
    log_debug "Installed packages: $(.venv/bin/pip list --format=freeze | wc -l) packages"
    
    mark_step_complete "VIRTUALENV"
}

# ============================================================================
# SECRETS GENERATION
# ============================================================================

generate_secrets() {
    if is_step_complete "SECRETS"; then
        log_info "Secrets already generated - skipping"
        if [ -f "$SECRETS_FILE" ]; then
            source "$SECRETS_FILE"
        fi
        return 0
    fi
    
    log_step "Generating Cryptographic Secrets"
    
    log_info "Generating secure random keys..."
    log_debug "Using openssl for key generation"
    
    MCP_TOKEN_SALT=$(openssl rand -base64 32)
    MCP_ENCRYPTION_KEY=$(openssl rand -base64 32)
    
    log_debug "Generated MCP_TOKEN_SALT: ${MCP_TOKEN_SALT:0:20}..."
    log_debug "Generated MCP_ENCRYPTION_KEY: ${MCP_ENCRYPTION_KEY:0:20}..."
    
    # Save to secure location
    cat > "$SECRETS_FILE" <<EOF
# MCP Redaction Server Secrets
# Generated: $(date)
# KEEP THIS FILE SECURE - DO NOT SHARE OR COMMIT TO VERSION CONTROL

MCP_TOKEN_SALT="$MCP_TOKEN_SALT"
MCP_ENCRYPTION_KEY="$MCP_ENCRYPTION_KEY"
EOF
    
    chmod 600 "$SECRETS_FILE" || {
        log_error "Failed to set permissions on secrets file"
        return 1
    }
    
    # On macOS, ensure the actual user owns the file
    if [ "$OS_TYPE" == "darwin" ] && [ -n "$ACTUAL_USER" ]; then
        chown "$ACTUAL_USER" "$SECRETS_FILE" 2>/dev/null || true
    fi
    
    log_debug "Set permissions on secrets file: 600"
    
    echo -e "\n${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  CRITICAL: Cryptographic Secrets Generated${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
    echo -e "\nLocation: ${YELLOW}$SECRETS_FILE${NC}"
    echo -e "\n${RED}⚠ BACKUP THESE SECRETS IMMEDIATELY ⚠${NC}"
    echo -e "${RED}Store in a password manager or secure vault.${NC}"
    echo -e "${RED}You cannot recover encrypted data without these!${NC}\n"
    echo -e "MCP_TOKEN_SALT:      ${YELLOW}${MCP_TOKEN_SALT}${NC}"
    echo -e "MCP_ENCRYPTION_KEY:  ${YELLOW}${MCP_ENCRYPTION_KEY}${NC}\n"
    
    echo -e "${CYAN}Have you securely backed up these secrets?${NC}"
    read -p "Type 'YES' to confirm: " confirm
    
    if [ "$confirm" != "YES" ]; then
        log_warn "Secrets not confirmed as backed up"
        echo -e "${YELLOW}Please back up the secrets file before continuing.${NC}"
        read -p "Press ENTER when you have backed up the secrets..."
    fi
    
    save_state "MCP_TOKEN_SALT" "$MCP_TOKEN_SALT"
    save_state "MCP_ENCRYPTION_KEY" "$MCP_ENCRYPTION_KEY"
    mark_step_complete "SECRETS"
    
    log_info "Secrets generated and saved ✓"
}

# ============================================================================
# SIEM CONFIGURATION
# ============================================================================

configure_siem() {
    if is_step_complete "SIEM_CONFIG"; then
        log_info "SIEM already configured - skipping"
        return 0
    fi
    
    log_step "Configuring SIEM Integration"
    
    echo -e "\n${BLUE}Select SIEM platform for audit log shipping:${NC}\n"
    echo "  1) Splunk (HTTP Event Collector)"
    echo "  2) Elasticsearch / ELK Stack"
    echo "  3) Datadog Logs"
    echo "  4) Syslog (Traditional SIEM)"
    echo "  5) None (Local logs only)"
    echo ""
    
    local valid_choice=false
    while [ "$valid_choice" = false ]; do
        read -p "Choice [1-5] (default: 5): " siem_choice
        siem_choice=${siem_choice:-5}
        
        if [[ "$siem_choice" =~ ^[1-5]$ ]]; then
            valid_choice=true
        else
            log_warn "Invalid choice. Please enter 1-5"
        fi
    done
    
    case $siem_choice in
        1)
            configure_splunk
            ;;
        2)
            configure_elasticsearch
            ;;
        3)
            configure_datadog
            ;;
        4)
            configure_syslog
            ;;
        5)
            SIEM_TYPE="none"
            save_state "SIEM_TYPE" "none"
            log_info "SIEM integration skipped - using local logs only"
            ;;
    esac
    
    mark_step_complete "SIEM_CONFIG"
}

configure_splunk() {
    log_info "Configuring Splunk HEC integration..."
    
    SIEM_TYPE="splunk"
    
    prompt_with_validation \
        "Splunk HEC URL (e.g., https://splunk.company.com:8088)" \
        "url" \
        "" \
        "SPLUNK_HEC_URL"
    
    prompt_with_validation \
        "Splunk HEC Token" \
        "nonempty" \
        "" \
        "SPLUNK_HEC_TOKEN"
    
    save_state "SIEM_TYPE" "splunk"
    log_info "Splunk SIEM configured ✓"
}

configure_elasticsearch() {
    log_info "Configuring Elasticsearch integration..."
    
    SIEM_TYPE="elasticsearch"
    
    prompt_with_validation \
        "Elasticsearch URL (e.g., https://es.company.com:9200)" \
        "url" \
        "" \
        "ELASTICSEARCH_URL"
    
    read -p "Elasticsearch API Key (press ENTER if none): " ELASTICSEARCH_API_KEY
    save_state "ELASTICSEARCH_API_KEY" "$ELASTICSEARCH_API_KEY"
    
    prompt_with_validation \
        "Index name" \
        "" \
        "mcp-audit" \
        "ELASTICSEARCH_INDEX"
    
    save_state "SIEM_TYPE" "elasticsearch"
    log_info "Elasticsearch SIEM configured ✓"
}

configure_datadog() {
    log_info "Configuring Datadog integration..."
    
    SIEM_TYPE="datadog"
    
    prompt_with_validation \
        "Datadog API Key" \
        "nonempty" \
        "" \
        "DATADOG_API_KEY"
    
    prompt_with_validation \
        "Datadog Site" \
        "" \
        "datadoghq.com" \
        "DATADOG_SITE"
    
    save_state "SIEM_TYPE" "datadog"
    log_info "Datadog SIEM configured ✓"
}

configure_syslog() {
    log_info "Configuring Syslog integration..."
    
    SIEM_TYPE="syslog"
    
    prompt_with_validation \
        "Syslog server hostname/IP" \
        "hostname" \
        "" \
        "SYSLOG_HOST"
    
    prompt_with_validation \
        "Syslog port" \
        "port" \
        "514" \
        "SYSLOG_PORT"
    
    save_state "SIEM_TYPE" "syslog"
    log_info "Syslog SIEM configured ✓"
}

# ============================================================================
# ENVIRONMENT FILE CREATION
# ============================================================================

create_env_file() {
    if is_step_complete "ENV_FILE"; then
        log_info "Environment file already created - skipping"
        return 0
    fi
    
    log_step "Creating Environment Configuration"
    
    log_info "Writing .env file..."
    log_debug "Target: $INSTALL_DIR/.env"
    
    cat > "$INSTALL_DIR/.env" <<EOF
# MCP Redaction Server Environment Configuration
# Generated: $(date)
# Installer Version: $SCRIPT_VERSION

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

# Claim Verification (Research-based hallucination detection)
CLAIM_VERIFICATION_ENABLED=false
CLAIM_VERIFICATION_MODEL=gpt-4o-mini
CLAIM_VERIFICATION_LEVEL=standard
CLAIM_VERIFICATION_INLINE=true

# Local Model Support (vLLM, FastAPI, etc.)
# For local models: Set BASE_URL to your local endpoint, REQUIRE_AUTH=false
# CLAIM_VERIFICATION_BASE_URL=http://localhost:8000/v1
# CLAIM_VERIFICATION_API_KEY=
# CLAIM_VERIFICATION_REQUIRE_AUTH=false
# CLAIM_VERIFICATION_SUPPORTS_JSON=false

# SIEM Configuration
EOF

    # Add SIEM-specific configuration
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
    if [ "$OS_TYPE" == "linux" ]; then
        chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
    fi
    
    log_info "Environment configuration created ✓"
    log_info "✓ Transparent Proxy Mode: ENABLED"
    log_info "✓ Claim Verification: DISABLED (enable in .env if needed)"
    
    mark_step_complete "ENV_FILE"
}

# ============================================================================
# SERVICE CREATION
# ============================================================================

create_service() {
    if is_step_complete "SERVICE"; then
        log_info "Service already created - skipping"
        return 0
    fi
    
    log_step "Creating System Service"
    
    if [ "$OS_TYPE" == "linux" ]; then
        create_systemd_service
    elif [ "$OS_TYPE" == "darwin" ]; then
        create_launchd_service
    fi
    
    mark_step_complete "SERVICE"
}

create_systemd_service() {
    log_info "Creating systemd service..."
    
    # Create audit and log directories
    mkdir -p "$INSTALL_DIR/audit"
    mkdir -p "/var/log/$SERVICE_NAME"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/audit"
    chown -R "$SERVICE_USER:$SERVICE_USER" "/var/log/$SERVICE_NAME"
    
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

    systemctl daemon-reload
    log_info "Systemd service created ✓"
}

create_launchd_service() {
    log_info "Creating launchd service..."
    
    local plist_file="$HOME/Library/LaunchAgents/com.mcp.redaction.plist"
    mkdir -p "$HOME/Library/LaunchAgents"
    mkdir -p "$INSTALL_DIR/audit"
    mkdir -p "$INSTALL_DIR/logs"
    
    cat > "$plist_file" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mcp.redaction</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/.venv/bin/uvicorn</string>
        <string>mcp_redaction.server:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8019</string>
        <string>--workers</string>
        <string>4</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$INSTALL_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/logs/stderr.log</string>
</dict>
</plist>
EOF
    
    log_info "launchd service created ✓"
    log_debug "Service file: $plist_file"
}

# ============================================================================
# SERVICE MANAGEMENT
# ============================================================================

start_service() {
    log_step "Starting MCP Redaction Service"
    
    if [ "$OS_TYPE" == "linux" ]; then
        log_info "Enabling and starting systemd service..."
        systemctl enable "$SERVICE_NAME"
        systemctl start "$SERVICE_NAME"
        sleep 3
        
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            log_info "Service started successfully ✓"
        else
            log_error "Service failed to start"
            log_error "Check logs: journalctl -u $SERVICE_NAME -n 50"
            return 1
        fi
    elif [ "$OS_TYPE" == "darwin" ]; then
        log_info "Loading launchd service..."
        launchctl load "$HOME/Library/LaunchAgents/com.mcp.redaction.plist"
        sleep 3
        
        if launchctl list | grep -q "com.mcp.redaction"; then
            log_info "Service started successfully ✓"
        else
            log_error "Service failed to start"
            log_error "Check logs: tail -f $INSTALL_DIR/logs/stderr.log"
            return 1
        fi
    fi
}

# ============================================================================
# HEALTH CHECK
# ============================================================================

health_check() {
    log_step "Running Health Check"
    
    local max_attempts=15
    local attempt=1
    local endpoint="http://localhost:8019/health"
    
    log_info "Waiting for service to be ready..."
    log_debug "Testing endpoint: $endpoint"
    
    while [ $attempt -le $max_attempts ]; do
        log_debug "Health check attempt $attempt/$max_attempts"
        
        if curl -sf "$endpoint" > /dev/null 2>&1; then
            log_info "Health check passed ✓"
            log_debug "Service is responding correctly"
            return 0
        fi
        
        if [ $attempt -lt $max_attempts ]; then
            log_debug "Service not ready yet, waiting 2 seconds..."
            sleep 2
        fi
        
        ((attempt++))
    done
    
    log_error "Health check failed after $max_attempts attempts"
    log_error "Service may not be running correctly"
    
    # Show recent logs for debugging
    if [ "$OS_TYPE" == "linux" ]; then
        log_error "Recent logs:"
        journalctl -u "$SERVICE_NAME" -n 20 --no-pager | tail -10
    elif [ "$OS_TYPE" == "darwin" ]; then
        log_error "Recent logs:"
        tail -20 "$INSTALL_DIR/logs/stderr.log"
    fi
    
    return 1
}

# ============================================================================
# SUMMARY GENERATION
# ============================================================================

generate_summary() {
    local status=$1
    
    # Ensure we can write to the summary file
    if [ ! -w "$(dirname "$SUMMARY_FILE")" ]; then
        log_warn "Cannot write summary to $SUMMARY_FILE"
        SUMMARY_FILE="/tmp/mcp-install-summary.txt"
        log_info "Using alternate location: $SUMMARY_FILE"
    fi
    
    cat > "$SUMMARY_FILE" <<EOF
MCP Redaction & Compliance Server - Installation Summary
Generated: $(date)
Installer Version: $SCRIPT_VERSION
Status: $status

PLATFORM:
  OS Type: $OS_TYPE
  Distribution: $OS_DIST
  Package Manager: $PACKAGE_MANAGER

INSTALLATION:
  Install Directory: $INSTALL_DIR
  Service User: $SERVICE_USER
  Service Name: $SERVICE_NAME

CONFIGURATION:
  Secrets File: $SECRETS_FILE
  Environment File: $INSTALL_DIR/.env
  SIEM Type: ${SIEM_TYPE:-none}
  Proxy Mode: ENABLED
  Claim Verification: DISABLED (configurable)

LOGS:
  Installation Log: $LOG_FILE
  Service Logs: $([ "$OS_TYPE" == "linux" ] && echo "/var/log/$SERVICE_NAME" || echo "$INSTALL_DIR/logs")
  Audit Logs: $INSTALL_DIR/audit/

SERVICE ACCESS:
  Local URL: http://localhost:8019
  Health Check: curl http://localhost:8019/health

NEXT STEPS:
  1. Test the API: curl http://localhost:8019/health
  2. Review configuration: cat $INSTALL_DIR/.env
  3. Check logs: $([ "$OS_TYPE" == "linux" ] && echo "journalctl -u $SERVICE_NAME -f" || echo "tail -f $INSTALL_DIR/logs/stderr.log")
  4. Enable claim verification (optional): Edit $INSTALL_DIR/.env

IMPORTANT:
  - Secrets backed up: $SECRETS_FILE
  - Review security settings before production use
  - Configure firewall rules as needed
  - Update trusted callers in policy file

For support: https://github.com/sunkencity999/redaction-compliance-MCP
EOF
    
    log_info "Installation summary saved: $SUMMARY_FILE"
}

# ============================================================================
# FINAL SUMMARY DISPLAY
# ============================================================================

print_success() {
    echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                                ║${NC}"
    echo -e "${GREEN}║  ✓ MCP Redaction Server Installed Successfully!               ║${NC}"
    echo -e "${GREEN}║                                                                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo -e "${BLUE}Installation Summary:${NC}"
    echo "  Platform:        $OS_TYPE ($OS_DIST)"
    echo "  Install Dir:     $INSTALL_DIR"
    echo "  Service:         $SERVICE_NAME"
    echo "  Local URL:       http://localhost:8019"
    echo ""
    
    echo -e "${BLUE}Features Enabled:${NC}"
    echo "  ✓ Transparent Proxy Mode (OpenAI/Claude/Gemini compatible)"
    echo "  ✓ Streaming Support"
    echo "  ✓ Redis Token Storage"
    echo "  ✓ SIEM Integration: ${SIEM_TYPE:-none}"
    echo "  • Claim Verification: Disabled (enable in .env)"
    echo ""
    
    echo -e "${BLUE}Quick Test:${NC}"
    echo "  curl http://localhost:8019/health"
    echo ""
    
    echo -e "${BLUE}Files Created:${NC}"
    echo "  Installation log:  $LOG_FILE"
    echo "  Summary:           $SUMMARY_FILE"
    echo "  Secrets:           $SECRETS_FILE ${RED}(BACKUP THIS!)${NC}"
    echo "  Config:            $INSTALL_DIR/.env"
    echo ""
    
    echo -e "${BLUE}Service Management:${NC}"
    if [ "$OS_TYPE" == "linux" ]; then
        echo "  Status:  systemctl status $SERVICE_NAME"
        echo "  Logs:    journalctl -u $SERVICE_NAME -f"
        echo "  Stop:    systemctl stop $SERVICE_NAME"
        echo "  Start:   systemctl start $SERVICE_NAME"
    elif [ "$OS_TYPE" == "darwin" ]; then
        echo "  Status:  launchctl list | grep mcp"
        echo "  Logs:    tail -f $INSTALL_DIR/logs/stderr.log"
        echo "  Stop:    launchctl unload ~/Library/LaunchAgents/com.mcp.redaction.plist"
        echo "  Start:   launchctl load ~/Library/LaunchAgents/com.mcp.redaction.plist"
    fi
    echo ""
    
    echo -e "${CYAN}Next Steps:${NC}"
    echo "  1. Test the API health endpoint"
    echo "  2. Review the summary file: cat $SUMMARY_FILE"
    echo "  3. Configure claim verification if needed: Edit $INSTALL_DIR/.env"
    echo "  4. Update firewall rules for production"
    echo "  5. See TRANSPARENT_PROXY.md and CLAIM_VERIFICATION.md for usage"
    echo ""
    
    echo -e "${RED}IMPORTANT:${NC}"
    echo "  ⚠ Backup your secrets file: $SECRETS_FILE"
    echo "  ⚠ Review security settings before production use"
    echo ""
}

# ============================================================================
# MAIN INSTALLATION FLOW
# ============================================================================

main_install() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  MCP Redaction & Compliance Server - Enhanced Installer       ║${NC}"
    echo -e "${BLUE}║  Version $SCRIPT_VERSION                                             ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}\n"
    
    log_info "Installation started"
    log_info "Log file: $LOG_FILE"
    log_info "Platform: $(uname -s) $(uname -m)"
    
    # Platform detection FIRST (sets paths)
    detect_platform
    
    # Load previous state if exists
    load_state || log_info "Starting fresh installation"
    
    # Check root/sudo requirements
    if [ "$OS_TYPE" == "linux" ]; then
        if [ "$EUID" -ne 0 ]; then
            log_error "Linux requires root access. Please run: sudo ./install_enhanced.sh"
            exit 1
        fi
    elif [ "$OS_TYPE" == "darwin" ]; then
        if [ "$EUID" -eq 0 ]; then
            log_error "macOS should NOT be run with sudo. Please run: ./install_enhanced.sh"
            exit 1
        fi
    fi
    
    # Installation steps (platform already detected above)
    check_prerequisites
    create_service_user
    download_repository
    setup_virtualenv
    generate_secrets
    configure_siem
    create_env_file
    create_service
    start_service
    health_check || {
        log_warn "Health check failed but continuing..."
    }
    
    # Generate summary
    generate_summary "SUCCESS"
    
    # Clean up state file on success
    rm -f "$STATE_FILE"
    log_info "Installation completed successfully"
    
    print_success
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

# Parse command line arguments
case "${1:-}" in
    --help|-h)
        cat <<EOF
MCP Redaction Server - Enhanced Installer v$SCRIPT_VERSION

Usage: sudo ./install_enhanced.sh [OPTIONS]

Options:
  --help, -h        Show this help message
  --debug           Enable debug logging
  --resume          Resume from previous failed installation
  --uninstall       Remove MCP Redaction Server

Features:
  ✓ Supports Linux (Ubuntu, RHEL, CentOS) and macOS
  ✓ Graceful failure handling with resume capability  
  ✓ Input validation with retry logic
  ✓ Detailed logging to timestamped log files
  ✓ Installation summary report
  ✓ Comprehensive error messages

Examples:
  sudo ./install_enhanced.sh            # Normal installation
  DEBUG=true sudo ./install_enhanced.sh # With debug output
  sudo ./install_enhanced.sh --resume   # Resume after failure

Documentation:
  https://github.com/sunkencity999/redaction-compliance-MCP
EOF
        exit 0
        ;;
    --debug)
        export DEBUG=true
        log_info "Debug mode enabled"
        main_install
        ;;
    --resume)
        log_info "Resuming installation from previous state"
        main_install
        ;;
    --uninstall)
        log_error "Uninstall not yet implemented in enhanced installer"
        log_info "Use the original install.sh --uninstall for now"
        exit 1
        ;;
    "")
        main_install
        ;;
    *)
        log_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac
