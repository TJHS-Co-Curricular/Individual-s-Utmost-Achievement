"""网站用的资料：读取 Result（有变动才重读）、手动调整（data/成就奖_手动调整.json）、参考清单资料。"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime

from .engine import current_folder, folder_version, load_batches, load_folder
from .paths import Dirs

log = logging.getLogger(__name__)


class Store:
    def __init__(self, dirs: Dirs):
        self.dirs = dirs
        self.lock = threading.Lock()
        self.version: str | None = None
        self.students: list = []
        self.files: list = []
        self.failed: list = []
        self.when = ""
        self._failed_logged: set = set()

    # ---- Result ----------------------------------------------------------
    @property
    def base(self):
        return self.dirs.result

    def folder(self):
        """Result 里只有年份子文件夹时，读最新一届"""
        return current_folder(self.base)

    def refresh(self, force: bool = False) -> str:
        """文件夹或规则有变动才重新整理（没改过的文件由 engine 的缓存直接取用）。"""
        src = self.folder()
        v = folder_version(src) + str(src)
        with self.lock:
            if force or v != self.version:
                self.students, self.files, self.failed = load_folder(src)
                self.version = v
                self.when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log.info("载入 %s：%d 个文件，%d 位学生，%d 个读取失败",
                         src, len(self.files), len(self.students), len(self.failed))
                for name, err in self.failed:
                    if (name, err) not in self._failed_logged:
                        self._failed_logged.add((name, err))
                        log.warning("读取失败：%s → %s", name, err)
        return self.version

    def info(self) -> dict:
        return {"files": len(self.files), "when": self.when, "version": self.version,
                "fail": [list(x) for x in self.failed], "folder": str(self.folder())}

    def ref_data(self):
        """参考清单（职位一览 / 获奖一览）的资料：Result 里有好几届（年份子文件夹）就每届分开列出次数；
        只有一批 → 照旧。"""
        b = load_batches(self.base)
        return b if len(b) > 1 else (next(iter(b.values())) if b else self.students)

    # ---- 手动调整 ----------------------------------------------------------
    def load_ov(self) -> dict:
        p = self.dirs.overrides
        if not p.is_file():
            return {}
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return {k: v for k, v in d.items() if v in ("in", "out")}
        except Exception as e:  # noqa: BLE001
            log.error("手动调整文件读取失败（格式有误？）%s：%s", p, e)
            return {}

    def save_ov(self, ov: dict) -> int:
        clean = {k: v for k, v in ov.items() if v in ("in", "out")}
        self.dirs.ensure("data")
        p = self.dirs.overrides
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)
        log.info("手动调整已保存：%d 项 → %s", len(clean), p)
        return len(clean)
