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


def test_health_endpoint() -> None:
    """Test that the health endpoint responds correctly."""
    url = f"{get_service_url()}/health"
    response = requests.get(url, timeout=30)
    assert response.status_code == 200, f"Health check failed: {response.status_code}"
    print("Health endpoint test passed")


def test_predict_endpoint() -> None:
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


def test_predict_empty_content() -> None:
    """Test that empty html_content returns 400."""
    url = f"{get_service_url()}/predict"
    payload = {"html_content": ""}
    response = requests.post(url, json=payload, timeout=30)
    assert response.status_code == 400, \
        f"Expected 400 for empty content, got: {response.status_code}"
    print("Predict empty content test passed")


def test_predict_missing_field() -> None:
    """Test that missing html_content field returns 400."""
    url = f"{get_service_url()}/predict"
    payload = {"wrong_field": "some content"}
    response = requests.post(url, json=payload, timeout=30)
    assert response.status_code == 400, \
        f"Expected 400 for missing field, got: {response.status_code}"
    print("Predict missing field test passed")


def test_get_url_endpoint() -> None:
    """Test GET /{url} pattern works for URL fetching."""
    # Use example.com as a reliable test target
    url = f"{get_service_url()}/https://example.com"
    response = requests.get(url, timeout=120)
    assert response.status_code == 200, \
        f"GET URL endpoint failed: {response.status_code}"

    content = response.text
    # example.com should contain "Example Domain" text
    assert "Example" in content or "example" in content.lower(), \
        f"Expected 'Example' in response, got: {content[:200]}"
    print("GET URL endpoint test passed")


def test_get_url_invalid_format() -> None:
    """Test that URL without http:// scheme returns 400."""
    url = f"{get_service_url()}/example.com"
    response = requests.get(url, timeout=30)
    assert response.status_code == 400, \
        f"Expected 400 for invalid URL format, got: {response.status_code}"
    print("GET URL invalid format test passed")


def test_get_url_ssrf_blocked() -> None:
    """Test that internal IPs are blocked with 403."""
    # Try to access localhost - should be blocked by SSRF protection
    url = f"{get_service_url()}/http://127.0.0.1"
    response = requests.get(url, timeout=30)
    assert response.status_code == 403, \
        f"Expected 403 for SSRF blocked request, got: {response.status_code}"
    print("GET URL SSRF blocked test passed")


if __name__ == "__main__":
    print(f"Testing service at: {get_service_url()}")
    test_health_endpoint()
    test_predict_endpoint()
    test_predict_empty_content()
    test_predict_missing_field()
    test_get_url_endpoint()
    test_get_url_invalid_format()
    test_get_url_ssrf_blocked()
    print("All tests passed!")
