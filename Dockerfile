# =============================================================================
# HTML2Markdown LitServe Dockerfile
# CPU-only multi-stage build for HTML to Markdown conversion
# =============================================================================
#
# Build: docker build -t html2markdown-litserve .
# Run:   docker run -p 8000:8000 html2markdown-litserve
#
# =============================================================================

# -----------------------------------------------------------------------------
# Build stage: Install dependencies in a virtual environment
# -----------------------------------------------------------------------------
FROM docker.io/python:3.12-slim AS builder

# Install build dependencies for lxml
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
# hadolint ignore=DL3013
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# -----------------------------------------------------------------------------
# Runtime stage: Minimal image with application
# -----------------------------------------------------------------------------
FROM docker.io/python:3.12-slim AS runtime

# =============================================================================
# Environment Variables
# =============================================================================
# SERVER_PORT          - Server listen port (default: 8000)
# URL_FETCH_TIMEOUT    - Timeout for URL fetching in seconds (default: 30)
# URL_FETCH_USER_AGENT - User-Agent header for URL requests (default: ReaderLM/1.0)
# BLOCK_PRIVATE_IPS    - Enable SSRF protection (default: true)
# ALLOWED_DOMAINS      - Comma-separated domain allowlist (default: empty=all)
# BLOCKED_DOMAINS      - Comma-separated domain blocklist (default: empty=none)
# =============================================================================

# Install runtime dependencies for lxml
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user with UID 1000 to match cluster volume permissions
# Delete any existing user/group with UID/GID 1000, then create appuser
RUN (getent group 1000 | cut -d: -f1 | xargs -r groupdel) 2>/dev/null || true && \
    (getent passwd 1000 | cut -d: -f1 | xargs -r userdel) 2>/dev/null || true && \
    groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser

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
ENV SERVER_PORT="8000" \
    URL_FETCH_TIMEOUT="30" \
    URL_FETCH_USER_AGENT="ReaderLM/1.0" \
    BLOCK_PRIVATE_IPS="true" \
    ALLOWED_DOMAINS="" \
    BLOCKED_DOMAINS=""

# Copy application code
COPY --chown=appuser:appuser server.py url_fetcher.py html_extractor.py ./

# Switch to non-root user
USER appuser

# Expose the server port
EXPOSE 8000

# Health check - verify server is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl --fail http://localhost:${SERVER_PORT}/health || exit 1

# Run the server
ENTRYPOINT ["python3", "server.py"]
