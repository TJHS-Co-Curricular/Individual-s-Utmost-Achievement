"""启动：读参数和 config.ini → 设置日志 → 启动画面 → 开网站（或只导出）。

    python app.py                    # 读取旁边的 Result/，自动打开浏览器
    python app.py "D:\\某处\\Result"   # 指定别的文件夹
    python app.py --local            # 只限本机（盖过 config.ini）
    python app.py --lan              # 局域网共享：同事可用 http://你的IP:端口 查看
    python app.py --port=5050        # 指定端口（盖过 config.ini）
    python app.py --no-browser       # 不自动打开浏览器
    python app.py --dev              # 显示每次请求记录（除错用），日志也更详细
    python app.py --export           # 不开网站，导出离线版 HTML + Excel 到 output/
    python app.py --list-roles       # 已知职位一览.xlsx → output/（只供参考）
    python app.py --list-awards      # 已知获奖一览.xlsx → output/（只供参考）
    python app.py --version          # 显示版本号
"""
from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import threading
import webbrowser

from . import APP_NAME, __version__, logs, paths
from .engine import current_folder
from .settings import load as load_settings
from .store import Store
from .web import create_app, export_files, write_reference

log = logging.getLogger("achievement")


def _console_utf8():
    """Windows 控制台编码不同时，避免个别符号导致崩溃"""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")
        except Exception:  # noqa: BLE001
            pass


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


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="app.py", description=f"{APP_NAME} v{__version__}", allow_abbrev=False)
    ap.add_argument("folder", nargs="?", help="Result 文件夹（不写就用 config.ini 的 result_folder）")
    ap.add_argument("--local", action="store_true", help="只限本机")
    ap.add_argument("--lan", "--share", dest="lan", action="store_true", help="局域网共享")
    ap.add_argument("--port", type=int, help="端口")
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    ap.add_argument("--dev", "--verbose", dest="dev", action="store_true", help="开发者模式")
    ap.add_argument("--export", action="store_true", help="导出离线版 HTML + Excel 到 output/")
    ap.add_argument("--list-roles", action="store_true", help="已知职位一览.xlsx → output/")
    ap.add_argument("--list-awards", action="store_true", help="已知获奖一览.xlsx → output/")
    ap.add_argument("--version", action="version", version=f"{APP_NAME} v{__version__}")
    args, unknown = ap.parse_known_args(argv)
    return args, unknown


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


