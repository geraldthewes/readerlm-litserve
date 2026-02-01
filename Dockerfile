# =============================================================================
# ReaderLM LitServe Dockerfile
# Multi-stage build with NVIDIA GPU support for HTML to Markdown conversion
# =============================================================================
#
# Build: docker build -t readerlm-litserve .
# Run:   docker run --gpus all -p 8000:8000 readerlm-litserve
#
# =============================================================================

# -----------------------------------------------------------------------------
# Build stage: Install dependencies in a virtual environment
# -----------------------------------------------------------------------------
FROM docker.io/nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04 AS builder

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.12 and pip
# hadolint ignore=DL3008
RUN mkdir -p /var/cache/apt/archives/partial && \
    apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
# First install PyTorch with CUDA 12.8 support, then other dependencies
COPY requirements.txt /tmp/requirements.txt
# hadolint ignore=DL3013
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu128 && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# -----------------------------------------------------------------------------
# Runtime stage: Minimal image with application
# -----------------------------------------------------------------------------
FROM docker.io/nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04 AS runtime

# =============================================================================
# Environment Variables
# =============================================================================
# MODEL_NAME           - HuggingFace model path (default: jinaai/ReaderLM-v2)
# MODEL_REVISION       - Model version/commit (default: main)
# MODEL_DTYPE          - Model precision: auto, float16, bfloat16, float32 (default: auto)
# ATTN_IMPLEMENTATION  - Attention implementation: eager, sdpa, flash_attention_2 (default: eager)
# MAX_NEW_TOKENS       - Maximum tokens to generate (default: 1024)
# TEMPERATURE          - Sampling temperature, 0=deterministic (default: 0)
# REPETITION_PENALTY   - Penalty for repeated tokens (default: 1.08)
# SERVER_PORT          - Server listen port (default: 8000)
# URL_FETCH_TIMEOUT    - Timeout for URL fetching in seconds (default: 30)
# URL_FETCH_USER_AGENT - User-Agent header for URL requests (default: ReaderLM/1.0)
# BLOCK_PRIVATE_IPS    - Enable SSRF protection (default: true)
# ALLOWED_DOMAINS      - Comma-separated domain allowlist (default: empty=all)
# BLOCKED_DOMAINS      - Comma-separated domain blocklist (default: empty=none)
# =============================================================================

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.12 runtime only (no pip needed in runtime)
# hadolint ignore=DL3008
RUN mkdir -p /var/cache/apt/archives/partial && \
    apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security (handle existing GID/UID gracefully)
RUN groupadd --gid 1000 appuser 2>/dev/null || true && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser 2>/dev/null || \
    useradd --shell /bin/bash --create-home appuser

# Set working directory and ensure appuser owns it
WORKDIR /app
RUN chown appuser:appuser /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Ensure virtualenv binaries are in PATH
ENV PATH="/opt/venv/bin:$PATH"

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

# Set default environment variables for the application
ENV MODEL_NAME="jinaai/ReaderLM-v2" \
    MODEL_REVISION="main" \
    MODEL_DTYPE="auto" \
    ATTN_IMPLEMENTATION="eager" \
    MAX_NEW_TOKENS="1024" \
    TEMPERATURE="0" \
    REPETITION_PENALTY="1.08" \
    SERVER_PORT="8000" \
    URL_FETCH_TIMEOUT="30" \
    URL_FETCH_USER_AGENT="ReaderLM/1.0" \
    BLOCK_PRIVATE_IPS="true" \
    ALLOWED_DOMAINS="" \
    BLOCKED_DOMAINS=""

# Copy application code
COPY --chown=appuser:appuser server.py url_fetcher.py ./

# Switch to non-root user
USER appuser

# Expose the server port
EXPOSE 8000

# Health check - verify server is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl --fail http://localhost:${SERVER_PORT}/health || exit 1

# Run the server
ENTRYPOINT ["python3.12", "server.py"]
