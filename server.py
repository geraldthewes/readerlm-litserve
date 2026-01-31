# Import necessary libraries
import logging
import os
import re

import litserve as ls
import torch
from dotenv import load_dotenv
from transformers import AutoModelForCausalLM, AutoTokenizer

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration from environment variables with defaults
MODEL_NAME = os.getenv("MODEL_NAME", "jinaai/reader-lm-1.5b")
MODEL_REVISION = os.getenv("MODEL_REVISION", "main")
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "1024"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", "1.08"))
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))


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

        try:
            self.model = (
                AutoModelForCausalLM.from_pretrained(  # nosec B615
                    MODEL_NAME, revision=MODEL_REVISION, trust_remote_code=True
                )
                .eval()
                .to(device)
            )
            self.tokenizer = AutoTokenizer.from_pretrained(  # nosec B615
                MODEL_NAME, revision=MODEL_REVISION, trust_remote_code=True
            )
            logger.info("Model loaded successfully")
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
            ValueError: If html_content is missing or invalid
        """
        logger.debug("Decoding request")

        try:
            html_content = request["html_content"]
        except KeyError:
            logger.error("Request missing required 'html_content' field")
            raise ValueError("Request must contain 'html_content' field")

        if not isinstance(html_content, str):
            logger.error("html_content is not a string: %s", type(html_content))
            raise ValueError("'html_content' must be a string")

        if not html_content.strip():
            logger.error("html_content is empty")
            raise ValueError("'html_content' cannot be empty")

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

        # Prepare the input for the model
        messages = [{"role": "user", "content": html_content}]
        input_text = self.tokenizer.apply_chat_template(messages, tokenize=False)
        inputs = self.tokenizer.encode(input_text, return_tensors="pt").to(self.device)

        logger.debug("Input tokens: %d", inputs.shape[1])

        # Generate a response from the model
        with torch.no_grad():
            output = self.model.generate(
                inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE,
                do_sample=True,
                repetition_penalty=REPETITION_PENALTY,
            )

        logger.info("Prediction completed, output tokens: %d", output.shape[1])
        return output

    def encode_response(self, outputs: torch.Tensor) -> dict:
        """
        Encodes the given results into a dictionary format.

        Args:
            outputs: Generated tensor from the model

        Returns:
            Dictionary with 'response' key containing the markdown text
        """
        logger.debug("Encoding response")

        decoded_text = self.tokenizer.decode(outputs[0])
        pattern = r"<\|im_start\|>assistant(.*?)<\|im_end\|>"
        matches = re.findall(pattern, decoded_text, re.DOTALL)

        if not matches:
            logger.warning("No assistant response found in model output")
            return {"response": "", "error": "No response generated"}

        response = matches[0].strip()
        logger.info("Response encoded, length: %d", len(response))
        return {"response": response}


if __name__ == "__main__":
    logger.info("Starting ReaderLM server on port %d", SERVER_PORT)
    logger.info("Configuration: model=%s, max_tokens=%d, temp=%.2f, rep_penalty=%.2f",
                MODEL_NAME, MAX_NEW_TOKENS, TEMPERATURE, REPETITION_PENALTY)

    api = ReaderLMAPI()
    server = ls.LitServer(api, track_requests=True)
    server.run(port=SERVER_PORT)
