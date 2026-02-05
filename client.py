import logging
import os
import sys

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration from environment variables with defaults
SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))


def test_server(html_content: str) -> None:
    """
    Sends a POST request to the server with the given input html content and prints the server's response.

    Args:
        html_content: The html content to be sent to the server for prediction.

    Returns:
        None
    """
    url = f"{SERVER_URL}/predict"
    payload = {"html_content": html_content}

    logger.info("Sending request to %s", url)
    logger.debug("Payload size: %d bytes", len(html_content))

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("Request timed out after %d seconds", REQUEST_TIMEOUT)
        print(f"Error: Request timed out after {REQUEST_TIMEOUT} seconds")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to server at %s", SERVER_URL)
        print(f"Error: Could not connect to server at {SERVER_URL}")
        print("Make sure the server is running: python server.py")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        logger.error("HTTP error: %s", e)
        print(f"Error: Server returned error - {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        logger.error("Request failed: %s", e)
        print(f"Error: Request failed - {e}")
        sys.exit(1)

    markdown_content = response.text
    if not markdown_content:
        logger.warning("Server returned empty response")
        print("Warning: Server returned empty response")
        return

    logger.info("Received response of length: %d", len(markdown_content))

    # Display the response in a formatted markdown format
    console = Console()
    markdown = Markdown(markdown_content)
    console.print(markdown)


if __name__ == "__main__":
    # Sample input html content for testing. eg. "<html><body><h1>Hello, world!</h1></body></html>"
    html_content = """<div id="myDIV" class="header">
  <h2>My To Do List</h2>
  <input type="text" id="myInput" placeholder="Title...">
  <span onclick="newElement()" class="addBtn">Add</span>
</div>
<ul id="myUL">
  <li>Hit the gym</li>
  <li class="checked">Pay bills</li>
  <li>Meet George</li>
  <li>Buy eggs</li>
  <li>Read a book</li>
  <li>Organize office</li>
</ul>"""
    test_server(html_content)
