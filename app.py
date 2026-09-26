"""成就奖履历查看网站 (Individual's Utmost Achievement Calculator) —— 程序入口

读取 Result/ 里每位学生的「联课活动个人表现履历表」（.xlsx / .pdf），按上级规则统计，
在浏览器里显示。所有参数和用法见 achievement/cli.py（或 python app.py --help）。

    python app.py            # 开网站
    python app.py --help     # 所有参数

程序在 achievement/，设定和规则在 config/，文件夹说明见 achievement/paths.py 和 README.md。
"""
from achievement.cli import main

if __name__ == "__main__":
    main()
