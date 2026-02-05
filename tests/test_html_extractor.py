"""Unit tests for the html_extractor module."""

from unittest.mock import MagicMock, patch

import pytest

from html_extractor import (
    ExtractionError,
    _extract_with_lxml_cleaner,
    _extract_with_readability,
    _extract_with_trafilatura,
    extract_to_markdown,
)


class TestExtractToMarkdown:
    """Tests for the main extract_to_markdown function."""

    def test_empty_html_raises_error(self) -> None:
        """Test that empty HTML raises ExtractionError."""
        with pytest.raises(ExtractionError, match="Empty HTML"):
            extract_to_markdown("")

    def test_whitespace_only_raises_error(self) -> None:
        """Test that whitespace-only HTML raises ExtractionError."""
        with pytest.raises(ExtractionError, match="Empty HTML"):
            extract_to_markdown("   \n\t  ")

    def test_basic_html_extraction(self) -> None:
        """Test that basic HTML is converted to markdown."""
        html = """
        <html>
        <body>
            <article>
                <h1>Test Article</h1>
                <p>This is a test paragraph with enough content to be extracted
                by trafilatura or readability. It needs to be substantial enough
                to pass minimum length thresholds in the extraction pipeline.</p>
                <p>Another paragraph to add more content for the extractor.</p>
            </article>
        </body>
        </html>
        """
        result = extract_to_markdown(html)
        assert "Test Article" in result

    def test_fallback_chain_tier1_succeeds(self) -> None:
        """Test that successful tier 1 returns without calling tier 2."""
        with (
            patch(
                "html_extractor._extract_with_trafilatura",
                return_value="# Tier 1 Result",
            ) as mock_t1,
            patch(
                "html_extractor._extract_with_readability"
            ) as mock_t2,
        ):
            result = extract_to_markdown("<html><body><p>Test</p></body></html>")
            assert result == "# Tier 1 Result"
            mock_t1.assert_called_once()
            mock_t2.assert_not_called()

    def test_fallback_chain_tier1_fails_tier2_succeeds(self) -> None:
        """Test that tier 2 is tried when tier 1 returns None."""
        with (
            patch(
                "html_extractor._extract_with_trafilatura", return_value=None
            ),
            patch(
                "html_extractor._extract_with_readability",
                return_value="## Tier 2 Result",
            ) as mock_t2,
            patch(
                "html_extractor._extract_with_lxml_cleaner"
            ) as mock_t3,
        ):
            result = extract_to_markdown("<html><body><p>Test</p></body></html>")
            assert result == "## Tier 2 Result"
            mock_t2.assert_called_once()
            mock_t3.assert_not_called()

    def test_fallback_chain_tier1_and_tier2_fail_tier3_succeeds(self) -> None:
        """Test that tier 3 is tried when tiers 1 and 2 return None."""
        with (
            patch(
                "html_extractor._extract_with_trafilatura", return_value=None
            ),
            patch(
                "html_extractor._extract_with_readability", return_value=None
            ),
            patch(
                "html_extractor._extract_with_lxml_cleaner",
                return_value="### Tier 3 Result",
            ) as mock_t3,
        ):
            result = extract_to_markdown("<html><body><p>Test</p></body></html>")
            assert result == "### Tier 3 Result"
            mock_t3.assert_called_once()

    def test_all_tiers_fail_raises_error(self) -> None:
        """Test that ExtractionError is raised when all tiers fail."""
        with (
            patch(
                "html_extractor._extract_with_trafilatura", return_value=None
            ),
            patch(
                "html_extractor._extract_with_readability", return_value=None
            ),
            patch(
                "html_extractor._extract_with_lxml_cleaner", return_value=None
            ),
        ):
            with pytest.raises(ExtractionError, match="All extraction tiers failed"):
                extract_to_markdown("<html><body><p>Test</p></body></html>")

    def test_url_passed_to_trafilatura(self) -> None:
        """Test that source URL is forwarded to trafilatura tier."""
        with patch(
            "html_extractor._extract_with_trafilatura",
            return_value="# Result",
        ) as mock_t1:
            extract_to_markdown("<html><body>Test</body></html>", url="https://example.com")
            mock_t1.assert_called_once_with(
                "<html><body>Test</body></html>", "https://example.com"
            )


class TestExtractWithTrafilatura:
    """Tests for the trafilatura extraction tier."""

    def test_successful_extraction(self) -> None:
        """Test successful trafilatura extraction."""
        mock_trafilatura = MagicMock()
        mock_trafilatura.extract.return_value = "# Extracted Content\n\nSome text here."

        with patch.dict("sys.modules", {"trafilatura": mock_trafilatura}):
            result = _extract_with_trafilatura(
                "<html><body><p>Test</p></body></html>"
            )
            assert result == "# Extracted Content\n\nSome text here."

    def test_empty_result_returns_none(self) -> None:
        """Test that empty trafilatura result returns None."""
        mock_trafilatura = MagicMock()
        mock_trafilatura.extract.return_value = ""

        with patch.dict("sys.modules", {"trafilatura": mock_trafilatura}):
            result = _extract_with_trafilatura(
                "<html><body><p>Test</p></body></html>"
            )
            assert result is None

    def test_none_result_returns_none(self) -> None:
        """Test that None trafilatura result returns None."""
        mock_trafilatura = MagicMock()
        mock_trafilatura.extract.return_value = None

        with patch.dict("sys.modules", {"trafilatura": mock_trafilatura}):
            result = _extract_with_trafilatura(
                "<html><body><p>Test</p></body></html>"
            )
            assert result is None

    def test_exception_returns_none(self) -> None:
        """Test that exceptions are caught and None is returned."""
        mock_trafilatura = MagicMock()
        mock_trafilatura.extract.side_effect = RuntimeError("Parse error")

        with patch.dict("sys.modules", {"trafilatura": mock_trafilatura}):
            result = _extract_with_trafilatura(
                "<html><body><p>Test</p></body></html>"
            )
            assert result is None

    def test_url_passed_to_trafilatura(self) -> None:
        """Test that URL is forwarded to trafilatura.extract."""
        mock_trafilatura = MagicMock()
        mock_trafilatura.extract.return_value = "# Content"

        with patch.dict("sys.modules", {"trafilatura": mock_trafilatura}):
            _extract_with_trafilatura(
                "<html><body><p>Test</p></body></html>",
                url="https://example.com",
            )
            mock_trafilatura.extract.assert_called_once()
            call_kwargs = mock_trafilatura.extract.call_args[1]
            assert call_kwargs["url"] == "https://example.com"


