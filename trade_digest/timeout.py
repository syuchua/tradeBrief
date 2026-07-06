# trade_digest/timeout.py
"""通用超时执行工具 —— 防御网络调用静默挂起。

普通 try/except 只能捕获"抛出异常"的失败；如果被调用方接受了连接却一直
不响应也不断开（常见于境外 IP 被国内数据源限流/静默丢包），调用会挂起
到操作系统级 TCP 超时（可能长达数分钟），任何 except 分支都救不了。
with_timeout() 在独立线程中运行目标函数，超过 timeout 秒仍未返回就直接
放弃等待并抛出 TimeoutError，交给调用方原有的 except Exception 分支
统一降级处理。
"""
import queue
import threading
from typing import Callable, TypeVar

T = TypeVar("T")

DEFAULT_TIMEOUT_SECONDS = 20.0


def with_timeout(func: Callable[..., T], *args, timeout: float = DEFAULT_TIMEOUT_SECONDS, **kwargs) -> T:
    """运行 func(*args, **kwargs)，超过 timeout 秒未返回则抛出 TimeoutError。

    使用守护线程（daemon=True）执行调用：即使目标函数真的永久挂起，也不会
    阻止 Python 进程退出——线程随进程退出而终止，调用方不需要、也无法主动
    杀死它，只需要放弃等待、继续往下走。
    """
    result_queue: "queue.Queue[tuple[str, object]]" = queue.Queue(maxsize=1)

    def _target():
        try:
            result_queue.put(("ok", func(*args, **kwargs)))
        except Exception as exc:
            result_queue.put(("error", exc))

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        func_name = getattr(func, "__name__", repr(func))
        raise TimeoutError(f"{func_name} timed out after {timeout}s")

    status, value = result_queue.get_nowait()
    if status == "error":
        raise value
    return value
