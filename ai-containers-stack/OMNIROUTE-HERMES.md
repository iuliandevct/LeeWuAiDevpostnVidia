# OmniRoute + Hermes

OmniRoute is installed as a local OpenAI-compatible gateway and exposed at
`http://127.0.0.1:20128/v1`. The macOS LaunchAgent template in `native/` keeps
the gateway running after login and restarts it after a crash.

Hermes uses OmniRoute as its primary provider. No secret is stored in YAML:

```yaml
model:
  default: auto/best-coding
  provider: omniroute
  base_url: http://127.0.0.1:20128/v1

custom_providers:
  - name: omniroute
    base_url: http://127.0.0.1:20128/v1
    api_mode: chat_completions
    model: auto/best-coding
    discover_models: true
```

Install and verify:

```sh
npm install --global omniroute
omniroute serve --daemon --no-open
curl http://127.0.0.1:20128/v1/models
hermes config get custom_providers
hermes -z 'Reply with exactly: HERMES_OMNIROUTE_OK'
```

Validated locally on 2026-08-02: the default Hermes invocation returned
`HERMES_OMNIROUTE_OK`. Google/Gemini remains available as a manually selectable
provider but is no longer the default inference path.

The dashboard is available at `http://127.0.0.1:20128`. Provider credentials
must be connected there or through OmniRoute's supported OAuth/API-key setup.
Never commit `~/.omniroute/.env`, `~/.hermes/.env`, endpoint keys, provider
tokens, or the OmniRoute SQLite database.
