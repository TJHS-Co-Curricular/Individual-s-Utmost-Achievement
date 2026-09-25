"""成就奖履历查看网站 (Achievement Viewer)

读取 Result/ 文件夹里每位学生的「联课活动个人表现履历表」（.xlsx / .pdf），
按手册规则统计，在浏览器里显示：搜索、排序、个人完整履历、对比、统计图表、
手动「计入 / 不计」。Result 里的文件有任何增删改，网页几秒内自动更新。

    python app.py                    # 读取旁边的 Result/，自动打开浏览器
    python app.py "D:\\某处\\Result"  # 指定别的文件夹
    python app.py --dev              # 显示每次请求记录（除错用）
    python app.py --local            # 只限本机（盖过 config.ini）
    python app.py --port=5050        # 指定端口（盖过 config.ini）
    python app.py --lan              # 局域网共享：同事可用 http://你的IP:5000 查看（也可双击 scripts\\start_lan.bat）
    python app.py --export           # 不开网站，直接在 Result 旁边导出离线版 HTML + Excel
    python app.py --list-roles       # 把 Result 里所有职位及目前归类，存成 docs/generated/已知职位一览.xlsx（只供参考）
    python app.py --list-awards      # 把 Result 里所有比赛条目及算不算获奖，存成 docs/generated/已知获奖一览.xlsx（只供参考）

计分规则全部在 achievement/rules.py。
"""
from __future__ import annotations

import io
import json
import os
import socket
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from flask import Flask, Response, jsonify, render_template, request, send_file

from achievement import __version__

for _s in (sys.stdout, sys.stderr):  # Windows 控制台编码不同时，避免个别符号导致崩溃
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass
from achievement.engine import current_folder, folder_version, load_batches, load_folder
from achievement.excel import write_xlsx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# PyInstaller --onefile 时有两个不同的位置：
#   APP_DIR       -- exe 所在的文件夹：Result/ 和 成就奖_手动调整.json 放这里
#   RESOURCE_DIR  -- 打包进 exe 的 templates/、static/ 解压到的临时文件夹
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = APP_DIR

_argv_flags = {a for a in sys.argv[1:] if a.startswith("--")}
_argv_positional = [a for a in sys.argv[1:] if not a.startswith("--")]
# 网站设定：config/config.ini（启动参数会盖过它）
from achievement.settings import load as _load_settings   # noqa: E402

SETTINGS = _load_settings()
if "--local" in _argv_flags:
    SETTINGS.access = "local"
LAN_MODE = SETTINGS.access == "lan" or bool(_argv_flags & {"--lan", "--share"}) or os.environ.get("ACHIEVEMENT_VIEWER_LAN") == "1"
DEV_MODE = bool(_argv_flags & {"--dev", "--verbose"} or os.environ.get("ACHIEVEMENT_VIEWER_DEBUG") == "1")

def _port_arg():
    for a in sys.argv[1:]:
        if a.startswith("--port="):
            return int(a.split("=", 1)[1])
    return None


if _port_arg():
    SETTINGS.port = _port_arg()
_rf = Path(SETTINGS.result_folder)
BASE_DIR = Path(_argv_positional[0]).resolve() if _argv_positional else (_rf if _rf.is_absolute() else APP_DIR / _rf).resolve()
DATA_DIR = BASE_DIR.parent                      # 手动调整、导出文件放在 Result 的上一层
OV_PATH = DATA_DIR / "成就奖_手动调整.json"
TITLE = "高三最高成就奖 · 履历总览"

app = Flask(__name__, template_folder=str(RESOURCE_DIR / "templates"), static_folder=str(RESOURCE_DIR / "static"))
app.json.ensure_ascii = False


@app.after_request
def _no_browser_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
class _State:
    lock = threading.Lock()
    version = None
    students: list = []
    files: list = []
    failed: list = []
    when = ""


