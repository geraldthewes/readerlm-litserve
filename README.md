# ReaderLM LitServe

[![Open In Studio](https://pl-bolts-doc-images.s3.us-east-2.amazonaws.com/app-2/studio-badge.svg)](https://lightning.ai/sitammeur/studios/readerlm-litserve)

[Jina.ai](https://jina.ai/) has introduced [ReaderLM-v2](https://huggingface.co/jinaai/ReaderLM-v2), a specialized small language model inspired by "Jina Reader" designed for converting raw, noisy HTML from the open web into clean markdown. ReaderLM-v2 features improved markdown generation, supports longer contexts (512K tokens), and outperforms larger LLMs in this specific task, offering a cost-effective and multilingual solution. This project demonstrates the use of the ReaderLM-v2 model for converting HTML content to Markdown content served using LitServe, an easy-to-use, flexible serving engine for AI models built on FastAPI.

## Project Structure

The project is structured as follows:

- `server.py`: The file containing the main code for the web server.
- `url_fetcher.py`: URL fetching module with SSRF protection for the GET endpoint.
- `client.py`: The file containing the code for client-side requests.
- `requirements.txt`: Python dependencies with pinned versions.
- `.env.template`: Template for environment variable configuration.
- `Dockerfile`: Multi-stage Docker build with NVIDIA GPU support.
- `Makefile`: Build and deployment targets for Nomad cluster.
- `deploy/`: Nomad cluster deployment configuration.
  - `build.yaml`: JobForge build configuration.
  - `readerlm-litserve.nomad`: Nomad job specification.
- `LICENSE`: The license file for the project.
- `README.md`: The README file that contains information about the project.
- `assets`: The folder containing screenshots for working on the application.
- `tests/`: Unit tests for the project.
- `.gitignore`: The file containing the list of files and directories to be ignored by Git.

## Tech Stack

- Python (for the programming language)
- PyTorch (for the deep learning framework)
- Hugging Face Transformers Library (for the model)
- LitServe (for the serving engine)

## Getting Started

### Option 1: Docker (Recommended)

The easiest way to run the service is using Docker with NVIDIA GPU support.

**Prerequisites:**
- Docker with NVIDIA Container Toolkit installed
- NVIDIA GPU with CUDA support

**Build and Run:**

```bash
# Build the Docker image
docker build -t readerlm-litserve .

# Run with GPU support
docker run --gpus all -p 8000:8000 readerlm-litserve

# Run with custom environment variables
docker run --gpus all -p 8000:8000 \
  -e MAX_NEW_TOKENS=2048 \
  -e TEMPERATURE=0.1 \
  readerlm-litserve
```

**Verify GPU is accessible:**
```bash
docker run --gpus all --rm readerlm-litserve nvidia-smi
```

**Test the endpoint:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"html_content": "<html><body><h1>Test</h1></body></html>"}'
```

### Option 2: Local Development

To run locally without Docker:

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. (Optional) Configure environment variables:
   ```bash
   cp .env.template .env
   # Edit .env to customize settings
   ```

3. Run the server:
   ```bash
   python server.py
   ```

4. Upon running the server successfully, you will see uvicorn running on port 8000.

5. Open a new terminal window and run the client:
   ```bash
   python client.py
   ```

Now, you can see the model output based on the HTML content. The model will convert the HTML content to Markdown content.

## Configuration

The server and client can be configured using environment variables. Copy `.env.template` to `.env` and modify as needed.

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `jinaai/ReaderLM-v2` | Hugging Face model name or path |
| `MODEL_REVISION` | `main` | Model revision (commit hash, tag, or branch) |
| `MAX_NEW_TOKENS` | `1024` | Maximum tokens to generate |
| `TEMPERATURE` | `0` | Sampling temperature (0 = deterministic) |
| `REPETITION_PENALTY` | `1.08` | Penalty for repeated tokens |
| `SERVER_PORT` | `8000` | Port to run the server on |

### Client Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_URL` | `http://127.0.0.1:8000` | Base URL of the server |
| `REQUEST_TIMEOUT` | `120` | Request timeout in seconds |

### URL Fetching Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `URL_FETCH_TIMEOUT` | `30` | Timeout for fetching external URLs (seconds) |
| `URL_FETCH_USER_AGENT` | `ReaderLM/1.0` | User-Agent header for URL requests |
| `BLOCK_PRIVATE_IPS` | `true` | Enable SSRF protection (block private IPs) |
| `ALLOWED_DOMAINS` | `` (empty=all) | Comma-separated domain allowlist |
| `BLOCKED_DOMAINS` | `` (empty=none) | Comma-separated domain blocklist |

## API Reference

### GET /{url}

Fetches a URL and converts its HTML to Markdown ([Jina.ai](https://jina.ai/reader/)-style).

This endpoint mimics Jina.ai's reader API pattern, allowing you to fetch and convert any webpage to markdown by simply prepending the server URL.

**Examples:**
```bash
# Fetch and convert a webpage
curl http://localhost:8000/https://example.com

# Fetch a specific page
curl http://localhost:8000/https://news.ycombinator.com/item?id=12345

# URL-encoded (alternative)
curl "http://localhost:8000/https%3A%2F%2Fexample.com"
```

**Responses:**
- **200:** Returns plain markdown text with `Content-Type: text/markdown`
- **400:** Invalid URL format (missing scheme, invalid URL)
- **403:** URL blocked by SSRF protection (private IP, blocked domain)
- **502:** Failed to fetch the URL (timeout, connection error, HTTP error)
- **500:** Conversion failed (model inference error)

### POST /predict

Converts HTML content to Markdown.

**Request:**
```json
{
  "html_content": "<html>...</html>"
}
```

**Response:**
- **Success (200):** Returns plain markdown text with `Content-Type: text/markdown`
- **Bad Request (400):** Missing or invalid `html_content` field
- **Server Error (500):** Failed to generate response

**Example:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"html_content": "<h1>Hello World</h1><p>This is a test.</p>"}'
```

## Nomad Cluster Deployment

The service can be deployed to a Nomad cluster using JobForge for image building.

### Prerequisites

- Access to the Nomad cluster with GPU-capable nodes
- JobForge CLI installed and configured
- Git repository pushed to origin

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

### Verification

```bash
# Check job status
nomad job status readerlm-litserve

# Check service registration
consul catalog services | grep readerlm

# Test health endpoint
curl http://fabio:9999/readerlm/health

# Test POST endpoint
curl -X POST http://fabio:9999/readerlm/predict \
  -H "Content-Type: application/json" \
  -d '{"html_content": "<h1>Test</h1><p>Hello world</p>"}'

# Test GET endpoint
curl http://fabio:9999/readerlm/https://example.com
```

### Resource Configuration

| Resource | Value |
|----------|-------|
| CPU | 2000 MHz (2 cores) |
| Memory | 16384 MB (16 GB) |
| GPU | Required (NVIDIA) |
| Shared Memory | 2 GB |

## Usage

The project can be used to serve the ReaderLM-v2 model using LitServe. Here, the model is used to convert HTML content to Markdown content. This suggests potential applications in web scraping, content repurposing, and accessibility improvements.

## Contributing

Contributions are welcome! If you would like to contribute to this project, please raise an issue to discuss the changes you want to make. Once the changes are approved, you can create a pull request.

## License

This project is licensed under the [Apache-2.0 License](LICENSE).

## Contact

If you have any questions or suggestions about the project, please contact me on my GitHub profile.

Happy coding! 🚀
