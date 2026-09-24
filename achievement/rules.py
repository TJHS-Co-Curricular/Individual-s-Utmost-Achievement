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
    ("role", "执委/职务", r"^(执委层/?中层管理/?联课处工委|执委层/?中层管理|执委层|职务|中层管理|执委)"),
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

AWARD_RE = re.compile(
    r"(冠军|亚军|季军|殿军|金奖|银奖|铜奖|金牌|银牌|铜牌|优秀奖|佳作|优胜|优等|特优|甲等|乙等|一等|二等|三等|荣誉奖|鼓励奖|入围|"
    r"第[一二三四五六七八九十\d]+名|前[一二三四五六七八九十\d]+名|最佳|Gold|Silver|Bronze|Champion|Merit|Distinction|金榜|金质|银质|铜质|"
    r"安慰奖|Hadiah|[甲乙丙][上中]|表现优异)", re.I)
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
    total, found = 0.0, False
    for m in _HOURS_RE.finditer(_HOURS_DENOM.sub("", str(s))):
        found = True
        if m.group(1):
            total += float(m.group(1))
            if m.group(3):
                total += float(m.group(3)) / 60
        elif m.group(4):
            total += float(m.group(4)) / 60
    return round(total, 2) if found else None


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
# 标准职称：主席/秘书/事务/财政（正/副）、查账、总学长（正/副）、助理总学长、执委、会员、队长、副队长
# 其它职位 → 执委(XXX,XXX)；主席等没写正/副 → 当作正（上级 2026-09-24 定：做法 A）
# 童军等「分团」职位（如 狮子分团--秘书）→ 一律标「执委」（上级 2026-09-24）
NOT_TITLE = re.compile(r"助理(?!总学长)|培训|监督|督导|顾问|候选|实习|筹委|筹主|《|活动|比赛|营|欢送会|汇报|晚会|庆典|公演|聚会|毕联会|毕业班联合会|工委会|班级|委员|小组")
_P = r"(?:^|(?<=[正副委会团队社·—\-：:（(]))"
TITLES = [
    ("主席", re.compile(_P + r"主席(?![股团])"), "主席"),
    ("秘书", re.compile(_P + r"秘书(?!股|小组|组)"), "秘书"),
    ("事务", re.compile(_P + r"事[务物](?!股)"), "事[务物]"),
    ("财政", re.compile(_P + r"财政(?!股|小组|组)"), "财政"),
]


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
        p = re.sub(r"^(的|之)", "", p).strip()
        if p and not re.fullmatch(r".{0,8}(学会|团|队|社)", p) and not re.fullmatch(r"[\d.、]+", p):
            parts.append(p)
    return "·".join(parts).strip("·")


def _fentuan_label(t):
    """童军分团职位的显示名：狮子分团--秘书 → 狮子分团秘书；老虎分团——分团秘书 → 老虎分团秘书"""
    x = re.sub(r"^担任", "", t)
    x = re.sub(r"\d{2,4}/\d{2,4}(年度|届|年)?|20\d\d(年度|年|届)?", "", x)
    x = re.sub(r"——|--|—|－|–|-|：|:|\s", "", x)
    return re.sub(r"分团分团", "分团", x)


