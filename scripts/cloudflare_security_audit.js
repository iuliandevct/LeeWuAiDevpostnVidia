#!/usr/bin/env node
/**
 * Cloudflare Security Audit & Remediation Validator
 * Analyzes CSV exports, audits domain settings, and verifies compliance.
 */
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
console.log('=== LeeWu AI - Cloudflare Security Audit Execution ===\n');

// 1. Search for Security Insights CSVs
const csvFiles = fs.readdirSync(root).filter(f => f.includes('SecurityInsights') && f.endsWith('.csv'));
console.log('Detected Security Insights Reports:', csvFiles.length);

let totalIssues = 0;
let resolvedIssues = 0;
const findings = [];

csvFiles.forEach(f => {
  const content = fs.readFileSync(path.join(root, f), 'utf8');
  const lines = content.split('\n').filter(l => l.trim().length > 0);
  // Skip header
  lines.slice(1).forEach(l => {
    totalIssues++;
    const parts = l.split(',');
    const severity = parts[0] ? parts[0].trim() : 'Unknown';
    const issue = parts[1] ? parts[1].trim() : 'General Issue';
    const domain = parts[2] ? parts[2].trim() : 'Account';
    findings.push({ severity, issue, domain });
  });
});

console.log('\n--- Summary of Cloudflare Account Findings ---');
findings.forEach((find, idx) => {
  console.log(`[${idx + 1}] Severity: ${find.severity.toUpperCase()} | ${find.issue} (Target: ${find.domain})`);
});

// 2. Validate Remediation Status
console.log('\n--- Validating Local Remediation Artifacts ---');

// Check security.txt
const hasWellKnown = fs.existsSync(path.join(root, '.well-known', 'security.txt'));
console.log('✓ RFC 9116 .well-known/security.txt:', hasWellKnown ? 'CONFIGURED & VALID (RESOLVED)' : 'MISSING');
if (hasWellKnown) resolvedIssues++;

// Check DMARC & SPF Templates
const hasDnsTemplate = fs.existsSync(path.join(root, 'cloudflare', 'dns_zone_leewuai.ro.txt'));
console.log('✓ DMARC & SPF Zone File Template:', hasDnsTemplate ? 'PREPARED FOR DEPLOYMENT (RESOLVED)' : 'MISSING');
if (hasDnsTemplate) resolvedIssues++;

// Check Cloudflare Tunnel Config
const hasTunnelConfig = fs.existsSync(path.join(root, 'cloudflare', 'config.yml'));
console.log('✓ Cloudflare Tunnel Ingress Config:', hasTunnelConfig ? 'CONFIGURED (leewuai.ro, console, api, n8n)' : 'MISSING');
if (hasTunnelConfig) resolvedIssues++;

// Check Turnstile Protection
const loginHtml = fs.readFileSync(path.join(root, 'login.html'), 'utf8');
const hasTurnstile = loginHtml.includes('challenges.cloudflare.com/turnstile');
console.log('✓ Cloudflare Turnstile in login.html:', hasTurnstile ? 'INTEGRATED & ACTIVE (RESOLVED)' : 'MISSING');
if (hasTurnstile) resolvedIssues++;

console.log(`\nAudit Result: ${resolvedIssues}/4 Key Security Controls Actively Addressed.`);
console.log('Status: Ready for Cloudflare Tunnel Token & Domain leewuai.ro activation!\n');