def refresh(force=False) -> str:
    """文件夹有变动才重新整理（没改过的文件由 engine 的缓存直接取用）。"""
    src = current_folder(BASE_DIR)          # Result 里只有年份子文件夹时，读最新一届
    v = folder_version(src) + str(src)
    with _State.lock:
        if force or v != _State.version:
            _State.students, _State.files, _State.failed = load_folder(src)
            _State.version = v
            _State.when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if DEV_MODE:
                print(f"[{_State.when}] 载入 {len(_State.files)} 个文件，共 {len(_State.students)} 位学生")
    return _State.version


def info():
    return {"files": len(_State.files), "when": _State.when, "version": _State.version,
            "fail": [list(x) for x in _State.failed], "folder": str(current_folder(BASE_DIR))}


def load_ov() -> dict:
    try:
        d = json.loads(OV_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in d.items() if v in ("in", "out")}
    except Exception:  # noqa: BLE001
        return {}


def save_ov(ov: dict):
    clean = {k: v for k, v in ov.items() if v in ("in", "out")}
    tmp = OV_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OV_PATH)


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str).replace("</", "<\\/")


def export_stamp(dt=None) -> str:
    """导出文件名里的日期时间：DD-MM-YYYY_HH.MM
    （Windows 文件名不能有冒号「:」，所以时和分之间用「.」）"""
    return (dt or datetime.now()).strftime("%d-%m-%Y_%H.%M")


def offline_name(dt=None) -> str:
    return f"成就奖履历总览_{export_stamp(dt)}.html"


def render_offline(dt=None) -> str:
    """单一 HTML 文件：CSS / JS / 资料全部内嵌，双击即可离线查看。"""
    static = RESOURCE_DIR / "static"
    inf = info()
    inf["when"] = (dt or datetime.now()).strftime("%d-%m-%Y %H:%M")   # 离线版显示「生成于」导出时间
    return render_template(
        "index.html", title=TITLE, offline=True,
        inline_css=(static / "style.css").read_text(encoding="utf-8"),
        inline_core=(static / "core.js").read_text(encoding="utf-8"),
        inline_app=(static / "app.js").read_text(encoding="utf-8"),
        favicon_svg=(static / "favicon.svg").read_text(encoding="utf-8"),
        data_json=_js(_State.students), info_json=_js(inf), ov_json=_js(load_ov()),
    )


def _attachment(name: str, ascii_name: str) -> dict:
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.svg")


@app.route("/")
def index():
    return render_template("index.html", title=TITLE, offline=False)


@app.route("/api/version")
def api_version():
    try:
        return jsonify(version=refresh())
    except Exception as e:  # noqa: BLE001  例：config/ 的 JSON 改到一半格式有误
        return jsonify(version=None, error=f"{type(e).__name__}: {e}")


@app.route("/api/data")
def api_data():
    try:
        refresh()
    except Exception as e:  # noqa: BLE001
        return jsonify(error=f"{type(e).__name__}: {e}"), 500
    if not BASE_DIR.is_dir():
        return jsonify(error=f"找不到 Result 文件夹：{BASE_DIR}"), 404
    return jsonify(version=_State.version, students=_State.students, info=info(), overrides=load_ov())


def _is_local_request() -> bool:
    return (request.remote_addr or "") in ("127.0.0.1", "::1", "localhost")


@app.route("/api/overrides", methods=["POST"])
def api_overrides():
    # 局域网共享时，同事可以查看、下载，但「计入 / 不计」只能在本机改（避免多人同时改乱）
    if not _is_local_request() and not SETTINGS.lan_allow_edit:
        return jsonify(ok=False, error="局域网访问只能查看，「计入 / 不计」请在开网站的那台电脑上修改"), 403
    ov = request.get_json(force=True, silent=True) or {}
    save_ov(ov)
    return jsonify(ok=True, count=len(ov))


@app.route("/export/excel")
def export_excel():
    refresh()
    buf = io.BytesIO()
    write_xlsx(_State.students, buf, load_ov())
    buf.seek(0)
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="成就奖统计.xlsx")


