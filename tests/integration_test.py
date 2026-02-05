#!/usr/bin/env python3
"""Integration tests for the HTML2Markdown LitServe service.

These tests run against a deployed instance of the service.
Configure the service URL via the READERLM_URL environment variable.

Usage:
    python tests/integration_test.py
    READERLM_URL=http://localhost:8000 python tests/integration_test.py
"""

import os
import sys
import time
from dataclasses import dataclass

import requests

# Service URL - can be overridden via environment variable
SERVICE_URL = os.getenv("READERLM_URL", "http://fabio.service.consul:9999/readerlm")


@dataclass
class TestResult:
    """Result of a single test."""

    name: str
    passed: bool
    message: str
    duration: float


def test_health_check() -> TestResult:
    """Test the health endpoint returns 200 OK."""
    start = time.time()
    try:
        response = requests.get(f"{SERVICE_URL}/health", timeout=10)
        passed = response.status_code == 200 and response.text == "ok"
        message = f"Status: {response.status_code}, Body: {response.text[:50]}"
    except Exception as e:
        passed = False
        message = str(e)
    return TestResult("Health Check", passed, message, time.time() - start)


def test_basic_html_conversion() -> TestResult:
    """Test basic HTML to Markdown conversion."""
    start = time.time()
    try:
        html = "<html><body><h1>Hello World</h1><p>Test paragraph.</p></body></html>"
        response = requests.post(
            f"{SERVICE_URL}/predict",
            json={"html_content": html},
            timeout=30,
        )
        passed = response.status_code == 200 and "Hello World" in response.text
        message = f"Status: {response.status_code}, Length: {len(response.text)}"
    except Exception as e:
        passed = False
        message = str(e)
    return TestResult("Basic HTML Conversion", passed, message, time.time() - start)


def test_html_cleaning() -> TestResult:
    """Test that scripts and styles are removed from HTML."""
    start = time.time()
    try:
        html = """
        <html>
        <head>
            <script>alert('xss')</script>
            <style>.red{color:red}</style>
        </head>
        <body>
            <article>
                <h1>Clean Content</h1>
                <p>This should appear without scripts.</p>
            </article>
        </body>
        </html>
        """
        response = requests.post(
            f"{SERVICE_URL}/predict",
            json={"html_content": html},
            timeout=30,
        )
        passed = (
            response.status_code == 200
            and "Clean Content" in response.text
            and "alert" not in response.text
            and "color:red" not in response.text
        )
        message = f"Status: {response.status_code}, Scripts removed: {'alert' not in response.text}"
    except Exception as e:
        passed = False
        message = str(e)
    return TestResult("HTML Cleaning (scripts/styles)", passed, message, time.time() - start)


def test_empty_content_validation() -> TestResult:
    """Test that empty content returns 400."""
    start = time.time()
    try:
        response = requests.post(
            f"{SERVICE_URL}/predict",
            json={"html_content": ""},
            timeout=10,
        )
        passed = response.status_code == 400
        message = f"Status: {response.status_code}, Detail: {response.json().get('detail', 'N/A')}"
    except Exception as e:
        passed = False
        message = str(e)
    return TestResult("Empty Content Validation", passed, message, time.time() - start)


def test_missing_field_validation() -> TestResult:
    """Test that missing html_content field returns 400."""
    start = time.time()
    try:
        response = requests.post(
            f"{SERVICE_URL}/predict",
            json={"wrong_field": "test"},
            timeout=10,
        )
        passed = response.status_code == 400
        message = f"Status: {response.status_code}, Detail: {response.json().get('detail', 'N/A')}"
    except Exception as e:
        passed = False
        message = str(e)
    return TestResult("Missing Field Validation", passed, message, time.time() - start)


def test_url_fetch_example() -> TestResult:
    """Test URL fetching with example.com."""
    start = time.time()
    try:
        response = requests.get(
            f"{SERVICE_URL}/https://example.com",
            timeout=30,
        )
        passed = response.status_code == 200 and "Example Domain" in response.text
        message = f"Status: {response.status_code}, Contains 'Example Domain': {'Example Domain' in response.text}"
    except Exception as e:
        passed = False
        message = str(e)
    return TestResult("URL Fetch (example.com)", passed, message, time.time() - start)


