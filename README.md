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
app.py                  网站路由（读取 Result、API、导出）
achievement/            履历解析与计分
  reader.py              读取 .xlsx（python-calamine）与 .pdf（pdfplumber）
  rules.py               ★ 所有计分规则都在这里
  engine.py              整个文件夹的读取、多线程解析、缓存
  excel.py               生成 Excel 统计表
templates/              网页 HTML 模板
  base.html
  index.html
static/                 样式 / 前端脚本 / 图示
  style.css
  app.js                 页面逻辑（搜索、排序、对比、图表、自动载入）
  core.js                手动调整后的即时重算
  favicon.svg
requirements.txt        Python 依赖清单
build_exe.bat           一次性打包成 .exe（见下方「方式 B」）
Result/                 你的资料（每位学生一份履历表）
```

打包后只需要 `Individual's Utmost Achievement Calculator.exe` 和 `Result/` 放在一起，`templates/`、`static/`
已经封装在 exe 里面。

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
   双击 `build_exe.bat`。
2. 等它跑完（约 1-3 分钟），同一个文件夹里会出现 `Individual's Utmost Achievement Calculator.exe`。
3. 把 `Individual's Utmost Achievement Calculator.exe` 和 `Result/` 放在同一层，双击 exe 即可——
   **这台或其他任何 Windows 电脑都不需要安装 Python**。

分享给别人时，只要一起拷贝：

```
Individual's Utmost Achievement Calculator.exe
Result/
成就奖_手动调整.json     ← 可选：你做过的「计入 / 不计」调整
```

---

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
5. 执委/职务按手册统一写法；其它职位写成「执委(XXX,XXX)」；主席等没写正/副的当作「正」；合唱团音乐主席、节令鼓队长类等同主席；童军分团、监督/督导/顾问/教练/领队、小队长类一律算会员。
6. 服务时数优先用学生自填的总服务时数，没填则逐项相加；不计入的服务条目的小时数会扣除。
