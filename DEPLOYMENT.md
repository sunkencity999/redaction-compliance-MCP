# Production Deployment Guide

Complete guide for deploying MCP Redaction Server to a Linux production server using the **automated installer with Direct API integration**.

**Key Features:**
- 🚀 Automated NGINX reverse proxy with HTTPS (Let's Encrypt or self-signed)
- 📦 Python Client SDK included
- 🔗 Seamless Direct API integration examples
- ⚡ 5-minute installation
- 🔄 Resumable if interrupted

---

## 📋 Prerequisites

### Server Requirements

**Minimum (Small Organization)**:
- OS: Ubuntu 20.04+ or RHEL 8+
- CPU: 4 cores
- RAM: 8 GB
- Disk: 50 GB SSD
- Network: 1 Gbps

**Recommended (Medium Organization)**:
- OS: Ubuntu 22.04 LTS
- CPU: 8-16 cores
- RAM: 32 GB
- Disk: 200 GB SSD
- Network: 10 Gbps

### Network Access

- Outbound HTTPS (443) for package downloads
- Outbound to SIEM platform (if using Splunk/Elasticsearch/Datadog)
- Inbound port 8019 (or custom port) for API access
- SSH access for installation

### Required Information

Before starting, gather:

1. **Server credentials**: Root or sudo access
2. **SIEM details** (if using):
   - Splunk: HEC URL and token
   - Elasticsearch: URL and API key
   - Datadog: API key and site
   - Syslog: Hostname and port
3. **DNS/Hostname**: Public hostname for the service
4. **TLS certificates**: For HTTPS (post-installation)

---

## 🚀 Quick Start (5 Minutes)

### 1. Download Installer

```bash
# SSH to your server
ssh user@your-server.example.com

# Become root
sudo su -

# Download installer
curl -fsSL https://raw.githubusercontent.com/sunkencity999/redaction-compliance-MCP/main/install.sh -o install.sh
chmod +x install.sh
```

### 2. Run Installer

```bash
./install.sh
```

### 3. Follow Prompts

The installer will:
- ✅ Install dependencies (Python 3.11, Redis, etc.)
- ✅ Clone repository from GitHub
- ✅ Generate cryptographic secrets
- ✅ Configure SIEM integration
- ✅ Create systemd service
- ✅ Run tests
- ✅ Start service

### 4. Verify Installation

```bash
# Check service status
systemctl status mcp-redaction

# Test health endpoint
curl http://localhost:8019/health

# View logs
journalctl -u mcp-redaction -f
```

---

## 📖 Detailed Installation Steps

### Step 1: System Preparation

```bash
# Update system
apt update && apt upgrade -y  # Ubuntu/Debian
yum update -y                  # RHEL/CentOS

# Install basic tools
apt install -y curl wget git  # Ubuntu/Debian
yum install -y curl wget git  # RHEL/CentOS
```

### Step 2: Download and Execute Installer

```bash
# Download installer
wget https://raw.githubusercontent.com/sunkencity999/redaction-compliance-MCP/main/install.sh

# Make executable
chmod +x install.sh

# Run as root
sudo ./install.sh
```

### Step 3: Installation Menu

```
╔════════════════════════════════════════════════════════════════╗
║  MCP Redaction & Compliance Server - Production Installer     ║
║  Version 2.0.0                                                 ║
╚════════════════════════════════════════════════════════════════╝

1) Install MCP Redaction Server
2) Uninstall MCP Redaction Server
3) Exit

Select option [1-3]:
```

Choose **1** to install.

### Step 4: Secret Generation

The installer will generate two cryptographic keys:

```
═══════════════════════════════════════════════════════
  IMPORTANT: Secrets Generated and Saved
═══════════════════════════════════════════════════════
Location: /root/.mcp-secrets

⚠ BACKUP THIS FILE IMMEDIATELY ⚠
Store in password manager or secure vault.

MCP_TOKEN_SALT: <32-byte base64 string>
MCP_ENCRYPTION_KEY: <32-byte base64 string>

Press ENTER after you have securely backed up these secrets...
```

**CRITICAL**: Copy these secrets to:
- Password manager (1Password, LastPass, etc.)
- Secure vault (HashiCorp Vault, AWS Secrets Manager, etc.)
- Encrypted backup location

### Step 5: SIEM Configuration

```
╔════════════════════════════════════════════════════════════════╗
║  SIEM Integration Configuration                                ║
╚════════════════════════════════════════════════════════════════╝

Select SIEM platform:
1) Splunk (HTTP Event Collector)
2) Elasticsearch / ELK Stack
3) Datadog Logs
4) Syslog (Traditional SIEM)
5) None (Local logs only)

Choice [1-5] (default: 1):
```

#### Option 1: Splunk

```
Choice [1-5] (default: 1): 1
Splunk HEC URL (e.g., https://splunk.example.com:8088): https://your-splunk:8088
Splunk HEC Token: 12345678-1234-1234-1234-123456789012
```

#### Option 2: Elasticsearch

```
Choice [1-5] (default: 1): 2
Elasticsearch URL (e.g., https://es.example.com:9200): https://your-es:9200
Elasticsearch API Key (press ENTER if none): your-api-key-here
Index name (default: mcp-audit): mcp-audit
```

#### Option 3: Datadog

```
Choice [1-5] (default: 1): 3
Datadog API Key: your-datadog-api-key
Datadog Site (default: datadoghq.com): datadoghq.com
```

#### Option 4: Syslog

```
Choice [1-5] (default: 1): 4
Syslog server hostname/IP: syslog.example.com
Syslog port (default: 514): 514
```

#### Option 5: None

```
Choice [1-5] (default: 1): 5
✓ SIEM integration skipped (local logs only)
```

### Step 6: Test Suite

```
Run test suite? (recommended) (Y/n): Y

Running test suite...
================================== test session starts ==================================
tests/test_detectors.py::TestCredentialDetection::test_aws_credentials PASSED
tests/test_detectors.py::TestCredentialDetection::test_azure_credentials PASSED
...
186 passed in 12.34s
✓ All tests passed ✓
```

### Step 7: Service Startup

```
✓ Starting MCP Redaction service...
✓ Service started successfully
✓ Health check passed ✓
```

### Step 8: Installation Complete

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ✓ MCP Redaction Server Installed Successfully!               ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

API Access:
  Public URL:      https://mcp.yourcompany.com
  Health check:    curl https://mcp.yourcompany.com/health

System Management:
  Service status:  systemctl status mcp-redaction
  View logs:       journalctl -u mcp-redaction -f
  Audit logs:      tail -f /opt/mcp-redaction/audit/audit.jsonl

Client SDK Integration:
  Python SDK:      Installed in /opt/mcp-redaction/.venv
  Examples:        /opt/mcp-redaction/examples/
    • basic_example.py        - Simple redact/detokenize
    • openai_integration.py   - OpenAI wrapper
    • safe_llm_wrapper.py     - Drop-in LLM protection
```

---

## 📦 Using the Python Client SDK

The installer automatically includes the Python Client SDK for seamless application integration.

### Quick Start

```python
from mcp_client import MCPClient, MCPConfig

# Configure client
mcp = MCPClient(MCPConfig(
    server_url="https://mcp.yourcompany.com",
    caller="your-app-name",
    region="us"
))

# Protect user input before sending to LLM
user_input = "My AWS key is AKIAIOSFODNN7EXAMPLE, help debug"

try:
    # Step 1: Redact sensitive data
    sanitized, token_handle = mcp.redact(user_input)
    # Result: "My AWS key is «token:SECRET:a3f9», help debug"
    
    # Step 2: Send sanitized version to your LLM
    llm_response = your_llm_function(sanitized)
    
    # Step 3: Restore non-secret tokens
    final = mcp.detokenize(llm_response, token_handle)
    
    return final

except MCPBlockedError as e:
    # Request was blocked by policy
    print(f"Blocked: {e}")
```

### Examples Included

After installation, find ready-to-run examples in `/opt/mcp-redaction/examples/`:

```bash
# Test basic functionality
cd /opt/mcp-redaction
.venv/bin/python examples/basic_example.py

# Test with OpenAI (requires OPENAI_API_KEY)
export OPENAI_API_KEY="your-key"
.venv/bin/python examples/openai_integration.py

# Use wrapper function
.venv/bin/python examples/safe_llm_wrapper.py
```

### Install SDK in Your Application

```bash
# Option 1: Install from server directory
pip install /opt/mcp-redaction

# Option 2: Copy SDK to your project
cp -r /opt/mcp-redaction/mcp_client /path/to/your/project/
```

### Environment Variables

Configure SDK via environment:

```bash
export MCP_SERVER_URL="https://mcp.yourcompany.com"
export MCP_CALLER="your-app-name"
export MCP_REGION="us"
export MCP_ENV="prod"
```

Then use `MCPConfig.from_env()` in your code.

---

## 🔧 Post-Installation Configuration

### 1. Setup TLS/HTTPS (REQUIRED for Production)

Install NGINX as reverse proxy:

```bash
# Install NGINX
apt install -y nginx certbot python3-certbot-nginx  # Ubuntu
yum install -y nginx certbot python3-certbot-nginx  # RHEL

# Configure NGINX
cat > /etc/nginx/sites-available/mcp-redaction <<'EOF'
server {
    listen 80;
    server_name mcp.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name mcp.example.com;

    ssl_certificate /etc/letsencrypt/live/mcp.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://localhost:8019;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/mcp-redaction /etc/nginx/sites-enabled/

# Get TLS certificate
certbot --nginx -d mcp.example.com

# Reload NGINX
systemctl reload nginx
```

### 2. Configure Firewall

```bash
# Allow HTTPS, block direct access to 8019
ufw allow 443/tcp
ufw deny 8019/tcp from any to any

# Or with firewalld
firewall-cmd --permanent --add-service=https
firewall-cmd --permanent --remove-port=8019/tcp
firewall-cmd --reload
```

### 3. Customize Policy

```bash
# Edit policy file
vi /opt/mcp-redaction/mcp_redaction/sample_policies/default.yaml

# Example: Add trusted caller
vi /opt/mcp-redaction/mcp_redaction/sample_policies/default.yaml
# Add under detokenize_permissions:
#   - caller: "my-app"
#     categories: ["pii", "ops_sensitive"]

# Reload service (policy hot-reloads automatically)
systemctl restart mcp-redaction
```

### 4. Setup Monitoring

```bash
# Add Prometheus metrics endpoint (future feature)
# For now, monitor with journalctl and SIEM

# Create monitoring script
cat > /usr/local/bin/mcp-monitor.sh <<'EOF'
#!/bin/bash
if ! systemctl is-active --quiet mcp-redaction; then
    echo "CRITICAL: MCP service is down"
    # Send alert to PagerDuty/Slack/etc
fi

if ! curl -sf http://localhost:8019/health > /dev/null; then
    echo "CRITICAL: MCP health check failed"
fi
EOF

chmod +x /usr/local/bin/mcp-monitor.sh

# Add to cron (every 5 minutes)
echo "*/5 * * * * /usr/local/bin/mcp-monitor.sh" | crontab -
```

---

## 🔄 Resume Interrupted Installation

The installer saves state and can resume from where it left off:

```bash
# If installation was interrupted
./install.sh

# The installer will detect existing state:
✓ Service user 'mcp' already exists
✓ Using existing secrets from previous run
✓ Using existing SIEM configuration: splunk
...continuing from last step...
```

State is saved in: `/tmp/mcp-install-state.conf`

---

## 🗑️ Uninstallation

### Option 1: Interactive

```bash
sudo ./install.sh

# Select option 2
2) Uninstall MCP Redaction Server
```

### Option 2: Command Line

```bash
sudo ./install.sh --uninstall
```

### What Gets Removed

- ✅ Systemd service
- ✅ Installation directory (`/opt/mcp-redaction`)
- ✅ Service user (`mcp`)
- ✅ Log rotation config
- ✅ Audit logs
- ❌ Secrets file (`/root/.mcp-secrets`) - **PRESERVED**

---

## 📊 Verification & Testing

### 1. Service Health

```bash
# Check service status
systemctl status mcp-redaction

# Check health endpoint
curl http://localhost:8019/health

# Expected response:
{
  "status": "healthy",
  "version": "2.0.0",
  "token_backend": "redis",
  "policy_version": 2,
  "siem_enabled": true
}
```

### 2. API Testing

```bash
# Test classify endpoint
curl -X POST http://localhost:8019/classify \
  -H "Content-Type: application/json" \
  -d '{
    "payload": "Email: test@example.com, AWS Key: AKIAIOSFODNN7EXAMPLE",
    "context": {"caller": "test", "region": "us"}
  }'

