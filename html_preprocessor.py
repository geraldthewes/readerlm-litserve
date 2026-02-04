"""HTML preprocessing module for ReaderLM-v2 VRAM optimization.

This module provides functions to extract main content from HTML documents
and chunk large documents for efficient processing with limited VRAM.
"""

import logging
import re
from typing import TYPE_CHECKING

from lxml.html.clean import Cleaner

if TYPE_CHECKING:
    from transformers import PreTrainedTokenizer

logger = logging.getLogger(__name__)


def extract_main_content(html: str, use_readability: bool = True) -> str:
    """Extract main content from HTML using readability-lxml.

    This function uses the readability-lxml library to extract the primary
    article content from an HTML page, removing navigation, ads, sidebars,
    and other boilerplate content.

    Args:
        html: Raw HTML content to process.
        use_readability: If True, use readability-lxml for extraction.
            If False, only apply basic HTML cleaning.

    Returns:
        Extracted HTML content containing only the main article body.
        Falls back to basic cleaning if readability extraction fails.
    """
    if not html or not html.strip():
        logger.warning("Empty HTML content provided")
        return html

    if not use_readability:
        return _fallback_clean_html(html)

    try:
        from readability import Document

        doc = Document(html)
        extracted = doc.summary()

        if not extracted or len(extracted.strip()) < 100:
            logger.warning(
                "Readability extraction produced minimal content, using fallback"
            )
            return _fallback_clean_html(html)

        logger.info(
            "Readability extraction reduced HTML from %d to %d chars (%.1f%% reduction)",
            len(html),
            len(extracted),
            (1 - len(extracted) / len(html)) * 100,
        )
        return extracted

    except ImportError:
        logger.error("readability-lxml not installed, using fallback cleaning")
        return _fallback_clean_html(html)
    except Exception as e:
        logger.warning("Readability extraction failed: %s, using fallback", e)
        return _fallback_clean_html(html)


def _fallback_clean_html(html: str) -> str:
    """Basic HTML cleaning when readability is unavailable or fails.

    Removes script, style, and other non-content elements using lxml Cleaner.

    Args:
        html: Raw HTML content to clean.

    Returns:
        Cleaned HTML with scripts, styles, and comments removed.
    """
    try:
        cleaner = Cleaner(
            scripts=True,
            javascript=True,
            comments=True,
            style=True,
            inline_style=True,
            links=False,
            meta=True,
            page_structure=False,
            processing_instructions=True,
            remove_unknown_tags=False,
            safe_attrs_only=False,
        )
        from lxml import html as lxml_html

        doc = lxml_html.fromstring(html)
        cleaned_doc = cleaner.clean_html(doc)
        result = lxml_html.tostring(cleaned_doc, encoding="unicode")
        logger.debug("Fallback cleaning reduced HTML from %d to %d chars", len(html), len(result))
        return result
    except Exception as e:
        logger.warning("Fallback HTML cleaning failed: %s, returning original", e)
        return html


def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    """Estimate token count based on character count.

    Args:
        text: Text to estimate tokens for.
        chars_per_token: Average characters per token (default 4.0).

    Returns:
        Estimated token count.
    """
    return int(len(text) / chars_per_token)


def count_tokens(text: str, tokenizer: "PreTrainedTokenizer") -> int:
    """Count actual tokens using the tokenizer.

    Args:
        text: Text to tokenize.
        tokenizer: HuggingFace tokenizer instance.

    Returns:
        Actual token count.
    """
    return len(tokenizer.encode(text, add_special_tokens=False))


def _find_split_points(html: str) -> list[int]:
    """Find natural split points in HTML at section boundaries.

    Looks for h1, h2, h3 headings, section tags, article tags, and hr elements
    as natural breaking points for chunking.

    Args:
        html: HTML content to analyze.

    Returns:
        List of character positions where splits can occur, sorted ascending.
    """
    split_patterns = [
        r"<h1[^>]*>",  # H1 headings
        r"<h2[^>]*>",  # H2 headings
        r"<h3[^>]*>",  # H3 headings
        r"<section[^>]*>",  # Section elements
        r"<article[^>]*>",  # Article elements
        r"<hr[^>]*>",  # Horizontal rules
        r"<div[^>]*class=[\"'][^\"']*(?:section|chapter|part)[^\"']*[\"'][^>]*>",  # Semantic divs
    ]

    positions: set[int] = set()
    for pattern in split_patterns:
        for match in re.finditer(pattern, html, re.IGNORECASE):
            positions.add(match.start())

    return sorted(positions)


