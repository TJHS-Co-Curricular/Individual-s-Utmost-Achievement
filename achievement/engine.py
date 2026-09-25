"""读取整个 Result 文件夹：多线程解析 + 按 (修改时间, 大小) 缓存，没改过的文件不重复解析。"""
from __future__ import annotations

import copy
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import award_rules, member_rules, rules
from .reader import read_any

_cache: dict[str, tuple[int, int, dict | None, str | None]] = {}
_cache_lock = threading.Lock()
_load_lock = threading.Lock()


def list_files(folder: Path):
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() in (".xlsx", ".pdf") and not p.name.startswith(("~$", ".")))


def batch_folders(folder: Path) -> list[tuple[str, Path]]:
    """Result 里的「届别」：直接放在 Result 的文件算一批（名称 ""），每个子文件夹（例：2025、2026）各算一届。"""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    out = [("", folder)] if list_files(folder) else []
    subs = [p for p in folder.iterdir() if p.is_dir() and not p.name.startswith((".", "~")) and list_files(p)]
    return out + [(p.name, p) for p in sorted(subs, key=lambda p: p.name)]


def current_folder(folder: Path) -> Path:
    """网站要读的文件夹：Result 里直接有履历表 → 就是 Result；
    只有年份子文件夹（例：2025、2026）→ 读最新的一届（名称最大的那个）。"""
    b = batch_folders(folder)
    if not b or b[0][0] == "":
        return Path(folder)
    return b[-1][1]


def load_batches(folder: Path) -> dict:
    """每一届分开读取（参考清单用）→ {届别: 学生清单}"""
    return {name or "Result": load_folder(p)[0] for name, p in batch_folders(folder)}


def folder_version(folder: Path) -> str:
    """文件夹内容指纹（文件名 + 修改时间 + 大小），任何增删改都会改变它。"""
    h = hashlib.md5()
    h.update(member_rules.fingerprint().encode("utf-8"))   # 改了 member_rules.json / award.json 也要重算
    h.update(award_rules.fingerprint().encode("utf-8"))
    for p in list_files(folder):
        try:
            st = p.stat()
        except OSError:
            continue
        h.update(f"{p.name}|{st.st_mtime_ns}|{st.st_size}\n".encode("utf-8"))
    return h.hexdigest()[:16]


def _content_count(blocks):
    return sum(len(a) for b in blocks for a in b["cats"].values())


def _parse_uncached(p: Path):
    best = None
    for sh in read_any(p):
        meta, blocks = rules.parse_rows(sh["rows"], sh["pdf"])
        if best is None or _content_count(blocks) > _content_count(best[1]):
            best = (meta, blocks)
    if best is None:
        raise ValueError("没有可读取的工作表")
    return rules.build_student(p.name, *best)


def parse_file(p: Path):
    """返回 (学生资料 或 None, 错误讯息 或 None)。坏文件不会让整体出错。"""
    try:
        st = p.stat()
    except OSError as e:
        return None, str(e)
    key = str(p.resolve())
    with _cache_lock:
        hit = _cache.get(key)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
        return hit[2], hit[3]
    try:
        raw, err = _parse_uncached(p), None
    except Exception as e:  # noqa: BLE001
        raw, err = None, f"{type(e).__name__}: {e}"
    with _cache_lock:
        _cache[key] = (st.st_mtime_ns, st.st_size, raw, err)
    return raw, err


def load_folder(folder: Path):
    files = list_files(folder)
    with _load_lock:
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(parse_file, files))
    students, failed = [], []
    for p, (raw, err) in zip(files, results):
        if err:
            failed.append((p.name, err))
        else:
            students.append(copy.deepcopy(raw))
    students = rules.finalize(rules.dedupe(students))
    return students, files, failed
