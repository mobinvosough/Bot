from datetime import datetime


def parse_admin_ids(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


def now_utc() -> str:
    return datetime.utcnow().isoformat()