def classify_role(raw, club_name=""):
    """返回 {'std': 标准写法} 或 {'other': 其它职位名} 或 None"""
    t = norm(raw)
    t = re.sub(r"^\d{1,2}[，,、.．]", "", t)
    t = re.sub(r"[。；;，,.]+$", "", t)
    if not t or EMPTY_RE.match(t) or re.fullmatch(r"[（(]?无[）)]?", t):
        return None
    if "助理总学长" in t:
        return {"std": "助理总学长"}
    if re.search(r"会员|团员|队员", t) and "组员" not in t:
        return {"std": "会员"}
    # 上级 2026-09-24：童军「分团」职位、监督/督导/顾问/教练/领队类、小队长/中队长/分队长 → 一律算「会员」
    if "分团" in t or SUPERVISE.search(t) or (re.search(r"小队|中队|分队", t) and "长" in t):
        return {"std": "会员"}
    # 上级 2026-09-24：合唱团「音乐主席」、二十四节令鼓队的队长类，等级与执委主席相同
    if "音乐主席" in t:
        return {"std": f"主席({_side(t, '音乐主席') or _no_side(t)})"}
    if "节令鼓" in norm(club_name or "") + t and re.search(r"队长", t):
        return {"std": f"主席({'副' if '副队长' in t else '正'})"}
    if not NOT_TITLE.search(t):
        if "总学长" in t:
            s = _side(t, "总学长")
            return {"std": f"总学长({s or _no_side(t)})"}
        if re.search(r"(?<![小中分])副队长", t):
            return {"std": "副队长"}
        if re.search(r"(?<![小中分组])队长", t):
            return {"std": "队长"}
        for title, rx, side_rx in TITLES:
            if rx.search(t):
                s = _side(t, side_rx)
                return {"std": f"{title}({s or _no_side(t)})"}
        if re.search(r"查账(?!股)", t):
            return {"std": "查账"}
    c = clean_role(t, club_name)
    if not c or c in ("执委", "执委层"):
        return {"std": "执委"}
    return {"other": c}


def standard_roles_from(classified):
    """同一年同一学会的职务 → 标准写法清单 + 职务数。
    其它职位合并成一个「执委(A,B)」（计 A、B 两个）；童军分团职位是独立的「执委(XXX)」，不合并。"""
    std, other = [], []
    for r in classified:
        if not r:
            continue
        if "other" in r:
            if r["other"] not in other:
                other.append(r["other"])
        elif r["std"] not in std:
            std.append(r["std"])
    out = [x for x in std if x != "执委" or not other]
    merged = f"执委({','.join(other)})" if other else None
    if merged:
        out.append(merged)
    if len(out) > 1:
        out = [x for x in out if x != "会员"]
    count = sum(len(other) if x == merged else (0 if x == "会员" else 1) for x in out)
    return out, count


# ---------------------------------------------------------------- 获奖识别
def is_award(s) -> bool:
    s = str(s)
    if AWARD_RE.search(s) or re.search(r"[八四十]强|半决赛|决赛入围|Honou?rable|mention|表扬奖|medal", s, re.I):
        return True
    parts = re.split(r"——|--|—|–|－|：|:|\s-\s|(?<=\S)-(?=\S*奖)", s)
    if len(parts) > 1 and re.search(r"奖|名次|第\S*名|强", "".join(parts[1:])):
        return True
    return bool(re.search(r"(获得?|荣获|赢得).{0,12}(奖|名|冠|强)", s))


