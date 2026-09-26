# CLAUDE.md —— 给 AI 助手（Claude）的项目说明

> 这份文件是「项目记忆」。在任何一台电脑用 Claude（Claude Code / Cowork / claude.ai）打开这个项目时，
> 先读这份文件，就能接着之前的工作做下去。**改了项目结构、规则流程或工作习惯，请同步更新这份文件。**
> 完整计分规则在 `Docs/成就奖计分规则.md`；每个版本改了什么在 `CHANGELOG.md`。

## 1. 这是什么

- **Individual's Utmost Achievement Calculator**（成就奖履历查看网站），维护者：ZhiJie Chong（循人中学 Tsun Jin High School）。
- 读取 `Result/` 里每位高三学生的「联课活动个人表现履历表」（`.xlsx` / `.pdf`），按**上级**（负责老师）定下的规则，
  统计「高三最高成就奖」：执委/职务数、中层管理数、筹委数、服务时数、活动、团内工作、比赛与获奖。
- 本地 Flask 网站 + 用 PyInstaller 打包成单一 exe（`scripts\build_exe.bat`），给不懂程序的老师双击使用。
- GitHub：`TJHS-Co-Curricular/Individual-s-Utmost-Achievement`。`Result/`、`data/`、`output/`、`logs/` 不进 git（学生个人资料）。

## 2. 和维护者沟通的方式

- **一律用简体中文回复**，用词浅白；维护者不是专业程序员，说明「改了什么、在哪里、要不要重新打包」即可，不要长篇技术细节。
- 规则由上级决定。维护者转达上级的修正时，**照做，不要自己发明规则**；遇到有歧义、会影响很多学生的情况，先举例问清楚。
- 每次改完告诉他：网页版按 Ctrl+F5 即可；改了 `static/`、`templates/`、`achievement/` 的话 exe 要重新跑 `scripts\build_exe.bat`；
  只改 `config/` 的 JSON 则不用重新打包（exe 旁边放 `config\` 会优先采用）。
- 可能有另一个 Claude 对话同时在改这个项目：动手前先看文件的最新版本，**合并**而不是覆盖别人的改动。

## 3. 文件结构（改动前先看这里）

```
app.py                入口，只有几行 → achievement/cli.py 的 main()
achievement/
  __init__.py         __version__（版本号唯一来源）、APP_NAME
  cli.py              参数（argparse）、启动画面、--export / --list-roles / --list-awards、开网站
  web.py              Flask：create_app(store, settings)、所有路由、离线版 HTML、导出
  store.py            Store：读取 Result（指纹有变才重读）、手动调整 data/成就奖_手动调整.json
  paths.py            ★ 所有文件夹位置：APP_DIR / RESOURCE_DIR、config 查找顺序、data/output/logs、旧文件搬迁
  logs.py             logs/app.log（RotatingFileHandler 1MB×5），未捕获的错误也写进去
  settings.py         读取 config/config.ini（[server] access/port/port_fallback/open_browser/lan_allow_edit；[data] result_folder/output_folder）
  reader.py           读 .xlsx（python-calamine）/ .pdf（pdfplumber）
  rules.py            计分流程：parse_rows、classify_role、standard_roles_from、move_event_roles、compute_exclusions、parse_hours、compute_stats …
  member_rules.py     读取 config/member_rules.json（职位归类、移栏、不计、特别标记）
  award_rules.py      读取 config/award.json（算不算获奖、是否代表本学会）
  engine.py           整个文件夹：多线程解析 + (mtime,size) 缓存、年份子文件夹（届别）、folder_version 指纹（含规则文件）
  excel.py            Excel 总表 / 明细 / 计分规则
