# Enhanced Installation Script

**Version 2.1.0** | Comprehensive installer with resume capability, input validation, and detailed logging

## 🎯 Key Features

### ✅ What Makes This Enhanced?

1. **Cross-Platform Support**
   - ✅ Linux (Ubuntu, RHEL, CentOS, Rocky, Alma)
   - ✅ macOS 12+ (with Homebrew)
   - Automatic platform detection and adaptation

2. **Graceful Failure Handling**
   - ✅ Resume from any failed step
   - ✅ State file tracks progress
   - ✅ Detailed error messages with recovery instructions
   - ✅ Never lose progress

3. **Input Validation**
   - ✅ URL format validation
   - ✅ Hostname validation
   - ✅ Port range checking (1-65535)
   - ✅ Email format validation
   - ✅ 3 retry attempts with helpful error messages

4. **Verbose Logging**
   - ✅ Timestamped log files in current directory
   - ✅ Color-coded console output
   - ✅ Debug mode available (`DEBUG=true`)
   - ✅ Installation summary report
   - ✅ Dual logging (file + console)

5. **Production-Ready**
   - ✅ Secrets generation with confirmation
   - ✅ SIEM integration (Splunk, Elasticsearch, Datadog, Syslog)
   - ✅ Service management (systemd for Linux, launchd for macOS)
   - ✅ Health checks with retry logic
   - ✅ Complete error handling

---

## 🚀 Quick Start

### Linux Installation

```bash
# Download and run
wget https://raw.githubusercontent.com/sunkencity999/redaction-compliance-MCP/main/install_enhanced.sh
chmod +x install_enhanced.sh
sudo ./install_enhanced.sh
```

### macOS Installation

```bash
# Download and run (no sudo needed on macOS)
curl -O https://raw.githubusercontent.com/sunkencity999/redaction-compliance-MCP/main/install_enhanced.sh
chmod +x install_enhanced.sh
./install_enhanced.sh
```

---

## 📋 Installation Steps

The installer will guide you through:

1. **Platform Detection** - Automatically detects your OS and package manager
2. **Prerequisites Check** - Installs Python 3.11, Git, Redis, etc.
3. **Service User Creation** - Creates dedicated service user (Linux only)
4. **Repository Download** - Clones from GitHub
5. **Python Environment** - Creates virtual environment and installs dependencies
6. **Secrets Generation** - Generates cryptographic keys (YOU MUST BACKUP THESE!)
7. **SIEM Configuration** - Optional integration with your SIEM platform
8. **Environment Setup** - Creates .env file with all configuration
9. **Service Creation** - Sets up systemd (Linux) or launchd (macOS)
10. **Service Start** - Starts the MCP server
11. **Health Check** - Verifies the server is responding

---

## 🛠️ Usage Examples

### Normal Installation
```bash
sudo ./install_enhanced.sh
```

### With Debug Output
```bash
DEBUG=true sudo ./install_enhanced.sh
```

### Resume After Failure
```bash
# Just run again - it automatically resumes!
sudo ./install_enhanced.sh
```

### Get Help
```bash
./install_enhanced.sh --help
```

---

## 📊 What Gets Created

### Log Files (in current directory)

- **`mcp-install-YYYYMMDD-HHMMSS.log`** - Complete installation log
  - All commands executed
  - All output (stdout + stderr)
  - Debug information
  - Timestamps for every step

- **`mcp-install-summary.txt`** - Installation summary
  - Platform information
  - Installation paths
  - Configuration details
  - Next steps
  - Quick reference commands

### State File (for resume capability)

- **`/tmp/mcp-install-state.conf`** - Progress tracking
  - Stores completed steps
  - Saves user inputs (SIEM config, etc.)
  - Allows resuming from failure point
  - Automatically deleted on success

### Installed Files

- **`/opt/mcp-redaction/`** - Main installation directory
  - Application code
  - Virtual environment (`.venv/`)
  - Configuration (`.env`)
  - Audit logs (`audit/`)
  - Examples (`examples/`)

- **`/root/.mcp-secrets`** - Cryptographic secrets
  - MCP_TOKEN_SALT
  - MCP_ENCRYPTION_KEY
  - **⚠️ BACKUP THIS FILE IMMEDIATELY!**

---

## 🔧 Resume Capability

### How It Works

The installer saves its progress to `/tmp/mcp-install-state.conf` after each step.

