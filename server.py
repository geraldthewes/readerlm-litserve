# Import necessary libraries
import logging
import os

import httpx
import litserve as ls
from dotenv import load_dotenv
from fastapi import HTTPException, Request
from starlette.responses import Response

from html_extractor import ExtractionError, extract_to_markdown
from url_fetcher import (
    FetchError,
    SSRFBlockedError,
    URLValidationError,
    fetch_url,
)

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration from environment variables with defaults
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))


class HTML2MarkdownAPI(ls.LitAPI):
    """CPU-only HTML to Markdown conversion API.

    Uses a 3-tier extraction chain (Trafilatura → readability-lxml +
    markdownify → lxml Cleaner + markdownify) for reliable, fast conversion
    without requiring a GPU or ML model.

    Methods:
        - setup(device): Verifies extraction dependencies are available.
        - decode_request(request): Extracts HTML content from the incoming request.
        - predict(html_content): Converts HTML to markdown using extraction chain.
        - encode_response(output): Returns markdown as a plain text response.
    """

    def setup(self, device: str) -> None:
        """Verify extraction dependencies are available.

        Args:
            device: Device string (ignored, CPU-only).
        """
        logger.info("Initializing HTML2Markdown extraction pipeline")
        logger.info("Device parameter '%s' ignored (CPU-only extraction)", device)

        # Verify trafilatura is importable (primary extraction tier)
        try:
            import trafilatura  # noqa: F401

            logger.info("Trafilatura available (primary extraction tier)")
        except ImportError:
            logger.warning(
                "Trafilatura not installed — tier 1 extraction unavailable, "
                "will fall back to readability-lxml + markdownify"
            )

        logger.info("HTML2Markdown extraction pipeline ready")

    def decode_request(self, request: dict) -> dict:
        """Decode the input request to extract HTML content and optional URL.

        Args:
            request: Dictionary containing 'html_content' key and optional 'source_url'.

        Returns:
            Dictionary with 'html_content' and optional 'source_url'.

        Raises:
            HTTPException: If html_content is missing or invalid (status 400).
        """
        logger.debug("Decoding request")

        try:
            html_content = request["html_content"]
        except KeyError:
            logger.error("Request missing required 'html_content' field")
            raise HTTPException(
                status_code=400,
                detail="Request must contain 'html_content' field",
            )

        if not isinstance(html_content, str):
            logger.error("html_content is not a string: %s", type(html_content))
            raise HTTPException(
                status_code=400,
                detail="'html_content' must be a string",
            )

        if not html_content.strip():
            logger.error("html_content is empty")
            raise HTTPException(
                status_code=400,
                detail="'html_content' cannot be empty",
            )

        logger.info("Received HTML content of length: %d", len(html_content))

        return {
            "html_content": html_content,
            "source_url": request.get("source_url"),
        }

    def predict(self, request_data: dict) -> str:
        """Convert HTML content to Markdown using extraction chain.

        Args:
            request_data: Dictionary with 'html_content' and optional 'source_url'.

        Returns:
            Markdown string extracted from the HTML content.

        Raises:
            HTTPException: If extraction fails (status 500).
        """
        html_content = request_data["html_content"]
        source_url = request_data.get("source_url")

        logger.info("Starting extraction (HTML length: %d)", len(html_content))

        try:
            markdown = extract_to_markdown(html_content, url=source_url)
            logger.info("Extraction completed, markdown length: %d", len(markdown))
            return markdown
        except ExtractionError as e:
            logger.error("Extraction failed: %s", e)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to extract content: {e}",
            )

    def encode_response(self, output: str) -> Response:
        """Encode the markdown output as a plain text response.

        Args:
            output: Markdown string from extraction.

        Returns:
            Response with text/markdown content type.
        """
        logger.info("Response encoded, length: %d", len(output))
        return Response(content=output, media_type="text/markdown")


if __name__ == "__main__":
    logger.info("Starting HTML2Markdown server on port %d", SERVER_PORT)

    api = HTML2MarkdownAPI()
    server = ls.LitServer(api, track_requests=True)

    # Add Jina.ai-style GET endpoint for URL fetching
    @server.app.get("/{url:path}")
    async def fetch_and_convert(request: Request, url: str) -> Response:
        """Fetch a URL and convert its HTML to Markdown (Jina.ai-style).

        This endpoint mimics Jina.ai's reader API pattern, allowing users to
        fetch and convert any URL to markdown by accessing /{url}.

        Example: GET /https://example.com

        Args:
            request: FastAPI request object
            url: The full URL to fetch and convert

        Returns:
            Response with markdown content

        Raises:
            HTTPException: Various HTTP errors based on failure type
        """
        # Validate URL format - ensure it starts with http:// or https://
        if not url.startswith(("http://", "https://")):
            logger.warning("Invalid URL format (missing scheme): %s", url)
            raise HTTPException(
                status_code=400,
                detail="URL must start with http:// or https://",
            )

        logger.info("GET request for URL: %s", url)

        # Fetch HTML content
        try:
            html_content = await fetch_url(url)
        except URLValidationError as e:
            logger.warning("URL validation failed: %s", e)
            raise HTTPException(status_code=400, detail=str(e))
        except SSRFBlockedError as e:
            logger.warning("SSRF protection blocked request: %s", e)
            raise HTTPException(status_code=403, detail=str(e))
        except FetchError as e:
            logger.error("Failed to fetch URL: %s", e)
            raise HTTPException(status_code=502, detail=str(e))

        # Route through LitServe's /predict endpoint internally
        # This ensures the request goes through workers where setup() has been called
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://localhost:{SERVER_PORT}/predict",
                    json={"html_content": html_content, "source_url": url},
                    timeout=60.0,
                )
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    media_type=response.headers.get(
                        "content-type", "text/markdown"
                    ),
                )
        except httpx.TimeoutException:
            logger.error(
                "Timeout during internal predict request for URL: %s", url
            )
            raise HTTPException(
                status_code=504,
                detail="Request timed out during conversion",
            )
        except httpx.RequestError as e:
            logger.exception("Internal predict request failed: %s", e)
            raise HTTPException(
                status_code=500,
                detail="Failed to convert HTML to markdown",
            )

    server.run(port=SERVER_PORT)