config/               ★ 所有 .ini / .json 设定都只放这里：config.ini、member_rules.json、award.json
templates/            base.html、index.html（Jinja；**不要用 Prettier 等格式化工具整理，会弄坏 {{ }}**）
static/               app.js（界面）、core.js（浏览器端即时重算）、style.css、favicon.svg
scripts/              build_exe.bat、start_lan.bat、allow_firewall.bat（**必须纯 ASCII + CRLF 换行**）
tests/test_rules.py   unittest：规则判断 + 结构（版本号、config 位置、运行时文件夹、路由）
Docs/                 成就奖计分规则.md（完整规则）、给上级校对的 docx
运行时自动产生：data/（手动调整）、output/（导出）、logs/（日志）——python 版和 exe 版都在程序旁边
```

- 设定文件查找顺序（`paths.config_candidates`）：环境变量 → 程序旁边 `config/` → 程序根目录（旧放法，会提示）→ exe 内置 `config/`。
- 规则 JSON 改了会自动重载（mtime 指纹），网页几秒内重算，不用重启。

## 4. 规则怎么改（最常见的工作）

1. **职位 / 执委 / 筹委 / 中层管理 / 不计 / 特别标记** → 改 `config/member_rules.json`（五部分：一、不计 二、执委栏移到筹委栏 三、筹委栏移到执委栏 四、职位归类 五、特别标记；文件开头有「说明」）。
   每条规则的字段：`名称`、`包含任一`、`正则`、`并且包含任一`、`不包含`、`学会或内容包含任一`、`适用栏目`、`归类`、`例子` 等。
2. **获奖 / 是否代表本学会** → 改 `config/award.json`。
3. 只有 JSON 做不到的流程（服务时数、B 类、双学会重复、拆句）才改 `achievement/rules.py`。
4. **浏览器端要同步**：`static/core.js` 的 `rolesFrom` 必须和 Python 的 `standard_roles_from` 结果一致（职务列表、数量、中层管理）。
   每个 block 预先算好的字段：`b.rc`、`b.ex`、`b.aw`、`b.hr`、`b.sp`、`b.mv`、`b.nk`。
5. 每条上级确认的规则，在 `tests/test_rules.py` 加一个测试；然后跑 `python -m unittest discover tests -v`。
6. 更新 `Docs/成就奖计分规则.md`（写明「上级定」和日期）；需要时用 `python app.py --list-roles` / `--list-awards` 产生参考清单到 `output/`。

## 5. 已确认的重要规则（摘要，细节看 Docs/成就奖计分规则.md）

- 标准职称：主席、秘书、事务（事务 = 事物 = 总务）、财政（正/副）、查账（不分正副）、总学长（正/副）、助理总学长；没写正副当「正」；
  其它职位写成「执委(XXX)」；有上下文的写成「执委(联课处工委联课表扬大会-事务(副))」这类。
- 主席级：合唱团音乐主席、节令鼓队长类、例常活动副主席 = 主席(副)。
- 中层管理（另计，不算职务数）：助理类、授课人类、队长类、监督/督导/顾问/教练/领队类、首席/组长/领养人类、家族职位、联课组别、
  校内服务负责人（「校内服务负责人：A、B」拆成两条）、制服负责人、课务股、队伍管理、师徒制度·师傅、
  小队常委、体能关主、口令员、堂主、队副 / 小队副。
- 会员（不计职务数）：分团职位、职衔（Koperal 等）、XX培训、实习学长、单写「学长」；同年有其它职位就不另列会员。
- 移到筹委：执委栏里的演出 / 公演工委 / 带领人、写了工作时数的活动职位、为活动组成的筹委团职位、「监督/督导XX主席」、运动会/田径赛筹委、交流志工团职位；写在筹委栏的监督/督导/顾问类移到执委栏。
- 不计：班级活动（含班级歌曲比赛、运动会写生/号码布/短片比赛）、B 类、高三毕联会（含编辑/广告/教师节工委会）、感恩聚会、
  学会在运动会的义卖、校内服务里的教师节相关、模范学长、教师节演出负责人、《校讯》主编。
- 特别标记 ★（只标记不计分）：联课处工委、文娱工委、XXX志工工委、国际交流筹委/负责人。
- 服务时数：优先学生自填总数；「11h，筹备6h，活动5h」这种「总数 + 细分」只算总数；被排除条目的时数要扣掉。
- 比赛须代表本学会，判断不了标「待确认」暂时计入。
- 还没得到上级答复：「二线执委--制服股」算不算中层管理；校内服务以外栏目的教师节条目；执委(A,B) 算 2、筹委每条算 1；资料问题：B08 C04 21806 蔡佳芯 的舞蹈团职位被读进 B08 那一格，需人工看原件。

## 6. 版本号与日志

- 版本号只改 `achievement/__init__.py` 的 `__version__`（语义化版本：修 bug +0.0.1、新功能 / 改界面 +0.1.0、结构大改 +1.0.0），
  同时在 `CHANGELOG.md` 最上面加一段（测试会检查）。只改 config/ 规则不用改版本号。
- 版本号显示在：网页底部、启动画面、`/api/version`、日志、`python app.py --version`。
- 日志 `logs/app.log`：排查「读取失败」、闪退时先看它；`--dev` 记录每次请求。新代码用 `logging.getLogger(__name__)` 记重要事件和错误，不要只用 print。

## 7. 改完的检查清单

- `python -m unittest discover tests -v` 全部 OK。
- `python -m pyflakes app.py achievement` 没有警告（有装的话）；改了 JS 跑 `node --check static/app.js static/core.js`。
- 开网站实际看一次（简单 / 详细页、学生列表在 1280 宽屏幕不用左右拉）。
- 改了 `scripts\*.bat`：确认纯 ASCII、CRLF。
- 需要的话更新 `README.md`、`Docs/成就奖计分规则.md`、这份 `CLAUDE.md`、`CHANGELOG.md`。
