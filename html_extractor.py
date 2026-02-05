"""HTML to Markdown extraction module with multi-tier fallback.

This module provides CPU-only HTML to Markdown conversion using a 3-tier
fallback chain: Trafilatura → readability-lxml + markdownify → lxml Cleaner
+ markdownify. No GPU or ML model required.
"""

import logging

from lxml.html.clean import Cleaner
from markdownify import markdownify as md

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Raised when all extraction tiers fail."""


def extract_to_markdown(
    html: str,
    url: str | None = None,
    include_links: bool = True,
    include_images: bool = True,
) -> str:
    """Extract main content from HTML and convert to Markdown.

    Uses a 3-tier fallback chain:
    1. Trafilatura (best F1, native markdown output)
    2. readability-lxml + markdownify (reliable fallback)
    3. lxml Cleaner + markdownify (last resort)

    Args:
        html: Raw HTML content to extract from.
        url: Optional source URL for resolving relative links.
        include_links: Whether to preserve hyperlinks in output.
        include_images: Whether to preserve images in output.

    Returns:
        Extracted content as a Markdown string.

    Raises:
        ExtractionError: If all extraction tiers fail to produce output.
    """
    if not html or not html.strip():
        raise ExtractionError("Empty HTML content provided")

    # Tier 1: Trafilatura
    result = _extract_with_trafilatura(html, url)
    if result:
        return result

    # Tier 2: readability-lxml + markdownify
    result = _extract_with_readability(html, include_links, include_images)
    if result:
        return result

    # Tier 3: lxml Cleaner + markdownify (last resort)
    result = _extract_with_lxml_cleaner(html, include_links, include_images)
    if result:
        return result

    raise ExtractionError("All extraction tiers failed to produce output")


def _extract_with_trafilatura(html: str, url: str | None = None) -> str | None:
    """Tier 1: Extract using Trafilatura with native markdown output.

    Args:
        html: Raw HTML content.
        url: Optional source URL for link resolution.

    Returns:
        Markdown string or None if extraction failed.
    """
    try:
        import trafilatura

        result = trafilatura.extract(
            html,
            url=url,
            output_format="markdown",
            include_links=True,
            include_images=True,
            include_tables=True,
            favor_recall=True,
        )

        if result and len(result.strip()) > 0:
            logger.info(
                "Trafilatura extraction succeeded: %d chars", len(result)
            )
            return result.strip()

        logger.warning("Trafilatura returned empty result, falling through")
        return None

    except ImportError:
        logger.error("trafilatura not installed, skipping tier 1")
        return None
    except Exception as e:
        logger.warning("Trafilatura extraction failed: %s, falling through", e)
        return None


def _extract_with_readability(
    html: str,
    include_links: bool = True,
    include_images: bool = True,
) -> str | None:
    """Tier 2: Extract using readability-lxml + markdownify.

    Args:
        html: Raw HTML content.
        include_links: Whether to preserve hyperlinks.
        include_images: Whether to preserve images.

    Returns:
        Markdown string or None if extraction failed.
    """
    try:
        from readability import Document

        doc = Document(html)
        extracted_html = doc.summary()

        if not extracted_html or len(extracted_html.strip()) < 50:
            logger.warning(
                "Readability produced minimal content (%d chars), falling through",
                len(extracted_html.strip()) if extracted_html else 0,
            )
            return None

        markdown = md(
            extracted_html,
            strip=["img"] if not include_images else None,
            convert=["a"] if include_links else None,
        )

        if markdown and len(markdown.strip()) > 0:
            logger.info(
                "Readability + markdownify extraction succeeded: "
                "%d HTML chars → %d markdown chars",
                len(extracted_html),
                len(markdown),
            )
            return markdown.strip()

        logger.warning("Readability + markdownify returned empty, falling through")
        return None

    except ImportError as e:
        logger.error("readability-lxml or markdownify not installed: %s", e)
        return None
    except Exception as e:
        logger.warning(
            "Readability + markdownify extraction failed: %s, falling through", e
        )
        return None


def _extract_with_lxml_cleaner(
    html: str,
    include_links: bool = True,
    include_images: bool = True,
) -> str | None:
    """Tier 3: Extract using lxml Cleaner + markdownify (last resort).

    Args:
        html: Raw HTML content.
        include_links: Whether to preserve hyperlinks.
        include_images: Whether to preserve images.

    Returns:
        Markdown string or None if extraction failed.
    """
    try:
        from lxml import html as lxml_html

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

        doc = lxml_html.fromstring(html)
        cleaned_doc = cleaner.clean_html(doc)
        cleaned_html = lxml_html.tostring(cleaned_doc, encoding="unicode")

        markdown = md(
            cleaned_html,
            strip=["img"] if not include_images else None,
            convert=["a"] if include_links else None,
        )

        if markdown and len(markdown.strip()) > 0:
            logger.info(
                "lxml Cleaner + markdownify extraction succeeded: "
                "%d HTML chars → %d markdown chars",
                len(html),
                len(markdown),
            )
            return markdown.strip()

        logger.warning("lxml Cleaner + markdownify returned empty")
        return None

    except Exception as e:
        logger.warning("lxml Cleaner + markdownify extraction failed: %s", e)
        return None
