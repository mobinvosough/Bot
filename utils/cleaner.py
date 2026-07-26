import re

DEFAULT_CUSTOM_TAG = "\U0001f916: @mitsellerbot\n\U0001f9d1\u200d\U0001f4bb 24/7 : @MITsupports"

# Matches lines that are ONLY a channel tag reference:
# - Optional non-letter characters (emoji, symbols, whitespace)
# - Then @username at end of line
# Examples: "@channel", "🌎 @channel", "🇮🇱 @channel", "⭕️ @channel"
_TAG_LINE_RE = re.compile(
    r"^\s*[^\w\n]*@[\w]+$",
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
