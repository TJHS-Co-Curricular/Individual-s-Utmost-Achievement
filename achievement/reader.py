"""读取履历表文件（.xlsx / .pdf），统一转成「行列表」交给 rules.parse_rows。"""
from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

logging.getLogger("pdfminer").setLevel(logging.ERROR)

CJK = r"[　-鿿＀-￯]"


# 有些输入法打出的「⼈」「⼯」是康熙部首（U+2F00–U+2FDF / U+2E80–U+2EFF），看起来一样但比对不到「人」「工」
_RADICAL = re.compile(r"[\u2e80-\u2fdf]")


def fix_radicals(s: str) -> str:
    return _RADICAL.sub(lambda m: unicodedata.normalize("NFKC", m.group()), s)


def _cell(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = fix_radicals(v)
        return v if v.strip() else None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def read_xlsx(path: Path) -> list[dict]:
    """返回 [{name, rows, pdf:False}]，每个工作表一项（跳过「指南」表）。"""
    from python_calamine import CalamineWorkbook

    wb = CalamineWorkbook.from_path(str(path))
    sheets = []
    for name in wb.sheet_names:
        if "指南" in name:
            continue
        try:
            raw = wb.get_sheet_by_name(name).to_python(skip_empty_area=False)
        except Exception:
            continue
        rows = []
        for r in raw:
            row = [_cell(v) for v in r]
            if any(v is not None for v in row):
                rows.append(row)
        sheets.append({"name": name, "rows": rows, "pdf": False})
    return sheets


def _clean(s: str) -> str:
    s = re.sub(rf"(?<={CJK})\s+(?={CJK})", "", fix_radicals(s))
    return s.strip()


def read_pdf(path: Path) -> list[dict]:
    """把 PDF 版履历表按版面位置还原成 [年份, 班级, 学会, 事项] 行。"""
    import pdfplumber

    lines, hdr, G, pre = [], None, 0.0, []
    with pdfplumber.open(str(path)) as pdf:
        for pi, p in enumerate(pdf.pages):
            ws = p.extract_words(keep_blank_chars=True, x_tolerance=1.5, y_tolerance=2)
            if hdr is None:
                h = {w["text"].strip(): (w["x0"] + w["x1"]) / 2 for w in ws
                     if w["text"].strip() in ("年份", "班级", "学会", "事项")}
                if len(h) >= 3 and "年份" in h:
                    hy = [w["top"] for w in ws if w["text"].strip() == "年份"][0]
                    xs = [w["x0"] for w in ws if w["top"] > hy + 5 and re.match(r"\s*(执委|职务)", w["text"])]
                    cx = min(xs) if xs else h.get("事项", 300) - 150
                    hdr = (h["年份"], h.get("班级", h["年份"] + 40), h.get("学会", h["年份"] + 100), cx - 3, hy)
            if hdr is None:
                continue
            rows: dict[int, list] = {}
            for w in sorted(ws, key=lambda w: (round(w["top"] / 3), w["x0"])):
                if pi == 0 and w["top"] <= hdr[4] + 4:
                    pre.append(w["text"])
                    continue
                rows.setdefault(round(w["top"] / 3), []).append(w)
            for k in sorted(rows):
                r = sorted(rows[k], key=lambda w: w["x0"])
                cells = ["", "", "", ""]
                for w in r:
                    if w["x0"] >= hdr[3]:
                        i = 3
                    else:
                        c = (w["x0"] + w["x1"]) / 2
                        i = min(range(3), key=lambda j: abs(c - hdr[j]))
                    cells[i] += (" " if cells[i] and i < 3 else "") + w["text"]
                lines.append((G + r[0]["top"], [_clean(c) for c in cells]))
            G += p.height
    if hdr is None:
        return []
    content = [(y, c[3]) for y, c in lines if c[3]]
    starts = [y for y, t in content if re.match(r"(执委|职务)", t)]
    labels = {0: [], 1: [], 2: []}
    for y, c in lines:
        for i in range(3):
            if c[i]:
                labels[i].append((y, c[i]))
    # 学会名称换行时合并
    merged = []
    for y, t in labels[2]:
        if merged and y - merged[-1][2] < 14:
            merged[-1] = (merged[-1][0], merged[-1][1] + t, y)
        else:
            merged.append((y, t, y))
    labels[2] = [(y, t) for y, t, _ in merged]

    def nearest(i, a, b):
        inside = [t for y, t in labels[i] if a <= y < b]
        if inside:
            return inside[0]
        if not labels[i]:
            return None
        mid = (a + b) / 2
        return min(labels[i], key=lambda l: abs(l[0] - mid))[1]

    bounds = starts + [1e12]
    out = [[" ".join(pre)], ["年份", "班级", "学会", "事项"]]
    for bi in range(len(starts)):
        a, b = bounds[bi], bounds[bi + 1]
        yr, cl, club = nearest(0, a, b), nearest(1, a, b), nearest(2, a, b)
        m = re.search(r"20\d\d", str(yr or ""))
        yr = int(m.group()) if m else yr
        first = True
        for y, t in content:
            if a <= y < b:
                out.append([yr, cl, club, t] if first else [None, None, None, t])
                first = False
    return [{"name": "pdf", "rows": out, "pdf": True}]


def read_any(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext == ".xlsx":
        return read_xlsx(path)
    if ext == ".pdf":
        return read_pdf(path)
    return []