# ---------------------------------------------------------------- 计分规则（手册）
# R1 以班级为单位的内容/服务/活动/比赛不计（学会的筹委、团内工作照算）
# 另外列出校内班级赛的活动名称（条目里可能没写「班级」两字）
CLASS_RE = re.compile(r"班级|班际|班长|班代|班委|班会|全班|本班|班务|康乐委员|学艺委员|常务委员|事务委员|班歌|班服|班旗|心动不如\s*sing\s*动|开启你的\s*music\s*show|运动会.{0,6}(?:写生|号码布|短片)", re.I)  # 运动会写生/号码布设计/短片制作比赛属班级活动（上级 2026-09-24）
CLASS_EXEMPT = {"comm", "team"}
# R2 B 类（体育、学术培训队）整年不计；A/C/D/E 类照算
B_NAME_RE = re.compile(r"培训队|篮球|排球|羽球|足球|乒乓|田径|游泳|辩论|口才|时事常识|数学培训")
# R4 比赛须代表本学会：各学会的比赛关键词
CLUB_KW = {
    "A01": r"学长|步操|基本操|花式操|操练|交流营", "A02": r"童军|步操|基本操|露营|野外|结绳|童行|扎营|交流营",
    "A03": r"救伤|急救|圣约翰|St\.?\s*John|步操|基本操|护理|交流营", "A04": r"学警|警察|步操|基本操|枪操|射击|交流营",
    "C01": r"管乐|band|Muzik|铜管|木管|打击乐|室内乐|春蕾|音乐节|器乐|合奏|独奏|乐团",
    "C02": r"华乐|民乐|春蕾|音乐节|器乐|合奏|独奏|乐团|二胡|琵琶|古筝|扬琴|笛|阮|唢呐",
    "C03": r"合唱|歌唱|歌曲|声乐|choir|choral|MCE|(?<![A-Za-z])sing(?![A-Za-z])|Song",
    "C04": r"舞|dance|PETARA", "C05": r"戏剧|戏聚|话剧|剧|演员|TEAM聚团|戏",
    "C06": r"武术|wushu|南拳|长拳|太极|南棍|南刀|刀术|剑术|棍术|枪术|套路|武", "C07": r"鼓", "C08": r"扯铃|铃|diabolo|SPIN",
    "D01": r"华文|中文|文学|作文|征文|散文|诗|汉字|朗诵|写作|茶艺|春联|挥春|对联",
    "D03": r"英文|English|Literary|Spelling|Poem|Short Stor|Essay|Writing|Speech",
    "D04": r"数学|Math|SMC|AMC|AMO|SASMO|陈景润|Kangaroo|袋鼠|奥数", "D05": r"生物|Biology|科学|生态|自然",
    "D10": r"美术|绘画|写生|画|设计|Art|海报|创作|素描|水彩", "D11": r"书法|挥春|硬笔|写字|春联|对联",
    "D12": r"电脑|程序|编程|coding|Robot|机器人|科技|Tech|AI|资讯|网站|电竞", "D13": r"环保|环境|绿色|再生|生态|回收",
    "D14": r"扶轮|Interact|社区|服务", "D15": r"漫画|插画|动漫|绘画|画|Comic|Manga", "D16": r"日语|日本|日文|Japan|Nihongo",
    "D17": r"花艺|插花|花", "D18": r"摄影|照片|photo|影像|相片", "D19": r"棋|chess|弈", "D21": r"模型|高达|DIORAMA|3D|手工|模",
    "D22": r"旅游|地理|导游|旅", "D23": r"烹饪|厨|料理|烘焙|食|饮", "D24": r"跆拳道|taekwondo|sparring|pattern|poomsae|品势|对练|腿",
    "D25": r"口琴|harmonica|春蕾|音乐节|合奏", "D26": r"吉他|guitar|音乐节", "D27": r"小提琴|弦乐|violin|viola|cello|春蕾|音乐节|合奏|独奏",
    "D28": r"韩|Korea|K-?pop", "E01": r"阅读|图书|读书|书评|阅|故事", "E02": r"编辑|写作|征文|文学|新闻|刊|作文", "E03": r"舞台|灯光|音响|技术|音控",
}
OTHER_KW = {"体育": r"运动会|田径|篮球|排球|羽球|足球|乒乓|游泳|接力|铅球|跳远|跳高|越野|马拉松|跑|跳绳|拔河|球",
            "辩论/口才": r"辩论|辩|口才|演讲|讲故事", "时事常识": r"时事|常识"}
CLUB_KW_RE = {k: re.compile(v, re.I) for k, v in CLUB_KW.items()}
OTHER_KW_RE = {k: re.compile(v, re.I) for k, v in OTHER_KW.items()}


def block_class(b) -> str:
    code = b.get("clubCode") or ""
    if code.startswith("B"):
        return "B"
    if not code and B_NAME_RE.search(b.get("clubName") or b.get("club") or ""):
        return "B"
    return code[:1]


