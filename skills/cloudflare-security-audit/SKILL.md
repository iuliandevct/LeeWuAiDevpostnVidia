---
name: cloudflare-security-audit
description: Comprehensive Cloudflare Security Audit, Security Insights CSV Analyzer, Email DMARC/SPF Remediation, Turnstile Protection, and Cloudflare Tunnel (cloudflared) Deployment for leewuai.ro.
---

# Cloudflare Security Audit & Tunnel Architecture Skill

This skill provides an automated framework to perform rigorous security posture audits, analyze Cloudflare Security Insights findings, remediate DNS/Email/WAF misconfigurations, and maintain zero-trust edge ingress tunnels (`cloudflared`) for maritime and enterprise applications.

---

## 1. Core Security Capabilities

### A. Security Insights Remediation
Automated parsing and fixing of vulnerabilities flagged in Cloudflare Security Insights:
1. **DMARC / SPF Record Validation**:
   - Problem: Missing or malformed DMARC allows attackers to spoof domain emails (`@leewuai.ro`, `@leewuai.ro`).
   - Remediation:
     - DMARC TXT: `_dmarc.leewuai.ro` -> `v=DMARC1; p=quarantine; sp=quarantine; rua=mailto:dmarc-reports@leewuai.ro; pct=100; aspf=r;`
     - SPF TXT: `leewuai.ro` -> `v=spf1 include:_spf.mx.cloudflare.net ~all`
2. **Security.txt Standard (RFC 9116)**:
   - Location: `/.well-known/security.txt` and `/security.txt`
   - Defines security contacts, encryption keys (OpenPGP), policy guidelines, and canonical acknowledgment URLs.
3. **Bot Fight Mode & Turnstile Protection**:
   - Mitigation of automated credential stuffing and bot scraping.
   - Embedded client-side Turnstile widget for authentication gateways (`login.html`).
4. **Zero-Trust MFA & RBAC Enforcement**:
   - Enforce hardware/TOTP Multi-Factor Authentication across all Cloudflare dashboard members.

---

## 2. Cloudflare Tunnel (`cloudflared`) Architecture for `leewuai.ro`

Cloudflare Tunnel creates an encrypted, outbound-only connection to Cloudflare’s global edge network without opening any inbound ports on firewalls or routers.

### Ingress Routing Rules:
```yaml
tunnel: <TUNNEL_UUID_OR_NAME>
credentials-file: /etc/cloudflared/<TUNNEL_UUID>.json

ingress:
  # 1. Main Landing & Overview
  - hostname: leewuai.ro
    service: http://localhost:8080

  # 2. Transparent Pricing Gateway
  - hostname: leewuai.ro
    path: ^/prices.*
    service: http://localhost:8080/prices.html

  # 3. Surveyor Operations Mission Console
  - hostname: console.leewuai.ro
    service: http://localhost:8080/survey-console.html

  # 4. Maritime REST API & Webhooks
  - hostname: api.leewuai.ro
    service: http://localhost:1880

  # 5. n8n Autonomous Workflow Ingestion
  - hostname: n8n.leewuai.ro
    service: http://localhost:5678

  # 6. Fallback 404 Catch-All
  - service: http_status:404
```

---

## 3. Deployment Commands & Verification

### Quick Start with Single Token:
```bash
# Install and run as a system service
sudo cloudflared service install <TUNNEL_TOKEN>
sudo systemctl enable --now cloudflared
cloudflared tunnel status
```

### Manual CLI Ingress Run:
```bash
cloudflared tunnel --config /etc/cloudflared/config.yml run leewu-tunnel
```

---

## 4. Security Audit Checklist
- [x] HTTPS Only (Automatic HTTPS Rewrites enabled)
- [x] Minimum TLS Version: TLS 1.3
- [x] HSTS: Enabled (max-age=31536000, includeSubDomains, preload)
- [x] DNSSEC: Active and signed
- [x] DMARC & SPF: `_dmarc` TXT record with quarantine policy
- [x] `/.well-known/security.txt`: Compliant with RFC 9116
- [x] Turnstile CAPTCHA: Enabled on login/register endpoints
- [x] Cloudflare Tunnel: Outbound TLS 1.3 edge proxy (Zero open incoming firewall ports)