@app.route("/export/roles.xlsx")
def export_roles():
    """已知职位一览：所有执委栏职位及目前的归类（只供参考）。"""
    from achievement import member_rules
    refresh()
    buf = io.BytesIO()
    member_rules.write_known_xlsx(_ref_data(), buf, datetime.now().strftime("%d-%m-%Y %H:%M"))
    buf.seek(0)
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="已知职位一览.xlsx")


@app.route("/export/awards.xlsx")
def export_awards():
    """已知获奖一览：所有比赛条目及目前算不算获奖（只供参考）。"""
    from achievement import award_rules
    refresh()
    buf = io.BytesIO()
    award_rules.write_known_xlsx(_ref_data(), buf, datetime.now().strftime("%d-%m-%Y %H:%M"))
    buf.seek(0)
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="已知获奖一览.xlsx")


@app.route("/export/offline.html")
def export_offline():
    refresh()
    now = datetime.now()
    return Response(render_offline(now), mimetype="text/html",
                    headers=_attachment(offline_name(now), f"achievement_{export_stamp(now)}.html"))


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
def _lan_ips():
    """这台电脑在局域网里的 IP（给同事用）"""
    ips = []
    try:   # 不会真的送出资料，只是让系统选出对外的网卡
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ips.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return [ip for ip in ips if not ip.startswith("127.")]


def _find_free_port(preferred=5000, tries=20, host="127.0.0.1"):
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return 0


def _ref_data():
    """参考清单（职位一览 / 获奖一览）的资料：Result 里有好几届（年份子文件夹）就每届分开列出次数；
    只有一批 → 照旧。"""
    b = load_batches(BASE_DIR)
    return b if len(b) > 1 else (next(iter(b.values())) if b else _State.students)


def generated_dir() -> Path:
    """自动产生的参考清单（已知职位一览、已知获奖一览）放 docs/generated/"""
    d = DATA_DIR / "docs" / "generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def export_files():
    """--export：不开网站，直接导出离线版 HTML + Excel 到 Result 的上一层。"""
    refresh(force=True)
    now = datetime.now()
    html = DATA_DIR / offline_name(now)
    with app.test_request_context():
        html.write_text(render_offline(now), encoding="utf-8")
    write_xlsx(_State.students, DATA_DIR / "成就奖统计.xlsx", load_ov())
    print(f" 已导出：{html}")
    print(f" 已导出：{DATA_DIR / '成就奖统计.xlsx'}")


def _disable_console_quick_edit():
    """Windows 黑色窗口的「快速编辑模式」：在窗口里点一下就会暂停整个程序，网页就会读取失败。这里把它关掉。"""
    if os.name != "nt":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-10)            # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            k32.SetConsoleMode(h, (mode.value & ~0x0040) | 0x0080)   # 去掉 QUICK_EDIT，保留 EXTENDED_FLAGS
    except Exception:  # noqa: BLE001
        pass


