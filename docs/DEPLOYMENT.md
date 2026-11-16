# Deployment, monitoring and backups

> **Status: not executed.** The Terraform in `infrastructure/acs_deployment.tf`
> and the Compose file have not been applied or run by the authors of this
> change. No cloud resources were created, no Docker image was built, and
> `terraform fmt`/`validate` were not run because Terraform is not installed in
> the development sandbox. Treat everything here as reviewed but untested
> configuration, and run `terraform plan` before `apply`.

## What gets deployed

| Piece | Local (Compose) | Alibaba Cloud (Terraform) |
|---|---|---|
| API (`uvicorn`) | `backend` service | container `memoria-backend` on ECS |
| Celery worker and beat | `worker`, `beat` | containers `memoria-worker`, `memoria-beat` |
| PostgreSQL 16 + pgvector | `db` service, `pgdata` volume | ApsaraDB RDS for PostgreSQL |
| Redis 7 | `redis` service, `redisdata` volume | ApsaraDB for Redis |

## Configuration and secrets

- All settings are environment variables (see `.env.example`). Never commit a
  real `.env`.
- **Production mode.** Set `ENVIRONMENT=production`. The backend then refuses to
  start with the default `SECRET_KEY` or one shorter than 32 characters, and the
  legacy `X-API-Token` guard is off by default.
- **Compose.** `SECRET_KEY`, `ENVIRONMENT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
  and all `LLM_*` / `DASHSCOPE_*` values are read from the shell or the root
  `.env`. The defaults (`pass`, `change-me-in-production`) are for local dev
  only. Postgres and Redis publish ports on `127.0.0.1` only.
- **Terraform.** `random_password` generates the database password, the Redis
  password and `SECRET_KEY`. `llm_api_key` and `dashscope_api_key` are
  `sensitive` variables with no default. Pass them with
  `TF_VAR_llm_api_key=...` in the environment, not on the command line or in a
  committed `.tfvars` file. `admin_cidr` (SSH) has no default, so you must name
  your own address range.
- **Where secrets still end up.** Terraform state contains the generated
  passwords and the provider keys in plain text, and the ECS `user_data` holds
  them too (written on the host to `/etc/memoria.env`, mode 600). Use an
  encrypted remote backend (for example OSS with server-side encryption and
  restricted access) for state, and restrict who can read instance metadata.
  For stricter setups, move the keys to Alibaba Cloud KMS or Secrets Manager
  and fetch them at boot.
- **Rotation.** To rotate `SECRET_KEY`, change it and restart the API. All
  issued access tokens become invalid and users log in again. To rotate a
  provider key, update the variable (or `/etc/memoria.env`) and recreate the
  containers.

## Switching the LLM provider

Memoria uses one provider at a time, chosen by environment variables
(details in [LLM_PROVIDERS.md](LLM_PROVIDERS.md)).

1. Set `LLM_BASE_URL` (for example `https://api.openai.com/v1`),
   `LLM_API_KEY`, `LLM_CHAT_MODEL` and `LLM_EMBEDDING_MODEL`. Leave
   `LLM_BASE_URL` empty to go back to DashScope.
2. **Check the embedding size.** `EMBEDDING_DIM` must equal the pgvector column
   size (1024 by default) and the new model must produce that size. The API
   checks this at startup and fails fast on a mismatch. A different model with
   the same size still changes the vector space, so existing memories will be
   retrieved poorly until re-embedded. See [EMBEDDINGS.md](EMBEDDINGS.md).
3. Compose: edit `.env`, then `docker compose up -d` (recreates containers with
   new values). Terraform: set `llm_base_url`, `llm_chat_model`,
   `llm_embedding_model` and `TF_VAR_llm_api_key`, then `terraform apply`. The
   instance's `user_data` change replaces or reboots the ECS instance depending
   on provider behavior, so read the plan first.
4. Image, video and voice generation still need DashScope credentials.
5. Confirm with `GET /health/ready` and one chat request.

## Health and metrics

| Endpoint | Purpose | Success | Failure |
|---|---|---|---|
| `GET /health` | Liveness. No dependencies touched. | 200 | process down |
| `GET /health/ready` | Readiness. Runs `SELECT 1` on Postgres and `PING` on Redis, each with a 3 second timeout. | 200 `{"status":"ready"}` | 503 `{"status":"unavailable","checks":{"database":"error",...}}` |
| `GET /metrics` | Prometheus text format. Needs `Authorization: Bearer <METRICS_TOKEN>`. | 200 | 401 wrong token, 403 no `METRICS_TOKEN` set |

The 503 body names the failing dependency but never includes the error text,
hostnames or connection strings.

`/metrics` exposes `memoria_http_requests_total{method,path,status}`,
`memoria_http_request_duration_seconds_sum/_count{method,path}` and
`memoria_uptime_seconds`. Paths are route templates, so labels stay bounded.
Counters live in process memory and reset on restart. If you run more than one
uvicorn worker process, scrape each instance. `/metrics` requires a bearer
token. Set `METRICS_TOKEN` (compose reads it from `.env`, Terraform from the
sensitive `metrics_token` variable, written to `/etc/memoria.env`). Outside
`ENVIRONMENT=dev`, an unset token makes `/metrics` return 403 and a wrong token
returns 401. The token does not replace network controls: also restrict the
path at your reverse proxy or security group to the Prometheus host.