def comp_judge(text, code):
    own = CLUB_KW_RE.get(code)
    if own and own.search(text):
        return None
    for lab, rx in OTHER_KW_RE.items():
        if rx.search(text):
            return f"非代表本学会（{lab}类比赛）"
    for c, rx in CLUB_KW_RE.items():
        if c != code and rx.search(text):
            return f"非代表本学会（看似 {c} 类比赛）"
    return "unsure" if own else None


def _simp(t):
    t = norm(t)
    t = re.sub(r"^[\d.、，,]+", "", t)
    t = re.sub(r"[。．.，,；;！!“”\"《》()（）\-—–:：]", "", t)
    return re.sub(r"^(参加|参与|代表\S{0,6}参加)", "", t)


# ---------------------------------------------------------------- 执委栏里的活动筹委 → 移到筹委（上级 2026-09-24 确认）
# 为某个活动而组成的筹委团职位不是学会行政的执委，即使写在执委栏也算筹委。
# 监督 / 督导 / 顾问类、联课处工委、毕联会等常设职位仍留在执委栏。
EVENT_STAY = re.compile(r"监督|督导|顾问|教练|领队|联课处|例常活动|联课活动组别|最佳学员|校内服务负责人")
EVENT_EXPLICIT = re.compile(r"筹委|筹主|筹办")
EVENT_NAME = re.compile(r"《|欢送会|惜别会|成果汇报|园游会|谢师宴|晚宴|午宴|户外考察|比赛|新生营|干训营|交流营|培训营|开放日|运动会|庆典|聚会|文娱汇演|教师节活动|大师班|快闪|义卖|市集|花市")
EVENT_POS = re.compile(r"主席|秘书|财政|总务|查账|事务|股|负责人|带领人|工委|助手|汇报员")


def is_event_committee(text) -> bool:
    t = norm(text)
    if EVENT_STAY.search(t):
        return False
    return bool(EVENT_EXPLICIT.search(t) or (EVENT_NAME.search(t) and EVENT_POS.search(t)))


# 监督 / 督导 / 顾问 / 教练 / 领队类：一律算执委（写在筹委栏的也移过去）（上级 2026-09-24）
SUPERVISE = re.compile(r"监督|督导|顾问|(?<!小)教练|领队")
# 运动会、田径赛等学校层面的活动：不是代表学会，算班级，不计筹委也不计执委（上级 2026-09-24）
SCHOOL_SPORTS = re.compile(r"运动会|田径")
SCHOOL_SPORTS_KEEP = re.compile(r"义卖|演出|表演")


def is_school_sports(text) -> bool:
    t = norm(text)
    return bool(SCHOOL_SPORTS.search(t) and (not SCHOOL_SPORTS_KEEP.search(t) or "班级" in t))


# 高三毕联会（毕业班联合会）属于年级，不属于学会：不计执委也不计筹委（上级 2026-09-24）
GRADE_ORG = re.compile(r"毕联|毕业班联合会|毕业联合会|毕业班联")


def _split_grade_parts(arr):
    """一条里同时写了学会职位和毕联会职位（用逗号隔开）时，拆成两条，只让毕联会那部分不计。"""
    out = []
    for t in arr:
        parts = [p.strip() for p in re.split(r"[，,；;]", t) if p.strip()]
        if len(parts) > 1 and any(GRADE_ORG.search(p) for p in parts) and not all(GRADE_ORG.search(p) for p in parts):
            keep = [p for p in parts if not GRADE_ORG.search(p)]
            grade = [p for p in parts if GRADE_ORG.search(p)]
            out.append("，".join(keep))
            out.extend(grade)
        else:
            out.append(t)
    return out


# 特别标记：联课处工委、文娱工委、XXX志工工委、国际交流筹委/负责人（上级 2026-09-24）——只做标记，不改变计分
SPECIAL_RE = re.compile(r"联课处?工委|文娱工委|志工工委")


INTL_RE = re.compile(r"国际.{0,4}交流")


