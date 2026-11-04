"""QoR Guard 0.3: v1/v2 requirement asymmetry and the intentional v1 threshold-precedence change.
v1 records are captured by the frozen 0.2.0 code from synthetic fixtures. v2 records are SYNTHETIC or use a made-up requirement.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import glob
import json
import os
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import compare, report, run, timing  # noqa: E402
from tests.test_v03_timing import FROZEN, FIXTURES, RULES, Base  # noqa: E402

UNAVAILABLE = 'REQUIREMENT COMPARISON UNAVAILABLE'
MISS = 'REQUIRED CLOCK NOT MET'
FIX_A, FIX_C = os.path.join(FIXTURES, 'design_a'), os.path.join(FIXTURES, 'design_c')
REQ = {'clk': 48.0}
OK, LOW = [50.0, 52.0], [40.0, 41.0]
FMAX_TIGHT = [dict(metric='fmax_min[*', max_decrease_pct=1.0)]
FMAX_AND_REQUIRED = FMAX_TIGHT + [dict(metric='lut4', max_increase_pct=1.0, required=True)]
PY = [sys.executable, '-I', '-B']


class Case(Base):
    def v1(self, name, src=FIX_A):
        out = f'{self.t}/{name}'
        p = subprocess.run(PY + [FROZEN, 'capture', '--out', out, '--nextpnr', *sorted(glob.glob(src + '/pnr_report_s*.json'))],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return out

    def result(self, b, c, rules=RULES):
        res = compare.compare(b, c, rules)
        return res['exit_code'], res['verdict']


class TestMixedVersions(Case):
    def test_v1_baseline_v2_current_declared_and_met(self):
        v1, v2 = run.load(self.v1('a')), self.side(OK, REQ)
        self.assertEqual(self.result(v1, v2), (2, UNAVAILABLE))
        md = report.markdown(v1, v2, compare.compare(v1, v2, RULES))
        self.assertIn('**Requirement comparison unavailable:** current declares 48.0 MHz for this clock, and baseline is a schema v1 record', md)
        self.assertIn('This is not taken to mean that no requirement existed', md)
        self.assertNotIn('PASS', md)

    def test_v2_baseline_declared_v1_current(self):
        v1, v2 = run.load(self.v1('a')), self.side(OK, REQ)
        self.assertEqual(self.result(v2, v1), (2, UNAVAILABLE))
        md = report.markdown(v2, v1, compare.compare(v2, v1, RULES))
        self.assertIn('**Requirement comparison unavailable:** baseline declares 48.0 MHz for this clock, and current is a schema v1 record', md)
        self.assertNotIn('PASS', md)

    def test_v1_baseline_with_current_miss(self):
        self.assertEqual(self.result(run.load(self.v1('a')), self.side(LOW, REQ)), (1, f'{MISS} + {UNAVAILABLE}'))

    def test_v1_baseline_with_current_threshold_violation(self):
        v1 = run.load(self.v1('a'))                                     # about 70 MHz
        self.assertEqual(self.result(v1, self.side(LOW, {'other': 1.0}, clock='clk$SB_IO_IN_$glb_clk'), FMAX_TIGHT),
                         (1, f'THRESHOLD EXCEEDED + REQUIRED CLOCK NOT EVALUATED + {UNAVAILABLE}'))

    def test_v2_baseline_declared_with_v1_current_threshold_violation(self):
        clock = 'clk$SB_IO_IN_$glb_clk'
        v2 = self.side([200.0, 201.0], {clock: 48.0}, clock=clock)
        self.assertEqual(self.result(v2, run.load(self.v1('a')), FMAX_TIGHT), (1, f'THRESHOLD EXCEEDED + {UNAVAILABLE}'))

    def test_nothing_is_copied_or_invented(self):
        v1, v2 = run.load(self.v1('a')), self.side(OK, REQ)
        x = next(k for k in timing.compare_timing(v1, v2)['clocks'] if k['clock'] == 'clk')
        self.assertEqual((x['baseline']['required_mhz'], x['baseline']['state']), (None, timing.NOT_STORED))
        self.assertEqual((x['requirement_comparison_unavailable_on'], x['declaration_missing_on'], x['values_differ']), ('baseline', None, False))
        self.assertNotIn('schema_version', v1)
        self.assertNotIn('provenance', v1)

    def test_v2_with_no_declaration_against_v1_passes(self):
        clock = 'clk$SB_IO_IN_$glb_clk'
        v1 = run.load(self.v1('a'))
        self.assertEqual(self.result(v1, self.side([70.0, 72.0], clock=clock)), (0, 'PASS'))
        self.assertEqual(self.result(self.side([70.0, 72.0], clock=clock), v1), (0, 'PASS'))

    def test_only_declared_clocks_are_flagged(self):
        v1 = run.load(self.v1('a'))
        res = compare.compare(v1, self.side([{'a': 50.0, 'b': 60.0}, {'a': 51.0, 'b': 61.0}], {'a': 48.0}), RULES)
        self.assertEqual(res['requirement_comparison_unavailable'], ['a'])


class TestUnchangedSymmetric(Case):
    def test_v1_vs_v1_preserved(self):
        a, b = run.load(self.v1('a')), run.load(self.v1('b'))
        self.assertEqual(self.result(a, b), (0, 'PASS'))
        self.assertEqual(compare.compare(a, b, RULES)['requirement_comparison_unavailable'], [])

    def test_v2_vs_v2_rules_preserved(self):
        self.assertEqual(self.result(self.side(OK, REQ), self.side(OK, REQ)), (0, 'PASS'))
        self.assertEqual(self.result(self.side(OK), self.side(OK, REQ)), (2, 'INCONSISTENT REQUIREMENTS'))
        self.assertEqual(compare.compare(self.side(OK), self.side(OK, REQ), RULES)['requirement_comparison_unavailable'], [])


class TestV1ThresholdChange(Case):
    def compare_cli(self, program, a, b, rules_path):
        return subprocess.run(PY + [program, 'compare', '--baseline', a, '--current', b, '--config', rules_path],
                              capture_output=True, text=True, encoding='utf-8')

    def test_threshold_violation_with_missing_required_metric_is_exit_1(self):
        a, b = self.v1('a', FIX_A), self.v1('b', FIX_C)                      # no Yosys input, so lut4 is missing; design_c's Fmax is lower
        p = f'{self.t}/rules.json'
        with open(p, 'w') as f:
            json.dump(dict(rules=FMAX_AND_REQUIRED), f)
        new = self.compare_cli(os.path.join(ROOT, 'qorguard.py'), a, b, p)
        self.assertEqual(new.returncode, 1, new.stderr)
        self.assertIn('THRESHOLD EXCEEDED + MISSING REQUIRED METRIC', new.stdout.splitlines()[0])

    def test_frozen_020_exits_2_on_the_same_input(self):
        a, b = self.v1('a', FIX_A), self.v1('b', FIX_C)
        p = f'{self.t}/rules.json'
        with open(p, 'w') as f:
            json.dump(dict(rules=FMAX_AND_REQUIRED), f)
        old = self.compare_cli(FROZEN, a, b, p)
        self.assertEqual(old.returncode, 2, old.stderr)
        self.assertIn('THRESHOLD EXCEEDED + MISSING REQUIRED METRIC', old.stdout.splitlines()[0])

    def test_change_is_documented(self):
        with open(os.path.join(ROOT, 'CHANGELOG_0.3.md'), encoding='utf-8') as f:
            self.assertIn('Intentional behaviour change from 0.2.0', f.read())


if __name__ == '__main__':
    unittest.main()
