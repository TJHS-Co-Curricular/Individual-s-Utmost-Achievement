"""本地网站（Flask）：网页、API、下载 / 导出。

create_app(store, settings) 建立网站；启动、参数、启动画面在 cli.py。
"""
from __future__ import annotations

import io
import json
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from flask import Flask, Response, jsonify, render_template, request, send_file

from . import __version__
from .excel import write_xlsx
from .paths import RESOURCE_DIR
from .settings import Settings
from .store import Store

log = logging.getLogger(__name__)

TITLE = "高三最高成就奖 · 履历总览"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ---------------------------------------------------------------------------
# 导出用的小工具
# ---------------------------------------------------------------------------
def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str).replace("</", "<\\/")


def export_stamp(dt=None) -> str:
    """导出文件名里的日期时间：DD-MM-YYYY_HH.MM
    （Windows 文件名不能有冒号「:」，所以时和分之间用「.」）"""
    return (dt or datetime.now()).strftime("%d-%m-%Y_%H.%M")


def offline_name(dt=None) -> str:
    return f"成就奖履历总览_{export_stamp(dt)}.html"


def render_offline(store: Store, dt=None) -> str:
    """单一 HTML 文件：CSS / JS / 资料全部内嵌，双击即可离线查看。（要在 app context 里调用）"""
    static = RESOURCE_DIR / "static"
    inf = store.info()
    inf["when"] = (dt or datetime.now()).strftime("%d-%m-%Y %H:%M")   # 离线版显示「生成于」导出时间
    return render_template(
        "index.html", title=TITLE, offline=True,
        inline_css=(static / "style.css").read_text(encoding="utf-8"),
        inline_core=(static / "core.js").read_text(encoding="utf-8"),
        inline_app=(static / "app.js").read_text(encoding="utf-8"),
        favicon_svg=(static / "favicon.svg").read_text(encoding="utf-8"),
        data_json=_js(store.students), info_json=_js(inf), ov_json=_js(store.load_ov()),
    )


def _attachment(name: str, ascii_name: str) -> dict:
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"}


def _xlsx_response(fill, download_name: str):
    buf = io.BytesIO()
    fill(buf)
    buf.seek(0)
    return send_file(buf, mimetype=XLSX, as_attachment=True, download_name=download_name)


def _now_label() -> str:
    return datetime.now().strftime("%d-%m-%Y %H:%M")


# ---------------------------------------------------------------------------
# 网站
# ---------------------------------------------------------------------------
def create_app(store: Store, settings: Settings) -> Flask:
    app = Flask("achievement", template_folder=str(RESOURCE_DIR / "templates"),
                static_folder=str(RESOURCE_DIR / "static"))
    app.json.ensure_ascii = False

    @app.context_processor
    def _inject():
        return {"app_version": __version__}

    @app.after_request
    def _no_browser_cache(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.errorhandler(Exception)
    def _error(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        log.exception("处理 %s 时出错", request.path)
        return jsonify(error=f"{type(e).__name__}: {e}"), 500

    def is_local_request() -> bool:
        return (request.remote_addr or "") in ("127.0.0.1", "::1", "localhost")

    @app.route("/favicon.ico")
    def favicon():
        return app.send_static_file("favicon.svg")

    @app.route("/")
    def index():
        return render_template("index.html", title=TITLE, offline=False)

    @app.route("/api/version")
    def api_version():
        try:
            return jsonify(version=store.refresh(), app=__version__)
        except Exception as e:  # noqa: BLE001  例：config/ 的 JSON 改到一半格式有误
            log.warning("重新载入失败：%s: %s", type(e).__name__, e)
            return jsonify(version=None, app=__version__, error=f"{type(e).__name__}: {e}")

    @app.route("/api/data")
    def api_data():
        store.refresh()
        if not store.base.is_dir():
            return jsonify(error=f"找不到 Result 文件夹：{store.base}"), 404
        return jsonify(version=store.version, app=__version__, students=store.students,
                       info=store.info(), overrides=store.load_ov())

    @app.route("/api/overrides", methods=["POST"])
    def api_overrides():
        # 局域网共享时，同事可以查看、下载，但「计入 / 不计」只能在本机改（避免多人同时改乱）
        if not is_local_request() and not settings.lan_allow_edit:
            log.info("拒绝来自 %s 的手动调整（局域网只能查看）", request.remote_addr)
            return jsonify(ok=False, error="局域网访问只能查看，「计入 / 不计」请在开网站的那台电脑上修改"), 403
        ov = request.get_json(force=True, silent=True) or {}
        return jsonify(ok=True, count=store.save_ov(ov))

    @app.route("/export/excel")
    def export_excel():
        store.refresh()
        log.info("下载 Excel 总表")
        return _xlsx_response(lambda b: write_xlsx(store.students, b, store.load_ov()), "成就奖统计.xlsx")

    @app.route("/export/roles.xlsx")
    def export_roles():
        """已知职位一览：所有执委栏职位及目前的归类（只供参考）。"""
        from . import member_rules
        store.refresh()
        log.info("下载 已知职位一览")
        return _xlsx_response(lambda b: member_rules.write_known_xlsx(store.ref_data(), b, _now_label()),
                              "已知职位一览.xlsx")

    @app.route("/export/awards.xlsx")
    def export_awards():
        """已知获奖一览：所有比赛条目及目前算不算获奖（只供参考）。"""
        from . import award_rules
        store.refresh()
        log.info("下载 已知获奖一览")
        return _xlsx_response(lambda b: award_rules.write_known_xlsx(store.ref_data(), b, _now_label()),
                              "已知获奖一览.xlsx")

    @app.route("/export/offline.html")
    def export_offline():
        store.refresh()
        now = datetime.now()
        log.info("导出离线版 HTML")
        return Response(render_offline(store, now), mimetype="text/html",
                        headers=_attachment(offline_name(now), f"achievement_{export_stamp(now)}.html"))

    return app


# ---------------------------------------------------------------------------
# 不开网站、直接写文件（--export / --list-roles / --list-awards）
# ---------------------------------------------------------------------------
def export_files(app: Flask, store: Store) -> list[Path]:
    """离线版 HTML + Excel → output/"""
    store.refresh(force=True)
    store.dirs.ensure("output")
    now = datetime.now()
    html = store.dirs.output / offline_name(now)
    with app.test_request_context():
        html.write_text(render_offline(store, now), encoding="utf-8")
    xlsx = store.dirs.output / f"成就奖统计_{export_stamp(now)}.xlsx"
    write_xlsx(store.students, xlsx, store.load_ov())
    for p in (html, xlsx):
        log.info("已导出 %s", p)
    return [html, xlsx]


def write_reference(store: Store, kind: str) -> tuple[Path, int, dict]:
    """参考清单 → output/：kind = "roles"（已知职位一览）或 "awards"（已知获奖一览）"""
    from . import award_rules, member_rules
    mod, name = (member_rules, "已知职位一览.xlsx") if kind == "roles" else (award_rules, "已知获奖一览.xlsx")
    store.refresh(force=True)
    store.dirs.ensure("output")
    p = store.dirs.output / name
    n, summ = mod.write_known_xlsx(store.ref_data(), p, _now_label())
    log.info("已写出 %s（%d 项）", p, n)
    return p, n, summ
