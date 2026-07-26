import re
import unicodedata

DEFAULT_CUSTOM_TAG = "\U0001f916: @mitsellerbot\n\U0001f9d1\u200d\U0001f4bb 24/7 : @MITsupports"

# Matches standalone link lines
_LINK_RE = re.compile(r"^\s*https?://\S+\s*$")

# VPN / proxy config line patterns
_CONFIG_RE = re.compile(
    r"^\s*(?:"
    r"vless://|vmess://|trojan://|ss://|ssr://|"
    r"hysteria://|hysteria2://|tuic://|"
    r"wg://|wireguard://|openvpn://|"
    r"socks5?://"
    r")",
    re.IGNORECASE,
)

# Emoji/symbol regex for stripping
_EMOJI_RE = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"
    "\U0001F300-\U0001F9FF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\u200d\u20E3"
    "\u2600-\u27BF"
    "\u2B50\u2B55"
    "\u203C\u2049\u2122"
    "\u2139\u2194-\u21AA"
    "\u231A-\u23FA"
    "\u25AA-\u25AB\u25B6\u25C0\u25FB-\u25FE"
    "\u2614-\u2615\u2648-\u2653\u267F"
    "\u2693\u26A1\u26AA-\u26AB\u26BD-\u26BE"
    "\u26C4-\u26C5\u26CE\u26D4\u26EA"
    "\u26F2-\u26F3\u26F5\u26FA\u26FD"
    "\u2702\u2705\u2708-\u270D\u270F"
    "]+",
    re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


def _is_tag_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _LINK_RE.match(s):
        return True

    # Check if line contains exactly one @username
    at_count = s.count("@")
    if at_count != 1:
        return False

    # Strip emoji/symbol/whitespace and see what's left
    stripped = _strip_emoji(s)
    # Remove common filler prefixes: "Join:", "Subscribe:", "More:", etc.
    stripped = re.sub(
        r"^(?:join|subscribe|follow|visit|check|see|more|info|channel|bot|link|tap)"
        r"\s*[:\-=]?\s*",
        "",
        stripped,
        flags=re.IGNORECASE,
    )
    stripped = stripped.strip()

    # After stripping emoji and filler, only @username should remain
    if re.match(r"^@[\w]+$", stripped):
        return True

    return False


def _is_config_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _CONFIG_RE.match(s):
        return True
    if re.match(r"^[A-Za-z0-9+/=]{20,}@", s):
        return True
    return False


def _fold_configs(text: str) -> str:
    lines = text.splitlines()
    result = []
    config_buf = []

    for line in lines:
        stripped = line.strip()
        if _is_config_line(line):
            config_buf.append(stripped)
        elif not stripped and config_buf:
            continue
        else:
            if config_buf:
                result.append("<blockquote>" + "\n".join(config_buf) + "</blockquote>")
                config_buf = []
            result.append(line)

    if config_buf:
        result.append("<blockquote>" + "\n".join(config_buf) + "</blockquote>")

    return "\n".join(result)


def clean_text(text: str | None) -> str | None:
    if not text:
        return text
    lines = text.splitlines()
    cleaned = [line for line in lines if not _is_tag_line(line)]
    result = "\n".join(cleaned).strip()
    return result if result else None


def clean_and_tag(text: str | None, custom_tag: str | None = None) -> str:
    tag = custom_tag or DEFAULT_CUSTOM_TAG
    cleaned = clean_text(text)
    if cleaned:
        folded = _fold_configs(cleaned)
        return f"{folded}\n\n{tag}"
    return tag
