"""URL fetching module with SSRF protection.

This module provides async URL fetching capabilities with security measures
to prevent Server-Side Request Forgery (SSRF) attacks following OWASP guidelines.
"""

import ipaddress
import logging
import os
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Configuration from environment variables
URL_FETCH_TIMEOUT = int(os.getenv("URL_FETCH_TIMEOUT", "30"))
URL_FETCH_USER_AGENT = os.getenv("URL_FETCH_USER_AGENT", "ReaderLM/1.0")
BLOCK_PRIVATE_IPS = os.getenv("BLOCK_PRIVATE_IPS", "true").lower() == "true"
ALLOWED_DOMAINS = [
    d.strip()
    for d in os.getenv("ALLOWED_DOMAINS", "").split(",")
    if d.strip()
]
BLOCKED_DOMAINS = [
    d.strip()
    for d in os.getenv("BLOCKED_DOMAINS", "").split(",")
    if d.strip()
]


class URLFetchError(Exception):
    """Base exception for URL fetching errors."""

    pass


class URLValidationError(URLFetchError):
    """Raised when URL validation fails."""

    pass


class SSRFBlockedError(URLFetchError):
    """Raised when a request is blocked due to SSRF protection."""

    pass


class FetchError(URLFetchError):
    """Raised when fetching the URL fails."""

    pass


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is private or reserved.

    Blocks RFC1918 private ranges, loopback, link-local, and cloud metadata IPs.

    Args:
        ip_str: IP address string to check

    Returns:
        True if the IP is private/reserved, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        logger.warning("Invalid IP address: %s", ip_str)
        return True  # Block invalid IPs

    # Check for private/reserved addresses
    if ip.is_private:
        return True
    if ip.is_loopback:
        return True
    if ip.is_link_local:
        return True
    if ip.is_reserved:
        return True
    if ip.is_multicast:
        return True

    # Block cloud metadata IP (169.254.169.254)
    if ip_str == "169.254.169.254":
        return True

    # IPv6 specific checks
    if isinstance(ip, ipaddress.IPv6Address):
        # IPv4-mapped IPv6 addresses
        if ip.ipv4_mapped is not None:
            return is_private_ip(str(ip.ipv4_mapped))

    return False


def validate_url(url: str) -> str:
    """Validate URL format and scheme.

    Args:
        url: URL string to validate

    Returns:
        Normalized URL string

    Raises:
        URLValidationError: If URL is invalid or uses disallowed scheme
    """
    if not url:
        raise URLValidationError("URL cannot be empty")

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        logger.error("Failed to parse URL: %s", e)
        raise URLValidationError(f"Invalid URL format: {e}") from e

    # Check scheme (only http/https allowed)
    if parsed.scheme not in ("http", "https"):
        raise URLValidationError(
            f"Invalid URL scheme '{parsed.scheme}'. Only http and https are allowed."
        )

    # Check hostname exists
    if not parsed.hostname:
        raise URLValidationError("URL must contain a hostname")

    # Check domain allowlist/blocklist
    hostname = parsed.hostname.lower()

    if ALLOWED_DOMAINS and hostname not in ALLOWED_DOMAINS:
        raise URLValidationError(f"Domain '{hostname}' is not in the allowlist")

    if BLOCKED_DOMAINS and hostname in BLOCKED_DOMAINS:
        raise URLValidationError(f"Domain '{hostname}' is blocked")

    return url


async def resolve_hostname(hostname: str) -> list[str]:
    """Resolve hostname to IP addresses.

    Args:
        hostname: Hostname to resolve

    Returns:
        List of IP address strings

    Raises:
        SSRFBlockedError: If hostname cannot be resolved
    """
    try:
        # Use getaddrinfo for both IPv4 and IPv6 resolution
        results = socket.getaddrinfo(
            hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
        ips = list({str(result[4][0]) for result in results})
        logger.debug("Resolved %s to: %s", hostname, ips)
        return ips
    except socket.gaierror as e:
        logger.error("DNS resolution failed for %s: %s", hostname, e)
        raise SSRFBlockedError(f"Cannot resolve hostname: {hostname}") from e


async def check_ssrf(url: str) -> None:
    """Check URL for SSRF vulnerabilities before making request.

    Args:
        url: URL to check

    Raises:
        SSRFBlockedError: If the URL targets a private/reserved IP
    """
    if not BLOCK_PRIVATE_IPS:
        logger.debug("SSRF protection disabled")
        return

    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise SSRFBlockedError("URL has no hostname")

    # Check if hostname is already an IP address
    try:
        ipaddress.ip_address(hostname)
        # It's a valid IP address, check if it's private
        if is_private_ip(hostname):
            raise SSRFBlockedError(
                f"Requests to private IP addresses are blocked: {hostname}"
            )
        return  # It's a valid public IP, no DNS resolution needed
    except ValueError:
        pass  # Not an IP address, continue to DNS resolution

    # Resolve hostname and check all IPs
    ips = await resolve_hostname(hostname)

    for ip in ips:
        if is_private_ip(ip):
            raise SSRFBlockedError(
                f"Hostname '{hostname}' resolves to private IP: {ip}"
            )


async def fetch_url(url: str) -> str:
    """Fetch HTML content from a URL.

    Args:
        url: URL to fetch

    Returns:
        HTML content as string

    Raises:
        URLValidationError: If URL is invalid
        SSRFBlockedError: If URL is blocked by SSRF protection
        FetchError: If fetching fails
    """
    # Validate URL format
    url = validate_url(url)
    logger.info("Fetching URL: %s", url)

    # Check SSRF before making request
    await check_ssrf(url)

    # Fetch the URL
    try:
        async with httpx.AsyncClient(
            timeout=URL_FETCH_TIMEOUT,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": URL_FETCH_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            )

            # Check for HTTP errors
            if response.status_code >= 400:
                logger.error(
                    "HTTP error %d fetching %s", response.status_code, url
                )
                raise FetchError(
                    f"HTTP error {response.status_code}: {response.reason_phrase}"
                )

            # Get content
            content = response.text
            logger.info(
                "Successfully fetched %s (%d bytes)", url, len(content)
            )
            return content

    except httpx.TimeoutException as e:
        logger.error("Timeout fetching %s: %s", url, e)
        raise FetchError(f"Request timed out after {URL_FETCH_TIMEOUT}s") from e
    except httpx.RequestError as e:
        logger.error("Request error fetching %s: %s", url, e)
        raise FetchError(f"Failed to fetch URL: {e}") from e
