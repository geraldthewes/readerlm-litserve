"""Unit tests for the url_fetcher module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import socket

from url_fetcher import (
    is_private_ip,
    validate_url,
    fetch_url,
    resolve_hostname,
    check_ssrf,
    URLValidationError,
    SSRFBlockedError,
    FetchError,
)


class TestIsPrivateIP:
    """Tests for is_private_ip function."""

    def test_localhost_ipv4(self) -> None:
        """Test that localhost (127.0.0.1) is detected as private."""
        assert is_private_ip("127.0.0.1") is True

    def test_localhost_ipv6(self) -> None:
        """Test that IPv6 localhost (::1) is detected as private."""
        assert is_private_ip("::1") is True

    def test_rfc1918_class_a(self) -> None:
        """Test that 10.0.0.0/8 range is detected as private."""
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("10.255.255.255") is True

    def test_rfc1918_class_b(self) -> None:
        """Test that 172.16.0.0/12 range is detected as private."""
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("172.31.255.255") is True

    def test_rfc1918_class_c(self) -> None:
        """Test that 192.168.0.0/16 range is detected as private."""
        assert is_private_ip("192.168.0.1") is True
        assert is_private_ip("192.168.255.255") is True

    def test_link_local(self) -> None:
        """Test that link-local addresses are detected as private."""
        assert is_private_ip("169.254.1.1") is True

    def test_cloud_metadata_ip(self) -> None:
        """Test that AWS/GCP/Azure metadata IP is blocked."""
        assert is_private_ip("169.254.169.254") is True

    def test_public_ip(self) -> None:
        """Test that public IPs are not detected as private."""
        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False
        assert is_private_ip("93.184.216.34") is False  # example.com

    def test_invalid_ip(self) -> None:
        """Test that invalid IPs are treated as private (blocked)."""
        assert is_private_ip("not-an-ip") is True
        assert is_private_ip("") is True

    def test_ipv4_mapped_ipv6(self) -> None:
        """Test that IPv4-mapped IPv6 addresses are checked correctly."""
        # ::ffff:127.0.0.1 should be detected as private
        assert is_private_ip("::ffff:127.0.0.1") is True
        # ::ffff:8.8.8.8 should not be private
        assert is_private_ip("::ffff:8.8.8.8") is False


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_https_url(self) -> None:
        """Test that valid HTTPS URLs pass validation."""
        url = "https://example.com/page"
        assert validate_url(url) == url

    def test_valid_http_url(self) -> None:
        """Test that valid HTTP URLs pass validation."""
        url = "http://example.com/page"
        assert validate_url(url) == url

    def test_invalid_scheme_file(self) -> None:
        """Test that file:// scheme is rejected."""
        with pytest.raises(URLValidationError, match="Invalid URL scheme"):
            validate_url("file:///etc/passwd")

    def test_invalid_scheme_ftp(self) -> None:
        """Test that ftp:// scheme is rejected."""
        with pytest.raises(URLValidationError, match="Invalid URL scheme"):
            validate_url("ftp://example.com/file")

    def test_invalid_scheme_javascript(self) -> None:
        """Test that javascript: scheme is rejected."""
        with pytest.raises(URLValidationError, match="Invalid URL scheme"):
            validate_url("javascript:alert(1)")

    def test_missing_hostname(self) -> None:
        """Test that URLs without hostname are rejected."""
        with pytest.raises(URLValidationError, match="hostname"):
            validate_url("http:///path")

    def test_empty_url(self) -> None:
        """Test that empty URLs are rejected."""
        with pytest.raises(URLValidationError, match="cannot be empty"):
            validate_url("")

    def test_url_with_query_params(self) -> None:
        """Test that URLs with query parameters are valid."""
        url = "https://example.com/search?q=test&page=1"
        assert validate_url(url) == url

    def test_url_with_fragment(self) -> None:
        """Test that URLs with fragments are valid."""
        url = "https://example.com/page#section"
        assert validate_url(url) == url

    @patch("url_fetcher.ALLOWED_DOMAINS", ["example.com"])
    def test_allowed_domain(self) -> None:
        """Test that allowed domains pass validation."""
        assert validate_url("https://example.com/page") == "https://example.com/page"

    @patch("url_fetcher.ALLOWED_DOMAINS", ["example.com"])
    def test_disallowed_domain_with_allowlist(self) -> None:
        """Test that non-allowed domains are rejected when allowlist is set."""
        with pytest.raises(URLValidationError, match="not in the allowlist"):
            validate_url("https://other.com/page")

    @patch("url_fetcher.BLOCKED_DOMAINS", ["blocked.com"])
    def test_blocked_domain(self) -> None:
        """Test that blocked domains are rejected."""
        with pytest.raises(URLValidationError, match="is blocked"):
            validate_url("https://blocked.com/page")


