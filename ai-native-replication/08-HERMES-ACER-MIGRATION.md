# Hermes Acer-to-Mac migration report

Date: 31 July 2026

Source: Acer Windows PC (`DESKTOP-505E8UJ`, user `pc`)

Destination: Jay Mac Pro

Method: additive, non-destructive migration

## Outcome

Hermes on the Mac now has the useful persistent knowledge from the Acer:

- 16 Acer conversations and all 517 associated messages;
- the Acer user memory (`USER.md`);
- 12 skills that were not present on the Mac;
- the original Acer Hermes backup, retained outside Git for recovery.

Nothing in the existing Mac Hermes installation was deleted or overwritten.
The destination database passed SQLite integrity and foreign-key checks after
the merge. Gemini inference, memory loading, Telegram polling, and launchd
supervision were all verified after migration.

## Before and after

| Item | Acer before migration | Mac before migration | Mac after migration |
| --- | ---: | ---: | ---: |
| Hermes version | 0.18.2 | 0.19.0 | 0.19.0 |
| Config schema | 33 | 33 | 33 |
| Provider | Gemini | Gemini | Gemini |
| Default model | `gemini-3.5-flash-lite` | `gemini-3.6-flash` | `gemini-3.6-flash` |
| Sessions | 16 | 9 | 25 |
| Messages | 517 | 50 | 567 |
| Skills | 74 | 69 | 81 |
| Explicit user-memory files | 1 | 0 | 1 |

The Mac remains on the newer Hermes runtime and model. Only portable user data
was activated; Windows/container runtime files were not installed into the
native macOS runtime.

## Data migrated

### Conversations and session memory

The Acer `state.db` was first converted offline with the Hermes 0.19.0
`sessions recover` command. Recovery produced:

- 16 of 16 sessions;
- 517 of 517 messages;
- 26 of 26 model-usage records;
- no skipped ranges;
- a valid recovered database.

There were no session-ID collisions with the Mac database. The recovered rows
were inserted transactionally into the existing Mac database. Acer session
titles received an `[Acer <id>]` suffix where necessary because Hermes 0.19.0
enforces unique non-null titles.

Gateway routing, active locks, pending delegations, and other machine-specific
runtime state were deliberately not merged.

### User memory

The Acer memory states:

> User prefers communicating in Romanian.

The Mac did not previously have `memories/USER.md`, so this file was copied
without conflict. A live Hermes prompt confirmed that the memory is loaded.

`SOUL.md` was identical on both machines, so the Mac copy was retained.

### Skills added

The following 12 skills existed only on the Acer before migration and were
copied to the Mac:

1. `computer-use`
2. `data-science/jupyter-live-kernel`
3. `dogfood`
4. `hermes-desktop-plugins`
5. `media/heartmula`
6. `mlops/evaluation/lm-evaluation-harness`
7. `mlops/inference/vllm`
8. `mlops/models/audiocraft`
9. `mlops/models/segment-anything`
10. `productivity/petdex`
11. `productivity/supabase-photo-log`
12. `yuanbao`

After migration, 74 skill paths are shared between the two installations:

- 44 have identical `SKILL.md` content;
- 30 have different content.

For all 30 shared-but-different skills, the Mac version was retained because
the Mac runs the newer Hermes release. The Acer variants remain recoverable
inside the preserved full backup.

The Mac also has seven skill paths absent from the Acer backup:

- `autonomous-ai-agents/computer-use`
- `mlops/evaluation/evaluating-llms-harness`
- `mlops/inference/serving-llms-vllm`
- `productivity/docx`
- `productivity/pdf`
- `productivity/xlsx`
- `software-development/dogfood`

Several of these are newer names or successors to similarly named Acer skills.
Both paths were retained to avoid deleting or silently replacing anything.

## Preserved but not activated

The full Acer backup contains additional machine-specific or sensitive state:

- provider and Telegram credentials;
- Google OAuth files;
- MCP/N8N installation files;
- cached documents and generated reports;
- Kanban and response-cache databases;
- logs, request dumps, and Windows/container helper files.

These were not copied into active macOS locations because doing so could
replace working credentials, introduce platform-incompatible binaries, or
reactivate stale jobs. They remain available in the protected source archive.

No backup, secret, database, session content, or user memory is committed to
Git. This repository contains only this redacted operational report.

## Backups and rollback

Local pre-migration backup:

```text
~/.hermes/backups/mac-before-acer-migration-20260731.zip
SHA-256: 703bac9bb915ede940279ed0fc128f3c71b6becd4b3665a93a12aee7d8c212f0
```

Preserved Acer source backup:

```text
~/.hermes/migrations/acer-20260731/acer-hermes-full-20260731.zip
SHA-256: c4f689fbc36be7e924c07d12f7f784f54d5dc95959f76f02005da9f876ee8d4d
```

Both archives are outside the repository. The Acer archive has mode `0600`
because it contains credentials and private conversation data.

Rollback must be intentional: stop the Hermes gateway and restore the local
pre-migration backup with the Hermes import command. Do not commit or share
either archive.

## Validation evidence

The following checks passed after migration:

- `hermes gateway status`: supervised by launchd;
- `hermes sessions stats`: 25 sessions and 567 messages;
- active skills discovered: 81;
- `PRAGMA integrity_check`: `ok`;
- `PRAGMA foreign_key_check`: no rows;
- Gemini memory smoke test: correctly reported Romanian as the preferred
  language;
- Telegram bot API: reachable;
- Telegram gateway: connected in polling mode.

## Remaining operational notes

- The Acer container remains independent and was not modified except for
  creating its official backup archive.
- The Mac is now the newer and more complete active Hermes installation.
- Windows-specific skills may still require macOS-compatible dependencies
  before every action described by those skills can run locally.
- The preserved archive should be treated like a password vault and included
  only in encrypted local backups.
