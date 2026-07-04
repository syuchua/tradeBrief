# trade_digest/logging_config.py
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path | None = None) -> None:
    """Configure logging to both console and rotating file.

    The log file rotates daily and keeps 30 days of history.
    """
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "state"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "trade_digest.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler（保留现有行为）
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        root_logger.addHandler(console)

    # File handler（每日轮转，保留 30 天）
    if not any(isinstance(h, TimedRotatingFileHandler) for h in root_logger.handlers):
        file_handler = TimedRotatingFileHandler(
            str(log_file),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        root_logger.addHandler(file_handler)
