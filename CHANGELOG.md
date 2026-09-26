# 更新记录（CHANGELOG）

版本号写在 `achievement/__init__.py` 的 `__version__`，改版时在这里最上面加一段。
规则表（`config/` 里的 JSON）的改动不用改版本号，但可以在这里顺便记下。

## 1.1.0 — 2026-09-26

**项目标准化**
- 代码结构：`app.py` 只剩入口；网站在 `achievement/web.py`，启动与参数在 `achievement/cli.py`，
  资料状态在 `achievement/store.py`，所有文件夹位置集中在 `achievement/paths.py`，日志在 `achievement/logs.py`。
- 运行时文件夹统一（python 版和 exe 版一样，都在程序旁边）：
  `data/`（手动调整）、`output/`（导出）、`logs/`（日志）。旧位置的 `成就奖_手动调整.json` 第一次启动时自动搬进 `data/`。
- 设定档全部在 `config/`：`config.ini`、`member_rules.json`、`award.json`；新增 `output_folder` 设定。
- 版本号：网页底部、启动画面、`/api/version`、日志都显示；`python app.py --version`。
- 日志：`logs/app.log`（满 1 MB 换新，保留 5 个），记录启动、载入、读取失败、手动调整、导出和所有错误。
- `--export` 的 Excel 文件名也加上日期时间。

**网页**
- 个人页「执委 / 中层管理 / 筹委」改成每个职位一行，前面标明类别（简单、详细都一样）。
- 学生列表栏宽收窄，一般屏幕不用左右拉；标签栏右边多出来的拉条已去掉。

## 1.0.0 — 2026-09-24

- 第一个完整版本：读取 Result 的 .xlsx / .pdf、按上级规则统计、网页查看 / 对比 / 图表、
  手动计入 / 不计、导出 Excel 与离线版、局域网共享、打包成 exe。
