#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER="$(mktemp)"
trap 'rm -f "$INSTALLER"' EXIT

command -v curl >/dev/null || { echo "curl is required" >&2; exit 1; }

curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o "$INSTALLER"
sh -n "$INSTALLER"
bash "$INSTALLER" --skip-setup --skip-browser --non-interactive

mkdir -p "$HOME/.hermes/skills"
cp -R "$PACKAGE_DIR/skills/." "$HOME/.hermes/skills/"

if [[ ! -f "$HOME/.hermes/.env" ]]; then
  install -m 600 "$PACKAGE_DIR/.env.example" "$HOME/.hermes/.env"
  echo "Created ~/.hermes/.env from the safe template. Add credentials before starting."
else
  chmod 600 "$HOME/.hermes/.env"
  echo "Kept the existing ~/.hermes/.env. No credentials were overwritten."
fi

MODEL="$(sed -n 's/^HERMES_MODEL=//p' "$HOME/.hermes/.env" | tail -n 1)"
MODEL="${MODEL:-gemini-2.5-flash-lite}"
"$HOME/.local/bin/hermes" config set model.provider gemini
"$HOME/.local/bin/hermes" config set model.default "$MODEL"

echo "Setup complete. Edit ~/.hermes/.env, then run: hermes gateway setup"
echo "For WSL use foreground mode: hermes gateway run"
