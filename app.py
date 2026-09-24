"""成就奖履历查看网站 (Achievement Viewer)

读取 Result/ 文件夹里每位学生的「联课活动个人表现履历表」（.xlsx / .pdf），
按手册规则统计，在浏览器里显示：搜索、排序、个人完整履历、对比、统计图表、
手动「计入 / 不计」。Result 里的文件有任何增删改，网页几秒内自动更新。

    python app.py                    # 读取旁边的 Result/，自动打开浏览器
    python app.py "D:\\某处\\Result"  # 指定别的文件夹
    python app.py --dev              # 显示每次请求记录（除错用）
    python app.py --export           # 不开网站，直接在 Result 旁边导出离线版 HTML + Excel

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
from achievement.engine import folder_version, load_folder
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
DEV_MODE = bool(_argv_flags & {"--dev", "--verbose"} or os.environ.get("ACHIEVEMENT_VIEWER_DEBUG") == "1")

BASE_DIR = Path(_argv_positional[0]).resolve() if _argv_positional else (APP_DIR / "Result")
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
    v = folder_version(BASE_DIR)
    with _State.lock:
        if force or v != _State.version:
            _State.students, _State.files, _State.failed = load_folder(BASE_DIR)
            _State.version = v
            _State.when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if DEV_MODE:
                print(f"[{_State.when}] 载入 {len(_State.files)} 个文件，共 {len(_State.students)} 位学生")
    return _State.version


def info():
    return {"files": len(_State.files), "when": _State.when, "version": _State.version,
            "fail": [list(x) for x in _State.failed], "folder": str(BASE_DIR)}


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
    return jsonify(version=refresh())


@app.route("/api/data")
def api_data():
    try:
        refresh()
    except Exception as e:  # noqa: BLE001
        return jsonify(error=f"{type(e).__name__}: {e}"), 500
    if not BASE_DIR.is_dir():
        return jsonify(error=f"找不到 Result 文件夹：{BASE_DIR}"), 404
    return jsonify(version=_State.version, students=_State.students, info=info(), overrides=load_ov())


@app.route("/api/overrides", methods=["POST"])
def api_overrides():
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


@app.route("/export/offline.html")
def export_offline():
    refresh()
    now = datetime.now()
    return Response(render_offline(now), mimetype="text/html",
                    headers=_attachment(offline_name(now), f"achievement_{export_stamp(now)}.html"))


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
def _find_free_port(preferred=5000, tries=20):
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


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


def main():
    import logging
    logging.getLogger("werkzeug").setLevel(logging.INFO if DEV_MODE else logging.WARNING)

    print("=" * 60)
    print(f" Individual's Utmost Achievement Calculator / 成就奖履历查看网站  v{__version__}")
    print("=" * 60)
    print(f" 资料来源 (Result folder): {BASE_DIR}")
    if not BASE_DIR.is_dir():
        print(" [!] 找不到 Result 文件夹：请把本程序放在 Result 文件夹旁边，")
        print("   或在命令后面写上文件夹路径。")
    if "--export" in _argv_flags:
        export_files()
        return
    try:
        refresh(force=True)
        print(f" 已读取 {len(_State.files)} 个文件，共 {len(_State.students)} 位学生"
              + (f"（{len(_State.failed)} 个读取失败）" if _State.failed else ""))
    except Exception as e:  # noqa: BLE001
        print(f" 读取出错：{e}")

    port = _find_free_port(5000)
    if port == 0:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    print(f" 网址 (URL): {url}")
    print(" Result 文件夹有新增 / 修改的履历表时，网页会自动更新。")
    if DEV_MODE:
        print(" 开发者模式：显示每次请求记录 (developer mode: request log shown)")
    else:
        print(" 如需显示每次请求记录，请加上 --dev 参数重新启动")
    print(" 关闭这个窗口即可停止网站 (Close this window to stop the site)")
    print("=" * 60)

    if "--no-browser" not in _argv_flags:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
