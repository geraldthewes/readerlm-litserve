# Import necessary libraries
import logging
import os
import re

import httpx
import litserve as ls
import torch
from dotenv import load_dotenv
from fastapi import HTTPException, Request
from starlette.responses import Response
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from html_preprocessor import preprocess_html
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
# Attention implementation: eager, sdpa, flash_attention_2
# Use "eager" for better compatibility with float16 on older GPUs
ATTN_IMPLEMENTATION = os.getenv("ATTN_IMPLEMENTATION", "eager")
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "1024"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))
REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", "1.08"))
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# Quantization configuration (VRAM optimization)
QUANTIZATION_MODE = os.getenv("QUANTIZATION_MODE", "none")  # none, 4bit, 8bit
QUANTIZATION_TYPE = os.getenv("QUANTIZATION_TYPE", "nf4")  # nf4, fp4 (for 4bit only)
USE_DOUBLE_QUANT = os.getenv("USE_DOUBLE_QUANT", "true").lower() == "true"

# Preprocessing configuration
USE_READABILITY = os.getenv("USE_READABILITY", "true").lower() == "true"
MAX_INPUT_TOKENS = int(os.getenv("MAX_INPUT_TOKENS", "8000"))
ENABLE_CHUNKING = os.getenv("ENABLE_CHUNKING", "true").lower() == "true"

# HTML cleaning patterns for ReaderLM-v2
SCRIPT_PATTERN = r"<[ ]*script.*?\/[ ]*script[ ]*>"
STYLE_PATTERN = r"<[ ]*style.*?\/[ ]*style[ ]*>"
META_PATTERN = r"<[ ]*meta.*?>"
COMMENT_PATTERN = r"<[ ]*!--.*?--[ ]*>"
LINK_PATTERN = r"<[ ]*link.*?>"


def get_quantization_config() -> BitsAndBytesConfig | None:
    """Create BitsAndBytesConfig based on environment variables.

    Returns:
        BitsAndBytesConfig for 4-bit or 8-bit quantization, or None if disabled.
    """
    if QUANTIZATION_MODE == "none":
        return None

    if QUANTIZATION_MODE == "4bit":
        logger.info(
            "Configuring 4-bit quantization: type=%s, double_quant=%s",
            QUANTIZATION_TYPE,
            USE_DOUBLE_QUANT,
        )
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=QUANTIZATION_TYPE,
            bnb_4bit_use_double_quant=USE_DOUBLE_QUANT,
            bnb_4bit_compute_dtype=torch.float16,
        )

    if QUANTIZATION_MODE == "8bit":
        logger.info("Configuring 8-bit quantization")
        return BitsAndBytesConfig(
            load_in_8bit=True,
        )

    logger.warning("Unknown quantization mode '%s', disabling quantization", QUANTIZATION_MODE)
    return None


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
        logger.info("Configured dtype: %s, attn_implementation: %s", MODEL_DTYPE, ATTN_IMPLEMENTATION)

        # Get quantization configuration
        quantization_config = get_quantization_config()

        try:
            model_kwargs: dict = {
                "revision": MODEL_REVISION,
                "trust_remote_code": True,
                "torch_dtype": torch_dtype,
                "attn_implementation": ATTN_IMPLEMENTATION,
            }

            if quantization_config:
                # Quantization handles device placement automatically
                model_kwargs["quantization_config"] = quantization_config
                model_kwargs["device_map"] = "auto"
                self.model = AutoModelForCausalLM.from_pretrained(  # nosec B615
                    MODEL_NAME, **model_kwargs
                ).eval()
                logger.info("Model loaded with %s quantization", QUANTIZATION_MODE)
            else:
                # Standard loading with explicit device placement
                self.model = (
                    AutoModelForCausalLM.from_pretrained(  # nosec B615
                        MODEL_NAME, **model_kwargs
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

    def predict(self, html_content: str) -> list[torch.Tensor]:
        """
        Generates a response based on the provided HTML content using the model.

        Args:
            html_content: The HTML content to convert to markdown

        Returns:
            List of generated token tensors from the model (one per chunk)
        """
        logger.info("Starting prediction")

        # Preprocess HTML: extract main content and chunk if needed
        html_chunks = preprocess_html(
            html_content,
            use_readability=USE_READABILITY,
            max_tokens=MAX_INPUT_TOKENS,
            enable_chunking=ENABLE_CHUNKING,
            tokenizer=self.tokenizer,
        )

        logger.info("Processing %d chunk(s)", len(html_chunks))

        outputs: list[torch.Tensor] = []

        for i, chunk in enumerate(html_chunks):
            logger.debug("Processing chunk %d/%d", i + 1, len(html_chunks))

            # Apply basic HTML cleaning (regex-based) after preprocessing
            cleaned_html = clean_html(chunk)

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

            logger.debug("Chunk %d input tokens: %d", i + 1, inputs.input_ids.shape[1])

            # Generate a response from the model (deterministic for ReaderLM-v2)
            with torch.no_grad():
                output = self.model.generate(
                    input_ids=inputs.input_ids,
                    attention_mask=inputs.attention_mask,
                    max_new_tokens=MAX_NEW_TOKENS,
                    do_sample=False,
                    repetition_penalty=REPETITION_PENALTY,
                )

            logger.debug("Chunk %d output tokens: %d", i + 1, output.shape[1])
            outputs.append(output)

        logger.info("Prediction completed for %d chunk(s)", len(outputs))
        return outputs

    def encode_response(self, outputs: list[torch.Tensor]) -> Response:
        """
        Encodes the given results into a plain markdown response.

        Args:
            outputs: List of generated tensors from the model (one per chunk)

        Returns:
            Response with text/markdown content type

        Raises:
            HTTPException: If no response could be generated (status 500)
        """
        logger.debug("Encoding response for %d output(s)", len(outputs))

        markdown_parts: list[str] = []
        pattern = r"<\|im_start\|>assistant(.*?)<\|im_end\|>"

        for i, output in enumerate(outputs):
            decoded_text = self.tokenizer.decode(output[0])
            matches = re.findall(pattern, decoded_text, re.DOTALL)

            if not matches:
                logger.warning("No assistant response found in chunk %d output", i + 1)
                continue

            markdown_parts.append(matches[0].strip())

        if not markdown_parts:
            logger.warning("No assistant response found in any model output")
            raise HTTPException(
                status_code=500,
                detail="No response generated"
            )

        # Join multiple chunks with separator
        if len(markdown_parts) > 1:
            markdown_text = "\n\n---\n\n".join(markdown_parts)
            logger.info("Combined %d chunks into response, total length: %d", len(markdown_parts), len(markdown_text))
        else:
            markdown_text = markdown_parts[0]
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

        # Route through LitServe's /predict endpoint internally
        # This ensures the request goes through workers where setup() has been called
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://localhost:{SERVER_PORT}/predict",
                    json={"html_content": html_content},
                    timeout=300.0,
                )
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    media_type=response.headers.get("content-type", "text/markdown"),
                )
        except httpx.TimeoutException:
            logger.error("Timeout during internal predict request for URL: %s", url)
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
