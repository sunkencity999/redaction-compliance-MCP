# Installation Quick Reference Card

## 🚀 One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/sunkencity999/redaction-compliance-MCP/main/install.sh | sudo bash
```

Or download and run:

```bash
wget https://raw.githubusercontent.com/sunkencity999/redaction-compliance-MCP/main/install.sh
chmod +x install.sh
sudo ./install.sh
```

---

## 📋 What You'll Need

Before starting:
- [ ] Linux server with root/sudo access
- [ ] 8GB+ RAM, 4+ CPU cores, 50GB+ disk
- [ ] SIEM credentials (Splunk HEC token, Elasticsearch API key, etc.)
- [ ] Password manager ready for secrets backup

---

## ⚡ Installation Flow (5 Minutes)

```
1. Run installer → ./install.sh
2. Choose "Install" (option 1)
3. Wait for dependencies
4. BACKUP SECRETS when prompted ⚠️
5. Configure SIEM (or skip)
6. Run tests (recommended)
7. Done! ✓
```

---

## 🔑 Critical: Save Your Secrets

The installer generates two secrets:

```
MCP_TOKEN_SALT="<32-byte base64 string>"
MCP_ENCRYPTION_KEY="<32-byte base64 string>"
```

**Save to**:
- Password manager (1Password, LastPass)
- Secure vault (HashiCorp Vault, AWS Secrets Manager)
- Encrypted backup location

**Location on server**: `/root/.mcp-secrets`

**⚠️ If you lose these, all encrypted tokens are unrecoverable!**

---

## 🎛️ SIEM Options

Choose during installation:

| Option | Platform | What You Need |
|--------|----------|---------------|
| 1 | **Splunk** | HEC URL + Token |
| 2 | **Elasticsearch** | URL + API Key (optional) |
| 3 | **Datadog** | API Key + Site |
| 4 | **Syslog** | Hostname + Port |
| 5 | **None** | Just local logs |

**Default**: Splunk (option 1)

---

## ✅ Verify Installation

```bash
# Service status
systemctl status mcp-redaction

# Health check
curl http://localhost:8019/health

# Expected response:
{"status":"healthy","version":"2.0.0",...}

# View logs
journalctl -u mcp-redaction -f
```

---

## 📁 Important Locations

| What | Where |
|------|-------|
| **Installation** | `/opt/mcp-redaction` |
| **Service** | `systemctl status mcp-redaction` |
| **Logs** | `journalctl -u mcp-redaction -f` |
| **Audit logs** | `/opt/mcp-redaction/audit/audit.jsonl` |
| **Config** | `/opt/mcp-redaction/.env` |
| **Secrets** | `/root/.mcp-secrets` |
| **Policy** | `/opt/mcp-redaction/mcp_redaction/sample_policies/default.yaml` |

---

## 🔧 Common Commands

```bash
# Start/stop/restart
systemctl start mcp-redaction
systemctl stop mcp-redaction
systemctl restart mcp-redaction

# View logs (live)
journalctl -u mcp-redaction -f

# View audit logs (live)
tail -f /opt/mcp-redaction/audit/audit.jsonl

# Check health
curl http://localhost:8019/health

# Run demo
cd /opt/mcp-redaction
sudo -u mcp .venv/bin/python mcp_redaction/demo_client.py

# Uninstall
./install.sh --uninstall
```

---

## 🌐 Post-Install: Setup HTTPS

**Required for production!**

```bash
# Install NGINX
apt install -y nginx certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d mcp.example.com

# Configure as reverse proxy (see DEPLOYMENT.md)
```

---

## 🔥 Troubleshooting

### Service won't start
```bash
journalctl -u mcp-redaction -n 100
systemctl status redis
```

### Can't reach service
```bash
netstat -tlnp | grep 8019
ufw status
```

### SIEM not receiving logs
```bash
grep SIEM /opt/mcp-redaction/.env
journalctl -u mcp-redaction | grep -i siem
```

### Forgot secrets
```bash
cat /root/.mcp-secrets
```

---

## 📖 Full Documentation

- **Complete Guide**: `DEPLOYMENT.md`
- **Quick Start**: `QUICKSTART.md`
- **SIEM Setup**: `SIEM_INTEGRATION.md`
- **Policy Config**: `POLICY_GUIDE.md`

---

## 🆘 Resume Failed Install

If installation was interrupted:

```bash
./install.sh
# Installer will resume from last successful step
```

State saved in: `/tmp/mcp-install-state.conf`

---

## 🗑️ Uninstall

```bash
sudo ./install.sh --uninstall
```

**What gets removed**:
- Service and installation directory
- Service user
- Logs

**What's preserved**:
- Secrets file (`/root/.mcp-secrets`)
- Install log (`/var/log/mcp-install.log`)

---

## 📊 Installation Summary

After successful installation:

```
✓ Python 3.11 + virtual environment
✓ Redis server
✓ MCP Redaction Server
✓ Systemd service (auto-start on boot)
✓ Log rotation (90 days audit, 30 days service)
✓ Firewall rules
✓ Secrets generated and backed up
✓ SIEM integration (if configured)
✓ All tests passed (186+ tests)
```

**Service URL**: `http://your-server:8019`

---

## 🎯 Next Steps

1. ✅ Verify installation with health check
2. 🔒 Setup HTTPS with NGINX/TLS certificates
3. 📝 Customize policy in `default.yaml`
4. 🔐 Configure mTLS for client authentication
5. 📊 Setup monitoring/alerts in SIEM
6. 🧪 Run demo client to test functionality
7. 🚀 Integrate with your applications

---

**Install Time**: ~5 minutes  
**Version**: 2.0.0  
**Script**: `install.sh`  
**Repository**: https://github.com/sunkencity999/redaction-compliance-MCP