Compose health checks: `db` (`pg_isready`), `redis` (`redis-cli ping`),
`backend` (`/health/ready`) and `worker` (`celery inspect ping`). Use
`/health/ready` for load balancer or orchestrator readiness and `/health` for
liveness, so a Redis outage takes the node out of rotation without restarting
it.

### Suggested Prometheus config and alerts

```yaml
scrape_configs:
  - job_name: memoria
    metrics_path: /metrics
    authorization:
      type: Bearer
      credentials: <METRICS_TOKEN>   # or use credentials_file
    static_configs:
      - targets: ["memoria-app:8000"]
  - job_name: memoria-ready
    # Requires the blackbox exporter; probes /health/ready for 200.
    metrics_path: /probe
    params: { module: [http_2xx] }
    static_configs:
      - targets: ["http://memoria-app:8000/health/ready"]
```

| Alert | Condition (starting point) |
|---|---|
| API down | `up{job="memoria"} == 0` for 2m |
| Not ready | blackbox `probe_success{job="memoria-ready"} == 0` for 2m |
| 5xx rate | `sum(rate(memoria_http_requests_total{status=~"5.."}[5m])) / sum(rate(memoria_http_requests_total[5m])) > 0.05` for 10m |
| Slow chat | `rate(memoria_http_request_duration_seconds_sum{path="/chat/stream"}[5m]) / rate(memoria_http_request_duration_seconds_count{path="/chat/stream"}[5m]) > 30` for 10m |
| Worker silent | no `Task ... succeeded` log lines from `memoria-worker` for 36h (decay runs daily at 03:00 UTC) |

On Alibaba Cloud you can use CloudMonitor for ECS CPU, memory and disk, RDS
connections and storage, and Redis memory and evictions, with the same
thresholds idea (for example RDS storage above 80%, Redis memory above 80%).

Logs go to stdout. Collect them with `docker logs` or the Alibaba Cloud Log
Service agent.

## Backups and restore

Postgres holds all durable state (memories, chats, users). Back it up with both
managed snapshots and logical dumps.

**Managed snapshots (ApsaraDB RDS).** Terraform sets
`backup_retention_period = 7` and a nightly window. Take a manual backup before
every migration or provider/embedding change. Restoring creates a new instance
or clones to a point in time from the console or API. After a restore, point
`DATABASE_URL` at the new instance and restart the containers.

**Logical dumps with `pg_dump`.** Use the custom format so you can restore
selectively:

```bash
# Backup (run where the DB is reachable; password via PGPASSWORD or ~/.pgpass)
pg_dump --format=custom --no-owner --file="memoria-$(date +%F).dump" \
  "postgresql://USER@HOST:5432/memoria"

# Compose equivalent
docker compose exec -T db pg_dump -U "$POSTGRES_USER" --format=custom memoria \
  > "memoria-$(date +%F).dump"
```

Restore into an empty database that has the extension available:

```bash
createdb -h HOST -U USER memoria_restore
psql -h HOST -U USER -d memoria_restore -c 'CREATE EXTENSION IF NOT EXISTS vector;'
pg_restore --no-owner --dbname=memoria_restore --exit-on-error memoria-YYYY-MM-DD.dump
```

Then run `alembic upgrade head` from `backend/` and check `GET /health/ready`.
Store dumps off the host (an encrypted OSS bucket with lifecycle rules), keep at
least 7 daily and 4 weekly copies, and **test a restore regularly**. A backup
that was never restored is unverified. Never use `docker compose down -v`, which
deletes the `pgdata` volume.

**Local Compose volume snapshot.** Stop the stack, then archive the volume:
`docker run --rm -v memoria_pgdata:/d -v "$PWD":/b alpine tar czf /b/pgdata.tgz -C /d .`
(the volume name is prefixed with your Compose project name). Prefer `pg_dump`
for anything you care about, since a file copy of a running database is not
consistent.

### Redis notes

- Redis holds ephemeral data: Celery broker queues, rate-limit and daily token
  counters, and session state. Losing it does not lose memories.
- Compose runs Redis with `--appendonly yes` and `--save 60 1` so queued tasks
  survive a restart. ApsaraDB Redis has its own persistence and backup; keep it
  enabled and use the daily backup plus a manual one before upgrades.
- Set a password (Terraform does) and keep Redis inside the VPC. Never publish
  6379 publicly.
- After a Redis loss: queued Celery tasks are gone, rate-limit counters reset,
  and the daily token cap restarts from zero. Beat will re-enqueue the scheduled
  decay and consolidation jobs on its next schedule.
- Watch memory use and set a `maxmemory` policy on self-hosted instances so the
  broker is not evicted unexpectedly (`noeviction` is the safe choice for a
  broker).

## Network exposure checklist

- Set `admin_cidr` to your own `/32`. Do not use `0.0.0.0/0` for SSH.
- Terminate TLS in front of port 8000 (SLB, or Caddy/Nginx on the host) and
  narrow `app_ingress_cidr` to the proxy if possible. The API is plain HTTP.
- CORS is currently open (`*`) in `app/main.py`. Restrict it before a public
  launch.
- Set `METRICS_TOKEN` and block `/metrics` from the public internet.
- RDS `security_ips` and Redis are limited to the VPC CIDR.

## Known gaps

- Single ECS instance and single-zone managed services, no autoscaling.
- Per-process metrics only, no tracing.
- The deployment path (Terraform, `user_data`, container start-up) is
  unexercised. Expect to fix small provider-version or image-registry issues on
  first apply.