def main(argv=None):
    _console_utf8()
    args, unknown = parse_args(argv)

    settings = load_settings()
    if args.local:
        settings.access = "local"
    if args.lan or os.environ.get("ACHIEVEMENT_VIEWER_LAN") == "1":
        settings.access = "lan"
    if args.port:
        settings.port = args.port
    dev = args.dev or os.environ.get("ACHIEVEMENT_VIEWER_DEBUG") == "1"

    dirs = paths.make_dirs(args.folder or settings.result_folder, settings.output_folder)
    log_file = logs.setup(dirs.logs, dev)
    moved = paths.migrate_legacy(dirs)
    store = Store(dirs)
    app = create_app(store, settings)
    _disable_console_quick_edit()

    log.info("===== 启动 %s v%s（%s）=====", APP_NAME, __version__, "exe" if paths.FROZEN else "python")
    print("=" * 60)
    print(f" {APP_NAME} / 成就奖履历查看网站  v{__version__}")
    print("=" * 60)
    for u in unknown:
        print(f" [!] 看不懂的参数：{u}（已忽略）")
    print(f" 设定 (config.ini): {settings.source or '（没找到，用预设值）'}")
    log.info("设定：%s；access=%s port=%s", settings.source, settings.access, settings.port)
    for w in settings.warnings:
        print(f" [!] config.ini：{w}")
        log.warning("config.ini：%s", w)
    print(f" 资料来源 (Result):  {dirs.result}")
    if current_folder(dirs.result) != dirs.result:
        print(f"   Result 里是年份子文件夹 → 网站读取最新一届：{current_folder(dirs.result).name}")
    print(f" 手动调整 (data):    {dirs.overrides}")
    print(f" 导出 (output):      {dirs.output}")
    print(f" 日志 (logs):        {log_file or '（无法写入）'}")
    for n in moved:
        print(f" [i] {n}")
        log.info(n)
    try:
        from . import award_rules, member_rules
        for label, p in (("职位规则", member_rules.path()), ("获奖规则", award_rules.path())):
            print(f" {label}:          {p}")
            log.info("%s：%s", label, p)
            if paths.is_legacy_location(p):
                print(f"   [!] 建议把 {p.name} 移进 config\\ 文件夹（放在程序根目录是旧的放法）")
    except Exception as e:  # noqa: BLE001
        print(f" [!] 规则读取失败：{e}")
        log.error("规则读取失败：%s", e)
    if not dirs.result.is_dir():
        print(" [!] 找不到 Result 文件夹：请把本程序放在 Result 文件夹旁边，")
        print("     或在 config\\config.ini 改 result_folder，或在命令后面写上文件夹路径。")
        log.warning("找不到 Result 文件夹：%s", dirs.result)

    if args.list_awards or args.list_roles:
        for kind, flag in (("awards", args.list_awards), ("roles", args.list_roles)):
            if flag:
                p, n, summ = write_reference(store, kind)
                print(f" 已把 {n} 项写进 {p}（{'、'.join(f'{k} {v}' for k, v in summ.items())}）")
        return
    if args.export:
        for p in export_files(app, store):
            print(f" 已导出：{p}")
        return

    try:
        store.refresh(force=True)
        print(f" 已读取 {len(store.files)} 个文件，共 {len(store.students)} 位学生"
              + (f"（{len(store.failed)} 个读取失败）" if store.failed else ""))
    except Exception as e:  # noqa: BLE001
        print(f" 读取出错：{e}")
        log.exception("第一次读取出错")

    lan = settings.access == "lan"
    host = "0.0.0.0" if lan else "127.0.0.1"
    port = _find_free_port(settings.port, tries=20 if settings.port_fallback else 1, host=host)
    if port == 0 and not settings.port_fallback:
        print(f" [!] 端口 {settings.port} 已经被别的程序占用（可能已经开了一个本程序）。")
        print("     请关掉另一个，或到 config\\config.ini 改 port / 把 port_fallback 设成 yes。")
        log.error("端口 %s 被占用，停止", settings.port)
        try:
            input(" 按 Enter 结束…")
        except EOFError:
            pass
        return
    if port != settings.port and port:
        print(f" [!] 端口 {settings.port} 被占用，改用 {port}")
    if port == 0:
        with socket.socket() as s:
            s.bind((host, 0))
            port = s.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    print(f" 网址 (URL): {url}")
    log.info("网站开在 %s:%s（%s）", host, port, "局域网" if lan else "只限本机")
    if lan:
        ips = _lan_ips()
        print(" 【局域网共享已开启】同一个网络里的同事可以打开：")
        for ip in ips or ["（找不到本机 IP，请在命令提示字元输入 ipconfig 查看 IPv4 地址）"]:
            print(f"     http://{ip}:{port}" if ips else f"     {ip}")
        print(" 同事可以查看、搜索、下载；" + ("也可以改「计入 / 不计」。" if settings.lan_allow_edit else "「计入 / 不计」只能在这台电脑上改。"))
        print(" 同事打不开：Windows 第一次会问「是否允许访问」，请选「允许」（专用网络）；")
        print("   之前按过「取消」的话，请以系统管理员身份执行 scripts\\allow_firewall.bat。")
    else:
        print(" 只有这台电脑能打开。要让同事用 IP 访问：config\\config.ini 改成 access = lan（或双击 scripts\\start_lan.bat）。")
    print(" Result 文件夹有新增 / 修改的履历表时，网页会自动更新。")
    print(" 开发者模式：显示每次请求记录" if dev else " 如需显示每次请求记录，请加上 --dev 参数重新启动")
    print(" 关闭这个窗口即可停止网站 (Close this window to stop the site)")
    print("=" * 60)

    if not args.no_browser and settings.open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
