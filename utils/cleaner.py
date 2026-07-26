import re

DEFAULT_CUSTOM_TAG = "\U0001f916: @mitsellerbot\n\U0001f9d1\u200d\U0001f4bb 24/7 : @MITsupports"


def clean_text(text: str | None) -> str | None:
    if not text:
        return text
    lines = text.splitlines()
    cleaned = [line for line in lines if not re.match(r"^\s*(@|\U0001f194@)", line)]
    result = "\n".join(cleaned).strip()
    return result if result else None


def clean_and_tag(text: str | None, custom_tag: str | None = None) -> str:
    tag = custom_tag or DEFAULT_CUSTOM_TAG
    cleaned = clean_text(text)
    if cleaned:
        return f"{cleaned}\n\n{tag}"
    return tag