def special_label(text, cat=None):
    t = norm(text)
    m = SPECIAL_RE.search(t)
    if m:
        w = m.group(0)
        return "联课处工委" if w.startswith("联课") else w
    # 国际交流的筹委 / 负责人（写在筹委栏的都算筹委）（上级 2026-09-24）
    if INTL_RE.search(t) and (cat == "comm" or re.search(r"筹委|负责人", t)):
        return "国际交流筹委/负责人"
    return None


def is_sports_sale(text) -> bool:
    """运动会上的义卖（学会摊位、兜售等）→ 不计"""
    t = norm(text)
    return bool(SCHOOL_SPORTS.search(t) and "义卖" in t)


def _sports_class(text) -> bool:
    """班级名义的运动会活动（如「班级运动会义卖活动负责人」）→ 不计"""
    t = norm(text)
    return bool(SCHOOL_SPORTS.search(t) and "班级" in t)


def move_event_roles(s):
    for b in s["blocks"]:
        for k in ("role", "comm"):
            if k in b["cats"]:
                b["cats"][k] = _split_grade_parts(b["cats"][k])
        roles, comms = b["cats"].get("role", []), b["cats"].get("comm", [])
        # 运动会 / 田径赛的职位算「服务筹委团」（上级 2026-09-24 改定），也移到筹委
        to_comm = [t for t in roles if (is_event_committee(t) or is_school_sports(t)) and not _sports_class(t)]
        to_role = [t for t in comms if SUPERVISE.search(norm(t)) and not is_school_sports(t)]
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
    for b in s["blocks"]:
        b["exBlock"] = "B类（体育/学术培训队）不计" if block_class(b) == "B" else None
        b["ex"], b["unsure"] = {}, {}
        for k, arr in b["cats"].items():
            b["ex"][k] = ["以班级为单位，不计" if (k not in CLASS_EXEMPT and CLASS_RE.search(t)) else None for t in arr]
            # 毕联会属于年级：它的职位、筹委不计；服务时数、活动照算（上级 2026-09-24 纠正）
            if k in ("role", "comm"):
                b["ex"][k] = [e or ("毕联会属于年级，不属于学会，职位/筹委不计" if GRADE_ORG.search(norm(t)) else None) for e, t in zip(b["ex"][k], arr)]
            if k in ("role", "comm"):
                b["ex"][k] = [e or ("班级的运动会活动，不计" if _sports_class(t) else None) for e, t in zip(b["ex"][k], arr)]
            # 运动会义卖不计（所有栏目）；运动会上的演出、服务照算（上级 2026-09-24）
            b["ex"][k] = [e or ("运动会义卖不计" if is_sports_sale(t) else None) for e, t in zip(b["ex"][k], arr)]

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
                own_new = bool(CLUB_KW_RE.get(b.get("clubCode")) and CLUB_KW_RE[b["clubCode"]].search(t))
                own_old = bool(CLUB_KW_RE.get(p[0].get("clubCode")) and CLUB_KW_RE[p[0]["clubCode"]].search(t))
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
        rl, rc = standard_roles_from([b["rc"][i] for i in range(len(b["cats"].get("role", []))) if item_state(s, b, "role", i, ov)["inc"]])
        roles_by_block.append(rl)
        c["roles"] += rc
        if b["exBlock"]:
            continue
        # 服务时数 = 该年采用的时数（自填总数优先），再扣掉不计入的服务项的时数
        h = b["hours"] or 0
        for k in ("extSvc", "intSvc"):
            for i, _ in enumerate(b["cats"].get(k, [])):
                if not item_state(s, b, k, i, ov)["inc"] and b["hr"][k][i]:
                    h -= b["hr"][k][i]
        hours += max(0.0, h)
    out = {k: c[k] for k in ("roles", "comm", "extComp", "intComp", "extAct", "intAct", "extSvc", "intSvc", "team", "badge", "honor", "unsure", "extAwards", "intAwards")}
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