If installation fails:
1. **Review the error** in the console output
2. **Check the log file** for detailed information
3. **Fix the issue** (if needed)
4. **Re-run the script** - it will skip completed steps!

### Example Resume Scenario

```bash
# First attempt - fails at SIEM configuration
$ sudo ./install_enhanced.sh
...
✓ Virtual environment created
✓ Secrets generated
✗ SIEM configuration failed (invalid URL)

# Fix the issue and resume
$ sudo ./install_enhanced.sh
✓ Platform already detected - skipping
✓ Prerequisites already checked - skipping
✓ Service user already created - skipping
✓ Repository already downloaded - skipping
✓ Virtual environment already set up - skipping
✓ Secrets already generated - skipping
→ Configuring SIEM Integration  # Resumes here!
```

---

## 🎨 Color-Coded Output

The installer uses colors to help you quickly understand status:

- **🟢 Green ✓** - Success messages
- **🟡 Yellow ⚠** - Warnings (non-fatal)
- **🔴 Red ✗** - Errors (need attention)
- **🔵 Blue ═══** - Section headers
- **🔷 Cyan ↳** - Debug information

---

## 🧪 Input Validation Examples

### URL Validation
```
Splunk HEC URL: htp://invalid
⚠ Invalid URL format. Must start with http:// or https://
Attempt 2 of 3. Please try again.
Splunk HEC URL: https://splunk.company.com:8088
✓ URL validated
```

### Port Validation
```
Syslog port: 99999
⚠ Invalid port. Must be between 1 and 65535
Attempt 2 of 3. Please try again.
Syslog port: 514
✓ Port validated
```

### Hostname Validation
```
Server hostname: my server!
⚠ Invalid hostname format
Attempt 2 of 3. Please try again.
Server hostname: mcp.company.com
✓ Hostname validated
```

---

## 📝 Example Installation Log Output

```
╔════════════════════════════════════════════════════════════════╗
║  MCP Redaction & Compliance Server - Enhanced Installer       ║
║  Version 2.1.0                                                 ║
╚════════════════════════════════════════════════════════════════╝

✓ Installation started
✓ Log file: ./mcp-install-20251028-120000.log
✓ Platform: Linux x86_64

═══ Detecting Platform ═══
✓ Platform: Linux
✓ Distribution: Ubuntu 22.04.3 LTS
  ↳ OS_DIST=ubuntu, VERSION=22.04

═══ Checking Prerequisites ═══
✓ Python found: 3.11.4
✓ Git found: git version 2.34.1
✓ curl found
✓ systemd found
✓ All prerequisites met ✓

═══ Creating Service User ═══
✓ Creating service user 'mcp'...
✓ Service user created ✓

═══ Downloading Repository ═══
✓ Cloning from GitHub: https://github.com/...
✓ Repository downloaded ✓

═══ Setting Up Python Virtual Environment ═══
✓ Using Python: python3.11
✓ Creating virtual environment...
✓ Installing Python dependencies...
✓ Virtual environment ready ✓

═══ Generating Cryptographic Secrets ═══
✓ Generating secure random keys...

═══════════════════════════════════════════════════════
  CRITICAL: Cryptographic Secrets Generated
═══════════════════════════════════════════════════════

Location: /root/.mcp-secrets

⚠ BACKUP THESE SECRETS IMMEDIATELY ⚠

MCP_TOKEN_SALT:      dGVzdF9zYWx0X2hlcmVfZm9y...
MCP_ENCRYPTION_KEY:  dGVzdF9lbmNyeXB0aW9uX2tl...

Have you securely backed up these secrets?
Type 'YES' to confirm: YES
✓ Secrets generated and saved ✓

═══ Configuring SIEM Integration ═══

Select SIEM platform for audit log shipping:
  1) Splunk (HTTP Event Collector)
  2) Elasticsearch / ELK Stack
  3) Datadog Logs
  4) Syslog (Traditional SIEM)
  5) None (Local logs only)

Choice [1-5] (default: 5): 5
✓ SIEM integration skipped - using local logs only

═══ Creating Environment Configuration ═══
✓ Writing .env file...
✓ Environment configuration created ✓
✓ Transparent Proxy Mode: ENABLED
✓ Claim Verification: DISABLED (enable in .env if needed)

═══ Creating System Service ═══
✓ Creating systemd service...
✓ Systemd service created ✓

═══ Starting MCP Redaction Service ═══
✓ Enabling and starting systemd service...
✓ Service started successfully ✓

═══ Running Health Check ═══
✓ Waiting for service to be ready...
✓ Health check passed ✓

✓ Installation summary saved: ./mcp-install-summary.txt
✓ Installation completed successfully

╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ✓ MCP Redaction Server Installed Successfully!               ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

---

## 🔍 Debugging Failed Installations

### 1. Check the Log File
```bash
# View the complete log
cat mcp-install-20251028-120000.log

