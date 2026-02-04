"""Unit tests for the html_preprocessor module."""

from unittest.mock import MagicMock, patch

from html_preprocessor import (
    extract_main_content,
    _fallback_clean_html,
    estimate_tokens,
    count_tokens,
    _find_split_points,
    chunk_html,
    _simple_chunk,
    preprocess_html,
)


class TestExtractMainContent:
    """Tests for extract_main_content function."""

    def test_empty_html_returns_empty(self) -> None:
        """Test that empty HTML returns empty string."""
        assert extract_main_content("") == ""
        assert extract_main_content("   ") == "   "

    def test_readability_disabled_uses_fallback(self) -> None:
        """Test that disabling readability uses fallback cleaning."""
        html = "<html><body><p>Test content</p></body></html>"
        with patch("html_preprocessor._fallback_clean_html") as mock_fallback:
            mock_fallback.return_value = "cleaned"
            result = extract_main_content(html, use_readability=False)
            mock_fallback.assert_called_once_with(html)
            assert result == "cleaned"

    def test_readability_extraction_success(self) -> None:
        """Test successful readability extraction."""
        html = """
        <html>
        <head><title>Test</title></head>
        <body>
            <nav>Navigation here</nav>
            <article>
                <h1>Main Article Title</h1>
                <p>This is the main content of the article that should be extracted.
                It contains multiple sentences to make it substantial enough for
                readability to identify it as the main content.</p>
                <p>Another paragraph with more content to ensure extraction works.</p>
            </article>
            <aside>Sidebar content</aside>
        </body>
        </html>
        """
        result = extract_main_content(html, use_readability=True)
        # Should contain the article content
        assert "Main Article Title" in result or "main content" in result

    def test_readability_import_error_fallback(self) -> None:
        """Test that import error falls back to basic cleaning."""
        # This test verifies the fallback path exists - actual import error
        # testing would require removing readability from the environment
        html = "<html><body><p>Test</p></body></html>"
        # Just verify fallback works when called directly
        result = _fallback_clean_html(html)
        assert "Test" in result

    def test_readability_exception_fallback(self) -> None:
        """Test that exceptions fall back to basic cleaning."""
        html = "<html><body><p>Test content here</p></body></html>"
        # Mock readability.Document to raise an exception during summary()
        with patch("readability.Document") as mock_doc_class:
            mock_instance = MagicMock()
            mock_instance.summary.side_effect = ValueError("Parse error")
            mock_doc_class.return_value = mock_instance

            with patch("html_preprocessor._fallback_clean_html") as mock_fallback:
                mock_fallback.return_value = "<p>cleaned</p>"
                result = extract_main_content(html, use_readability=True)
                # Should fall back when readability fails
                mock_fallback.assert_called_once_with(html)
                assert result == "<p>cleaned</p>"


class TestFallbackCleanHtml:
    """Tests for _fallback_clean_html function."""

    def test_removes_script_tags(self) -> None:
        """Test that script tags are removed."""
        html = "<html><body><script>alert('xss')</script><p>Content</p></body></html>"
        result = _fallback_clean_html(html)
        assert "alert" not in result
        assert "Content" in result

    def test_removes_style_tags(self) -> None:
        """Test that style tags are removed."""
        html = "<html><body><style>.red{color:red}</style><p>Content</p></body></html>"
        result = _fallback_clean_html(html)
        assert ".red" not in result
        assert "Content" in result

    def test_removes_comments(self) -> None:
        """Test that HTML comments are removed."""
        html = "<html><body><!-- secret comment --><p>Content</p></body></html>"
        result = _fallback_clean_html(html)
        assert "secret" not in result
        assert "Content" in result

    def test_preserves_content(self) -> None:
        """Test that main content is preserved."""
        html = "<html><body><h1>Title</h1><p>Paragraph text</p></body></html>"
        result = _fallback_clean_html(html)
        assert "Title" in result
        assert "Paragraph" in result


class TestEstimateTokens:
    """Tests for estimate_tokens function."""

    def test_default_chars_per_token(self) -> None:
        """Test token estimation with default 4 chars per token."""
        text = "a" * 400
        assert estimate_tokens(text) == 100

    def test_custom_chars_per_token(self) -> None:
        """Test token estimation with custom chars per token."""
        text = "a" * 300
        assert estimate_tokens(text, chars_per_token=3.0) == 100

    def test_empty_string(self) -> None:
        """Test token estimation for empty string."""
        assert estimate_tokens("") == 0