def chunk_html(
    html: str,
    max_tokens: int,
    tokenizer: "PreTrainedTokenizer | None" = None,
    chars_per_token: float = 4.0,
) -> list[str]:
    """Split HTML into chunks at natural boundaries.

    This function splits large HTML documents into smaller chunks that fit
    within the token limit while preserving semantic structure by splitting
    at heading and section boundaries.

    Args:
        html: HTML content to chunk.
        max_tokens: Maximum tokens per chunk.
        tokenizer: Optional tokenizer for accurate counting. If None, uses
            character-based estimation.
        chars_per_token: Average characters per token for estimation
            (used when tokenizer is None).

    Returns:
        List of HTML chunks, each within the token limit.
    """
    if not html or not html.strip():
        return [html] if html else []

    # Check if chunking is needed
    if tokenizer:
        total_tokens = count_tokens(html, tokenizer)
    else:
        total_tokens = estimate_tokens(html, chars_per_token)

    if total_tokens <= max_tokens:
        logger.debug("HTML within token limit (%d <= %d), no chunking needed", total_tokens, max_tokens)
        return [html]

    logger.info("HTML exceeds token limit (%d > %d), chunking at natural boundaries", total_tokens, max_tokens)

    # Find natural split points
    split_points = _find_split_points(html)

    if not split_points:
        # No natural boundaries found, fall back to simple splitting
        logger.warning("No natural split points found, using character-based splitting")
        return _simple_chunk(html, max_tokens, tokenizer, chars_per_token)

    # Add start and end positions
    split_points = [0] + split_points + [len(html)]

    chunks: list[str] = []
    current_chunk_start = 0

    for i in range(1, len(split_points)):
        candidate_end = split_points[i]
        candidate_chunk = html[current_chunk_start:candidate_end]

        if tokenizer:
            candidate_tokens = count_tokens(candidate_chunk, tokenizer)
        else:
            candidate_tokens = estimate_tokens(candidate_chunk, chars_per_token)

        if candidate_tokens > max_tokens:
            # Current chunk would be too large, save previous chunk
            if i > 1 and split_points[i - 1] > current_chunk_start:
                chunk = html[current_chunk_start : split_points[i - 1]]
                if chunk.strip():
                    chunks.append(chunk)
                current_chunk_start = split_points[i - 1]

                # Check if remaining segment is still too large
                remaining = html[current_chunk_start:candidate_end]
                if tokenizer:
                    remaining_tokens = count_tokens(remaining, tokenizer)
                else:
                    remaining_tokens = estimate_tokens(remaining, chars_per_token)

                if remaining_tokens > max_tokens:
                    # Need to split this segment further
                    sub_chunks = _simple_chunk(
                        remaining, max_tokens, tokenizer, chars_per_token
                    )
                    chunks.extend(sub_chunks)
                    current_chunk_start = candidate_end

    # Don't forget the last chunk
    if current_chunk_start < len(html):
        final_chunk = html[current_chunk_start:]
        if final_chunk.strip():
            chunks.append(final_chunk)

    logger.info("Split HTML into %d chunks", len(chunks))
    return chunks


def _simple_chunk(
    text: str,
    max_tokens: int,
    tokenizer: "PreTrainedTokenizer | None" = None,
    chars_per_token: float = 4.0,
) -> list[str]:
    """Simple character-based chunking as fallback.

    Args:
        text: Text to chunk.
        max_tokens: Maximum tokens per chunk.
        tokenizer: Optional tokenizer for accurate counting.
        chars_per_token: Characters per token estimate.

    Returns:
        List of text chunks.
    """
    max_chars = int(max_tokens * chars_per_token)
    chunks: list[str] = []

    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))

        # Try to break at whitespace
        if end < len(text):
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end

    return chunks


def preprocess_html(
    html: str,
    use_readability: bool = True,
    max_tokens: int = 8000,
    enable_chunking: bool = True,
    tokenizer: "PreTrainedTokenizer | None" = None,
) -> list[str]:
    """Full preprocessing pipeline for HTML content.

    Combines readability extraction and chunking into a single function.

    Args:
        html: Raw HTML content to process.
        use_readability: Whether to use readability-lxml for extraction.
        max_tokens: Maximum tokens per chunk (for chunking).
        enable_chunking: Whether to chunk large documents.
        tokenizer: Optional tokenizer for accurate token counting.

    Returns:
        List of preprocessed HTML chunks ready for model inference.
        Returns a single-element list if content fits within limits.
    """
    # Step 1: Extract main content
    extracted = extract_main_content(html, use_readability=use_readability)

    # Step 2: Chunk if needed and enabled
    if enable_chunking:
        chunks = chunk_html(extracted, max_tokens=max_tokens, tokenizer=tokenizer)
    else:
        chunks = [extracted]

    return chunks
