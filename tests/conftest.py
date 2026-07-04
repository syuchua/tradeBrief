import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _dummy_smtp_env(monkeypatch):
    """main.py 调用 resolve_smtp_config() 读取 SMTP 环境变量，虽然测试
    中 send_email 被 mock，但 main.py 启动阶段需要这些变量存在。
    使用显式 SMTP_HOST 模式（不用 SMTP_PROVIDER 预设）避免依赖查表逻辑。"""
    monkeypatch.setenv("SMTP_HOST", "smtp.test.invalid")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test-password")
