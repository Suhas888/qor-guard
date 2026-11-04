"""QoR Guard 0.3: a declared required clock missed on the current side exits 1.
All reports are SYNTHETIC (temp dirs, invented values) including the v1 record and fixture case. Logic only, no hardware validation.
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
from qorguard import compare, ranges, report, run  # noqa: E402
from tests.test_v03_timing import FROZEN, FIXTURES, RULES, TIGHT, Base  # noqa: E402

MISS = 'REQUIRED CLOCK NOT MET'
SOME = 'INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED'
ALL = 'INCOMPLETE EVIDENCE: ALL DECLARED RUNS FAILED'
REQ = {'clk': 48.0}


class Exit(Base):
    def result(self, b, c, rules=RULES):
        res = compare.compare(b, c, rules)
        return res['exit_code'], res['verdict']


class TestCurrentMiss(Exit):
    def test_miss_when_percentage_thresholds_pass(self):
        b, c = self.side([40.0, 41.0], REQ), self.side([40.0, 41.0], REQ)
        res = compare.compare(b, c, RULES)
        self.assertTrue(all(r['status'] == 'OK' for r in res['rows']))
        self.assertEqual((res['exit_code'], res['verdict']), (1, MISS))
        self.assertEqual(res['required_clock_misses'], ['clk'])

    def test_some_observations_miss(self):
        self.assertEqual(self.result(self.side([50.0, 52.0], REQ), self.side([47.0, 52.0], REQ)), (1, MISS))

    def test_exact_tie_meets(self):
        self.assertEqual(self.result(self.side([48.0, 50.0], REQ), self.side([48.0, 50.0], REQ)), (0, 'PASS'))

    def test_miss_below_rounding_still_exits_1(self):
        c = self.side([47.99999, 50.0], REQ)
        self.assertEqual(c['metrics']['fmax_min[clk]']['value'], 48.0)
        self.assertEqual(self.result(self.side([50.0, 52.0], REQ), c), (1, MISS))

    def test_all_met_passes(self):
        self.assertEqual(self.result(self.side([50.0, 52.0], REQ), self.side([50.0, 52.0], REQ)), (0, 'PASS'))

    def test_one_of_two_clocks_missed(self):
        c = self.side([{'a': 50.0, 'b': 90.0}, {'a': 52.0, 'b': 91.0}], {'a': 48.0, 'b': 95.0})
        res = compare.compare(c, c, RULES)
        self.assertEqual((res['exit_code'], res['required_clock_misses']), (1, ['b']))

    def test_miss_and_threshold_violation_both_named(self):
        for kind, word in (('revision', 'REGRESSION'), ('unknown', 'THRESHOLD EXCEEDED')):
            res = compare.compare(self.side([90.0, 91.0], REQ), self.side([40.0, 41.0], REQ), TIGHT, kind)
            self.assertEqual((res['exit_code'], res['verdict']), (1, f'{word} + {MISS}'))


class TestBaselineMiss(Exit):
    def test_baseline_miss_alone_does_not_fail(self):
        b, c = self.side([40.0, 41.0], REQ), self.side([50.0, 52.0], REQ)
        self.assertEqual(self.result(b, c), (0, 'PASS'))
        self.assertIn('**baseline: the observed minimum does not meet', report.markdown(b, c, compare.compare(b, c, RULES)))

    def test_baseline_miss_with_current_omitting_the_requirement(self):
        self.assertEqual(self.result(self.side([40.0, 41.0], REQ), self.side([40.0, 41.0])), (2, 'INCONSISTENT REQUIREMENTS'))


class TestFailedRuns(Exit):
    def test_partial_failure_with_miss_exits_1_and_keeps_details(self):
        b, c = self.side([50.0, 52.0], REQ), self.side([40.0, 41.0], REQ, failed=2)
        self.assertEqual(self.result(b, c), (1, f'{MISS} + {SOME}'))
        md = report.markdown(b, c, compare.compare(b, c, RULES))
        self.assertIn('## Incomplete evidence', md)
        self.assertIn('| current | 4 | 2 | 2 | run 2, seed 3; run 3, seed 4 |', md)
        self.assertNotIn('PASS', md)

    def test_partial_failure_without_miss_stays_2(self):
        self.assertEqual(self.result(self.side([50.0, 52.0], REQ), self.side([50.0, 52.0], REQ, failed=1)), (2, SOME))

    def test_all_current_failed_stays_2(self):
        self.assertEqual(self.result(self.side([50.0, 52.0], REQ), self.side([], REQ, failed=2)), (2, f'REQUIRED CLOCK NOT EVALUATED + {ALL}'))
        self.assertEqual(self.result(self.side([50.0, 52.0]), self.side([], failed=2)), (2, ALL))

    def test_all_baseline_failed_with_current_miss_exits_1(self):
        self.assertEqual(self.result(self.side([], REQ, failed=1), self.side([40.0, 41.0], REQ)), (1, f'{MISS} + {ALL}'))

    def test_all_baseline_failed_with_current_met_stays_2(self):
        self.assertEqual(self.result(self.side([], REQ, failed=1), self.side([50.0, 52.0], REQ)), (2, ALL))


class TestMissingMetric(Exit):
    def test_required_metric_missing_with_miss_exits_1_and_names_both(self):
        rules = RULES + [dict(metric='lut4', max_increase_pct=1.0, required=True)]
        self.assertEqual(self.result(self.side([50.0, 52.0], REQ), self.side([40.0, 41.0], REQ), rules), (1, f'MISSING REQUIRED METRIC + {MISS}'))
        self.assertEqual(self.result(self.side([50.0, 52.0], REQ), self.side([50.0, 52.0], REQ), rules), (2, 'MISSING REQUIRED METRIC'))


class TestNoRequirement(Exit):
    def test_tool_constraint_is_never_substituted(self):
        c = self.side([5.0, 6.0])                    # below the tool's 12 MHz constraint
        self.assertEqual(self.result(self.side([5.0, 6.0]), c), (0, 'PASS'))

    def frozen(self, name):
        out = f'{self.t}/{name}'
        d = os.path.join(FIXTURES, 'design_a')
        p = subprocess.run([sys.executable, '-I', '-B', FROZEN, 'capture', '--out', out, '--nextpnr',
                            *sorted(glob.glob(d + '/pnr_report_s*.json'))], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return run.load(out)

    def test_v1_vs_v1_unchanged(self):
        self.assertEqual(self.result(self.frozen('a'), self.frozen('b')), (0, 'PASS'))

    def test_v1_current_with_v2_baseline_requirement_cannot_pass(self):
        d = os.path.join(FIXTURES, 'design_a')
        p = f'{self.t}/m.json'
        clock = next(iter(json.load(open(glob.glob(d + '/pnr_report_s*.json')[0]))['fmax']))
        with open(p, 'w') as f:
            json.dump(dict(manifest_version=1, required_clocks_mhz={clock: 900.0},
                           runs=[dict(report=q, status='success') for q in sorted(glob.glob(d + '/pnr_report_s*.json'))]), f)
        v2 = run.capture(self.t + '/x', manifest=p)
        self.assertEqual(self.result(v2, self.frozen('a')), (2, 'REQUIREMENT COMPARISON UNAVAILABLE'))

    def test_v1_baseline_with_v2_current_miss_exits_1(self):
        d = os.path.join(FIXTURES, 'design_a')
        paths = sorted(glob.glob(d + '/pnr_report_s*.json'))
        clock = next(iter(json.load(open(paths[0]))['fmax']))
        p = f'{self.t}/m.json'
        with open(p, 'w') as f:
            json.dump(dict(manifest_version=1, required_clocks_mhz={clock: 900.0}, runs=[dict(report=q, status='success') for q in paths]), f)
        self.assertEqual(self.result(self.frozen('a'), run.capture(self.t + '/x', manifest=p)), (1, f'{MISS} + REQUIREMENT COMPARISON UNAVAILABLE'))


class TestInconsistentRequirements(Exit):
    def test_lowered_requirement_flagged_and_current_governs(self):
        b, c = self.side([50.0, 52.0], {'clk': 60.0}), self.side([50.0, 52.0], REQ)
        self.assertEqual(self.result(b, c), (2, 'INCONSISTENT REQUIREMENTS'))
        md = report.markdown(b, c, compare.compare(b, c, RULES))
        self.assertNotIn('PASS', md)
        self.assertIn('**Inconsistent requirements:** baseline 60.0 MHz, current 48.0 MHz', md)
        self.assertIn('no timing improvement or decline is implied', md)

    def test_raised_requirement_flagged_and_current_governs(self):
        b, c = self.side([50.0, 52.0], REQ), self.side([50.0, 52.0], {'clk': 60.0})
        self.assertEqual(self.result(b, c), (1, f'{MISS} + INCONSISTENT REQUIREMENTS'))
        self.assertIn('**Inconsistent requirements:**', report.markdown(b, c, compare.compare(b, c, RULES)))

    def test_equal_requirements_not_flagged(self):
        b, c = self.side([50.0, 52.0], REQ), self.side([50.0, 52.0], REQ)
        self.assertNotIn('Inconsistent requirements', report.markdown(b, c, compare.compare(b, c, RULES)))


class TestUnchanged(Exit):
    def test_range_result_not_affected_by_a_miss(self):
        b, c = self.side([40.0, 42.0], REQ), self.side([41.0, 43.0], REQ)
        k = ranges.compare_ranges(b, c)['clocks'][0]
        self.assertEqual((k['state'], k['current']['min'], k['current']['max']), ('OVERLAP', 41.0, 43.0))
        self.assertEqual(self.result(b, c), (1, MISS))

    def test_threshold_rows_not_affected_by_a_miss(self):
        b = self.side([50.0, 52.0])
        x, y = compare.compare(b, self.side([50.0, 52.0], {'clk': 900.0}), TIGHT), compare.compare(b, self.side([50.0, 52.0]), TIGHT)
        self.assertEqual(x['rows'], y['rows'])
        self.assertEqual((x['exit_code'], y['exit_code']), (1, 0))

    def test_cli_returns_the_code(self):
        from qorguard import cli
        self.side([40.0, 41.0], REQ)
        d = f'{self.t}/run{self.n}'
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['compare', '--baseline', d, '--current', d]), 1)


if __name__ == '__main__':
    unittest.main()
