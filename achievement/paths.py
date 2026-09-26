"""所有文件夹位置集中在这里（python 版和 exe 版用同一套规则）。

    程序根目录 APP_DIR（python：项目根目录；exe：exe 所在的文件夹）
    ├─ config/    设定与规则表（config.ini、member_rules.json、award.json）——只放人改的设定
    ├─ Result/    学生履历表（输入）
    ├─ data/      程序自己保存的资料：成就奖_手动调整.json（网页里的「计入 / 不计」）
    ├─ output/    导出的文件：离线版 HTML、Excel、已知职位一览、已知获奖一览
    └─ logs/      运行日志 app.log（出问题时把它发给维护的人）

RESOURCE_DIR 是 templates/、static/、内置 config/ 所在的位置（exe 版是打包解压出来的临时文件夹）。
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent.parent
    RESOURCE_DIR = APP_DIR

CONFIG_DIR = "config"
OV_NAME = "成就奖_手动调整.json"


# ---------------------------------------------------------------------------
# 设定文件（config/）
# ---------------------------------------------------------------------------
def config_candidates(file_name: str, env_name: str | None = None) -> list[Path]:
    """设定 / 规则文件的查找顺序（找到第一个就用）：
    1. 环境变量指定的文件
    2. 程序旁边的 config/（exe 版：把改好的文件放这里就会优先采用，不用重新打包）
    3. 程序旁边（旧的放法，仍然支持，启动时会提示移进 config/）
    4. exe 版：打包在 exe 里的 config/"""
    out = []
    env = os.environ.get(env_name) if env_name else None
    if env:
        out.append(Path(env))
    out += [APP_DIR / CONFIG_DIR / file_name, APP_DIR / file_name]
    if FROZEN:
        out.append(RESOURCE_DIR / CONFIG_DIR / file_name)
    return out


def find_config(file_name: str, env_name: str | None = None) -> Path:
    for p in config_candidates(file_name, env_name):
        if p.is_file():
            return p
    raise FileNotFoundError(f"找不到 {file_name}（应放在程序旁边的 config 文件夹）："
                            + "；".join(map(str, config_candidates(file_name, env_name))))


def is_legacy_location(p: Path | None) -> bool:
    """设定文件放在程序根目录（旧的放法）而不是 config/ 里"""
    return bool(p) and Path(p).resolve().parent == APP_DIR


# ---------------------------------------------------------------------------
# 运行时文件夹（data/、output/、logs/）
# ---------------------------------------------------------------------------
def _resolve(folder: str | Path, base: Path = APP_DIR) -> Path:
    p = Path(folder)
    return (p if p.is_absolute() else base / p).resolve()


@dataclass
class Dirs:
    result: Path
    data: Path
    output: Path
    logs: Path

    @property
    def overrides(self) -> Path:
        return self.data / OV_NAME

    def ensure(self, *names: str) -> None:
        for n in names or ("data", "output", "logs"):
            getattr(self, n).mkdir(parents=True, exist_ok=True)


def make_dirs(result_folder: str | Path = "Result", output_folder: str | Path = "output") -> Dirs:
    return Dirs(result=_resolve(result_folder), data=APP_DIR / "data",
                output=_resolve(output_folder), logs=APP_DIR / "logs")


def migrate_legacy(dirs: Dirs) -> list[str]:
    """旧版把「手动调整」存在程序根目录（或 Result 的上一层）；第一次用新版时自动搬进 data/。
    返回说明文字（给启动画面和日志用）。"""
    notes = []
    new = dirs.overrides
    for old in dict.fromkeys([APP_DIR / OV_NAME, dirs.result.parent / OV_NAME]):
        if not old.is_file() or old.resolve() == new.resolve():
            continue
        if new.exists():
            notes.append(f"发现旧的手动调整 {old}，但 {new} 已经存在，没有搬动（需要的话请手动合并）")
            continue
        dirs.ensure("data")
        shutil.move(str(old), str(new))
        notes.append(f"手动调整已从 {old} 搬到 {new}")
    return notes
