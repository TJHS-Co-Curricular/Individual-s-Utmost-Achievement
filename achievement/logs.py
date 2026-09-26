"""运行日志：logs/app.log（满 1 MB 自动换新文件，保留最近 5 个）。

- 启动资料、每次载入的文件数、读取失败的文件、手动调整保存、导出、所有错误都会记下来。
- 黑色窗口只显示警告和错误；--dev 时连每次网页请求也写进日志并显示。
- 程序意外崩溃时，错误内容也会写进日志，方便排查。
"""
from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_NAME = "achievement"
log = logging.getLogger(LOG_NAME)
_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup(log_dir: Path, dev: bool = False) -> Path | None:
    """设置日志。返回日志文件路径（无法写入时返回 None，程序照常运行）。"""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if dev else logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO if dev else logging.WARNING)
    console.setFormatter(logging.Formatter(" [%(levelname)s] %(message)s"))
    root.addHandler(console)

    path = None
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "app.log"
        fh = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        fh.setLevel(logging.DEBUG if dev else logging.INFO)
        fh.setFormatter(logging.Formatter(_FMT, "%Y-%m-%d %H:%M:%S"))
        root.addHandler(fh)
    except OSError as e:   # 例：程序放在只读的位置
        log.warning("无法写入日志文件夹 %s：%s", log_dir, e)
        path = None

    # 网页请求记录（werkzeug）：平时只记警告，--dev 时每次请求都记
    logging.getLogger("werkzeug").setLevel(logging.INFO if dev else logging.WARNING)

    def _hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("程序意外出错", exc_info=(exc_type, exc, tb))

    sys.excepthook = _hook
    threading.excepthook = lambda a: _hook(a.exc_type, a.exc_value, a.exc_traceback)
    return path