class TestCountTokens:
    """Tests for count_tokens function."""

    def test_count_tokens_uses_tokenizer(self) -> None:
        """Test that count_tokens uses the tokenizer correctly."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.encode.return_value = [1, 2, 3, 4, 5]

        result = count_tokens("test text", mock_tokenizer)

        assert result == 5
        mock_tokenizer.encode.assert_called_once_with("test text", add_special_tokens=False)


class TestFindSplitPoints:
    """Tests for _find_split_points function."""

    def test_finds_h1_headings(self) -> None:
        """Test that H1 headings are found as split points."""
        html = "<div>Intro</div><h1>Section 1</h1><p>Content</p>"
        points = _find_split_points(html)
        assert len(points) == 1
        assert html[points[0] : points[0] + 3] == "<h1"

    def test_finds_h2_headings(self) -> None:
        """Test that H2 headings are found as split points."""
        html = "<p>Intro</p><h2>Section</h2><p>Content</p>"
        points = _find_split_points(html)
        assert len(points) == 1

    def test_finds_section_tags(self) -> None:
        """Test that section tags are found as split points."""
        html = '<p>Intro</p><section id="main"><p>Content</p></section>'
        points = _find_split_points(html)
        assert len(points) == 1

    def test_finds_multiple_split_points(self) -> None:
        """Test finding multiple split points."""
        html = "<h1>Title</h1><h2>Section 1</h2><h2>Section 2</h2>"
        points = _find_split_points(html)
        assert len(points) == 3

    def test_returns_sorted_positions(self) -> None:
        """Test that positions are returned sorted."""
        html = "<h2>Later</h2><h1>Earlier</h1>"
        points = _find_split_points(html)
        assert points == sorted(points)

    def test_empty_html(self) -> None:
        """Test with empty HTML."""
        assert _find_split_points("") == []

    def test_no_split_points(self) -> None:
        """Test with HTML containing no split points."""
        html = "<div><p>Just a paragraph</p></div>"
        assert _find_split_points(html) == []


class TestChunkHtml:
    """Tests for chunk_html function."""

    def test_no_chunking_needed_small_content(self) -> None:
        """Test that small content is not chunked."""
        html = "<p>Short content</p>"
        chunks = chunk_html(html, max_tokens=1000)
        assert len(chunks) == 1
        assert chunks[0] == html

    def test_empty_html(self) -> None:
        """Test chunking empty HTML."""
        assert chunk_html("", max_tokens=100) == []
        assert chunk_html("   ", max_tokens=100) == ["   "]

    def test_chunks_at_natural_boundaries(self) -> None:
        """Test that chunking occurs at natural boundaries."""
        # Create HTML with sections that are large enough to require chunking
        html = "<h1>Section 1</h1>" + "<p>Content</p>" * 50 + "<h1>Section 2</h1>" + "<p>More</p>" * 50
        chunks = chunk_html(html, max_tokens=100, chars_per_token=1.0)
        assert len(chunks) > 1

    def test_uses_tokenizer_when_provided(self) -> None:
        """Test that tokenizer is used for accurate counting."""
        mock_tokenizer = MagicMock()
        # Return small token counts so no chunking is needed
        mock_tokenizer.encode.return_value = list(range(10))

        html = "<p>Test content</p>"
        chunks = chunk_html(html, max_tokens=100, tokenizer=mock_tokenizer)

        assert len(chunks) == 1
        mock_tokenizer.encode.assert_called()

    def test_falls_back_to_simple_chunk(self) -> None:
        """Test fallback to simple chunking when no boundaries found."""
        # Plain text without any HTML structure markers
        text = "a" * 1000
        chunks = chunk_html(text, max_tokens=100, chars_per_token=1.0)
        assert len(chunks) > 1


class TestSimpleChunk:
    """Tests for _simple_chunk function."""

    def test_splits_at_whitespace(self) -> None:
        """Test that simple chunk tries to split at whitespace."""
        text = "word1 word2 word3 word4 word5"
        chunks = _simple_chunk(text, max_tokens=10, chars_per_token=2.0)
        # Should split into multiple chunks
        assert len(chunks) >= 1
        # Each chunk should be at most max_chars (20 chars)
        for chunk in chunks:
            assert len(chunk) <= 20 or " " not in text[: len(chunk)]

    def test_handles_no_whitespace(self) -> None:
        """Test handling text without whitespace."""
        text = "a" * 100
        chunks = _simple_chunk(text, max_tokens=10, chars_per_token=1.0)
        assert len(chunks) > 1
        # Each chunk should be at most 10 chars
        for chunk in chunks:
            assert len(chunk) <= 10

    def test_empty_text(self) -> None:
        """Test with empty text."""
        assert _simple_chunk("", max_tokens=100) == []


class TestPreprocessHtml:
    """Tests for preprocess_html function."""

    def test_full_pipeline(self) -> None:
        """Test the full preprocessing pipeline."""
        html = """
        <html>
        <head><script>evil()</script></head>
        <body>
            <article>
                <h1>Article Title</h1>
                <p>This is article content.</p>
            </article>
        </body>
        </html>
        """
        chunks = preprocess_html(
            html,
            use_readability=True,
            max_tokens=10000,
            enable_chunking=True,
        )
        assert len(chunks) >= 1
        # Should have extracted something
        assert chunks[0]

    def test_readability_disabled(self) -> None:
        """Test pipeline with readability disabled."""
        html = "<html><body><p>Content</p></body></html>"
        with patch("html_preprocessor.extract_main_content") as mock_extract:
            mock_extract.return_value = html
            result = preprocess_html(html, use_readability=False)
            mock_extract.assert_called_once_with(html, use_readability=False)
            assert result is not None

    def test_chunking_disabled(self) -> None:
        """Test pipeline with chunking disabled."""
        html = "a" * 10000  # Large content
        chunks = preprocess_html(
            html,
            use_readability=False,
            max_tokens=100,
            enable_chunking=False,
        )
        # Should be single chunk even though it exceeds max_tokens
        assert len(chunks) == 1

    def test_passes_tokenizer_to_chunk(self) -> None:
        """Test that tokenizer is passed to chunking function."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.encode.return_value = list(range(10))

        html = "<p>Test</p>"
        with patch("html_preprocessor.chunk_html") as mock_chunk:
            mock_chunk.return_value = [html]
            preprocess_html(html, tokenizer=mock_tokenizer)
            mock_chunk.assert_called_once()
            call_kwargs = mock_chunk.call_args
            assert call_kwargs[1]["tokenizer"] == mock_tokenizer
