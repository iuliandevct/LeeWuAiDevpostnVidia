# Hermes Acer sales gateway

Minimal, secret-free deployment package for Gabriel's Acer Windows computer.
It runs Hermes natively inside WSL2, uses Gemini cloud inference, skips the
browser and local models, and installs only focused skills. It does not copy
Mac sessions, caches, logs, databases, OAuth files, or credentials.

## Requirements

- Windows 10/11 with WSL2 and Ubuntu
- Python/runtime dependencies installed by the official Hermes installer
- a separate Gemini API key and Telegram bot token for this gateway

## Install

1. Extract the archive to a normal Windows folder.
2. In PowerShell run `Set-ExecutionPolicy -Scope Process Bypass`.
3. Run `.\setup-acer.ps1`.
4. Inside Ubuntu edit `~/.hermes/.env` and replace every placeholder.
5. Run `hermes gateway setup` and configure Telegram with a strict user allowlist.
6. Start with `.\start-gateway.ps1`. Keep this window open during initial testing.

For automatic startup, create a Windows Task Scheduler entry that runs
`powershell.exe -ExecutionPolicy Bypass -File <full-path>\start-gateway.ps1`
at Gabriel's logon. Configure this only after manual Telegram and model tests pass.

## Low-resource profile

- no Docker Desktop;
- no Ollama or local LLM;
- no Chromium/browser automation;
- Gemini Flash Lite cloud model;
- two CPU threads requested for numerical/tokenizer libraries;
- foreground gateway in WSL, as recommended by Hermes for WSL.

Do not reuse Jay's Telegram token or Gemini key. Separate credentials allow the
sales gateway to be revoked or rate-limited without affecting the main Hermes.