def main():
    import logging
    logging.getLogger("werkzeug").setLevel(logging.INFO if DEV_MODE else logging.WARNING)
    _disable_console_quick_edit()

    print("=" * 60)
    print(f" Individual's Utmost Achievement Calculator / 成就奖履历查看网站  v{__version__}")
    print("=" * 60)
    print(f" 设定 (config.ini): {SETTINGS.source or '（没找到，用预设值）'}")
    for w in SETTINGS.warnings:
        print(f" [!] config.ini：{w}")
    print(f" 资料来源 (Result folder): {BASE_DIR}")
    if current_folder(BASE_DIR) != BASE_DIR:
        print(f"   Result 里是年份子文件夹 → 网站读取最新一届：{current_folder(BASE_DIR).name}")
    try:
        from achievement import member_rules
        print(f" 职位规则 (member rules): {member_rules.path()}")
        from achievement import award_rules
        print(f" 获奖规则 (award rules):  {award_rules.path()}")
    except Exception as e:  # noqa: BLE001
        print(f" [!] 职位规则读取失败：{e}")
    if not BASE_DIR.is_dir():
        print(" [!] 找不到 Result 文件夹：请把本程序放在 Result 文件夹旁边，")
        print("   或在命令后面写上文件夹路径。")
    if "--list-awards" in _argv_flags:
        from achievement import award_rules
        refresh(force=True)
        out_dir = generated_dir()
        p = out_dir / "已知获奖一览.xlsx"
        n, summ = award_rules.write_known_xlsx(_ref_data(), p, datetime.now().strftime("%d-%m-%Y %H:%M"))
        print(f" 已把 {n} 个比赛条目写进 {p}（获奖 {summ.get('★ 获奖', 0)}、未获奖 {summ.get('—', 0)}）")
        return
    if "--list-roles" in _argv_flags:
        from achievement import member_rules
        refresh(force=True)
        out_dir = generated_dir()
        p = out_dir / "已知职位一览.xlsx"
        n, summ = member_rules.write_known_xlsx(_ref_data(), p, datetime.now().strftime("%d-%m-%Y %H:%M"))
        print(f" 已把 {n} 个职位写进 {p}（{'、'.join(f'{k} {v}' for k, v in summ.items())}）")
        return
    if "--export" in _argv_flags:
        export_files()
        return
    try:
        refresh(force=True)
        print(f" 已读取 {len(_State.files)} 个文件，共 {len(_State.students)} 位学生"
              + (f"（{len(_State.failed)} 个读取失败）" if _State.failed else ""))
    except Exception as e:  # noqa: BLE001
        print(f" 读取出错：{e}")

    host = "0.0.0.0" if LAN_MODE else "127.0.0.1"
    port = _find_free_port(SETTINGS.port, tries=20 if SETTINGS.port_fallback else 1, host=host)
    if port == 0 and not SETTINGS.port_fallback:
        print(f" [!] 端口 {SETTINGS.port} 已经被别的程序占用（可能已经开了一个本程序）。")
        print("     请关掉另一个，或到 config\\config.ini 改 port / 把 port_fallback 设成 yes。")
        try:
            input(" 按 Enter 结束…")
        except EOFError:
            pass
        return
    if port != SETTINGS.port and port:
        print(f" [!] 端口 {SETTINGS.port} 被占用，改用 {port}")
    if port == 0:
        with socket.socket() as s:
            s.bind((host, 0))
            port = s.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    print(f" 网址 (URL): {url}")
    if LAN_MODE:
        ips = _lan_ips()
        print(" 【局域网共享已开启】同一个网络里的同事可以打开：")
        for ip in ips or ["（找不到本机 IP，请在命令提示字元输入 ipconfig 查看 IPv4 地址）"]:
            print(f"     http://{ip}:{port}" if ips else f"     {ip}")
        print(" 同事可以查看、搜索、下载；" + ("也可以改「计入 / 不计」。" if SETTINGS.lan_allow_edit else "「计入 / 不计」只能在这台电脑上改。"))
        print(" 同事打不开：Windows 第一次会问「是否允许访问」，请选「允许」（专用网络）；")
        print("   之前按过「取消」的话，请以系统管理员身份执行 scripts\\allow_firewall.bat。")
    else:
        print(" 只有这台电脑能打开。要让同事用 IP 访问：config\\config.ini 改成 access = lan（或双击 scripts\\start_lan.bat）。")
    print(" Result 文件夹有新增 / 修改的履历表时，网页会自动更新。")
    if DEV_MODE:
        print(" 开发者模式：显示每次请求记录 (developer mode: request log shown)")
    else:
        print(" 如需显示每次请求记录，请加上 --dev 参数重新启动")
    print(" 关闭这个窗口即可停止网站 (Close this window to stop the site)")
    print("=" * 60)

    if "--no-browser" not in _argv_flags and SETTINGS.open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
