"""QoR Guard 0.3: each Fmax threshold rule is judged on its own, so a median violation fails the comparison even when
the worst-seed rule passes. Locks in existing behaviour; production logic is unchanged.
The minimum and median below match figures an external evaluator reported for spi-fpga-core (spi_top, v1.0 against
v1.1 before its timing restructure), but every report here is SYNTHETIC: the seed 2 and 4 values are invented
fillers, and these are not that evaluator's report files.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import compare, run  # noqa: E402

RULES = os.path.join(ROOT, 'config', 'thresholds.example.json')
# SYNTHETIC per-seed achieved Fmax (MHz). Only min and median are fixed by the reported figures; the rest are invented.
BASELINE = [42.3, 39.9, 43.6, 41.0, 43.0]   # min 39.9, median 42.3
CURRENT = [37.1, 36.5, 38.3, 36.8, 37.7]    # min 36.5, median 37.1


class TestMedianRuleFailsWhileWorstSeedPasses(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='qg_fmax_rules_')
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        with open(RULES, encoding='utf-8') as f:
            self.rules = [r for r in json.load(f)['rules'] if r['metric'].startswith('fmax')]

    def capture(self, name, values):
        files = []
        for seed, v in enumerate(values, 1):
            p = os.path.join(self.tmp, f'{name}_s{seed}.json')
            with open(p, 'w', encoding='utf-8') as f:
                json.dump({'fmax': {'clk': {'achieved': v, 'constraint': 50.0}},
                           'utilization': {'ICESTORM_LC': {'used': 1000, 'available': 5280}}}, f)
            files.append(p)
        return run.capture(os.path.join(self.tmp, name), None, None, files, name)

    def test_median_violation_fails_comparison(self):
        base, cur = self.capture('base', BASELINE), self.capture('cur', CURRENT)
        m_b, m_c = base['metrics'], cur['metrics']
        self.assertEqual(m_b['fmax_min[clk]']['value'], 39.9)
        self.assertEqual(m_c['fmax_min[clk]']['value'], 36.5)
        self.assertEqual(m_b['fmax_median[clk]']['value'], 42.3)
        self.assertEqual(m_c['fmax_median[clk]']['value'], 37.1)

        limits = {r['metric']: r['max_decrease_pct'] for r in self.rules}
        self.assertEqual(limits, {'fmax_min[*': 10.0, 'fmax_median[*': 10.0})

        res = compare.compare(base, cur, self.rules, 'revision')
        rows = {r['metric']: r for r in res['rows']}
        self.assertEqual(rows['fmax_min[clk]']['status'], 'OK')            # -8.52%, within -10%
        self.assertEqual(rows['fmax_median[clk]']['status'], 'REGRESSION')  # -12.29%, beyond -10%
        self.assertEqual(res['exit_code'], 1)
        self.assertEqual(res['verdict'], 'REGRESSION')

        self.assertEqual(compare.compare(base, cur, self.rules, 'unknown')['verdict'], 'THRESHOLD EXCEEDED')
        min_only = [r for r in self.rules if r['metric'].startswith('fmax_min')]
        self.assertEqual(compare.compare(base, cur, min_only, 'revision')['exit_code'], 0)


if __name__ == '__main__':
    unittest.main()
