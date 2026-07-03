import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _dummy_smtp_env(monkeypatch):
    """main.py reads SMTP_HOST/USER/PASSWORD directly (not inside the mocked
    send_email), so these must exist even though send_email itself is always
    mocked in tests. Values are placeholders only, never used for a real
    connection."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test.invalid")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test-password")
