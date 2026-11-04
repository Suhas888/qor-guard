"""QoR Guard 0.3 Phase 2 tests: observed Fmax ranges.
SYNTHETIC reports (temp dirs, invented values) cover the edge cases and validate no hardware behaviour. The TestFixtureRegression class
uses the synthetic fixtures as a regression check.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import glob
import io
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import cli, compare, ranges, report, run  # noqa: E402

FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'synthetic')
FROZEN = os.path.join(ROOT, 'tests', 'legacy_v020', 'qorguard.py')
CLK = 'clk'
PROV = dict(device='synthetic-device', yosys_version='1.0', nextpnr_version='2.0')
WIDE = dict(rules=[dict(metric='fmax_min[*', max_decrease_pct=99.0), dict(metric='fmax_median[*', max_decrease_pct=99.0)])
TIGHT = dict(rules=[dict(metric='fmax_min[*', max_decrease_pct=1.0)])


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix='qg03r_')
        self.addCleanup(shutil.rmtree, self.t)
        self.n = 0

    def report(self, fmax, clock=CLK, constraint=12):
        self.n += 1
        p = f'{self.t}/synthetic_report_{self.n}.json'
        with open(p, 'w') as f:
            json.dump(dict(fmax={clock: dict(achieved=fmax, constraint=constraint)},
                           utilization=dict(ICESTORM_LC=dict(used=10, available=100))), f)
        return p

    def side(self, vals, failed=0, seeds=True, clock=CLK, constraint=12, **prov):
        """vals: successful Fmax values. Seeds start at 1; failed runs take the following seeds."""
        runs = []
        for i, v in enumerate(vals):
            r = dict(report=self.report(v, clock, constraint), status='success')
            if seeds:
                r['seed'] = i + 1
            runs.append(r)
        for i in range(failed):
            r = dict(status='failed')
            if seeds:
                r['seed'] = len(vals) + i + 1
            runs.append(r)
        self.n += 1
        m = f'{self.t}/m{self.n}.json'
        with open(m, 'w') as f:
            json.dump(dict(manifest_version=1, runs=runs, **{**PROV, **prov}), f)
        return run.capture(f'{self.t}/run{self.n}', manifest=m)

    def only(self, b, c):
        rg = ranges.compare_ranges(b, c)
        self.assertEqual(len(rg['clocks']), 1)
        return rg['clocks'][0]

    def section(self, b, c, rules=WIDE):
        md = report.markdown(b, c, compare.compare(b, c, rules['rules']))
        start = md.index('## Observed Fmax ranges')
        end = md.find('\n## ', start)
        return md, md[start:end]


class TestStates(Base):
    def test_overlap(self):
        c = self.only(self.side([10.0, 12.0, 14.0]), self.side([13.0, 15.0, 17.0]))
        self.assertEqual((c['state'], c['direction']), ('OVERLAP', None))
        self.assertEqual((c['baseline']['min'], c['baseline']['median'], c['baseline']['max'], c['baseline']['observations']), (10.0, 12.0, 14.0, 3))

    def test_no_overlap_both_directions(self):
        c = self.only(self.side([10.0, 11.0]), self.side([20.0, 21.0]))
        self.assertEqual((c['state'], c['direction']), ('NO_OVERLAP', 'current_higher'))
        c = self.only(self.side([20.0, 21.0]), self.side([10.0, 11.0]))
        self.assertEqual((c['state'], c['direction']), ('NO_OVERLAP', 'current_lower'))

    def test_touching_ranges_overlap(self):
        self.assertEqual(self.only(self.side([10.0, 12.0]), self.side([12.0, 14.0]))['state'], 'OVERLAP')

    def test_exactly_two_observations_with_even_median(self):
        c = self.only(self.side([10.0, 13.0]), self.side([11.0, 12.0]))
        self.assertEqual(c['state'], 'OVERLAP')
        self.assertEqual(c['baseline']['median'], 11.5)
        self.assertFalse(c['baseline']['insufficient'])

    def test_one_observation_on_either_side(self):
        for b, k, who in (([10.0], [10.0, 11.0], 'baseline'), ([10.0, 11.0], [10.5], 'current')):
            c = self.only(self.side(b), self.side(k))
            self.assertEqual(c['state'], 'INSUFFICIENT_DATA')
            self.assertTrue(c[who]['insufficient'])
            self.assertIn('1 valid Fmax observation', c['insufficient_reasons'][0])
            _, sec = self.section(self.side(b), self.side(k))
            self.assertIn('Insufficient data:', sec)
            self.assertNotIn('observed ranges overlap', sec)
            self.assertNotIn('do not overlap', sec)

    def test_identical_values_are_a_sufficient_zero_width_range(self):
        c = self.only(self.side([10.0, 10.0]), self.side([10.0, 10.0]))
        self.assertEqual(c['state'], 'OVERLAP')


class TestFailedRuns(Base):
    def test_partial_failure_either_side_shown_and_qualified(self):
        for b, k, who in ((dict(failed=1), dict(), 'baseline'), (dict(), dict(failed=2), 'current')):
            x, y = self.side([10.0, 11.0], **b), self.side([10.5, 11.5], **k)
            c = self.only(x, y)
            self.assertEqual(c['state'], 'OVERLAP')
            self.assertTrue(c['qualified'])
            self.assertTrue(any(who in q and 'declared runs failed' in q for q in c['qualifiers']))
            failed = k.get('failed', b.get('failed'))
            self.assertEqual(c[who]['failed'], failed)
            _, sec = self.section(x, y)
            self.assertIn(f'| {who} | {2 + failed} | 2 | {failed} | 2 |', sec)

    def test_failed_run_values_not_in_range(self):
        p = self.report(1.0)
        m = f'{self.t}/m.json'
        with open(m, 'w') as f:
            json.dump(dict(manifest_version=1, **PROV, runs=[dict(report=self.report(10.0), seed=1, status='success'),
                                                             dict(report=self.report(11.0), seed=2, status='success'),
                                                             dict(report=p, seed=3, status='failed')]), f)
        c = self.only(run.capture(self.t + '/x', manifest=m), self.side([10.0, 11.0]))
        self.assertEqual((c['baseline']['min'], c['baseline']['observations'], c['baseline']['failed']), (10.0, 2, 1))

    def test_partial_failure_leaving_one_observation_is_insufficient(self):
        c = self.only(self.side([10.0], failed=4), self.side([10.0, 11.0]))
        self.assertEqual(c['state'], 'INSUFFICIENT_DATA')
        self.assertEqual((c['baseline']['attempted'], c['baseline']['failed'], c['baseline']['observations']), (5, 4, 1))

    def test_all_failed_no_clock_known_still_shows_counts(self):
        b, k = self.side([10.0, 11.0]), self.side([], failed=3)
        c = self.only(b, k)
        self.assertEqual(c['state'], 'INSUFFICIENT_DATA')
        self.assertEqual((c['current']['attempted'], c['current']['successful'], c['current']['failed']), (3, 0, 3))
        b, k = self.side([], failed=2), self.side([], failed=3)
        rg = ranges.compare_ranges(b, k)
        self.assertEqual(rg['clocks'], [])
        _, sec = self.section(b, k)
        self.assertIn('| baseline | 2 | 0 | 2 |', sec)
        self.assertIn('| current | 3 | 0 | 3 |', sec)


class TestSeeds(Base):
    def test_missing_seeds_no_same_seed_claim(self):
        b, k = self.side([10.0, 11.0], seeds=False), self.side([10.5, 11.5], seeds=False)
        c = self.only(b, k)
        self.assertEqual(c['seed_relation'], 'unavailable')
        self.assertTrue(c['qualified'])
        self.assertIn('no claim is made', self.section(b, k)[1])

    def test_seed_from_one_side_only_is_unavailable(self):
        self.assertEqual(self.only(self.side([10.0, 11.0]), self.side([10.5, 11.5], seeds=False))['seed_relation'], 'unavailable')

    def test_filenames_never_supply_seeds(self):
        d = os.path.join(FIXTURES, 'design_a')
        r = run.capture(self.t + '/x', nextpnr=sorted(glob.glob(d + '/pnr_report_s*.json')))
        self.assertEqual(self.only(r, r)['seed_relation'], 'unavailable')

    def test_same_and_different_declared_seeds(self):
        self.assertEqual(self.only(self.side([10.0, 11.0]), self.side([10.5, 11.5]))['seed_relation'], 'same_seed_values')
        c = self.only(self.side([10.0, 11.0]), self.side([10.5, 11.5, 12.0]))
        self.assertEqual(c['seed_relation'], 'different_seed_values')
        self.assertTrue(c['qualified'])

    def test_fully_matched_record_is_unqualified(self):
        c = self.only(self.fully_declared(), self.fully_declared())
        self.assertEqual((c['qualified'], c['qualifiers']), (False, []))

    def fully_declared(self):
        pcf = f'{self.t}/top.pcf'
        with open(pcf, 'w') as f:
            f.write('synthetic\n')
        m = f'{self.t}/f{self.n}.json'
        with open(m, 'w') as f:
            json.dump(dict(manifest_version=1, **PROV, constraint_files=['top.pcf'],
                           runs=[dict(report=self.report(10.0), seed=1, status='success'),
                                 dict(report=self.report(11.0), seed=2, status='success')]), f)
        self.n += 1
        return run.capture(f'{self.t}/full{self.n}', manifest=m)


class TestCompatibility(Base):
    def test_different_toolchains_disclosed(self):
        for key in ('yosys_version', 'nextpnr_version', 'device'):
            b, k = self.side([10.0, 11.0]), self.side([10.5, 11.5], **{key: 'other'})
            c = self.only(b, k)
            self.assertEqual(c['state'], 'OVERLAP')
            self.assertTrue(c['qualified'])
            self.assertTrue(any(key.replace('_', ' ') + ' differs' in q for q in c['qualifiers']))
            sec = self.section(b, k)[1]
            self.assertIn('with the qualifications below', sec)
            self.assertIn(f'| {key} | ', sec)

    def test_unavailable_provenance_qualifies(self):
        self.assertTrue(any('device unavailable' in q for q in
                            self.only(self.manifest_free(), self.manifest_free())['qualifiers']))

    def manifest_free(self):
        self.n += 1
        return run.capture(f'{self.t}/free{self.n}', nextpnr=[self.report(10.0), self.report(11.0)])

    def test_different_clock_names_are_not_merged(self):
        b, k = self.side([10.0, 11.0], clock='clk_a'), self.side([10.5, 11.5], clock='clk_b')
        rg = ranges.compare_ranges(b, k)
        self.assertEqual([c['clock'] for c in rg['clocks']], ['clk_a', 'clk_b'])
        self.assertTrue(all(c['state'] == 'INSUFFICIENT_DATA' for c in rg['clocks']))
        self.assertTrue(any('renamed clock' in q for q in rg['clocks'][0]['qualifiers']))

    def test_different_constraint_disclosed(self):
        c = self.only(self.side([10.0, 11.0]), self.side([10.5, 11.5], constraint=25))
        self.assertTrue(any('clock constraint differs' in q for q in c['qualifiers']))


class TestV1(Base):
    def frozen(self, name):
        d = os.path.join(FIXTURES, 'design_a')
        out = f'{self.t}/{name}'
        p = subprocess.run([sys.executable, '-I', '-B', FROZEN, 'capture', '--out', out, '--nextpnr',
                            *sorted(glob.glob(d + '/pnr_report_s*.json'))], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return run.load(out)

    def test_v1_vs_v2_fabricates_nothing(self):
        v1, v2 = self.frozen('a'), self.side([10.0, 11.0])
        self.assertIn('fmax_min[clk$SB_IO_IN_$glb_clk]', v1['metrics'])
        for b, k, old in ((v1, v2, 'baseline'), (v2, v1, 'current')):
            rg = ranges.compare_ranges(b, k)
            for c in rg['clocks']:
                self.assertEqual(c['state'], 'INSUFFICIENT_DATA')
                self.assertIsNone(c[old]['observations'])
                self.assertIsNone(c[old]['min'])
                self.assertIsNone(c[old]['failed'])
                self.assertTrue(any('schema v1' in x for x in c['insufficient_reasons']))

    def test_v1_vs_v1_has_no_range(self):
        a, b = self.frozen('a'), self.frozen('b')
        rg = ranges.compare_ranges(a, b)
        self.assertEqual((rg['available'], rg['clocks']), (False, []))
        self.assertIn('Not available: both records are schema v1', self.section(a, b)[1])

    def test_v1_vs_v2_report_says_not_stored(self):
        self.assertIn('not stored (v1)', self.section(self.frozen('a'), self.side([10.0, 11.0]))[1])


class TestPrecision(Base):
    def test_calculated_at_full_precision_displayed_rounded(self):
        vals = [70.40169525146484, 70.49557495117188, 71.34234567891234]
        b, k = self.side(vals), self.side(vals)
        c = self.only(b, k)
        self.assertEqual((c['baseline']['min'], c['baseline']['median'], c['baseline']['max']), (vals[0], vals[1], vals[2]))
        sec = self.section(b, k)[1]
        self.assertIn('| 70.402 | 70.496 | 71.342 |', sec)
        self.assertNotIn('70.40169525', sec)

    def test_ranges_rounding_alike_still_separate(self):
        b, k = self.side([10.00001, 10.00002]), self.side([10.00003, 10.00004])
        self.assertEqual(self.only(b, k)['state'], 'NO_OVERLAP')
        self.assertIn('separate only beyond the displayed 0.001 MHz', self.section(b, k)[1])

    def test_not_taken_from_rounded_metrics(self):
        b = self.side([10.00001, 10.00002])
        b['metrics'][f'fmax_min[{CLK}]']['value'] = 999.0
        self.assertEqual(self.only(b, b)['baseline']['min'], 10.00001)


class TestWording(Base):
    def test_no_forbidden_claims(self):
        for vals in (([10.0, 12.0], [11.0, 13.0]), ([10.0, 11.0], [20.0, 21.0]), ([10.0], [11.0, 12.0])):
            sec = self.section(self.side(vals[0]), self.side(vals[1]))[1].lower()
            for w in ('equivalen', 'statistic', 'significan', 'noise', 'no regression found', 'pass'):
                self.assertNotIn(w, sec)
            self.assertIn('an overlap does not establish', sec)


class TestDecisionsUnchanged(Base):
    def cli_compare(self, b, k, rules):
        p = f'{self.t}/rules.json'
        with open(p, 'w') as f:
            json.dump(rules, f)
        o, e = io.StringIO(), io.StringIO()
        with redirect_stdout(o), redirect_stderr(e):
            code = cli.main(['compare', '--baseline', b, '--current', k, '--config', p])
        return code, o.getvalue().splitlines()[0].replace('# QoR Guard report — ', '')

    def capture_dir(self, vals, failed=0):
        before = set(glob.glob(self.t + '/run*'))
        self.side(vals, failed=failed)
        return (set(glob.glob(self.t + '/run*')) - before).pop()

    def test_no_overlap_does_not_fail_and_overlap_does_not_pass(self):
        code = self.cli_compare(self.capture_dir([20.0, 21.0]), self.capture_dir([10.0, 11.0]), WIDE)
        self.assertEqual(code, (0, 'PASS'))
        code = self.cli_compare(self.capture_dir([10.0, 20.0]), self.capture_dir([5.0, 15.0]), TIGHT)
        self.assertEqual(code, (1, 'THRESHOLD EXCEEDED'))

    def test_incomplete_evidence_codes_unchanged(self):
        self.assertEqual(self.cli_compare(self.capture_dir([10.0, 11.0]), self.capture_dir([10.0, 11.0], failed=1), WIDE),
                         (2, 'INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED'))
        self.assertEqual(self.cli_compare(self.capture_dir([10.0, 11.0]), self.capture_dir([], failed=1), WIDE)[0], 2)
        self.assertEqual(self.cli_compare(self.capture_dir([20.0, 21.0]), self.capture_dir([10.0, 11.0], failed=1), TIGHT),
                         (1, 'THRESHOLD EXCEEDED + INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED'))

    def test_ranges_are_not_read_by_the_decision(self):
        b, k = self.side([20.0, 21.0]), self.side([10.0, 11.0])
        res = compare.compare(b, k, TIGHT['rules'])
        original = compare.ranges.compare_ranges
        compare.ranges.compare_ranges = lambda a, c: dict(available=False, clocks=[], compatibility=[], sides={}, reason='x')
        try:
            other = compare.compare(b, k, TIGHT['rules'])
        finally:
            compare.ranges.compare_ranges = original
        self.assertEqual((res['exit_code'], res['verdict'], res['rows']), (other['exit_code'], other['verdict'], other['rows']))


class TestFixtureRegression(Base):
    """Regression on the fixtures, checked against a calculation read directly from the raw JSON."""

    def test_all_fixtures_match_raw_values(self):
        names = ('design_a', 'design_b', 'design_c', 'design_d')
        for a, b in zip(names[::2], names[1::2]):
            paths = {d: sorted(glob.glob(os.path.join(FIXTURES, d, 'pnr_report_s*.json'))) for d in (a, b)}
            ra, rb = run.capture(f'{self.t}/{a}', nextpnr=paths[a]), run.capture(f'{self.t}/{b}', nextpnr=paths[b])
            rg = ranges.compare_ranges(ra, rb)
            self.assertEqual(len(rg['clocks']), 1)
            c = rg['clocks'][0]
            raw = {d: [json.load(open(p))['fmax'][c['clock']]['achieved'] for p in paths[d]] for d in (a, b)}
            for side, d in (('baseline', a), ('current', b)):
                self.assertEqual(c[side]['observations'], 5)
                self.assertEqual(c[side]['min'], min(raw[d]))
                self.assertEqual(c[side]['max'], max(raw[d]))
                self.assertEqual(c[side]['median'], statistics.median(raw[d]))
                self.assertIsNone(c[side]['failed'])
            overlap = min(raw[a]) <= max(raw[b]) and min(raw[b]) <= max(raw[a])
            self.assertEqual(c['state'], 'OVERLAP' if overlap else 'NO_OVERLAP')
            self.assertEqual(c['seed_relation'], 'unavailable')
            self.assertTrue(c['qualified'])


if __name__ == '__main__':
    unittest.main()
