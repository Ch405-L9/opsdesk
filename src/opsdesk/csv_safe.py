"""CSV formula-injection protection for spreadsheet consumers.

Text cells starting with = + - @ tab or CR are prefixed with a single quote on
export and the prefix is removed on import. Numeric columns are never escaped,
so negative amounts round-trip unchanged.
"""
DANGEROUS = ("=", "+", "-", "@", "\t", "\r")
PREFIX = "'"


def escape(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(DANGEROUS) or (text.startswith(PREFIX) and text[1:2] in DANGEROUS):
        return PREFIX + text
    return text


def unescape(text):
    if text.startswith(PREFIX) and text[1:2] in DANGEROUS:
        return text[1:]
    if text.startswith(PREFIX + PREFIX) and text[2:3] in DANGEROUS:
        return text[1:]
    return text