def test_url_invalid_format() -> TestResult:
    """Test that invalid URL format returns 400."""
    start = time.time()
    try:
        response = requests.get(
            f"{SERVICE_URL}/not-a-valid-url",
            timeout=10,
        )
        passed = response.status_code == 400
        message = f"Status: {response.status_code}, Detail: {response.json().get('detail', 'N/A')}"
    except Exception as e:
        passed = False
        message = str(e)
    return TestResult("URL Invalid Format", passed, message, time.time() - start)


def test_ssrf_protection() -> TestResult:
    """Test that SSRF protection blocks private IPs."""
    start = time.time()
    try:
        response = requests.get(
            f"{SERVICE_URL}/http://127.0.0.1/admin",
            timeout=10,
        )
        passed = response.status_code == 403
        message = f"Status: {response.status_code}, Detail: {response.json().get('detail', 'N/A')}"
    except Exception as e:
        passed = False
        message = str(e)
    return TestResult("SSRF Protection", passed, message, time.time() - start)


def test_url_fetch_github() -> TestResult:
    """Test URL fetching with GitHub (structured page)."""
    start = time.time()
    try:
        response = requests.get(
            f"{SERVICE_URL}/https://github.com/anthropics",
            timeout=30,
        )
        # GitHub profile pages have structured content
        passed = response.status_code == 200 and len(response.text) > 50
        message = f"Status: {response.status_code}, Length: {len(response.text)}"
    except Exception as e:
        passed = False
        message = str(e)
    return TestResult("URL Fetch (github.com)", passed, message, time.time() - start)


def test_url_fetch_wikipedia() -> TestResult:
    """Test URL fetching with Wikipedia (large page)."""
    start = time.time()
    try:
        response = requests.get(
            f"{SERVICE_URL}/https://en.wikipedia.org/wiki/Markdown",
            timeout=60,
        )
        passed = response.status_code == 200 and len(response.text) > 100
        message = f"Status: {response.status_code}, Length: {len(response.text)}"
    except Exception as e:
        passed = False
        message = str(e)
    return TestResult("URL Fetch (wikipedia.org)", passed, message, time.time() - start)


def test_complex_html_structure() -> TestResult:
    """Test conversion of complex HTML with nested elements."""
    start = time.time()
    try:
        html = """
        <html>
        <body>
            <article>
                <header>
                    <h1>Main Title</h1>
                    <p class="subtitle">A subtitle here</p>
                </header>
                <section>
                    <h2>Section One</h2>
                    <p>First paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
                    <ul>
                        <li>Item one</li>
                        <li>Item two</li>
                        <li>Item three</li>
                    </ul>
                </section>
                <section>
                    <h2>Section Two</h2>
                    <p>A paragraph with a <a href="https://example.com">link</a>.</p>
                    <blockquote>A famous quote here.</blockquote>
                </section>
            </article>
        </body>
        </html>
        """
        response = requests.post(
            f"{SERVICE_URL}/predict",
            json={"html_content": html},
            timeout=30,
        )
        text = response.text
        passed = (
            response.status_code == 200
            and "Main Title" in text
            and "Section One" in text
            and "Section Two" in text
        )
        message = f"Status: {response.status_code}, Has sections: {passed}"
    except Exception as e:
        passed = False
        message = str(e)
    return TestResult("Complex HTML Structure", passed, message, time.time() - start)


def run_all_tests() -> list[TestResult]:
    """Run all integration tests and return results."""
    tests = [
        test_health_check,
        test_basic_html_conversion,
        test_html_cleaning,
        test_empty_content_validation,
        test_missing_field_validation,
        test_url_fetch_example,
        test_url_invalid_format,
        test_ssrf_protection,
        test_url_fetch_github,
        test_url_fetch_wikipedia,
        test_complex_html_structure,
    ]

    results = []
    for test_func in tests:
        print(f"Running: {test_func.__name__}...", end=" ", flush=True)
        result = test_func()
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} ({result.duration:.2f}s)")

    return results


def print_summary(results: list[TestResult]) -> bool:
    """Print test summary and return True if all tests passed."""
    print("\n" + "=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)
    print(f"Service URL: {SERVICE_URL}")
    print("-" * 60)

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total_time = sum(r.duration for r in results)

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} {result.name}")
        print(f"   {result.message}")

    print("-" * 60)
    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")
    print(f"Total time: {total_time:.2f}s")
    print("=" * 60)

    return failed == 0


def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("HTML2Markdown LitServe Integration Tests")
    print("=" * 60)
    print(f"Target: {SERVICE_URL}")
    print()

    results = run_all_tests()
    all_passed = print_summary(results)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
