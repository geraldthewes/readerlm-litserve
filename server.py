# Import necessary libraries
import asyncio
import logging
import os
import re

import litserve as ls
import torch
from dotenv import load_dotenv
from fastapi import HTTPException, Request
from starlette.responses import Response
from transformers import AutoModelForCausalLM, AutoTokenizer

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
MODEL_NAME = os.getenv("MODEL_NAME", "jinaai/ReaderLM-v2")
MODEL_REVISION = os.getenv("MODEL_REVISION", "main")
MODEL_DTYPE = os.getenv("MODEL_DTYPE", "auto")  # auto, float16, bfloat16, float32
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "1024"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))
REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", "1.08"))
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# HTML cleaning patterns for ReaderLM-v2
SCRIPT_PATTERN = r"<[ ]*script.*?\/[ ]*script[ ]*>"
STYLE_PATTERN = r"<[ ]*style.*?\/[ ]*style[ ]*>"
META_PATTERN = r"<[ ]*meta.*?>"
COMMENT_PATTERN = r"<[ ]*!--.*?--[ ]*>"
LINK_PATTERN = r"<[ ]*link.*?>"


def clean_html(html: str) -> str:
    """Remove script, style, meta, comment, and link tags from HTML."""
    html = re.sub(
        SCRIPT_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    html = re.sub(
        STYLE_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    html = re.sub(
        META_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    html = re.sub(
        COMMENT_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    html = re.sub(
        LINK_PATTERN, "", html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    return html


class ReaderLMAPI(ls.LitAPI):
    """
    ReaderLMAPI is a subclass of ls.LitAPI that provides methods for the HTML to Markdown conversion task.

    Methods:
        - setup(device): Initializes the model and tokenizer with the specified device.
        - decode_request(request): Extracts the HTML content from the incoming request.
        - predict(html_content): Generates a response based on the provided HTML content using the model.
        - encode_response(output): Encodes the generated response into a dictionary format.
    """

    def setup(self, device: str) -> None:
        """
        Sets up the model and tokenizer on the specified device.
        """
        logger.info("Loading model: %s", MODEL_NAME)
        logger.info("Using device: %s", device)

        # Determine torch dtype from configuration
        dtype_map: dict[str, str | torch.dtype] = {
            "auto": "auto",
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        torch_dtype = dtype_map.get(MODEL_DTYPE, "auto")
        logger.info("Configured dtype: %s", MODEL_DTYPE)

        try:
            self.model = (
                AutoModelForCausalLM.from_pretrained(  # nosec B615
                    MODEL_NAME,
                    revision=MODEL_REVISION,
                    trust_remote_code=True,
                    torch_dtype=torch_dtype,
                )
                .eval()
                .to(device)
            )
            self.tokenizer = AutoTokenizer.from_pretrained(  # nosec B615
                MODEL_NAME, revision=MODEL_REVISION, trust_remote_code=True
            )
            logger.info("Model loaded successfully with dtype: %s", self.model.dtype)
        except Exception as e:
            logger.exception("Failed to load model: %s", e)
            raise

    def decode_request(self, request: dict) -> str:
        """
        Decodes the input request to extract the HTML content.

        Args:
            request: Dictionary containing 'html_content' key

        Returns:
            The HTML content string

        Raises:
            HTTPException: If html_content is missing or invalid (status 400)
        """
        logger.debug("Decoding request")

        try:
            html_content = request["html_content"]
        except KeyError:
            logger.error("Request missing required 'html_content' field")
            raise HTTPException(
                status_code=400,
                detail="Request must contain 'html_content' field"
            )

        if not isinstance(html_content, str):
            logger.error("html_content is not a string: %s", type(html_content))
            raise HTTPException(
                status_code=400,
                detail="'html_content' must be a string"
            )

        if not html_content.strip():
            logger.error("html_content is empty")
            raise HTTPException(
                status_code=400,
                detail="'html_content' cannot be empty"
            )

        logger.info("Received HTML content of length: %d", len(html_content))
        return html_content

    def predict(self, html_content: str) -> torch.Tensor:
        """
        Generates a response based on the provided HTML content using the model.

        Args:
            html_content: The HTML content to convert to markdown

        Returns:
            Generated token tensor from the model
        """
        logger.info("Starting prediction")

        # Clean HTML and prepare prompt for ReaderLM-v2
        cleaned_html = clean_html(html_content)
        instruction = (
            "Extract the main content from the given HTML "
            "and convert it to Markdown format."
        )
        prompt = f"{instruction}\n```html\n{cleaned_html}\n```"

        # Prepare the input for the model
        messages = [{"role": "user", "content": prompt}]
        input_text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(input_text, return_tensors="pt").to(self.device)

        logger.debug("Input tokens: %d", inputs.input_ids.shape[1])

        # Generate a response from the model (deterministic for ReaderLM-v2)
        with torch.no_grad():
            output = self.model.generate(
                input_ids=inputs.input_ids,
                attention_mask=inputs.attention_mask,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                repetition_penalty=REPETITION_PENALTY,
            )

        logger.info("Prediction completed, output tokens: %d", output.shape[1])
        return output

    def encode_response(self, outputs: torch.Tensor) -> Response:
        """
        Encodes the given results into a plain markdown response.

        Args:
            outputs: Generated tensor from the model

        Returns:
            Response with text/markdown content type

        Raises:
            HTTPException: If no response could be generated (status 500)
        """
        logger.debug("Encoding response")

        decoded_text = self.tokenizer.decode(outputs[0])
        pattern = r"<\|im_start\|>assistant(.*?)<\|im_end\|>"
        matches = re.findall(pattern, decoded_text, re.DOTALL)

        if not matches:
            logger.warning("No assistant response found in model output")
            raise HTTPException(
                status_code=500,
                detail="No response generated"
            )

        markdown_text = matches[0].strip()
        logger.info("Response encoded, length: %d", len(markdown_text))
        return Response(content=markdown_text, media_type="text/markdown")


if __name__ == "__main__":
    logger.info("Starting ReaderLM server on port %d", SERVER_PORT)
    logger.info("Configuration: model=%s, max_tokens=%d, temp=%.2f, rep_penalty=%.2f",
                MODEL_NAME, MAX_NEW_TOKENS, TEMPERATURE, REPETITION_PENALTY)

    api = ReaderLMAPI()
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
                detail="URL must start with http:// or https://"
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

        # Run model inference in a thread to avoid blocking
        try:
            output = await asyncio.to_thread(api.predict, html_content)
            response = api.encode_response(output)
            return response
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Model inference failed: %s", e)
            raise HTTPException(
                status_code=500,
                detail="Failed to convert HTML to markdown"
            )

    server.run(port=SERVER_PORT)