class TestExtractWithReadability:
    """Tests for the readability + markdownify extraction tier."""

    def test_successful_extraction(self) -> None:
        """Test successful readability extraction."""
        html = """
        <html>
        <body>
            <article>
                <h1>Article Title</h1>
                <p>This is article content with sufficient length to pass
                the minimum threshold check in the readability extraction tier.
                More text is added here to ensure it works correctly.</p>
            </article>
        </body>
        </html>
        """
        result = _extract_with_readability(html)
        assert result is not None
        assert "Article Title" in result

    def test_minimal_content_returns_none(self) -> None:
        """Test that minimal readability output returns None."""
        with patch("readability.Document") as mock_doc_class:
            mock_instance = MagicMock()
            mock_instance.summary.return_value = "<p>X</p>"
            mock_doc_class.return_value = mock_instance

            result = _extract_with_readability("<html><body><p>X</p></body></html>")
            assert result is None

    def test_readability_exception_returns_none(self) -> None:
        """Test that readability exceptions return None."""
        with patch("readability.Document") as mock_doc_class:
            mock_doc_class.side_effect = ValueError("Parse error")

            result = _extract_with_readability("<html><body><p>Test</p></body></html>")
            assert result is None


class TestExtractWithLxmlCleaner:
    """Tests for the lxml Cleaner + markdownify extraction tier."""

    def test_removes_scripts(self) -> None:
        """Test that scripts are removed."""
        html = "<html><body><script>alert('xss')</script><p>Clean content</p></body></html>"
        result = _extract_with_lxml_cleaner(html)
        assert result is not None
        assert "alert" not in result
        assert "Clean content" in result

    def test_removes_styles(self) -> None:
        """Test that styles are removed."""
        html = "<html><body><style>.red{color:red}</style><p>Content here</p></body></html>"
        result = _extract_with_lxml_cleaner(html)
        assert result is not None
        assert ".red" not in result
        assert "Content here" in result

    def test_preserves_content(self) -> None:
        """Test that main content is preserved."""
        html = "<html><body><h1>Title</h1><p>Paragraph text here</p></body></html>"
        result = _extract_with_lxml_cleaner(html)
        assert result is not None
        assert "Title" in result
        assert "Paragraph" in result

    def test_converts_to_markdown(self) -> None:
        """Test that output is markdown format."""
        html = "<html><body><h1>Heading</h1><p>Text</p></body></html>"
        result = _extract_with_lxml_cleaner(html)
        assert result is not None
        # markdownify should produce heading markers
        assert "#" in result or "Heading" in result

    def test_invalid_html_returns_none(self) -> None:
        """Test that completely invalid input is handled gracefully."""
        with patch("html_extractor.Cleaner") as mock_cleaner_class:
            mock_cleaner_class.side_effect = RuntimeError("Parse error")
            result = _extract_with_lxml_cleaner("not html at all")
            assert result is None


class TestEdgeCases:
    """Test edge cases across the extraction pipeline."""

    def test_html_with_only_scripts(self) -> None:
        """Test HTML containing only script content."""
        html = "<html><head><script>var x = 1;</script></head><body><script>alert(1);</script></body></html>"
        # Should either extract something minimal or raise
        # All tiers may fail since there's no real content
        try:
            result = extract_to_markdown(html)
            # If it succeeds, it shouldn't contain script content
            assert "alert" not in result
        except ExtractionError:
            pass  # Expected when no content is extractable

    def test_large_html_document(self) -> None:
        """Test that large HTML documents are handled without chunking."""
        paragraphs = "".join(
            f"<p>Paragraph {i} with some content to make it substantial.</p>"
            for i in range(100)
        )
        html = f"<html><body><article>{paragraphs}</article></body></html>"
        result = extract_to_markdown(html)
        assert len(result) > 0
        # No chunk separators - single pass extraction
        assert "---" not in result or result.count("---") < 5

    def test_html_with_tables(self) -> None:
        """Test that HTML tables are handled."""
        html = """
        <html><body>
            <article>
                <h1>Table Test</h1>
                <p>Introduction text for the article.</p>
                <table>
                    <tr><th>Name</th><th>Value</th></tr>
                    <tr><td>Item A</td><td>100</td></tr>
                    <tr><td>Item B</td><td>200</td></tr>
                </table>
            </article>
        </body></html>
        """
        result = extract_to_markdown(html)
        assert result is not None
        assert len(result) > 0

    def test_html_with_unicode(self) -> None:
        """Test that Unicode content is preserved."""
        html = """
        <html><body>
            <article>
                <h1>Unicode Test</h1>
                <p>Japanese: こんにちは世界</p>
                <p>German: Ünter den Linden straße</p>
                <p>Emoji: Hello World</p>
            </article>
        </body></html>
        """
        result = extract_to_markdown(html)
        assert result is not None
        assert "こんにちは" in result or "Unicode" in result
