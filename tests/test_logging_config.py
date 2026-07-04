from trade_digest.logging_config import setup_logging


def test_setup_logging_creates_log_file(tmp_path):
    log_dir = tmp_path / "logs"
    setup_logging(log_dir)
    log_file = log_dir / "trade_digest.log"
    # After setup, the file should exist (created by TimedRotatingFileHandler on first emit)
    import logging
    logging.getLogger("test").info("test message")
    assert log_file.exists()
