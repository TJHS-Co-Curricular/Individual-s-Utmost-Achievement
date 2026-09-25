# 成就奖履历查看网站 (Achievement Viewer)

`app.py` 是一个本地小网站，会读取 `Result/` 文件夹里每位学生的「联课活动个人表现履历表」
（`.xlsx` / `.pdf`），按手册规则统计，在浏览器里显示：

- 学生列表：搜索、按学会 / 班级 / 年份筛选、点表头排序（服务时数、职务、获奖…）
- 个人完整履历：按年份分组，不计入的条目以灰色划线显示并注明原因
- 最多 4 人并排对比、统计图表、资料问题清单
- 手动「计入 / 不计」：自动保存到 `成就奖_手动调整.json`，下次打开照样套用
- **自动载入**：网站开着的时候，往 `Result/` 新增、修改、删除履历表，网页几秒内自动更新
- 下载 Excel（总表 + 明细 + 计分规则）、导出离线版 HTML（单一文件，可发给别人）

有两种使用方式：**A) 直接用 Python 运行**，或 **B) 打包成一个不需要 Python 的 .exe**，
两者显示的内容完全一样。

---

## 项目文件结构

```
Individual's Utmost Achievement/
├─ app.py                  程序入口：本地网站（读取 Result、API、导出）
├─ config/                 ★ 设定与规则表——平时只改这里
│   ├─ config.ini             网站设定：只限本机 / 局域网、端口、自动开浏览器、Result 位置
│   ├─ member_rules.json      执委 / 职务归类（执委、主席级、中层管理、会员、筹委、不计）
│   └─ award.json             比赛规则（算不算获奖 ★、是不是代表本学会）
├─ achievement/            程序（Python 套件），平时不用改
│   ├─ reader.py              读取 .xlsx（python-calamine）与 .pdf（pdfplumber）
│   ├─ rules.py               计分流程（服务时数、B 类、双学会重复等），职位 / 比赛部分照 config/ 执行
│   ├─ member_rules.py        读取 config/member_rules.json
│   ├─ award_rules.py         读取 config/award.json
│   ├─ engine.py              整个文件夹的读取、多线程解析、缓存
│   └─ excel.py               生成 Excel 统计表
├─ templates/              网页 HTML 模板（base.html、index.html）
├─ static/                 网页样式与脚本（style.css、app.js、core.js、favicon.svg）
├─ scripts/
│   ├─ build_exe.bat          一次性打包成 .exe（见下方「方式 B」）
│   ├─ start_lan.bat          局域网共享启动（让同事用 IP 访问）
│   └─ allow_firewall.bat     开防火墙端口（以系统管理员身份执行，只在需要时用）
├─ tests/
│   └─ test_rules.py          规则自动测试：python -m unittest discover tests -v
├─ docs/                   文档（计分规则、供校对的 Word 等）
│   └─ generated/             自动产生的参考清单（已知职位一览.xlsx、已知获奖一览.xlsx），不进 git
├─ Result/                 你的资料（每位学生一份履历表），不进 git
├─ requirements.txt        Python 依赖清单
├─ README.md
└─ .gitignore
```

运行时还会在项目根目录产生：`成就奖_手动调整.json`（网页里的「计入 / 不计」）、导出的离线版 HTML 和 Excel。

**Result 里放年份子文件夹**（例：`Result/2025/`、`Result/2026/`）：网站读取最新一届（名称最大的那个文件夹）；
「下载职位一览 / 获奖一览」（`--list-roles` / `--list-awards`）会读全部届别，每一届的出现次数另列一栏（`2025届`、`2026届`）。
Result 里直接放履历表的话，照旧只读 Result 本身。

打包后只需要 `Individual's Utmost Achievement Calculator.exe` 和 `Result/` 放在一起；`templates/`、`static/`、
`config/` 已经封装在 exe 里面。要在 exe 版改规则：在 exe 旁边建一个 `config/` 文件夹，放入改好的
`member_rules.json` / `award.json`，就会优先采用，不必重新打包。

### 修改职位规则（config/member_rules.json）

- 用任何文字编辑器打开 `config/member_rules.json`，文件最上面的「说明」写了每个栏位的意思。
- 分五部分：一、不计　二、执委栏移到筹委栏　三、筹委栏移到执委栏　四、职位归类（执委 / 主席级 / 中层管理 / 会员 + 标准职称）　五、特别标记。
- 例：要让「XX部长」算中层管理，在「四、职位归类」里的某个中层管理规则的「包含任一」加上 `"部长"`。
- 存档后网页几秒内自动重算；exe 版把改好的 `member_rules.json` 放在 exe 旁边的 `config/` 文件夹即可（会优先采用，不必重新打包）。
- 想看每个职位目前被算成什么：网页右上角「下载职位一览」，或运行 `python app.py --list-roles`（存成 `docs/generated/已知职位一览.xlsx`）。里面列出 Result 里出现过的所有执委栏职位及目前的归类（执委 / 主席级 / 中层管理 / 会员 / 筹委 / 不计），可筛选排序；只供参考，改它不影响计算。
- 存档前注意 JSON 格式：字串用英文双引号，项目之间用英文逗号，最后一项后面不能有逗号。
- 改完可以跑一次 `python -m unittest discover tests -v`，确认已确认的规则没被改坏。


### 修改比赛规则（config/award.json）

