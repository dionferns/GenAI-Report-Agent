"""PII scrubbing utilities."""

import re


def scrub(text: str) -> str:
    """
    Detect and replace PII before sending to LLM.
    Returns sanitized string.
    """
    # Email addresses
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", text)

    # UK phone numbers (various formats)
    text = re.sub(r"\b(?:\+44|0)[0-9]{10,11}\b", "[PHONE]", text)

    # UK National Insurance numbers (format: 2 letters, 6 numbers, 1 letter)
    text = re.sub(r"\b[A-Z]{2}[0-9]{6}[A-Z]\b", "[NI_NUMBER]", text)

    # UK postcodes (simplified pattern)
    text = re.sub(
        r"\b[A-Z]{1,2}[0-9]{1,2}[A-Z]?\s?[0-9][A-Z]{2}\b",
        "[POSTCODE]",
        text,
        flags=re.IGNORECASE,
    )

    return text
