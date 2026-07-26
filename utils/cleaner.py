import re

DEFAULT_CUSTOM_TAG = "\U0001f916: @mitsellerbot\n\U0001f9d1\u200d\U0001f4bb 24/7 : @MITsupports"

# Matches lines that are ONLY a channel tag reference:
# - Starts with optional whitespace
# - Then optional emoji(s)
# - Then @username
# Examples: "@channel", "🌎@channel", "🇮🇱@channel", "⭕️@channel", "🚨@channel"
_TAG_LINE_RE = re.compile(
    r"^\s*(?:[\U0001F1E0-\U0001F1FF\U0001F300-\U0001F9FF"
    r"\U00002702-\U000027B0\U0000FE00-\U0000FE0F"
    r"\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
    r"\u200d\u20E3\uFE0F\u2003\u2002\u200C]+)?@[\w]+",
    re.UNICODE,
)

# Matches standalone link lines (e.g. "https://t.me/channel/123")
_LINK_RE = re.compile(r"^\s*https?://\S+\s*$")


def clean_text(text: str | None) -> str | None:
    if not text:
        return text
    lines = text.splitlines()
    cleaned = [
        line for line in lines
        if not _TAG_LINE_RE.match(line) and not _LINK_RE.match(line)
    ]
    result = "\n".join(cleaned).strip()
    return result if result else None


def clean_and_tag(text: str | None, custom_tag: str | None = None) -> str:
    tag = custom_tag or DEFAULT_CUSTOM_TAG
    cleaned = clean_text(text)
    if cleaned:
        return f"{cleaned}\n\n{tag}"
    return tag
