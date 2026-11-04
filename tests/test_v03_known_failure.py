"""QoR Guard 0.3: a known failure outranks incomplete evidence, including all-failed runs.
All logs, manifests and Fmax reports are SYNTHETIC. Logic only, no hardware validation.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import compare, report, run  # noqa: E402
from tests.test_v03_timing import FIXTURES, RULES, TIGHT, Base  # noqa: E402

LOG_A = os.path.join(FIXTURES, 'design_a', 'synth.log')
LOG_B = os.path.join(FIXTURES, 'design_c', 'synth.log')
ANY_LUT_CHANGE = [dict(metric='lut4', max_increase_pct=0.0, max_decrease_pct=0.0)]
MISS = 'REQUIRED CLOCK NOT MET'
SOME = 'INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED'
ALL = 'INCOMPLETE EVIDENCE: ALL DECLARED RUNS FAILED'
REQ = {'clk': 48.0}


class Case(Base):
    def with_log(self, log, vals=(), failed=0):
        """Yosys data from a fixture log beside synthetic nextpnr runs, so a side can have valid data while all its runs failed."""
        runs = [dict(report=self.report({'clk': v}), seed=i + 1, status='success') for i, v in enumerate(vals)]
        runs += [dict(seed=len(vals) + i + 1, status='failed') for i in range(failed)]
        self.n += 1
        p = f'{self.t}/m{self.n}.json'
        with open(p, 'w') as f:
            json.dump(dict(manifest_version=1, runs=runs), f)
        return run.capture(f'{self.t}/log{self.n}', yosys_log=log, manifest=p)

    def result(self, b, c, rules=RULES):
        res = compare.compare(b, c, rules)
        return res['exit_code'], res['verdict']


class TestKnownFailureOutranksIncomplete(Case):
    def test_1_baseline_all_failed_with_known_threshold_violation(self):
        b, c = self.with_log(LOG_A, failed=2), self.with_log(LOG_B, [50.0, 52.0])
        self.assertEqual(self.result(b, c, ANY_LUT_CHANGE), (1, f'THRESHOLD EXCEEDED + {ALL}'))
        self.assertIn('## Incomplete evidence', report.markdown(b, c, compare.compare(b, c, ANY_LUT_CHANGE)))

    def test_2_current_partial_failure_with_known_threshold_violation(self):
        self.assertEqual(self.result(self.side([90.0, 91.0]), self.side([50.0, 52.0], failed=1), TIGHT), (1, f'THRESHOLD EXCEEDED + {SOME}'))

    def test_3_current_all_failed_no_demonstrable_violation(self):
        self.assertEqual(self.result(self.side([50.0, 52.0]), self.side([], failed=2), TIGHT), (2, ALL))
        same_log = self.result(self.with_log(LOG_A, [50.0, 52.0]), self.with_log(LOG_A, failed=2), ANY_LUT_CHANGE)
        self.assertEqual(same_log, (2, ALL))

    def test_4_current_all_failed_with_demonstrable_violation(self):
        b, c = self.with_log(LOG_A, [50.0, 52.0]), self.with_log(LOG_B, failed=2)
        res = compare.compare(b, c, ANY_LUT_CHANGE)
        self.assertEqual((res['exit_code'], res['verdict']), (1, f'THRESHOLD EXCEEDED + {ALL}'))
        row = res['rows'][0]
        self.assertEqual((row['metric'], row['status']), ('lut4', 'REGRESSION'))
        self.assertNotEqual(row['baseline'], row['current'])
        self.assertIn('## Incomplete evidence', report.markdown(b, c, res))

    def test_5_baseline_all_failed_with_current_miss(self):
        self.assertEqual(self.result(self.side([], REQ, failed=1), self.side([40.0, 41.0], REQ)), (1, f'{MISS} + {ALL}'))

    def test_both_sides_all_failed_nothing_known(self):
        self.assertEqual(self.result(self.side([], failed=1), self.side([], failed=1), TIGHT), (2, ALL))

    def test_baseline_all_failed_no_violation_and_no_pass(self):
        self.assertEqual(self.result(self.with_log(LOG_A, failed=2), self.with_log(LOG_A, [50.0, 52.0]), ANY_LUT_CHANGE), (2, ALL))

    def test_clean_run_still_passes(self):
        self.assertEqual(self.result(self.with_log(LOG_A, [50.0, 52.0]), self.with_log(LOG_A, [50.0, 52.0]), ANY_LUT_CHANGE), (0, 'PASS'))


if __name__ == '__main__':
    unittest.main()
