"""读取 config/config.ini（网站设定：只限本机 / 局域网、端口、自动开浏览器、Result 位置）。

找不到文件或某一项没写，就用预设值；写错的值会在启动时提示，并改用预设值。
查找位置和规则表一样：exe 旁边的 config/ → exe 旁边 → 打包在 exe 里的 config/（开发时：项目的 config/）。
"""
from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path

from .member_rules import find_file

FILE_NAME = "config.ini"


@dataclass
class Settings:
    access: str = "local"          # local / lan
    port: int = 5000
    port_fallback: bool = True
    open_browser: bool = True
    lan_allow_edit: bool = False
    result_folder: str = "Result"
    source: Path | None = None
    warnings: list = field(default_factory=list)


def _bool(v, default, name, warn):
    s = str(v).strip().lower()
    if s in ("yes", "y", "true", "1", "on", "是", "开"):
        return True
    if s in ("no", "n", "false", "0", "off", "否", "关"):
        return False
    warn.append(f"{name} = {v} 看不懂（要写 yes 或 no），改用 {'yes' if default else 'no'}")
    return default


def load() -> Settings:
    st = Settings()
    try:
        p = find_file(FILE_NAME, "ACHIEVEMENT_CONFIG")
    except FileNotFoundError:
        return st
    cp = configparser.ConfigParser(inline_comment_prefixes=(";", "#"), interpolation=None)
    try:
        cp.read(p, encoding="utf-8-sig")   # utf-8-sig：记事本存档时加的 BOM 也读得懂
    except configparser.Error as e:
        st.warnings.append(f"config.ini 格式有误，全部改用预设值：{e}")
        return st
    st.source = p
    srv = cp["server"] if cp.has_section("server") else {}
    data = cp["data"] if cp.has_section("data") else {}
    w = st.warnings
    a = str(srv.get("access", st.access)).strip().lower()
    if a in ("local", "lan"):
        st.access = a
    else:
        w.append(f"access = {a} 看不懂（要写 local 或 lan），改用 local")
    try:
        port = int(str(srv.get("port", st.port)).strip())
        if not 1024 <= port <= 65535:
            raise ValueError
        st.port = port
    except ValueError:
        w.append(f"port = {srv.get('port')} 不是 1024~65535 的数字，改用 5000")
    st.port_fallback = _bool(srv.get("port_fallback", "yes"), True, "port_fallback", w)
    st.open_browser = _bool(srv.get("open_browser", "yes"), True, "open_browser", w)
    st.lan_allow_edit = _bool(srv.get("lan_allow_edit", "no"), False, "lan_allow_edit", w)
    st.result_folder = str(data.get("result_folder", st.result_folder)).strip() or "Result"
    return st
