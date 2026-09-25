"""规则的自动测试（不需要额外安装东西）。

在项目根目录运行：
    python -m unittest discover tests -v

改了 config/ 里的规则或 achievement/ 的程序后跑一次：全部 OK 就表示下面这些已确认的判断都没被改坏。
如果是「故意改了规则」导致某条测试不通过，把那条测试的预期结果一起改掉即可。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from achievement import award_rules, member_rules, rules  # noqa: E402


class ConfigFiles(unittest.TestCase):
    def test_rule_files_are_in_config(self):
        self.assertEqual(member_rules.path().parent.name, "config")
        self.assertEqual(award_rules.path().parent.name, "config")

    def test_rule_files_load(self):
        self.assertTrue(member_rules.get().roles)
        self.assertTrue(award_rules.get().club_kw)


class Roles(unittest.TestCase):
    def cls(self, text, club=""):
        return rules.classify_role(text, club)

    def test_standard_titles(self):
        self.assertEqual(self.cls("副主席"), {"std": "主席(副)"})
        self.assertEqual(self.cls("主席"), {"std": "主席(正)"})          # 没写正副 → 正
        self.assertEqual(self.cls("查账"), {"std": "查账"})              # 查账不分正副
        self.assertEqual(self.cls("音乐主席"), {"std": "主席(正)"})      # 合唱团音乐主席 = 主席级

    def test_shiwu_aliases(self):   # 事务 = 事物 = 总务
        self.assertEqual(self.cls("副总务"), {"std": "事务(副)"})
        self.assertEqual(self.cls("正事物"), {"std": "事务(正)"})
        self.assertNotEqual(self.cls("总务股"), {"std": "事务(正)"})

    def test_title_with_context(self):
        self.assertEqual(self.cls("担任联课处工委联课表扬大会——副总务"), {"other": "联课处工委联课表扬大会-事务(副)"})

    def test_member(self):
        self.assertEqual(self.cls("会员"), {"std": "会员"})

    def test_mid_management(self):
        self.assertEqual(self.cls("华乐团副弹拨首席。", "华乐团")["mid"], ["副弹拨首席"])
        self.assertEqual(self.cls("秘书助理")["mid"], ["秘书助理"])
        self.assertEqual(self.cls("学生顾问")["mid"], ["学生顾问"])
        self.assertEqual(self.cls("校内服务负责人：新春快闪、运动会开幕及闭幕仪式演出")["mid"],
                         ["校内服务负责人-新春快闪", "校内服务负责人-运动会开幕及闭幕仪式演出"])

    def test_moves(self):
        R = member_rules.get()
        self.assertTrue(R.moves_to_comm("《弈德杯》筹委主席"))
        self.assertTrue(R.moves_to_comm("监督成果汇报主席"))
        self.assertTrue(R.moves_to_comm("运动会主席"))
        self.assertFalse(R.moves_to_comm("2024/2025 联课处工委"))
        self.assertTrue(R.moves_to_role("高三欢送会——学生顾问"))

    def test_exclusions(self):
        R = member_rules.get()
        self.assertIsNotNone(R.exclusion("高三毕联会广告工委", "role"))
        self.assertIsNotNone(R.exclusion("感恩聚会-灯光服务（19.5小时）", "intSvc"))
        self.assertIsNotNone(R.exclusion("教师节场布服务（2小时）", "intSvc"))
        self.assertIsNone(R.exclusion("教师节场布服务（2小时）", "comm"))     # 只限校内服务栏
        self.assertIsNotNone(R.exclusion("心动不如 Sing 动", "intComp"))
        self.assertIsNone(R.exclusion("班级歌曲比赛票务股", "comm"))          # 学会的筹委照算


class Awards(unittest.TestCase):
    def test_award(self):
        self.assertTrue(rules.is_award("全国华乐比赛——第五名"))
        self.assertTrue(rules.is_award("Individual pattern - Bronze medal"))
        self.assertTrue(rules.is_award("参加 XX 比赛并获得团体第三名"))
        self.assertFalse(rules.is_award("参与步操比赛"))

    def test_represents_club(self):
        self.assertIsNone(rules.comp_judge("全国舞蹈比赛", "C04"))
        self.assertIn("非代表本学会", rules.comp_judge("武术比赛", "C04"))
        self.assertIn("体育", rules.comp_judge("参与运动会跳高比赛", "A01"))


class Hours(unittest.TestCase):
    def test_parse_hours(self):
        self.assertEqual(rules.parse_hours("3小时"), 3.0)
        self.assertEqual(rules.parse_hours("（5小时5分钟）"), 5.08)
        self.assertEqual(rules.parse_hours("60M / 120M"), 1.0)
        self.assertEqual(rules.parse_hours("（11h，筹备6h，活动5h）"), 11.0)   # 总数 + 细分 → 只算总数
        self.assertEqual(rules.parse_hours("2小时35分钟+ 9小时50分钟"), 12.42)


class WholeFolder(unittest.TestCase):
    """有 Result/ 文件夹时，确认整个文件夹都读得进来、算得出来。"""

    def test_load_result_folder(self):
        folder = ROOT / "Result"
        if not folder.is_dir():
            self.skipTest("没有 Result/ 文件夹")
        from achievement.engine import load_folder
        students, files, failed = load_folder(folder)
        self.assertTrue(students)
        for s in students:
            st, _ = rules.compute_stats(s)
            self.assertGreaterEqual(st["hours"], 0)


if __name__ == "__main__":
    unittest.main()