class TestResolveHostname:
    """Tests for resolve_hostname function."""

    @pytest.mark.asyncio
    async def test_resolve_valid_hostname(self) -> None:
        """Test resolving a valid hostname."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))
            ]
            ips = await resolve_hostname("example.com")
            assert "93.184.216.34" in ips

    @pytest.mark.asyncio
    async def test_resolve_invalid_hostname(self) -> None:
        """Test that unresolvable hostnames raise SSRFBlockedError."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.side_effect = socket.gaierror(8, "Name not resolved")
            with pytest.raises(SSRFBlockedError, match="Cannot resolve"):
                await resolve_hostname("nonexistent.invalid")


class TestCheckSsrf:
    """Tests for check_ssrf function."""

    @pytest.mark.asyncio
    async def test_public_ip_allowed(self) -> None:
        """Test that public IPs are allowed."""
        with patch("url_fetcher.resolve_hostname", new_callable=AsyncMock) as mock:
            mock.return_value = ["93.184.216.34"]
            # Should not raise
            await check_ssrf("https://example.com")

    @pytest.mark.asyncio
    async def test_private_ip_blocked(self) -> None:
        """Test that private IPs are blocked."""
        with pytest.raises(SSRFBlockedError, match="private IP"):
            await check_ssrf("http://127.0.0.1/secret")

    @pytest.mark.asyncio
    async def test_hostname_resolving_to_private_ip(self) -> None:
        """Test that hostnames resolving to private IPs are blocked."""
        with patch("url_fetcher.resolve_hostname", new_callable=AsyncMock) as mock:
            mock.return_value = ["192.168.1.1"]
            with pytest.raises(SSRFBlockedError, match="resolves to private IP"):
                await check_ssrf("https://evil.com")

    @pytest.mark.asyncio
    @patch("url_fetcher.BLOCK_PRIVATE_IPS", False)
    async def test_ssrf_protection_disabled(self) -> None:
        """Test that SSRF protection can be disabled."""
        # Should not raise even for private IP
        await check_ssrf("http://127.0.0.1/")


class TestFetchUrl:
    """Tests for fetch_url function."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self) -> None:
        """Test successful URL fetch."""
        with (
            patch("url_fetcher.check_ssrf", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Test</body></html>"

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await fetch_url("https://example.com")
            assert result == "<html><body>Test</body></html>"

    @pytest.mark.asyncio
    async def test_http_error(self) -> None:
        """Test that HTTP errors raise FetchError."""
        with (
            patch("url_fetcher.check_ssrf", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.reason_phrase = "Not Found"

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(FetchError, match="HTTP error 404"):
                await fetch_url("https://example.com/notfound")

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        """Test that timeouts raise FetchError."""
        import httpx

        with (
            patch("url_fetcher.check_ssrf", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Timeout")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(FetchError, match="timed out"):
                await fetch_url("https://slow.example.com")

    @pytest.mark.asyncio
    async def test_invalid_url(self) -> None:
        """Test that invalid URLs raise URLValidationError."""
        with pytest.raises(URLValidationError):
            await fetch_url("file:///etc/passwd")

    @pytest.mark.asyncio
    async def test_ssrf_blocked(self) -> None:
        """Test that SSRF-blocked URLs raise SSRFBlockedError."""
        with pytest.raises(SSRFBlockedError):
            await fetch_url("http://127.0.0.1/admin")
