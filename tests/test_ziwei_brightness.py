"""Source fidelity tests, not validation of astrological interpretation."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
ZIWEI = ROOT / 'scripts/pai_pan_ziwei'


@unittest.skipUnless((ZIWEI / 'node_modules/tsx').exists(), 'npm ci required')
class ZiweiBrightnessTests(unittest.TestCase):
    def test_all_stars_preserve_source_and_legacy_fields(self):
        # Execute both the actual pinned dependency and wrapper, not a mocked chart.
        js = r'''
const { astro } = require('iztro');
const { generateChart } = require('./vendor/algorithm.ts');
const result = [];
for (let hour = 0; hour < 12; hour++) {
  const source = astro.bySolar('1990-5-15', hour, '男', true, 'zh-CN');
  const chart = generateChart({year:1990, month:5, day:15, hour, gender:'male'}, 2026);
  result.push({
    source: source.palaces.map(p => [...p.majorStars, ...p.minorStars, ...p.adjectiveStars]
      .map(s => ({name:s.name, brightness:s.brightness ?? null}))),
    stars: chart.palaces.map(p => p.stars)
  });
}
console.log(JSON.stringify(result));
'''
        r = subprocess.run(['node', '--import', 'tsx', '-e', js], cwd=ZIWEI,
                           text=True, capture_output=True, check=True)
        seen, missing, auxiliary = set(), 0, 0
        for pair in json.loads(r.stdout):
            for source, stars in zip(pair['source'], pair['stars']):
                self.assertEqual(len(source), len(stars))
                for s, star in zip(source, stars):
                    self.assertEqual(star['name'], s['name'])
                    raw = s['brightness'] or None
                    self.assertIn('brightnessRaw', star)
                    self.assertEqual(star['brightnessRaw'], raw)
                    if raw is None:
                        missing += 1
                    else:
                        seen.add(raw)
                    if star['type'] == 'major':
                        expected = 'bright' if raw in ('庙', '旺') else 'dim' if raw in ('不', '陷') else 'normal'
                        self.assertEqual(star['brightness'], expected)
                    else:
                        self.assertNotIn('brightness', star)
                        auxiliary += raw is not None
        self.assertEqual(seen, {'庙', '旺', '得', '利', '平', '不', '陷'})
        self.assertGreater(missing, 0)
        self.assertGreater(auxiliary, 0)

    def test_cli_preserves_distinction_in_json_and_text(self):
        cmd = ['node', '--import', 'tsx', 'pai_pan.ts', '--solar', '1990-05-15',
               '--hour', '12:30', '--sex', '男', '--age-year', '2026']
        data = json.loads(subprocess.run(cmd + ['--format', 'json'], cwd=ZIWEI,
                                        text=True, capture_output=True, check=True).stdout)
        stars = {s['name']: s for p in data['chart']['palaces'] for s in p['stars']}
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(stars['太阴']['brightnessRaw'], '不')
        self.assertEqual(stars['天梁']['brightnessRaw'], '陷')
        self.assertEqual(stars['太阴']['brightness'], stars['天梁']['brightness'])
        output = subprocess.run(cmd, cwd=ZIWEI, text=True, capture_output=True, check=True).stdout
        self.assertIn('太阴 (不)', output)
        self.assertIn('天梁 (陷)', output)
        self.assertNotIn('太阴 (落陷)', output)

    def test_combined_snapshot_retains_raw_field(self):
        import sys
        cmd = [sys.executable, str(ROOT / 'scripts/build_chart.py'), '--solar',
               '1990-05-15', '--hour', '12:30', '--sex', '男', '--lat', '31.23',
               '--lon', '121.47', '--analysis-year', '2026', '--format', 'json']
        result = json.loads(subprocess.run(cmd, text=True, capture_output=True, check=True).stdout)
        self.assertIsNone(result['degradation']['ziwei'])
        stars = [s for p in result['ziwei']['chart']['palaces'] for s in p['stars']]
        self.assertTrue(all('brightnessRaw' in s for s in stars))
        self.assertTrue(any(s['brightnessRaw'] is None for s in stars))


if __name__ == '__main__':
    unittest.main()
