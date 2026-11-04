"""QoR Guard 0.3: a declared required clock with no observations, and inconsistent requirements, can never PASS.
All reports are SYNTHETIC (temp dirs, invented values): logic only, no hardware validation.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import os
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import compare, report, timing  # noqa: E402
from tests.test_v03_timing import RULES, TIGHT, Base  # noqa: E402

MISS = 'REQUIRED CLOCK NOT MET'
NOT_EVAL = 'REQUIRED CLOCK NOT EVALUATED'
INCONS = 'INCONSISTENT REQUIREMENTS'
SOME = 'INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED'
ALL = 'INCOMPLETE EVIDENCE: ALL DECLARED RUNS FAILED'
REQ = {'clk': 48.0}
OK = [50.0, 52.0]
LOW = [40.0, 41.0]
REQUIRED_METRIC = RULES + [dict(metric='lut4', max_increase_pct=1.0, required=True)]


class Case(Base):
    def result(self, b, c, rules=RULES):
        res = compare.compare(b, c, rules)
        return res['exit_code'], res['verdict']


class TestNoObservations(Case):
    def test_mistyped_clock_cannot_pass(self):
        b, c = self.side(OK, {'clok': 48.0}), self.side(OK, {'clok': 48.0})
        self.assertEqual(self.result(b, c), (2, NOT_EVAL))
        md = report.markdown(b, c, compare.compare(b, c, RULES))
        self.assertNotIn('PASS', md)
        self.assertIn('could not be evaluated because no matching observations exist', md)

    def test_renamed_clock_is_not_matched(self):
        b, c = self.side(OK, {'clk_a': 48.0}, clock='clk_a'), self.side(OK, {'clk_a': 48.0}, clock='clk_b')
        res = compare.compare(b, c, RULES)
        self.assertEqual((res['exit_code'], res['verdict'], res['required_clocks_not_evaluated']), (2, NOT_EVAL, ['clk_a']))

    def test_distinct_from_a_miss(self):
        c = self.side(LOW, {'clk': 48.0, 'clok': 48.0})
        rows = {x['clock']: x['current']['state'] for x in timing.compare_timing(c, c)['clocks']}
        self.assertEqual(rows, {'clk': timing.MISSES, 'clok': timing.NO_OBSERVATIONS})

    def test_baseline_side_only_is_inconsistent_not_unevaluated(self):
        self.assertEqual(self.result(self.side(OK, {'clok': 48.0}), self.side(OK)), (2, INCONS))

    def test_miss_on_another_clock_gives_1_and_names_both(self):
        self.assertEqual(self.result(self.side(OK, {'clk': 48.0, 'clok': 48.0}), self.side(LOW, {'clk': 48.0, 'clok': 48.0})), (1, f'{MISS} + {NOT_EVAL}'))

    def test_threshold_violation_gives_1_and_names_both(self):
        self.assertEqual(self.result(self.side([90.0, 91.0], {'clok': 48.0}), self.side(OK, {'clok': 48.0}), TIGHT), (1, f'THRESHOLD EXCEEDED + {NOT_EVAL}'))

    def test_met_clock_plus_unevaluated_clock_gives_2(self):
        self.assertEqual(self.result(self.side(OK, {'clk': 48.0, 'clok': 48.0}), self.side(OK, {'clk': 48.0, 'clok': 48.0})), (2, NOT_EVAL))


class TestInconsistent(Case):
    def test_met_gives_2_not_pass(self):
        b, c = self.side(OK, {'clk': 60.0}), self.side(OK, REQ)
        self.assertEqual(self.result(b, c), (2, INCONS))
        md = report.markdown(b, c, compare.compare(b, c, RULES))
        self.assertNotIn('PASS', md)
        self.assertIn('**Inconsistent requirements:** baseline 60.0 MHz, current 48.0 MHz', md)
        self.assertIn('no timing improvement or decline is implied', md)

    def test_missed_gives_1(self):
        self.assertEqual(self.result(self.side(OK, {'clk': 30.0}), self.side(LOW, REQ)), (1, f'{MISS} + {INCONS}'))

    def test_current_requirement_governs(self):
        # the current side meets its own 48 and would miss the baseline's 60
        self.assertEqual(compare.compare(self.side(OK, {'clk': 60.0}), self.side(OK, REQ), RULES)['required_clock_misses'], [])
        # the current side misses its own 48 and would meet the baseline's 30
        self.assertEqual(compare.compare(self.side(OK, {'clk': 30.0}), self.side(LOW, REQ), RULES)['required_clock_misses'], ['clk'])

    def test_no_current_observations_gives_2(self):
        self.assertEqual(self.result(self.side(OK, {'clk': 60.0}), self.side([], REQ, failed=1)), (2, f'{NOT_EVAL} + {INCONS} + {ALL}'))

    def test_each_clock_is_judged_separately(self):
        b, c = self.side(OK, {'clk': 48.0, 'other': 60.0}), self.side(OK, REQ)
        self.assertEqual(compare.compare(b, c, RULES)['inconsistent_requirements'], ['other'])

    def test_one_side_declares_nothing_invented(self):
        for b, c in ((self.side(OK, REQ), self.side(OK)), (self.side(OK), self.side(OK, REQ))):
            res = compare.compare(b, c, RULES)
            self.assertEqual((res['exit_code'], res['verdict'], res['inconsistent_requirements']), (2, INCONS, ['clk']))
            x = timing.compare_timing(b, c)['clocks'][0]
            self.assertTrue(x['requirements_inconsistent'])
            self.assertTrue(any('only one side' in n for n in x['notes']))
            self.assertEqual(sorted(str(x[n]['required_mhz']) for n in ('baseline', 'current')), ['48.0', 'None'])
            self.assertIn('Inconsistent requirements', report.markdown(b, c, res))

    def test_equal_requirements_pass(self):
        self.assertEqual(self.result(self.side(OK, REQ), self.side(OK, REQ)), (0, 'PASS'))


class TestPrecedence(Case):
    def test_miss_with_no_successful_baseline_runs(self):
        self.assertEqual(self.result(self.side([], REQ, failed=1), self.side(LOW, REQ)), (1, f'{MISS} + {ALL}'))

    def test_miss_with_missing_required_metric(self):
        self.assertEqual(self.result(self.side(OK, REQ), self.side(LOW, REQ), REQUIRED_METRIC), (1, f'MISSING REQUIRED METRIC + {MISS}'))

    def test_all_current_failed_without_a_requirement(self):
        self.assertEqual(self.result(self.side(OK), self.side([], failed=2)), (2, ALL))

    def test_all_current_failed_with_a_requirement(self):
        self.assertEqual(self.result(self.side(OK, REQ), self.side([], REQ, failed=2)), (2, f'{NOT_EVAL} + {ALL}'))

    def test_partial_failure_with_miss_keeps_details(self):
        b, c = self.side(OK, REQ), self.side(LOW, REQ, failed=1)
        self.assertEqual(self.result(b, c), (1, f'{MISS} + {SOME}'))
        self.assertIn('## Incomplete evidence', report.markdown(b, c, compare.compare(b, c, RULES)))

    def test_partial_failure_with_inconsistent_requirements(self):
        self.assertEqual(self.result(self.side(OK, {'clk': 60.0}), self.side(OK, REQ, failed=1)), (2, f'{INCONS} + {SOME}'))

    def test_partial_failure_with_unevaluated_clock(self):
        self.assertEqual(self.result(self.side(OK, {'clok': 48.0}), self.side(OK, {'clok': 48.0}, failed=1)), (2, f'{NOT_EVAL} + {SOME}'))

    def test_no_requirement_keeps_existing_results(self):
        self.assertEqual(self.result(self.side(OK), self.side(OK)), (0, 'PASS'))
        self.assertEqual(self.result(self.side([90.0, 91.0]), self.side(OK), TIGHT), (1, 'THRESHOLD EXCEEDED'))
        self.assertEqual(self.result(self.side(OK), self.side(OK), REQUIRED_METRIC), (2, 'MISSING REQUIRED METRIC'))

    def test_baseline_miss_alone(self):
        self.assertEqual(self.result(self.side(LOW, REQ), self.side(OK, REQ)), (0, 'PASS'))


if __name__ == '__main__':
    unittest.main()
