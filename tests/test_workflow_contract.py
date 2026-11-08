"""Documentation contract checks, not evidence of predictive validity."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkflowContractTests(unittest.TestCase):
    def test_no_legacy_validation_or_numeric_weight_claims(self):
        paths = [ROOT / 'SKILL.md', *sorted((ROOT / 'workflows').glob('*.md'))]
        for path in paths:
            text = path.read_text()
            with self.subTest(path=path.name):
                for phrase in ('同一底层能量', '待其他盘验证', '置信度升级', '经过时间验证', '可选严格执行层'):
                    self.assertNotIn(phrase, text)
                self.assertIsNone(re.search(r'(?:命格|大运|流年|流月|流日)[（( ]?\d+%', text))

    def test_deep_entry_has_one_default(self):
        skill = (ROOT / 'SKILL.md').read_text()
        strict = (ROOT / 'workflows/fortune-auditable-reading.md').read_text()
        full = (ROOT / 'workflows/fortune-full-reading.md').read_text()
        self.assertIn('严格层默认执行', skill)
        self.assertIn('默认执行的严格层', strict)
        self.assertIn('先读取 `workflows/fortune-auditable-reading.md`', full)
        self.assertIn('旧输出 schema', full)
        self.assertIn('三盘对照', full)

    def test_depth_keeps_substance_and_boundaries(self):
        text = (ROOT / 'workflows/fortune-auditable-reading.md').read_text()
        for phrase in ('七节易读详批', '为什么这样解释', '什么时候不适用', '你可以做什么', '用户无示例', '未命中', '统计独立', '暂不判'):
            self.assertIn(phrase, text)

    def test_missing_data_and_legacy_fields_do_not_raise_reliability(self):
        skill = (ROOT / 'SKILL.md').read_text()
        self.assertIn('不将缺失证据转移给流年层', skill)
        self.assertIn('旧消费者确需星级', skill)
        specific = (ROOT / 'workflows/fortune-specific.md').read_text()
        self.assertIn('weights 时保留空对象', specific)
        self.assertIn('confidence 字段', specific)


if __name__ == '__main__':
    unittest.main()