# Expected: Detects PII and secret
```

### 3. Run Demo Client

```bash
cd /opt/mcp-redaction
sudo -u mcp .venv/bin/python mcp_redaction/demo_client.py
```

### 4. Check Logs

```bash
# Service logs
journalctl -u mcp-redaction -n 100

# Audit logs
tail -f /opt/mcp-redaction/audit/audit.jsonl

# SIEM logs
# Check your SIEM platform for incoming logs
```

---

## 🔐 Security Hardening

### 1. Secrets Management

```bash
# Rotate secrets quarterly
NEW_SALT=$(openssl rand -base64 32)
NEW_KEY=$(openssl rand -base64 32)

# Update /opt/mcp-redaction/.env
sed -i "s/MCP_TOKEN_SALT=.*/MCP_TOKEN_SALT=\"$NEW_SALT\"/" /opt/mcp-redaction/.env
sed -i "s/MCP_ENCRYPTION_KEY=.*/MCP_ENCRYPTION_KEY=\"$NEW_KEY\"/" /opt/mcp-redaction/.env

# Restart service
systemctl restart mcp-redaction

# Update backup
echo "MCP_TOKEN_SALT=\"$NEW_SALT\"" > /root/.mcp-secrets-$(date +%F)
echo "MCP_ENCRYPTION_KEY=\"$NEW_KEY\"" >> /root/.mcp-secrets-$(date +%F)
```

### 2. Enable mTLS (Client Certificate Authentication)

```nginx
# In NGINX config
server {
    listen 443 ssl http2;
    server_name mcp.example.com;

    # Add client certificate verification
    ssl_client_certificate /etc/nginx/ssl/ca.crt;
    ssl_verify_client on;
    ssl_verify_depth 2;

    location / {
        proxy_pass http://localhost:8019;
        # Pass client cert info to backend
        proxy_set_header X-Client-CN $ssl_client_s_dn_cn;
    }
}
```

### 3. Network Isolation

```bash
# Bind to localhost only (force traffic through NGINX)
# Edit systemd service:
vi /etc/systemd/system/mcp-redaction.service

