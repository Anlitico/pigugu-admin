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

## Structure

```
backend/   FastAPI — read-only CH queries + S3 presigned URL signing
web/       single-page console — filterable turn table, detail, wav playback
k8s/       Deployment (ClusterIP) + IRSA ServiceAccount
.github/workflows/deploy.yml — build ECR image on push; manual deploy
Dockerfile single-stage python:3.13-slim, deps from pyproject via tomllib
```

## Local dev

Requires a reachable ClickHouse. From the cluster:

```sh
kubectl port-forward svc/clickhouse 9000:9000          # asynch native protocol
kubectl get secret clickhouse-password \
  -o jsonpath='{.data.password}' | base64 -d           # → backend/.env
```

```sh
cd backend
cp ../.env.example .env    # fill CLICKHOUSE_PASSWORD, AUDIO_S3_BUCKET
uv sync
uv run uvicorn main:app --port 8000
# open http://127.0.0.1:8000
```

Config is env-driven (`core/config.py`); `.env` lives in `backend/.env`
(gitignored) or `../.env`.

## Endpoints

- `GET /api/health` — liveness + ClickHouse probe
- `GET /api/turns` — list, filters: `device_id`, `user_id`, `session_id`,
  `turn_type`, `stt_status`, `tts_status`, `q` (substring on STT/TTS text),
  `start_ms`/`end_ms`, `limit` (≤200), `offset`
- `GET /api/turns/{turn_id}` — full row incl. `stt_interims[]`, `abandoned_stts[]`
- `GET /api/turns/{turn_id}/audio/{input|tts}` — presigned S3 URL

## Deploy

1. Create the ECR repo `pigugu-admin` and set the repo-level GH Actions
   secrets `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (same as
   pigugu-server).
2. Fill `<ROLE-ARN>` in `k8s/sa-pigugu-admin.yaml` with a
   `s3:GetObject`-on-audio-bucket role (see comments in that file).
3. `push` to `main` builds + pushes the ECR image; `workflow_dispatch`
   with an `image_tag` deploys it.

To view locally from the cluster without a LoadBalancer:

```sh
kubectl port-forward svc/pigugu-admin 8000:80
```

## Notes / deferrals

- **No auth yet** — the console is ClusterIP-only; human auth via
  OIDC/SSO is a follow-up.
- **Read-only CH user** — currently uses `default` (write-capable);
  a SELECT-only user is planned.
