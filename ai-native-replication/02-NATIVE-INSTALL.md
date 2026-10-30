# Native macOS installation

## Prerequisites

```bash
uname -m
sw_vers
brew --version
git --version
node --version
python3 --version
```

The reference machine is Intel (`x86_64`). Confirm formula availability on
other architectures before installation.

## Homebrew packages

```bash
brew install grafana influxdb@2 influxdb-cli telegraf
brew install mariadb php postgresql@15 nginx wp-cli
brew install gh
brew install --cask repetier-host
```

Start the Homebrew-managed services:

```bash
brew services start grafana
brew services start influxdb@2
brew services start mariadb
brew services start php
brew services start nginx
```

Do not run InfluxDB 3 on port 8086 when the stack expects InfluxDB 2.

## Stack source

Place the source in a user-owned directory, for example:

```text
~/Downloads/ai-containers-stack
```

Do not copy:

```text
.env
vibe-trading/
vibe-trading-src/
**/__pycache__/
node_modules/
```

Generate a fresh `.env` on each destination. See `06-SECRETS-TRANSFER.md`.

## Native runtime files

Create native launch scripts for:

- Telegraf using `http://127.0.0.1:8086`;
- WordPress using `php -S 127.0.0.1:8081`;
- the static graph using `python3 -m http.server 8090`;
- Graph API using Python on port 8091;
- PostgreSQL 15 using port 54322 and `LC_ALL=en_US.UTF-8`.

Create per-user LaunchAgents under:

```text
~/Library/LaunchAgents/
```

Recommended labels:

```text
local.ai-stack.telegraf
local.ai-stack.wordpress
local.ai-stack.obsidian-graph
local.ai-stack.graph-api
local.ai-stack.postgresql15
```

Keep logs under:

```text
~/Library/Logs/ai-containers-stack/
```

Validate every plist before loading:

```bash
plutil -lint ~/Library/LaunchAgents/local.ai-stack.*.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/NAME.plist
```

Bind HTTP services to `127.0.0.1` by default. Change to LAN binding only for
services that another authorized Mac must reach.