# Change ExecStart line to:
ExecStart=/opt/mcp-redaction/.venv/bin/uvicorn mcp_redaction.server:app \
    --host 127.0.0.1 \
    --port 8019 \
    --workers 4

systemctl daemon-reload
systemctl restart mcp-redaction
```

---

## 📈 Scaling

### Vertical Scaling (Single Server)

```bash
# Increase workers in systemd service
vi /etc/systemd/system/mcp-redaction.service

# Change --workers based on CPU cores (2x cores recommended)
--workers 16  # For 8-core server

systemctl daemon-reload
systemctl restart mcp-redaction
```

### Horizontal Scaling (Load Balancer)

1. Install on multiple servers using same script
2. Use same secrets on all servers (copy `/root/.mcp-secrets`)
3. Setup HAProxy or NGINX load balancer

```nginx
# Load balancer config
upstream mcp_backend {
    server mcp1.internal:8019;
    server mcp2.internal:8019;
    server mcp3.internal:8019;
}

server {
    listen 443 ssl;
    server_name mcp.example.com;

    location / {
        proxy_pass http://mcp_backend;
    }
}
```

---

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check logs
journalctl -u mcp-redaction -n 100 --no-pager

# Check Redis
systemctl status redis
redis-cli ping  # Should return PONG

# Check Python environment
sudo -u mcp /opt/mcp-redaction/.venv/bin/python -c "import mcp_redaction; print('OK')"

# Verify secrets
grep MCP_TOKEN_SALT /opt/mcp-redaction/.env
```