- 结构和 member_rules.json 一样，文件最上面有「说明」。分五部分：一、不算获奖（例外）　二、出现即算获奖　三、比赛名称后面写的名次 / 奖项　四、写明「获得 / 荣获 / 赢得」　五、比赛是否代表本学会（各学会关键词 + 体育 / 辩论 / 时事常识等其它类别关键词）。
- 例：舞蹈团学生的某个比赛被判成「非代表本学会」，但其实是舞蹈比赛 → 在「五」的「各学会关键词」→ C04 的「关键词」加上那个比赛的字眼。
- 例：要让「参与奖」不算获奖，在「一、不算获奖（例外）」的「包含任一」加上 `"参与奖"`；要让「Participation」算获奖，加在「二」的「包含任一」。
- 想看每个比赛条目目前算不算获奖：网页右上角「下载获奖一览」，或 `python app.py --list-awards`（存成 `docs/generated/已知获奖一览.xlsx`）。
---

## 方式 A：直接用 Python 运行

```bash
pip install -r requirements.txt
python app.py
```

浏览器会自动打开 <http://127.0.0.1:5000>（5000 被占用时自动换下一个端口）。

## 方式 B：打包成可携带的 .exe（不需要 Python）

> 真正的 Windows `.exe` 只能在 **Windows 电脑上打包**（PyInstaller 的限制），
> 但这一步**只需要做一次**。

1. 在任何一台装有 Python 的 Windows 电脑上（安装 Python 时勾选 **"Add python.exe to PATH"**），
   双击 `scripts\build_exe.bat`（exe 会产生在项目根目录，和 `Result/` 放在一起）。
2. 等它跑完（约 1-3 分钟），项目根目录里会出现 `Individual's Utmost Achievement Calculator.exe`。
3. 把 `Individual's Utmost Achievement Calculator.exe` 和 `Result/` 放在同一层，双击 exe 即可——
   **这台或其他任何 Windows 电脑都不需要安装 Python**。

分享给别人时，只要一起拷贝：

```
Individual's Utmost Achievement Calculator.exe
Result/
成就奖_手动调整.json     ← 可选：你做过的「计入 / 不计」调整
```

---

## 网站设定（config/config.ini）

用记事本打开 `config/config.ini`，改完存档、重新启动就生效：

| 设定 | 意思 | 预设 |
|---|---|---|
| `access` | `local` = 只有这台电脑能开；`lan` = 同一网络的同事也能用 IP 打开 | `local` |
| `port` | 网站端口，同事的网址就是 `http://IP:这个号码` | `5000` |
| `port_fallback` | 端口被占用时，`yes` 自动改用下一个，`no` 停止并提示 | `yes` |
| `open_browser` | 启动时自动打开浏览器 | `yes` |
| `lan_allow_edit` | 局域网的同事可不可以改「计入 / 不计」 | `no` |
| `result_folder` | 履历表文件夹（相对路径或完整路径） | `Result` |

写错的值会在黑色窗口提示，并改用预设值。exe 版：把改好的 `config.ini` 放在 exe 旁边的 `config\` 文件夹就会采用。
启动参数会盖过设定：`--lan`、`--local`、`--port=5050`、`--no-browser`。

## 让同事用 IP 访问（局域网共享）

平常网站只有开网站的这台电脑能打开（`127.0.0.1`）。要让同一个网络里的同事也能看：

1. 把 `config/config.ini` 的 `access` 改成 `lan` 再启动；或只这一次双击 `scripts\start_lan.bat`（等于 `--lan`）。
2. 黑色窗口会列出给同事的网址，例：`http://192.168.0.23:5000`。
3. 第一次会跳出 Windows 防火墙窗口，勾「专用网络」→「允许访问」。之前按过「取消」的话，
   右键 `scripts\allow_firewall.bat` →「以系统管理员身份执行」。
4. 还是打不开：到 Windows 设置 → 网络，把这个网络设为「专用」（不是「公用」）；两台电脑要在同一个网络（同一个 Wi-Fi / 路由器）。

同事只能查看、搜索、下载 Excel / 离线版；「计入 / 不计」只能在开网站的那台电脑上改。
学生资料会在局域网里看得到，不需要时请用一般方式（直接双击 exe）启动。

## 其它用法

```
python app.py "D:\某个地方\Result"      指定别的 Result 文件夹
python app.py --dev                     显示每次请求记录（除错用）
python app.py --export                  不开网站，直接在 Result 旁边导出离线版 HTML + Excel
python app.py --no-browser              不自动打开浏览器
```

exe 用法相同，例如 `Individual's Utmost Achievement Calculator.exe "D:\某个地方\Result"`。

## 计分规则（摘要）

所有规则集中在 `achievement/rules.py`，网页「说明」页和 Excel「计分规则」表也有完整说明。

1. 以班级为单位的内容、服务、活动、比赛不计；学会的筹委、团内工作照算。
2. 只计 A、C、D、E 类；B 类（体育、学术培训队）整年不计。
3. 同一年同一比赛写在两个学会时只计一次，保留与比赛相关的学会。
4. 比赛须代表本学会；与所属学会无关的个人比赛不计。按学会关键词自动判断，判断不了的标「待确认」，暂时计入。
5. 执委/职务按手册统一写法；其它职位写成「执委(XXX,XXX)」；主席等没写正/副的当作「正」；合唱团音乐主席、节令鼓队长类等同主席；童军分团算会员；「监督/督导XX主席」算活动筹委；助理类、授课人类、队长类、监督/督导/顾问/教练/领队类、首席/组长/领养人类、家族职位、联课组别、校内服务负责人另计「中层管理」；感恩聚会不计。
6. 服务时数优先用学生自填的总服务时数，没填则逐项相加；不计入的服务条目的小时数会扣除。
