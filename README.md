# HTML2Markdown LitServe

A fast, CPU-only HTML to Markdown conversion service built with [LitServe](https://github.com/Lightning-AI/LitServe). Converts raw HTML from the open web into clean Markdown using a multi-tier extraction pipeline.

## Architecture

The service uses a 3-tier fallback extraction chain for maximum reliability:

1. **Trafilatura** (primary) — Best F1 score (0.958), native markdown output
2. **readability-lxml + markdownify** (fallback) — Reliable article extraction
3. **lxml Cleaner + markdownify** (last resort) — Basic HTML cleaning

No GPU or ML model required. Sub-second response times for most pages.

## Project Structure

- `server.py`: LitServe web server with GET and POST endpoints.
- `html_extractor.py`: Multi-tier HTML to Markdown extraction pipeline.
- `url_fetcher.py`: URL fetching module with SSRF protection.
- `client.py`: Client for testing the service.
- `requirements.txt`: Python dependencies.
- `.env.template`: Template for environment variable configuration.
- `Dockerfile`: Multi-stage Docker build (CPU-only, ~300-500MB).
- `Makefile`: Build and deployment targets for Nomad cluster.
- `deploy/`: Nomad cluster deployment configuration.
  - `build.yaml`: JobForge build configuration.
  - `readerlm-litserve.nomad`: Nomad job specification.
- `tests/`: Unit and integration tests.

## Getting Started

### Option 1: Docker (Recommended)

```bash
# Build the Docker image
docker build -t html2markdown-litserve .

# Run the service
docker run -p 8000:8000 html2markdown-litserve

# Test the endpoint
curl http://localhost:8000/https://example.com
```

### Option 2: Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. (Optional) Configure environment variables:
   ```bash
   cp .env.template .env
   ```

3. Run the server:
   ```bash
   python server.py
   ```

4. Test with the client:
   ```bash
   python client.py
   ```

## Configuration

Copy `.env.template` to `.env` and modify as needed.

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_PORT` | `8000` | Port to run the server on |

### URL Fetching Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `URL_FETCH_TIMEOUT` | `30` | Timeout for fetching external URLs (seconds) |
| `URL_FETCH_USER_AGENT` | `ReaderLM/1.0` | User-Agent header for URL requests |
| `BLOCK_PRIVATE_IPS` | `true` | Enable SSRF protection (block private IPs) |
| `ALLOWED_DOMAINS` | `` (empty=all) | Comma-separated domain allowlist |
| `BLOCKED_DOMAINS` | `` (empty=none) | Comma-separated domain blocklist |

### Client Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_URL` | `http://127.0.0.1:8000` | Base URL of the server |
| `REQUEST_TIMEOUT` | `30` | Request timeout in seconds |

## API Reference

### GET /{url}

Fetches a URL and converts its HTML to Markdown ([Jina.ai](https://jina.ai/reader/)-style).

**Examples:**
```bash
# Fetch and convert a webpage
curl http://localhost:8000/https://example.com

# Fetch a Wikipedia article
curl http://localhost:8000/https://en.wikipedia.org/wiki/Markdown
```

**Responses:**
- **200:** Returns plain markdown text with `Content-Type: text/markdown`
- **400:** Invalid URL format (missing scheme, invalid URL)
- **403:** URL blocked by SSRF protection (private IP, blocked domain)
- **502:** Failed to fetch the URL (timeout, connection error, HTTP error)
- **500:** Conversion failed

### POST /predict

Converts HTML content to Markdown.

**Request:**
```json
{
  "html_content": "<html>...</html>",
  "source_url": "https://example.com"
}
```

The `source_url` field is optional and helps resolve relative links.

**Response:**
- **Success (200):** Returns plain markdown text with `Content-Type: text/markdown`
- **Bad Request (400):** Missing or invalid `html_content` field
- **Server Error (500):** Failed to extract content

**Example:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"html_content": "<h1>Hello World</h1><p>This is a test.</p>"}'
```

## Nomad Cluster Deployment

### Build and Deploy

```bash
# Build and push image to registry
make build

# Deploy to Nomad cluster
make deploy

# Restart to pick up new image
make restart

# Check status
make status

# View logs
make logs
```

### Access URLs

After deployment, the service is accessible via Fabio load balancer:

- **POST endpoint:** `http://fabio:9999/readerlm/predict`
- **GET endpoint:** `http://fabio:9999/readerlm/https://example.com`
- **Health check:** `http://fabio:9999/readerlm/health`

### Resource Requirements

| Resource | Value |
|----------|-------|
| CPU | 1000 MHz (1 core) |
| Memory | 4096 MB (4 GB) |
| GPU | None |
| Docker Image | ~300-500 MB |
| Startup Time | < 5 seconds |

## Development

### Running Tests

```bash
# Unit tests
make test-unit

# Integration tests (requires running service)
make test-integration

# All tests
make test
```

### Code Quality

```bash
# Linting
make lint

# Type checking
make typecheck

# Security scan
make security-scan
```

## License

This project is licensed under the [Apache-2.0 License](LICENSE).
