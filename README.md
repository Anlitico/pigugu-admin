# pigugu-admin

Internal admin console for Pigugu — query per-turn conversation logs and
play back audio. It is a **pure read-only consumer** of the turn-storage
system built in [pigugu-server](https://github.com/Anlitico/pigugu-server):
it reads ClickHouse and S3, never writes to either.

## What it reads

- **ClickHouse `voice.turns`** — per-turn metadata index: STT text, models,
  latencies, `voice_segments[]`, S3 object paths.
- **S3 `pigugu-clickhouse-audio`** — 5 files per turn:
  `{utc_date}/{session_id}/{turn_id}/{input.wav, input.json, tts.wav, tts.json, turn.json}`.

Authoritative layout and schema:
- Schema: `pigugu-server/clickhouse/migrations/0001_voice_turns.sql`
- Design: `pigugu-server/docs/clickhouse-audio-storage.md`

## Planned structure

```
backend/       FastAPI — read-only CH queries + S3 presigned URL signing
web/           frontend — conversation list → session timeline → wav playback
k8s/           Deployment + Service + IRSA ServiceAccount
.github/workflows/deploy.yml — build ECR image + apply manifests
```

## Planned dependencies

- Read-only ClickHouse user (SELECT on `voice.turns` only; not `default`)
- GetObject-only IRSA role for S3 (existing cluster, `pigugu-cluster`)
- Human auth via OIDC/SSO — not the device IoT mTLS path

## Status

Repository created. Implementation not started.
