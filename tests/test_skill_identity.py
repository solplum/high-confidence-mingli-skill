"""Keep the discoverable skill identity aligned with the repository name."""
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAME = "high-confidence-mingli-skill"


class SkillIdentityTests(unittest.TestCase):
    def test_registration_and_installation_agree(self):
        skill = (ROOT / "SKILL.md").read_text()
        name = re.search(r"^name: (.+)$", skill, re.MULTILINE).group(1)
        self.assertEqual(name, NAME)
        self.assertRegex(name, r"^[a-z0-9-]{1,64}$")
        # Exercise the documented installation layout without changing user data.
        with tempfile.TemporaryDirectory() as home:
            install = Path(home) / ".claude" / "skills" / NAME
            shutil.copytree(ROOT, install, ignore=shutil.ignore_patterns(
                ".git", "node_modules", "__pycache__"))
            discovered = list((Path(home) / ".claude" / "skills").glob("*/SKILL.md"))
            self.assertEqual(discovered, [install / "SKILL.md"])
            self.assertEqual(discovered[0].parent.name, name)
            for resource in ("scripts/build_chart.py", "docs/onboarding.md",
                             "knowledge/catalog.json", "workflows/fortune-close.md"):
                self.assertTrue((install / resource).is_file(), resource)

    def test_bilingual_install_and_invocation_examples(self):
        readme = (ROOT / "README.md").read_text()
        command = f"git clone https://github.com/solplum/{NAME}.git ~/.claude/skills/{NAME}"
        self.assertEqual(readme.count(command), 2)
        self.assertEqual(readme.count(f"cd ~/.claude/skills/{NAME}/scripts/pai_pan_ziwei && npm ci"), 2)
        for text in (readme, (ROOT / "SKILL.md").read_text()):
            self.assertIn(f"`/{NAME}`", text)
            self.assertNotIn("`/fortune-telling`", text)

    def test_legacy_data_remains_accessible(self):
        for file in ("SKILL.md", "docs/onboarding.md", "templates/chart.template.md",
                     "scripts/build_chart.py", "workflows/fortune-close.md"):
            text = (ROOT / file).read_text()
            self.assertIn("~/.claude/fortune-telling/", text)
            self.assertNotIn(f"~/.claude/{NAME}/", text)


if __name__ == "__main__":
    unittest.main()
