# STAnalyzer

STAnalyzer is a spatial transcriptomics analysis platform that combines an AI-assisted analysis backend, a web frontend, and a pluggable service manager for computational biology workflows.

This repository is organized as a monorepo so the frontend, main backend, and service management layer can be developed, deployed, and released together.

## What Is Included

- `textMSA`: FastAPI backend package for users, projects, files, agent workflows, knowledge retrieval, and service registration.
- `textMSA-frontend`: Vue 3 + Vite web application served under `/STAnalyzer/`.
- `system_server`: FastAPI service registry and analysis service manager.
- `system_server/services`: standalone analysis services used by `system_server`.

## Architecture

Runtime dependency direction:

```text
Browser
  |
  v
STAnalyzer frontend
  |
  v
STAnalyzer API
  |
  v
system_server
  |
  v
analysis services
```

The frontend sends API requests to `/STAnalyzer/api/*`. In production Docker deployment, Nginx rewrites those requests to the STAnalyzer backend at `/api/*`.

The backend uses MongoDB for application data and calls `system_server` to discover or register analysis services. `system_server` reads service metadata from `system_server/services_config.json` and the service folders under `system_server/services`.

## Directory Layout

```text
.
|-- docker-compose.yml
|-- scripts/
|   `-- deploy.sh
|-- textMSA/
|   |-- Dockerfile
|   |-- server/
|   `-- textmsa/
|-- textMSA-frontend/
|   |-- Dockerfile
|   |-- deploy/nginx.conf
|   `-- src/
`-- system_server/
    |-- Dockerfile
    |-- system_server/
    |-- services/
    `-- services_config.json
```

## One-Command Deployment

Prerequisites:

- Docker
- Docker Compose v2

Run:

```bash
cd /home/common/hwluo/project/STAnalyzer
bash scripts/deploy.sh
```

After startup:

- Frontend: `http://localhost:18080/STAnalyzer/`
- STAnalyzer API docs: `http://localhost:18000/docs`
- system_server API docs: `http://localhost:19000/docs`

Check service status:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f textmsa-api
docker compose logs -f system-server
docker compose logs -f frontend
```

Stop the stack:

```bash
docker compose down
```

Remove persistent volumes as well:

```bash
docker compose down -v
```

## Deployment Modes

The default deployment starts the core system:

- MongoDB
- `system_server`
- STAnalyzer API
- frontend Nginx

Analysis services are not auto-started by default because many of them have heavy scientific dependencies, large image builds, or external data requirements. The default keeps the platform bootable for development, documentation, and service catalog inspection.

To let `system_server` start services automatically, edit `.env`:

```dotenv
AUTO_START_SERVICES=true
SERVICE_RUN_MODE=docker
DOCKER_BUILD_ON_START=true
```

Then restart:

```bash
docker compose up -d --build
```

## Configuration

The deployment script creates `.env` from `.env.example` if it does not already exist.

Important root `.env` values:

```dotenv
FRONTEND_PORT=18080
TEXTMSA_API_PORT=18000
SYSTEM_SERVER_PORT=19000
MONGO_PORT=27018
AUTO_START_SERVICES=false
SERVICE_RUN_MODE=process
```

The backend reads JSON config from:

```text
textMSA/textmsa/config/config.docker.json
```

For a public release, replace placeholder model settings before enabling LLM-dependent features:

- `llm.api_key`
- `multimodal_llm.api_key`
- `reranker_llm.api_key`
- `codegen_llm.api_key`
- `server.jwt_secret_key`

The checked-in values are placeholders and are intended for bootstrapping only.

## Local Development

Frontend:

```bash
cd textMSA-frontend
npm install
npm run dev
```

Main backend:

```bash
cd textMSA
cp textmsa/config/config.example.json textmsa/config/config.json
pip install -r server/requirements.txt
python server/app.py
```

System server:

```bash
cd system_server
pip install -r requirements.txt
uvicorn system_server.main:app --host 0.0.0.0 --port 9000
```

Recommended startup order for local development:

1. MongoDB
2. `system_server`
3. STAnalyzer backend
4. `textMSA-frontend`

## API Surfaces

- STAnalyzer backend: `/api/user`, `/api/file`, `/api/analysis`, `/api/spatial`, `/api/service`, `/api/project`, `/api/agent`
- `system_server`: `/api/v1/services`, `/api/v1/services/{service_name}`, `/api/v1/services/{service_name}/start`, `/api/v1/services/{service_name}/stop`
- Frontend base path: `/STAnalyzer/`

## License

STAnalyzer code developed by the authors is released under the Apache License 2.0. See [`LICENSE`](LICENSE).

Bundled third-party components retain their original licenses and are not relicensed by this repository. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and the license files in the relevant component directories. Use of a hosted STAnalyzer service may also be subject to separate service-access terms and to the terms of third-party software, APIs, databases, LLM providers, and hosted model providers used during analysis.

## Open-Source Release Notes

This monorepo was prepared from three existing project directories. The original `.git` histories, runtime logs, generated outputs, local caches, virtual environments, and large local datasets were excluded.

The checked-in configuration uses placeholders only. Operators should configure deployment-specific credentials, review third-party software and data redistribution terms, and run secret scans before publishing deployment-specific configuration.