### Health Check Fails

```bash
# Check if service is listening
netstat -tlnp | grep 8019

# Test locally
curl http://127.0.0.1:8019/health

# Check firewall
ufw status
iptables -L -n
```

### SIEM Not Receiving Logs

```bash
# Check SIEM config
grep SIEM /opt/mcp-redaction/.env

# Test connectivity
# For Splunk:
curl -k https://your-splunk:8088/services/collector/health

# For Elasticsearch:
curl https://your-es:9200/_cluster/health

# Check service logs for SIEM errors
journalctl -u mcp-redaction | grep -i siem
```

### High Memory Usage

```bash
# Reduce workers
vi /etc/systemd/system/mcp-redaction.service
# Change --workers to lower number

# Add memory limit
vi /etc/systemd/system/mcp-redaction.service
# Add under [Service]:
MemoryMax=4G

systemctl daemon-reload
systemctl restart mcp-redaction
```

---

## 📚 Additional Resources

- **Main Documentation**: `/opt/mcp-redaction/README.md`
- **Quick Start**: `/opt/mcp-redaction/QUICKSTART.md`
- **SIEM Integration**: `/opt/mcp-redaction/SIEM_INTEGRATION.md`
- **Policy Guide**: `/opt/mcp-redaction/POLICY_GUIDE.md`
- **GitHub**: https://github.com/sunkencity999/redaction-compliance-MCP

---

## 📞 Support

**Installation Issues**:
- Check installation log: `/var/log/mcp-install.log`
- Review service logs: `journalctl -u mcp-redaction -n 200`
- Open GitHub issue with logs

**Production Support**:
- Monitor health endpoint: `GET /health`
- Review audit logs: `/opt/mcp-redaction/audit/audit.jsonl`
- Check SIEM platform for alerts

---

**Deployment Guide Version**: 2.0.0  
**Last Updated**: 2025-10-10  
**Installation Script**: `install.sh`