# Search for errors
grep -i error mcp-install-20251028-120000.log
```

### 2. Check Service Status
```bash
# Linux
systemctl status mcp-redaction
journalctl -u mcp-redaction -n 50

# macOS
launchctl list | grep mcp
tail -50 /opt/mcp-redaction/logs/stderr.log
```

### 3. Verify Prerequisites
```bash
# Check Python
python3 --version

# Check Redis
redis-cli ping

# Check Git
git --version
```

### 4. Test Health Endpoint
```bash
curl -v http://localhost:8019/health
```

---

## ⚙️ Configuration After Installation

### Enable Claim Verification

Edit `/opt/mcp-redaction/.env`:
```bash
# Change this line:
CLAIM_VERIFICATION_ENABLED=false

# To:
CLAIM_VERIFICATION_ENABLED=true
```

Then restart:
```bash
# Linux
sudo systemctl restart mcp-redaction

# macOS
launchctl unload ~/Library/LaunchAgents/com.mcp.redaction.plist
launchctl load ~/Library/LaunchAgents/com.mcp.redaction.plist
```

### Update Trusted Callers

Edit `/opt/mcp-redaction/mcp_redaction/sample_policies/default.yaml` to add your application names.

---

## 📚 Differences from Original `install.sh`

| Feature | Original | Enhanced |
|---------|----------|----------|
| **macOS Support** | ❌ No | ✅ Yes |
| **Resume Capability** | ❌ No | ✅ Yes |
| **Input Validation** | ❌ Basic | ✅ Comprehensive |
| **Logging** | ❌ Mixed | ✅ Dedicated files |
| **Error Handling** | ❌ Basic | ✅ Detailed + recovery |
| **Progress Tracking** | ❌ No | ✅ State file |
| **Debug Mode** | ❌ No | ✅ Yes |
| **Summary Report** | ❌ No | ✅ Yes |
| **Verbosity** | ❌ Minimal | ✅ Very detailed |

---

## 🎯 Production Checklist

After installation completes:

- [ ] **Secrets backed up** - Copy `/root/.mcp-secrets` to password manager
- [ ] **Test health endpoint** - `curl http://localhost:8019/health`
- [ ] **Review logs** - Check for any warnings
- [ ] **Configure firewall** - Open port 8019 or setup NGINX
- [ ] **Update trusted callers** - Edit policy file
- [ ] **Enable claim verification** - If needed for your use case
- [ ] **Setup monitoring** - Add to your monitoring system
- [ ] **Configure backups** - For audit logs and config
- [ ] **Review security** - Before exposing to network
- [ ] **Test API** - Run example scripts in `/opt/mcp-redaction/examples/`

---

## 🆘 Getting Help

If you encounter issues:

1. **Check the log file** - It has detailed information
2. **Review the summary** - `cat mcp-install-summary.txt`
3. **Run with debug** - `DEBUG=true sudo ./install_enhanced.sh`
4. **Check GitHub Issues** - https://github.com/sunkencity999/redaction-compliance-MCP/issues
5. **Review documentation** - See README.md, DEPLOYMENT.md

---

## 🚀 Next Steps After Installation

1. **Test the installation**
   ```bash
   curl http://localhost:8019/health
   ```

2. **Review the summary**
   ```bash
   cat mcp-install-summary.txt
   ```

3. **Try the examples**
   ```bash
   cd /opt/mcp-redaction/examples
   /opt/mcp-redaction/.venv/bin/python basic_example.py
   ```

4. **Read the guides**
   - `TRANSPARENT_PROXY.md` - Zero-code LLM integration
   - `CLAIM_VERIFICATION.md` - Hallucination detection

5. **Configure for production**
   - Setup NGINX reverse proxy
   - Enable HTTPS
   - Configure firewall rules
   - Add to monitoring

---

**Your MCP Redaction & Compliance Server is now ready to use!** 🎉
