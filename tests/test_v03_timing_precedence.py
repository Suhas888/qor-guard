"""QoR Guard 0.3: a known failure outranks missing or inconsistent evidence, and a requirement declared on one side is inconsistent.
All reports are SYNTHETIC (temp dirs, invented values) including the v1 records: logic only, no hardware validation.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import glob
import os
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import compare, report, run, timing  # noqa: E402
from tests.test_v03_timing import FROZEN, FIXTURES, RULES, TIGHT, Base  # noqa: E402

MISS = 'REQUIRED CLOCK NOT MET'
NOT_EVAL = 'REQUIRED CLOCK NOT EVALUATED'
INCONS = 'INCONSISTENT REQUIREMENTS'
SOME = 'INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED'
ALL = 'INCOMPLETE EVIDENCE: ALL DECLARED RUNS FAILED'
REQ = {'clk': 48.0}
OK, LOW, HIGH = [50.0, 52.0], [40.0, 41.0], [90.0, 91.0]
REQUIRED_METRIC = RULES + [dict(metric='lut4', max_increase_pct=1.0, required=True)]
TIGHT_REQUIRED = TIGHT + [dict(metric='lut4', max_increase_pct=1.0, required=True)]


class Case(Base):
    def result(self, b, c, rules=RULES, kind='unknown'):
        res = compare.compare(b, c, rules, kind)
        return res['exit_code'], res['verdict']

    def report_text(self, b, c, rules=RULES):
        return report.markdown(b, c, compare.compare(b, c, rules))


class TestAsymmetricDeclarations(Case):
    def test_baseline_declares_current_omits(self):
        b, c = self.side(OK, REQ), self.side(OK)
        self.assertEqual(self.result(b, c), (2, INCONS))
        md = self.report_text(b, c)
        self.assertIn('**Inconsistent requirements:** baseline declares 48.0 MHz for this clock and current declares none', md)
        self.assertIn('No requirement is copied or inferred', md)
        self.assertNotIn('PASS', md)
        self.assertIn('### Timing for clock `clk`', md)

    def test_current_declares_baseline_omits(self):
        b, c = self.side(OK), self.side(OK, REQ)
        self.assertEqual(self.result(b, c), (2, INCONS))
        md = self.report_text(b, c)
        self.assertIn('**Inconsistent requirements:** current declares 48.0 MHz for this clock and baseline declares none', md)
        self.assertNotIn('PASS', md)

    def test_side_recorded_and_nothing_copied(self):
        for b, c, side in ((self.side(OK, REQ), self.side(OK), 'current'), (self.side(OK), self.side(OK, REQ), 'baseline')):
            x = timing.compare_timing(b, c)['clocks'][0]
            self.assertEqual(x['declaration_missing_on'], side)
            self.assertFalse(x['values_differ'])
            self.assertIsNone(x[side]['required_mhz'])
            self.assertEqual(x[side]['state'], timing.REQUIREMENT_MISSING)
            self.assertIn('cannot be assessed', self.report_text(b, c))

    def test_tool_constraint_does_not_fill_the_gap(self):
        x = timing.compare_timing(self.side(OK, REQ), self.side(OK))['clocks'][0]
        self.assertEqual((x['current']['constraints'], x['current']['required_mhz']), ([12.0], None))

    def test_no_declaration_on_either_side_is_informational(self):
        self.assertEqual(self.result(self.side(OK), self.side(OK)), (0, 'PASS'))
        self.assertIsNone(timing.compare_timing(self.side(OK), self.side(OK))['clocks'][0]['declaration_missing_on'])

    def test_same_value_both_sides_passes(self):
        self.assertEqual(self.result(self.side(OK, REQ), self.side(OK, REQ)), (0, 'PASS'))


class TestMultipleClocks(Case):
    def values(self, a=50.0, b=100.0):
        return [{'a': a, 'b': b, 'c': 200.0}, {'a': a + 1, 'b': b + 1, 'c': 201.0}]

    def test_unlisted_clock_is_informational(self):
        v = self.values()
        self.assertEqual(self.result(self.side(v, {'a': 48.0}), self.side(v, {'a': 48.0})), (0, 'PASS'))

    def test_mixed_states_are_named_per_clock(self):
        v = self.values()
        b, c = self.side(v, {'a': 48.0, 'b': 95.0}), self.side(v, {'a': 48.0})
        res = compare.compare(b, c, RULES)
        self.assertEqual((res['exit_code'], res['verdict'], res['inconsistent_requirements']), (2, INCONS, ['b']))
        rows = {x['clock']: x for x in res['timing']['clocks']}
        self.assertEqual(rows['a']['declaration_missing_on'], None)
        self.assertEqual(rows['b']['declaration_missing_on'], 'current')
        self.assertEqual(rows['c']['declaration_missing_on'], None)
        self.assertEqual(self.report_text(b, c).count('**Inconsistent requirements:**'), 1)

    def test_each_kind_at_once(self):
        v = self.values()
        b = self.side(v, {'a': 48.0, 'b': 95.0, 'gone': 10.0})          # 'b' omitted on current; 'gone' reported by no run
        c = self.side(v, {'a': 900.0, 'gone': 10.0})                    # 'a' differs and is missed
        res = compare.compare(b, c, RULES)
        self.assertEqual((res['exit_code'], res['verdict']), (1, f'{MISS} + {NOT_EVAL} + {INCONS}'))
        self.assertEqual((res['required_clock_misses'], res['required_clocks_not_evaluated'], res['inconsistent_requirements']),
                         (['a'], ['gone'], ['a', 'b']))

    def test_miss_on_one_clock_asymmetry_on_another(self):
        v = self.values()
        self.assertEqual(self.result(self.side(v, {'a': 900.0, 'b': 95.0}), self.side(v, {'a': 900.0})), (1, f'{MISS} + {INCONS}'))


class TestKnownFailureOutranksEvidence(Case):
    def test_threshold_violation_with_asymmetric_requirements(self):
        for b, c in ((self.side(HIGH, REQ), self.side(OK)), (self.side(HIGH), self.side(OK, REQ))):
            self.assertEqual(self.result(b, c, TIGHT), (1, f'THRESHOLD EXCEEDED + {INCONS}'))
            self.assertIn('**Inconsistent requirements:**', self.report_text(b, c, TIGHT))

    def test_threshold_violation_with_unevaluated_clock(self):
        b, c = self.side(HIGH, {'clok': 48.0}), self.side(OK, {'clok': 48.0})
        self.assertEqual(self.result(b, c, TIGHT), (1, f'THRESHOLD EXCEEDED + {NOT_EVAL}'))
        self.assertIn('could not be evaluated because no matching observations exist', self.report_text(b, c, TIGHT))

    def test_threshold_violation_with_different_values(self):
        self.assertEqual(self.result(self.side(HIGH, {'clk': 60.0}), self.side(OK, REQ), TIGHT), (1, f'THRESHOLD EXCEEDED + {INCONS}'))

    def test_revision_wording(self):
        self.assertEqual(self.result(self.side(HIGH), self.side(OK, REQ), TIGHT, 'revision'), (1, f'REGRESSION + {INCONS}'))

    def test_threshold_violation_with_missing_required_metric(self):
        self.assertEqual(self.result(self.side(HIGH), self.side(OK), TIGHT_REQUIRED), (1, 'THRESHOLD EXCEEDED + MISSING REQUIRED METRIC'))

    def test_threshold_violation_with_partial_failure(self):
        self.assertEqual(self.result(self.side(HIGH), self.side(OK, failed=1), TIGHT), (1, f'THRESHOLD EXCEEDED + {SOME}'))

    def test_current_miss_with_asymmetric_requirement_on_same_clock(self):
        b, c = self.side(OK), self.side(LOW, REQ)
        self.assertEqual(self.result(b, c), (1, f'{MISS} + {INCONS}'))
        md = self.report_text(b, c)
        self.assertIn('**current: the observed minimum does not meet the required frequency.**', md)
        self.assertIn('**Inconsistent requirements:**', md)

    def test_current_miss_with_failed_baseline_and_asymmetry(self):
        self.assertEqual(self.result(self.side([], failed=1), self.side(LOW, REQ)), (1, f'{MISS} + {INCONS} + {ALL}'))


class TestNoKnownFailure(Case):
    def test_missing_evidence_gives_2(self):
        self.assertEqual(self.result(self.side(OK), self.side(OK), REQUIRED_METRIC), (2, 'MISSING REQUIRED METRIC'))
        self.assertEqual(self.result(self.side(OK), self.side(OK, failed=1)), (2, SOME))
        self.assertEqual(self.result(self.side(OK, {'clok': 48.0}), self.side(OK, {'clok': 48.0})), (2, NOT_EVAL))

    def test_asymmetry_with_partial_failure(self):
        self.assertEqual(self.result(self.side(OK), self.side(OK, REQ, failed=1)), (2, f'{INCONS} + {SOME}'))

    def test_baseline_miss_alone_with_matching_requirement(self):
        self.assertEqual(self.result(self.side(LOW, REQ), self.side(OK, REQ)), (0, 'PASS'))

    def test_all_failed_stays_2_when_no_threshold_row_can_be_compared(self):
        rules = [dict(metric='lc', max_increase_pct=1.0)]
        report_only = self.side(OK)
        self.assertEqual(self.result(self.side([], failed=1), report_only, rules)[0], 2)
        self.assertEqual(self.result(report_only, self.side([], failed=1), rules)[0], 2)


class TestV1(Case):
    def frozen(self, name):
        out = f'{self.t}/{name}'
        d = os.path.join(FIXTURES, 'design_a')
        p = subprocess.run([sys.executable, '-I', '-B', FROZEN, 'capture', '--out', out, '--nextpnr',
                            *sorted(glob.glob(d + '/pnr_report_s*.json'))], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return run.load(out)

    def test_v1_side_is_not_counted_as_omitting_a_requirement(self):
        v1, v2 = self.frozen('a'), self.side(OK, REQ)
        for b, c in ((v1, v2), (v2, v1)):
            x = next(k for k in timing.compare_timing(b, c)['clocks'] if k['clock'] == 'clk')
            self.assertIsNone(x['declaration_missing_on'])

    def test_v1_vs_v1_passes(self):
        self.assertEqual(self.result(self.frozen('a'), self.frozen('b')), (0, 'PASS'))


class TestWording(Case):
    def test_no_claim_to_detect_a_wrong_value(self):
        r = self.side(OK, REQ)
        self.assertIn('it cannot tell whether a declared value is correct', self.report_text(r, r))


if __name__ == '__main__':
    unittest.main()
