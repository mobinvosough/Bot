import os
import sys
from pathlib import Path
from loguru import logger
from config import settings

LOG_DIR = Path(__file__).parent.parent / "logs"
MAX_LOG_SIZE = 20 * 1024 * 1024


def _rotate_log(log_path: Path):
    if not log_path.exists():
        return
    if log_path.stat().st_size >= MAX_LOG_SIZE:
        rotated = log_path.with_suffix(".log.old")
        if rotated.exists():
            rotated.unlink()
        log_path.rename(rotated)
        log_path.touch()


def setup_logger():
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / "bot.log"

    _rotate_log(log_file)

    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(
        str(log_file),
        level="DEBUG",
        rotation="20 MB",
        retention="7 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} - {message}",
    )
    return logger
