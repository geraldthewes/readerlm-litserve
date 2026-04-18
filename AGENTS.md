# Agent Guidelines for readerlm-litserve

## Key Commands
- **Build & Deploy**: `make build && make deploy`
- **Restart Service**: `make restart`
- **View Logs**: `make logs`
- **Check Status**: `make status`
- **Run Tests**: `make test` (unit + integration)
- **Unit Tests Only**: `make test-unit`
- **Integration Tests**: `make test-integration` (requires running service)
- **Lint**: `make lint` (ruff)
- **Typecheck**: `make typecheck` (mypy)
- **Security Scan**: `make security-scan` (bandit)

## Architecture Notes
- Server entrypoint: `server.py` (LitServe web server)
- Extraction pipeline: `html_extractor.py` (3-tier fallback)
- URL fetching with SSRF protection: `url_fetcher.py`
- Client for testing: `client.py`
- Docker image: CPU-only, ~300-500MB
- Nomad deployment: `deploy/readerlm-litserve.nomad`
- Service accessible via Fabio: `http://fabio:9999/readerlm/`

## Testing Quirks
- Integration tests require service to be running first
- Unit tests: `tests/test_html_extractor.py` and `tests/test_url_fetcher.py`
- Integration test: `tests/integration_test.py`

## Environment
- Copy `.env.template` to `.env` for configuration
- Key vars: `SERVER_PORT`, `URL_FETCH_TIMEOUT`, `URL_FETCH_USER_AGENT`, `BLOCK_PRIVATE_IPS`, `ALLOWED_DOMAINS`, `BLOCKED_DOMAINS`
- Client uses `SERVER_URL` and `REQUEST_TIMEOUT`

## Deployment Flow
1. Push git changes: `git push origin` (done in `make build`)
2. Build via JobForge: `jobforge submit-job --image-tags "latest" --watch --history deploy/build.yaml`
3. Deploy to Nomad: `nomad job run deploy/readerlm-litserve.nomad`
4. Access via Fabio load balancer on port 9999