import os
from unittest.mock import patch, MagicMock
from trade_digest.notify.feishu import try_create_feishu_sender, _html_to_feishu_md


def test_try_create_returns_none_when_not_configured(monkeypatch):
    monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
    assert try_create_feishu_sender() is None


def test_try_create_returns_sender_when_configured(monkeypatch):
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://open.feishu.cn/hook/test")
    result = try_create_feishu_sender()
    assert result is not None
    name, sender = result
    assert name == "feishu"


def test_feishu_sender_posts_correct_payload():
    fake_response = MagicMock()
    fake_response.json.return_value = {"StatusCode": 0}
    fake_response.raise_for_status.return_value = None

    with patch.dict(os.environ, {"FEISHU_WEBHOOK_URL": "https://hook.test"}, clear=True):
        result = try_create_feishu_sender()
    _, sender = result

    with patch("trade_digest.notify.feishu.requests.post", return_value=fake_response) as mock_post:
        sender({"html": "<h1>标题</h1><p>内容</p>", "subject": "Test", "plain": "Test"})

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "Test"


def test_html_to_feishu_md_strips_style_attrs_from_adjacent_table_cells():
    """回归测试：<th style="...">/<td style="..."> 相邻单元格之间的分隔符替换
    之前只消费了 "<th"/"<td" 三个字符，导致 style 属性字符串原样泄漏进输出。
    """
    html = (
        '<table><tr>'
        '<th style="text-align:left;padding:10px;">指数</th>'
        '<th style="text-align:right;padding:10px;">最新价</th>'
        '</tr>'
        '<tr>'
        '<td style="padding:10px;">上证指数</td>'
        '<td style="padding:10px;color:#27ae60;">-0.06%</td>'
        '</tr></table>'
    )
    result = _html_to_feishu_md(html)
    assert "style=" not in result
    assert "指数 | 最新价" in result
    assert "上证指数 | -0.06%" in result
