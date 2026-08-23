import html
import re
import unicodedata
import urllib.parse


class UnicodeNormalizationError(Exception):
    pass

def secure_normalize(text: str, max_decode_passes: int = 3, max_length: int = 500_000) -> str:
    """
    Normalizes text to prevent bypass via homoglyphs, zero-width chars, or odd spaces.
    Bounds decoding and length to prevent DoS attacks.
    """
    if not text:
        return ""

    # 1. Length Bound (Prevent DoS)
    if len(text) > max_length:
        raise UnicodeNormalizationError(f"Text length ({len(text)}) exceeds maximum allowed ({max_length}).")

    # 2. Bounded Decoding
    decoded = text
    for _ in range(max_decode_passes):
        prev = decoded
        decoded = urllib.parse.unquote(decoded)
        decoded = html.unescape(decoded)
        if prev == decoded:
            break

    # 3. Unicode Normalization & Case Folding
    # NFKC normalizes compatibility characters (e.g., fullwidth chars)
    normalized = unicodedata.normalize('NFKC', decoded).casefold()

    # 3.5 Homoglyph Mapping
    # Map common Cyrillic/Greek characters that look like Latin characters
    homoglyphs = str.maketrans("асеорхуі", "aceopxyi")
    normalized = normalized.translate(homoglyphs)

    # 4. Strip Zero-Width and Control Characters
    # Removes zero-width spaces, joiners, non-joiners, BOM, etc.
    # Detects BiDi overrides
    if re.search(r'[\u202A-\u202E\u2066-\u2069]', normalized):
        raise UnicodeNormalizationError("BiDi override characters detected. Possible payload obfuscation.")

    normalized = re.sub(r'[\u200b\u200c\u200d\uFEFF]', '', normalized)

    # 5. Collapse Whitespace
    normalized = re.sub(r'\s+', ' ', normalized)

    return normalized

def aggressive_normalize_for_banlist(text: str, max_decode_passes: int = 3, max_length: int = 500_000) -> str:
    """
    Strips all whitespace and punctuation for strict substring matching
    to defeat spacing and punctuation attacks (e.g., 'b.a.d', 'b a d').
    """
    normalized = secure_normalize(text, max_decode_passes, max_length)

    # Remove all punctuation
    normalized = re.sub(r'[^\w\s]|_', '', normalized)

    # Remove spaces
    normalized = normalized.replace(" ", "")

    return normalized
