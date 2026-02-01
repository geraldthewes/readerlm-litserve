"""Integration tests for ReaderLM-LitServe API.

These tests run against a live service instance during the build process.
SERVICE_HOST and SERVICE_PORT are injected by python-executor.
"""

import os
import requests


def get_service_url() -> str:
    """Get the service URL from environment variables."""
    host = os.environ.get("SERVICE_HOST", "localhost")
    port = os.environ.get("SERVICE_PORT", "8000")
    return f"http://{host}:{port}"


def test_health_endpoint():
    """Test that the health endpoint responds correctly."""
    url = f"{get_service_url()}/health"
    response = requests.get(url, timeout=30)
    assert response.status_code == 200, f"Health check failed: {response.status_code}"
    print("Health endpoint test passed")


def test_predict_endpoint():
    """Test HTML to Markdown conversion via POST /predict."""
    url = f"{get_service_url()}/predict"
    payload = {
        "html_content": "<html><body><h1>Test Header</h1><p>Hello world</p></body></html>"
    }
    response = requests.post(url, json=payload, timeout=120)
    assert response.status_code == 200, f"Predict failed: {response.status_code}"

    content = response.text
    assert "Test Header" in content or "# Test Header" in content, \
        f"Expected 'Test Header' in response, got: {content[:200]}"
    print("Predict endpoint test passed")


# Run tests when module is imported or executed
print(f"Testing service at: {get_service_url()}")
test_health_endpoint()
test_predict_endpoint()
print("All tests passed!")
