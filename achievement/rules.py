"""履历表解析 + 手册计分规则。

所有「怎么算」的规则都集中在这个文件：
  - 类别标题识别（CATS）
  - 执委/职务标准化（classify_role / standard_roles）
  - 获奖识别（is_award）
  - 计分规则 R1~R4（compute_exclusions）
  - 统计（compute_stats）
要改规则，改这里即可。
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

# ---------------------------------------------------------------- 类别
CATS = [
    ("role", "执委/职务", r"^(执委层/?中层管理/?联课处工委(/?会员)?|执委层/?中层管理|执委层|职务|中层管理|执委)"),
    ("comm", "筹委", r"^(筹委)"),
    ("extComp", "校外比赛", r"^(参与校外比赛(及|与)奖项|参与校外比赛|校外比赛(及|与)奖项|校外比赛|曾参与社团比赛)"),
    ("intComp", "校内比赛", r"^(参与校内比赛(及|与)奖项|参与校内比赛|校内比赛(及|与)奖项|校内比赛|校内奖项)"),
    ("extAct", "校外活动", r"^(参与校外活动|观看校外活动|校外活动)"),
    ("intAct", "校内活动", r"^(参与校内活动|校内活动)"),
    ("extSvc", "校外服务", r"^(校外服务)"),
    ("intSvc", "校内服务", r"^(校内服务)"),
    ("total", "总服务时数", r"^(总服务时数|服务总时数|服务时数)"),
    ("team", "团内工作/表演", r"^(团内活动的?工作人员(/表演)?|团内工作人员)"),
    ("badge", "考章", r"^(考章)"),
    ("honor", "团内荣誉", r"^(团内荣誉|团内荣耀)"),
]
CATS_RE = [(k, lab, re.compile(rx)) for k, lab, rx in CATS]
CAT_LABEL = {k: lab for k, lab, _ in CATS}
CAT_LABEL["other"] = "其他（未注明类别）"

# 获奖的判断规则在 config/award.json
EMPTY_RE = re.compile(r"^[\s\-—－–_/无nN/A.。、:：]*$")
_WS = re.compile(r"[\s 　​-‏⁠-⁯﻿]+")


def norm(s) -> str:
    return _WS.sub("", str(s))


def match_header(text):
    t = norm(text)
    for key, _, rx in CATS_RE:
        m = rx.match(t)
        if not m:
            continue
        rest = t[m.end():]
        if re.match(r"^[：:]", rest):
            return key, re.sub(r"^[^：:]*[：:]", "", str(text), count=1).strip()
        if rest == "":
            return key, ""
        return None
    return None


def strip_num(s) -> str:
    return re.sub(r"^\s*(\d{1,2}\s*[.．、)）]|\d{1,2}\s+(?=\D)|[•·●▪\-–—]\s*(?=\S))\s*", "", str(s), count=1).strip()


_HOURS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:个)?\s*((?i:小时|hours?|hrs?|h\b))(?:\s*(\d+(?:\.\d+)?)\s*分钟?)?|(\d+(?:\.\d+)?)\s*(?:分钟|(?i:mins?\b)|M\b)")
# 「60M / 120M」这类写法只取斜线前的数字
_HOURS_DENOM = re.compile(r"/\s*\d+(?:\.\d+)?\s*(?:小时|分钟|mins?\b|M\b|hours?|hrs?|h\b)", re.I)


def parse_hours(s):
    vals = []
    for m in _HOURS_RE.finditer(_HOURS_DENOM.sub("", str(s))):
        if m.group(1):
            vals.append(float(m.group(1)) + (float(m.group(3)) / 60 if m.group(3) else 0))
        elif m.group(4):
            vals.append(float(m.group(4)) / 60)
    if not vals:
        return None
    # 「11h，筹备6h，活动5h」：第一个是总数、后面是细分（加起来刚好等于总数）→ 只算总数
    if len(vals) > 2 and abs(vals[0] - sum(vals[1:])) < 0.02:
        return round(vals[0], 2)
    return round(sum(vals), 2)


def year_of(v):
    if v is None:
        return None
    if isinstance(v, (int, float)) and 2000 < v < 2100:
        return int(round(v))
    m = re.search(r"20\d\d", str(v))
    return int(m.group()) if m else None


def _s(v) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


# ---------------------------------------------------------------- 解析一张表
def parse_rows(rows, is_pdf=False):
    yi, hi = 0, -1
    for r in range(min(len(rows), 30)):
        row = rows[r] or []
        j = next((j for j, v in enumerate(row) if v is not None and norm(v) == "年份"), -1)
        if j >= 0:
            yi, hi = j, r
            break
    ci, ki, di = yi + 1, yi + 2, yi + 3
    meta = {}
    for r in range(hi if hi >= 0 else min(6, len(rows))):
        txt = " ".join(_s(v) for v in (rows[r] or []) if v is not None)
        m = re.search(r"姓名[：:]\s*([^\s班学]+(?:\s+[A-Za-z][A-Za-z \-]*)?)", txt)
        if m:
            meta["name"] = m.group(1).strip()
        m = re.search(r"班级[：:]\s*([A-Za-z0-9]+)", txt)
        if m:
            meta["cls"] = m.group(1)
        m = re.search(r"学号[：:]\s*(\d{4,6})", txt)
        if m:
            meta["sid"] = m.group(1)

    blocks = []
    st = {"blk": None, "cat": None, "last": None, "lastYear": None, "lastCls": None}

    def new_block(year, cls, club):
        st["blk"] = {"year": year, "cls": cls, "club": club, "cats": {}, "declaredTotal": None}
        blocks.append(st["blk"])
        st["cat"], st["last"] = None, None

    def add_item(text):
        t = strip_num(text)
        if not t or EMPTY_RE.match(t):
            st["last"] = None
            return
        if st["blk"] is None:
            new_block(st["lastYear"], st["lastCls"], "")
        if t == "0":
            return
        k = st["cat"] or "other"
        if k == "other":
            if re.search(r"执委|干部|主席|财政|秘书", t) and "筹委" not in t:
                k = "role"
            elif re.search(r"筹委|筹主", t):
                k = "comm"
        blk = st["blk"]
        if k == "total":
            h = parse_hours(t)
            if h is None and re.fullmatch(r"\d+(\.\d+)?", norm(t)):
                h = float(norm(t))
            if h is not None:
                blk["declaredTotal"] = (blk["declaredTotal"] or 0) + h
            st["last"] = None
            return
        blk["cats"].setdefault(k, []).append(t)
        st["last"] = (k, len(blk["cats"][k]) - 1)

    def split_lines(s):
        return [x.strip() for x in re.split(r"\r?\n|\r", str(s)) if x.strip()]

    def handle_text(text):
        h = match_header(text)
        if h:
            st["cat"], st["last"] = h[0], None
            if h[1]:
                for l in split_lines(h[1]):
                    handle_line(l)
            return True
        return False

    def handle_line(line):
        if match_header(line):
            handle_text(line)
            return
        if is_pdf and st["last"] and not re.match(r"^\s*\d{1,2}\s*[.．、]", line) and not EMPTY_RE.match(line):
            k, i = st["last"]
            st["blk"]["cats"][k][i] += line
            return
        add_item(line)

    for r in range(hi + 1, len(rows)):
        row = rows[r] or []
        get = lambda i: row[i] if i < len(row) else None
        y = year_of(get(yi))
        club = _s(get(ki)).strip() if get(ki) is not None and _s(get(ki)).strip() else None
        cls = _s(get(ci)).strip() if get(ci) is not None and _s(get(ci)).strip() else None
        blk = st["blk"]
        if y:
            st["lastYear"] = y
            st["lastCls"] = cls or st["lastCls"]
            new_block(y, cls, club or (blk["club"] if blk else ""))
        elif club and blk and club != blk["club"] and not re.fullmatch(r"学会|班级|年份", club):
            new_block(st["lastYear"], cls or st["lastCls"], club)
        row_item = None
        for c in range(di, len(row)):
            v = row[c]
            if v is None or _s(v).strip() == "":
                continue
            s = _s(v)
            flat = re.sub(r"[\r\n]+", "", s)
            whole = match_header(flat)
            if whole and (not whole[1] or not re.search(r"[\r\n]", s)):
                handle_text(flat)
                continue
            lines = split_lines(s)
            if len(lines) > 1 or match_header(lines[0]):
                for l in lines:
                    handle_line(l)
                continue
            if row_item and c > di:  # 同一行右边的格子 = 备注（例如奖项）
                if not EMPTY_RE.match(s):
                    k, i = row_item
                    cur, add = st["blk"]["cats"][k][i], s.strip()
                    # 同一段文字被复制到右边多个格子时（合并格/复制），不要重复接上去
                    if k != "total" and norm(strip_num(add)) not in norm(cur):
                        st["blk"]["cats"][k][i] += " —— " + add
                continue
            if st["cat"] == "total" and not EMPTY_RE.match(s):
                add_item(s)
                continue
            handle_line(s)
            if st["last"]:
                row_item = st["last"]

    out = []
    for b in blocks:
        for k in list(b["cats"]):
            b["cats"][k] = [x.strip() for x in b["cats"][k] if x.strip() and not EMPTY_RE.match(x.strip())]
            if not b["cats"][k]:
                del b["cats"][k]
        itemized, anyh = 0.0, False
        for k in ("extSvc", "intSvc"):
            for it in b["cats"].get(k, []):
                h = parse_hours(it)
                if h is not None:
                    itemized += h
                    anyh = True
        b["itemizedHours"] = round(itemized, 2) if anyh else None
        # 服务时数：优先用学生自填的「总服务时数」；该年没填才用逐项相加（上级 2026-09-24 定，对没逐项写时数的学生较公平）
        b["hours"] = round(b["declaredTotal"], 2) if b["declaredTotal"] is not None else b["itemizedHours"]
        b["club"] = re.sub(r"\s+", " ", _s(b["club"] or "")).strip()
        if b["cats"] or b["hours"]:
            out.append(b)
    return meta, out


def parse_filename(fn: str) -> dict:
    base = re.sub(r"\.(xlsx|pdf)$", "", fn, flags=re.I)
    out = {}
    m = re.match(r"^\s*([A-Z]\d{2}|0\d{2})[\s_\-]+", base, re.I)
    if m:
        out["code"] = m.group(1).upper()
    m = re.search(r"(?:^|[\s_\-])(\d{5})(?=[\s_\-成]|$)", base)
    if m:
        out["sid"] = m.group(1)
    who = base.split(" - ")[-1]
    m = re.match(r"^([㐀-鿿\U00020000-\U0002FFFF]+)-(.+)$", who)
    if m:
        out["cn"], out["en"] = m.group(1), re.sub(r"\(\d+\)$", "", m.group(2)).strip()
    else:
        out["en"] = re.sub(r"\(\d+\)$", "", who).strip()
    return out


# ---------------------------------------------------------------- 执委/职务标准化（手册）
# 「什么职位算什么」全部写在 config/member_rules.json（四、职位归类），这里只负责照表执行。
# 下面只保留文字处理的细节：判断正/副、去掉年份和学会名、把一条拆成几个职位等。
from . import member_rules as MR

_P = r"(?:^|(?<=[正副委会团队社·—\-：:（(]))"
# 标准职称的细节写法（名称来自 member_rules.json 的「标准职称」；这里补上「不要误认成 XX股 / XX小组」的细节）
# 标准职称后面不能接的字（避免把「秘书股」「主席团」当成职称）
_TITLE_AFTER = {"主席": r"(?![股团])", "秘书": r"(?!股|小组|组)", "事务": r"(?!股)", "财政": r"(?!股|小组|组)", "总学长": "", "查账": r"(?!股)"}
_TITLE_NOPREFIX = {"总学长", "查账"}   # 这两个前面接什么字都算


def _title_rx(name, R=None):
    """标准职称的比对方式；「同等写法」（member_rules.json）里的写法也算同一个职称，例：事物、总务 = 事务"""
    alts = (R.title_alias.get(name) if R else None) or [name]
    words = "(?:" + "|".join(map(re.escape, alts)) + ")"
    after = _TITLE_AFTER.get(name, r"(?!股)")
    pre = "" if name in _TITLE_NOPREFIX else _P
    return re.compile(pre + words + after), words


def _side(t, title):
    m = re.search(r"(正|副)(?:执委)?" + title, t)
    if m:
        return m.group(1)
    a = re.search(title + r"(?:股)?[（(](正|副)[）)]", t)
    return a.group(1) if a else ""


def _no_side(t):
    """没写正/副 → 当作正（做法 A）。保留函数名以便日后改规则。"""
    return "正"


def clean_role(t, club_name):
    club = re.sub(r"^[A-E]\d{2}", "", norm(club_name or ""))
    parts = []
    for p in re.split(r"——|--|—|－|–|-|：|:", t):
        p = re.sub(r"^担任", "", p)
        p = re.sub(r"\d{2,4}/\d{2,4}(年度|届|年)?", "", p)
        p = re.sub(r"20\d\d(年度|年|届)?", "", p)
        p = re.sub(r"循人中学|联课活动", "", p)
        if club:
            p = p.replace(club, "")
        p = re.sub(r"执委层|中层管理|中层干部", "", p).replace("执委", "")
        p = re.sub(r"^[A-E]\d{2}", "", p)
        p = re.sub(r"^(的|之)", "", p).strip().lstrip("，,、;；。.")
        if p and not re.fullmatch(r".{0,8}(学会|团|队|社)", p) and not re.fullmatch(r"[\d.、]+", p):
            parts.append(p)
    return "·".join(parts).strip("·")


MID_SPLIT = re.compile(r"[+＋、，,/]|兼")


def _mid_label(p, R):
    p = re.sub(r"^会员[（(](.*)[）)]$", r"\1", p.strip())
    m = re.search(r"(总|正|副|小|中|分)?队长", p)
    if m and not any(w in p.lower() for w in R.mid_words if w not in R.captain_words):
        return m.group(0).replace("正队长", "队长")
    return p


def _classify_mid(t, club_name, R):
    """含中层管理职位的一条：拆出中层管理部分；同一条里的其它职位照原规则分类。"""
    c = clean_role(t, club_name) or t
    c = re.sub(r"^会员[（(](.*)[）)]$", r"\1", c)
    full = c.strip("。.· ")
    c = re.sub(r"[（(][^）)]*[）)]", "", c).strip("。.· ") or c   # 去掉「（已取消，但有进行筹备工作）」这类备注
    if not R.has_mid(c):   # 中层字眼只在括号里，如「家族家长（小组组长）」→ 整条算一个
        return {"mid": [full]}
    for w in R.split_words:   # 规则表里标了「拆开」的，如「校内服务负责人：A、B」→ 每项各算 1 个
        if w in c.lower():
            head = c[c.lower().index(w):c.lower().index(w) + len(w)]
            items = [x.strip("·：: ") for x in re.split(r"[、，,；;/]", c[c.lower().index(w) + len(w):]) if x.strip("·：: ")]
            return {"mid": list(dict.fromkeys(f"{head}·{x}" for x in items)) or [head]}
    if re.match(r"(负责)?(监督|督导)", c):   # 「监督壁报股，多媒体，课程…」：整条都是监督的对象，不拆
        return {"mid": [c]}
    parts = [x for x in (p.strip("·").strip() for p in MID_SPLIT.split(c)) if x]
    mids = [_mid_label(p, R) for p in parts if R.has_mid(p)]
    rest = [p for p in parts if not R.has_mid(p)]
    if not mids:
        mids = [_mid_label(c, R)]
    out = {"mid": list(dict.fromkeys(mids))}
    if rest:
        r = classify_role(rest[0], club_name) if len(rest) == 1 else {"other": "、".join(rest)}
        if r:
            for k in ("std", "other"):
                if r.get(k):
                    out[k] = r[k]
    return out


_CTX_DROP = re.compile(r"^[（(]\d+[）)]|学会|执委|^第[一二三四五]$|【[^】]*】")


def _with_context(std, words, t, club_name):
    """标准职称前面还写了别的单位 / 活动（例：「联课处工委联课表扬大会——副总务」）→ 保留下来：
    执委(联课处工委联课表扬大会-事务(副))。用「+」「兼」连着的另一个职位 → 另外算一个执委(…)。"""
    c = re.sub(r"[。.；;，,]+$", "", clean_role(t, club_name) or t)
    m = re.search(r"(?:正|副)?(?:执委)?(?:正|副)?" + words + r"(?:股)?(?:[（(](?:正|副)[）)])?", c)
    if not m:
        return {"std": std}
    before, after = c[:m.start()], c[m.end():]
    clean = lambda x: _CTX_DROP.sub("", x).strip("·-—–－:：+＋、，, ")
    before, after = clean(before), clean(after)
    if not before and not after:
        return {"std": std}
    if re.search(r"[+＋]|兼", c):   # 「财政+联课处工委」：两个职位
        return {"std": std, "other": "、".join(x for x in (before, after) if x)}
    return {"other": "-".join(x for x in (before, std, after) if x)}


def classify_role(raw, club_name=""):
    """执委栏的一条 → {'std': 标准写法} / {'other': 其它职位名} / {'mid': [中层管理职位…]}（可同时有）或 None。
    按 member_rules.json「四、职位归类」从上往下找第一条符合的规则。"""
    R = MR.get()
    t = norm(raw)
    t = re.sub(r"^\d{1,2}[，,、.．]", "", t)
    t = re.sub(r"[。；;，,.]+$", "", t)
    if not t or EMPTY_RE.match(t) or re.fullmatch(r"[（(]?无[）)]?", t):
        return None
    rule = R.role_rule(t, club_name)
    kind = rule.get("归类") if rule else None
    if kind == "执委":
        return {"std": rule.get("写法") or rule.name}
    if kind == "主席级":
        w = rule.hit_first(t) or "主席"
        return {"std": f"主席({_side(t, re.escape(w)) or _no_side(t)})"}
    if kind == "中层管理":
        r = _classify_mid(t, club_name, R)
        # 显示成「校内服务负责人-新春快闪」（用「-」连接，不用「·」）
        r["mid"] = list(dict.fromkeys(re.sub(r"\s*·\s*", "-", m) for m in r["mid"]))
        return r
    if kind == "会员":
        return {"std": "会员"}
    if not any(w in t.lower() for w in R.not_title):
        for name in R.titles_side + R.titles_plain:
            rx, side_rx = _title_rx(name, R)
            if rx.search(t):
                std = name if name in R.titles_plain else f"{name}({_side(t, side_rx) or _no_side(t)})"
                return _with_context(std, side_rx, t, club_name)
    c = clean_role(t, club_name)
    if not c or c in ("执委", "执委层"):
        return {"std": "执委"}
    return {"other": c}


def standard_roles_from(classified):
    """同一年同一学会的职务 → (执委标准写法清单, 职务数, 中层清单)。
    其它职位合并成一个「执委(A,B)」（计 A、B 两个）；会员不计职务数；
    中层（助理类、授课人类、队长类）另列，中层数 = 不同中层职位的个数。"""
    std, other, mid = [], [], []
    for r in classified:
        if not r:
            continue
        if r.get("other") and r["other"] not in other:
            other.append(r["other"])
        if r.get("std") and r["std"] not in std:
            std.append(r["std"])
        for m in r.get("mid") or []:
            if m not in mid:
                mid.append(m)
    out = [x for x in std if x != "执委" or not other]
    merged = f"执委({','.join(other)})" if other else None
    if merged:
        out.append(merged)
    if len(out) > 1:
        out = [x for x in out if x != "会员"]
    count = sum(len(other) if x == merged else (0 if x == "会员" else 1) for x in out)
    return out, count, mid


# ---------------------------------------------------------------- 获奖识别
def is_award(s) -> bool:
    """比赛条目算不算获奖 → 规则在 award.json"""
    from . import award_rules
    return award_rules.get().why(s) is not None


# ---------------------------------------------------------------- 计分规则（手册）
# R1 以班级为单位的内容/服务/活动/比赛不计 → 见 member_rules.json「一、不计」
# R2 B 类（体育、学术培训队）整年不计；A/C/D/E 类照算
B_NAME_RE = re.compile(r"培训队|篮球|排球|羽球|足球|乒乓|田径|游泳|辩论|口才|时事常识|数学培训")
# R4 比赛须代表本学会 → 各学会关键词写在 award.json「五、比赛是否代表本学会」


def block_class(b) -> str:
    code = b.get("clubCode") or ""
    if code.startswith("B"):
        return "B"
    if not code and B_NAME_RE.search(b.get("clubName") or b.get("club") or ""):
        return "B"
    return code[:1]


def comp_judge(text, code):
    """比赛是否代表本学会（规则在 award.json）：None=计入；"unsure"=待确认；其它字串=不计原因"""
    from . import award_rules
    return award_rules.get().comp_judge(text, code)


def _simp(t):
    t = norm(t)
    t = re.sub(r"^[\d.、，,]+", "", t)
    t = re.sub(r"[。．.，,；;！!“”\"《》()（）\-—–:：]", "", t)
    return re.sub(r"^(参加|参与|代表\S{0,6}参加)", "", t)


# ---------------------------------------------------------------- 执委栏 ↔ 筹委栏 的移动
# 什么要移、什么不计，写在 member_rules.json 的「一、不计」「二、执委栏移到筹委栏」「三、筹委栏移到执委栏」。


def _split_grade_parts(arr):
    """一条里同时写了学会职位和毕联会职位（用逗号隔开）时，拆成两条，只让毕联会那部分不计。"""
    R = MR.get()
    out = []
    for t in arr:
        parts = [p.strip() for p in re.split(r"[，,；;]", t) if p.strip()]
        if len(parts) > 1 and any(R.is_grade(p) for p in parts) and not all(R.is_grade(p) for p in parts):
            out.append("，".join(p for p in parts if not R.is_grade(p)))
            out.extend(p for p in parts if R.is_grade(p))
        else:
            out.append(t)
    return out


def special_label(text, cat=None):
    """特别标记（member_rules.json「五、特别标记」）——只做标记，不改变计分"""
    return MR.get().special_label(norm(text), cat)


def _split_supervise(arr):
    """「执委主席监督成果汇报主席监督《弈德杯》…主席」这种连在一起的，拆成「执委主席」+ 各个「监督…主席」。"""
    out = []
    for t in arr:
        n = norm(t)
        parts = [p for p in re.split(r"(?=监督|督导)", n) if p]
        if len(parts) > 1 and re.fullmatch(r"(执委)?(正|副)?主席|执委(正|副)主席", parts[0]):
            out.extend(parts)
        else:
            out.append(t)
    return out


def _split_mixed_comm(arr, R, col="role"):
    """「A 兼 B」两个职位该放不同栏（一个是筹委、一个是执委 / 中层管理）→ 拆成两条，各自移到该去的栏。
    连接词见 member_rules.json「二」的「拆开连接词」。"""
    if not R.comm_joiners:
        return arr
    rx = re.compile("|".join(map(re.escape, R.comm_joiners)))
    test = R.moves_to_comm if col == "role" else R.moves_to_role
    out = []
    for t in arr:
        parts = [p.strip(" 　。.") for p in rx.split(t) if p.strip(" 　。.")]
        if len(parts) > 1:
            mv = [test(p) for p in parts]
            if any(mv) and not all(mv):
                out.extend(parts)
                continue
        out.append(t)
    return out


def move_event_roles(s):
    R = MR.get()
    for b in s["blocks"]:
        for k in ("role", "comm"):
            if k in b["cats"]:
                b["cats"][k] = _split_grade_parts(b["cats"][k])
        if "role" in b["cats"]:
            b["cats"]["role"] = _split_mixed_comm(_split_supervise(b["cats"]["role"]), R, "role")
        if "comm" in b["cats"]:
            b["cats"]["comm"] = _split_mixed_comm(b["cats"]["comm"], R, "comm")
        roles, comms = b["cats"].get("role", []), b["cats"].get("comm", [])
        to_comm = [t for t in roles if R.moves_to_comm(t)]
        to_role = [t for t in comms if R.moves_to_role(t)]
        if not to_comm and not to_role:
            continue
        new_role = [t for t in roles if t not in to_comm] + to_role
        new_comm = [t for t in comms if t not in to_role] + to_comm
        for k, arr in (("role", new_role), ("comm", new_comm)):
            if arr:
                b["cats"][k] = arr
            else:
                b["cats"].pop(k, None)
        b["movedComm"], b["movedRole"] = to_comm, to_role


def compute_exclusions(s):
    R = MR.get()
    for b in s["blocks"]:
        b["exBlock"] = "B类（体育/学术培训队）不计" if block_class(b) == "B" else None
        b["ex"], b["unsure"] = {}, {}
        for k, arr in b["cats"].items():
            # member_rules.json「一、不计」：班级、毕联会/高三年级组、班级运动会、感恩聚会、运动会义卖……
            b["ex"][k] = [R.exclusion(t, k) for t in arr]

            if k in ("extComp", "intComp"):
                for i, t in enumerate(arr):
                    if b["ex"][k][i]:
                        continue
                    j = comp_judge(t, b.get("clubCode", ""))
                    if j == "unsure":
                        b["unsure"][f"{k}#{i}"] = 1
                    elif j:
                        b["ex"][k][i] = j
    # R3 同年同一比赛写在两个学会 → 只计一次
    seen = {}
    for b in s["blocks"]:
        for k in ("extComp", "intComp"):
            for i, t in enumerate(b["cats"].get(k, [])):
                st = _simp(t)
                if len(st) < 4:
                    continue
                key = f"{b['year']}|{st}"
                if key not in seen:
                    seen[key] = (b, k, i)
                    continue
                p = seen[key]
                from . import award_rules
                A = award_rules.get()
                own_new = A.own(b.get("clubCode"), t)
                own_old = A.own(p[0].get("clubCode"), t)
                drop, keep = (p, (b, k, i)) if (own_new and not own_old) else ((b, k, i), p)
                db, dk, di = drop
                if not db["exBlock"] and not db["ex"][dk][di]:
                    db["ex"][dk][di] = f"双学会重复，只计入 {keep[0].get('clubCode', '')}{keep[0].get('clubName', '')}"
                seen[key] = keep
    # 预先计算每条的属性，供网页即时重算用
    for b in s["blocks"]:
        b["aw"] = {k: [is_award(t) for t in b["cats"].get(k, [])] for k in ("extComp", "intComp") if k in b["cats"]}
        b["hr"] = {k: [parse_hours(t) for t in b["cats"].get(k, [])] for k in ("extSvc", "intSvc") if k in b["cats"]}
        b["rc"] = [classify_role(t, b.get("clubName") or b.get("club")) for t in b["cats"].get("role", [])]
        b["nk"] = {k: [norm(t) for t in arr] for k, arr in b["cats"].items()}
        mc, mr = set(b.get("movedComm") or []), set(b.get("movedRole") or [])
        b["mv"] = {}
        sp = {k: [special_label(t, k) for t in arr] for k, arr in b["cats"].items()}
        b["sp"] = {k: v for k, v in sp.items() if any(v)}
        if mc:
            b["mv"]["comm"] = [t in mc for t in b["cats"].get("comm", [])]
        if mr:
            b["mv"]["role"] = [t in mr for t in b["cats"].get("role", [])]


def item_key(s, b, k, t):
    """手动调整的识别键（网页端用同样的规则，见 template.html 的 itemKey）"""
    return "|".join([str(s["sid"] or s["file"]), str(b["year"] or ""), str(b.get("clubCode") or b.get("clubName") or ""), k, norm(t)])


def item_state(s, b, k, i, ov):
    t = b["cats"][k][i]
    auto = b["exBlock"] or (b["ex"].get(k) or [None] * (i + 1))[i]
    m = (ov or {}).get(item_key(s, b, k, t))
    inc = False if b["exBlock"] else (m == "in" if m else not auto)
    return {"inc": inc, "auto": auto, "manual": None if b["exBlock"] else m,
            "reason": b["exBlock"] or ("手动设为不计" if m == "out" else None if m == "in" else auto),
            "unsure": bool(b["unsure"].get(f"{k}#{i}")) and not m}


def mid_by_block(s, ov=None, year=None):
    bl = [b for b in s["blocks"] if not year or b["year"] == year]
    return [standard_roles_from([b["rc"][i] for i in range(len(b["cats"].get("role", []))) if item_state(s, b, "role", i, ov)["inc"]])[2] for b in bl]


def compute_stats(s, ov=None, year=None):
    bl = [b for b in s["blocks"] if not year or b["year"] == year]
    c = Counter()
    hours = 0.0
    roles_by_block = []
    for b in bl:
        for k, arr in b["cats"].items():
            for i, _ in enumerate(arr):
                x = item_state(s, b, k, i, ov)
                if x["unsure"]:
                    c["unsure"] += 1
                if x["inc"]:
                    c[k] += 1
                    if k in ("extComp", "intComp") and b["aw"][k][i]:
                        c["extAwards" if k == "extComp" else "intAwards"] += 1
        rl, rc, ml = standard_roles_from([b["rc"][i] for i in range(len(b["cats"].get("role", []))) if item_state(s, b, "role", i, ov)["inc"]])
        roles_by_block.append(rl)
        c["roles"] += rc
        c["mid"] += len(ml)
        if b["exBlock"]:
            continue
        # 服务时数 = 该年采用的时数（自填总数优先），再扣掉不计入的服务项的时数
        h = b["hours"] or 0
        for k in ("extSvc", "intSvc"):
            for i, _ in enumerate(b["cats"].get(k, [])):
                if not item_state(s, b, k, i, ov)["inc"] and b["hr"][k][i]:
                    h -= b["hr"][k][i]
        hours += max(0.0, h)
    out = {k: c[k] for k in ("roles", "mid", "comm", "extComp", "intComp", "extAct", "intAct", "extSvc", "intSvc", "team", "badge", "honor", "unsure", "extAwards", "intAwards")}
    out["awards"] = out["extAwards"] + out["intAwards"]
    out["hours"] = round(hours, 2)
    return out, roles_by_block


# ---------------------------------------------------------------- 学生记录
def build_student(file, meta, blocks):
    fn = parse_filename(file)
    blocks.sort(key=lambda b: -(b["year"] or 0))
    latest = blocks[0] if blocks else {}
    code = fn.get("code")
    if not code or code in ("099", "2026"):
        m = re.match(r"^([A-E]\d{2})", latest.get("club") or "")
        if m:
            code = m.group(1)
    cls = next((b["cls"] for b in blocks if b["year"] == latest.get("year") and b["cls"]), None) or meta.get("cls") or ""
    issues = []
    if not blocks:
        issues.append("未能读取任何年份资料")
    if any("other" in b["cats"] for b in blocks):
        issues.append("有未归类的条目")
    return {
        "file": file, "sid": fn.get("sid") or meta.get("sid") or "",
        "cn": fn.get("cn") or (meta.get("name") or "").split(" ")[0], "en": fn.get("en") or "",
        "code": code or "", "club": latest.get("club") or "", "cls": _s(cls).upper(),
        "years": [b["year"] for b in blocks if b["year"]], "blocks": blocks, "issues": issues,
    }


def _richness(s):
    return sum(len(a) for b in s["blocks"] for a in b["cats"].values())


def dedupe(students):
    by = defaultdict(list)
    for s in students:
        by[s["sid"] or s["file"]].append(s)
    out = []
    for arr in by.values():
        arr.sort(key=lambda s: (-_richness(s), len(s["file"])))
        main = arr[0]
        main["otherFiles"] = [x["file"] for x in arr[1:]]
        if len(arr) > 1:
            main["issues"].append(f"有 {len(arr)} 个版本，已采用内容最多的一个")
        out.append(main)
    return out


def finalize(students):
    """统一学会代号/名称，套用计分规则，算出统计。"""
    split = lambda c: (lambda m: (m.group(1), m.group(2).strip()) if m else (None, str(c or "").strip()))(re.match(r"^([A-E]\d{2})\s*(.*)$", str(c or "")))
    code_name, name_code = defaultdict(Counter), defaultdict(Counter)
    for s in students:
        for b in s["blocks"]:
            c, n = split(b["club"])
            code = c or (s["code"] if s["code"] and b is s["blocks"][0] else None)
            if code and n:
                code_name[code][n] += 1
                name_code[n][code] += 1
    top = lambda cnt: cnt.most_common(1)[0][0] if cnt else None
    for s in students:
        for b in s["blocks"]:
            c, n = split(b["club"])
            if not c and n:
                c = top(name_code.get(n, Counter()))
            if c and not n:
                n = top(code_name.get(c, Counter()))
            if not c and n:
                for cc, nn in code_name.items():
                    t = top(nn)
                    if t and len(t) >= 2 and (t in n or n in t):
                        c = cc
                        break
            if not c and not n and re.fullmatch(r"[A-E]\d{2}", s["code"] or ""):
                c = s["code"]
            b["clubCode"] = c or ""
            b["clubName"] = n or b["club"] or (top(code_name.get(c, Counter())) if c else "") or ""
        if not re.fullmatch(r"[A-E]\d{2}", s["code"] or ""):
            s["code"] = s["blocks"][0]["clubCode"] if s["blocks"] else ""
        move_event_roles(s)
        compute_exclusions(s)
        s["special"] = sorted({x for b in s["blocks"] for v in b["sp"].values() for x in v if x})
        st, rbb = compute_stats(s)
        for b, rl in zip(s["blocks"], rbb):
            b["roleStd"] = rl
        s["stats"] = st
        s["roleLatest"] = next(("、".join(rl) for rl in rbb if rl), "")
        s["club"] = top(code_name.get(s["code"], Counter())) or (s["blocks"][0]["clubName"] if s["blocks"] else "")
        seen = []
        for b in s["blocks"]:
            x = ((b["clubCode"] + " ") if b["clubCode"] else "") + b["clubName"]
            if x.strip() and x not in seen:
                seen.append(x)
        s["clubs"] = seen
    students.sort(key=lambda s: (s["code"], s["sid"]))
    return students
