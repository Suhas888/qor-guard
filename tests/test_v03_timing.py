"""QoR Guard 0.3 Phase 3 tests: explicit required-clock timing and frequency margin.
SYNTHETIC reports (temp dirs, invented values) test logic only and validate no hardware behaviour. TestFixtureRegression uses the synthetic
fixtures with a made-up requirement, as a regression check against values read directly from the raw JSON.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import glob
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import compare, ranges, report, run, schema, timing  # noqa: E402

FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'synthetic')
FROZEN = os.path.join(ROOT, 'tests', 'legacy_v020', 'qorguard.py')
RULES = [dict(metric='fmax_min[*', max_decrease_pct=99.0)]
TIGHT = [dict(metric='fmax_min[*', max_decrease_pct=1.0)]


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix='qg03t_')
        self.addCleanup(shutil.rmtree, self.t)
        self.n = 0

    def report(self, fmax):
        """fmax: {clock: achieved}; every clock gets the tool constraint 12."""
        self.n += 1
        p = f'{self.t}/synthetic_{self.n}.json'
        with open(p, 'w') as f:
            json.dump(dict(fmax={c: dict(achieved=v, constraint=12) for c, v in fmax.items()},
                           utilization=dict(ICESTORM_LC=dict(used=10, available=100))), f)
        return p

    def side(self, vals, required=None, failed=0, clock='clk'):
        """vals: list of Fmax values, or of {clock: Fmax} for several clocks."""
        runs = [dict(report=self.report(v if isinstance(v, dict) else {clock: v}), seed=i + 1, status='success') for i, v in enumerate(vals)]
        runs += [dict(seed=len(vals) + i + 1, status='failed') for i in range(failed)]
        m = dict(manifest_version=1, runs=runs)
        if required is not None:
            m['required_clocks_mhz'] = required
        self.n += 1
        p = f'{self.t}/m{self.n}.json'
        with open(p, 'w') as f:
            json.dump(m, f)
        return run.capture(f'{self.t}/run{self.n}', manifest=p)

    def clock(self, b, c, name='clk'):
        return next(x for x in timing.compare_timing(b, c)['clocks'] if x['clock'] == name)

    def md(self, b, c, rules=RULES):
        return report.markdown(b, c, compare.compare(b, c, rules))

    def section(self, b, c):
        md = self.md(b, c)
        start = md.index('## Required-clock timing')
        return md[start:md.find('\n## ', start)]


class TestAssessment(Base):
    def test_all_observations_meet(self):
        r = self.side([50.0, 52.0, 54.0, 56.0, 58.0], {'clk': 48.0})
        s = self.clock(r, r)['current']
        self.assertEqual(s['state'], timing.MEETS)
        self.assertEqual(s['observations_meeting'], 5)
        self.assertEqual(s['margin']['min'], dict(absolute_mhz=2.0, percent=2.0 / 48.0 * 100))
        self.assertEqual(s['margin']['median']['absolute_mhz'], 6.0)
        self.assertEqual(s['margin']['max']['absolute_mhz'], 10.0)
        sec = self.section(r, r)
        self.assertIn('the observed minimum meets the required frequency', sec)
        self.assertIn('does not predict other runs or seeds', sec)

    def test_some_meet_others_miss(self):
        r = self.side([46.0, 48.0, 50.0], {'clk': 48.0})
        s = self.clock(r, r)['baseline']
        self.assertEqual((s['state'], s['observations_meeting']), (timing.MISSES, 2))
        self.assertEqual(s['margin']['min']['absolute_mhz'], -2.0)
        self.assertEqual(s['margin']['max']['absolute_mhz'], 2.0)
        self.assertIn('2 of 3 observations meet', self.section(r, r))

    def test_all_miss(self):
        r = self.side([40.0, 41.0], {'clk': 48.0})
        s = self.clock(r, r)['baseline']
        self.assertEqual((s['state'], s['observations_meeting']), (timing.MISSES, 0))
        self.assertLess(s['margin']['max']['percent'], 0)
        self.assertIn('does not meet', self.section(r, r))

    def test_exact_tie_meets(self):
        s = self.clock(*[self.side([48.0, 50.0], {'clk': 48.0})] * 2)['baseline']
        self.assertEqual(s['state'], timing.MEETS)
        self.assertEqual(s['margin']['min']['absolute_mhz'], 0.0)

    def test_single_observation_is_assessed_but_labelled(self):
        r = self.side([50.0], {'clk': 48.0})
        x = self.clock(r, r)
        self.assertEqual(x['baseline']['state'], timing.MEETS)
        self.assertTrue(any('small sample of 1' in n for n in x['notes']))


class TestRequirementAndConstraintAreSeparate(Base):
    def test_missing_requirement(self):
        r = self.side([50.0, 52.0])
        s = self.clock(r, r)['baseline']
        self.assertEqual((s['state'], s['required_mhz'], s['required_status'], s['margin']), (timing.REQUIREMENT_MISSING, None, 'unavailable', None))
        self.assertEqual(r['provenance']['required_clocks_mhz']['status'], 'unavailable')

    def test_tool_default_is_not_a_requirement(self):
        r = self.side([5.0, 6.0])              # would miss the tool's 12 MHz if it were wrongly used
        s = self.clock(r, r)['baseline']
        self.assertEqual(s['constraints'], [12.0])
        self.assertEqual((s['state'], s['meets_at_observed_minimum']), (timing.REQUIREMENT_MISSING, None))
        sec = self.section(r, r)
        self.assertIn('timing compliance cannot be assessed', sec)
        self.assertIn('(12.0 MHz) is not used as a substitute', sec)
        self.assertNotIn('Min margin', sec)

    def test_requirement_differs_from_constraint(self):
        r = self.side([20.0, 21.0], {'clk': 48.0})    # meets the constraint of 12, misses the requirement
        x = self.clock(r, r)
        self.assertEqual((x['baseline']['state'], x['baseline']['required_mhz'], x['baseline']['constraints']), (timing.MISSES, 48.0, [12.0]))
        self.assertEqual(x['baseline']['margin']['min']['absolute_mhz'], -28.0)
        self.assertTrue(any('kept separate' in n for n in x['notes']))
        self.assertEqual(r['provenance']['clock_constraints_mhz']['value'], {'clk': 12.0})
        self.assertEqual(r['provenance']['required_clocks_mhz']['value'], {'clk': 48.0})

    def test_recording(self):
        f = self.side([20.0, 21.0], {'clk': 48.0})['provenance']['required_clocks_mhz']
        self.assertEqual((f['status'], f['value'], f['source']), ('declared', {'clk': 48.0}, 'manifest required_clocks_mhz'))
        s = self.clock(*[self.side([20.0, 21.0], {'clk': 48.0})] * 2)['baseline']
        self.assertEqual((s['required_status'], s['required_source']), ('declared', 'manifest required_clocks_mhz'))

    def test_bad_manifest_values_rejected(self):
        for req in ({}, [], 48, {'clk': 0}, {'clk': -1}, {'clk': '48'}, {'clk': True}, {'clk': None}, {'': 48}):
            with self.subTest(req=req), self.assertRaises(ValueError):
                self.side([20.0], req)
        p = f'{self.t}/nan.json'
        for v in ('NaN', 'Infinity'):
            with open(p, 'w') as f:
                f.write('{"manifest_version": 1, "required_clocks_mhz": {"clk": %s}}' % v)
            with self.subTest(v=v), self.assertRaises(ValueError):
                schema.load_manifest(p)

    def test_corrupted_records_rejected(self):
        self.side([20.0, 21.0], {'clk': 48.0})
        d = f'{self.t}/run{self.n}/run.json'
        good = json.load(open(d))
        for change in (dict(status='extracted'), dict(status='unavailable'), dict(value={'clk': -1}), dict(value=None)):
            r = json.loads(json.dumps(good))
            r['provenance']['required_clocks_mhz'].update(change)
            with open(d, 'w') as f:
                json.dump(r, f)
            with self.subTest(change=change), self.assertRaises(ValueError):
                run.load(d)

    def test_older_v2_record_without_the_field_still_loads(self):
        self.side([20.0, 21.0])
        d = f'{self.t}/run{self.n}/run.json'
        r = json.load(open(d))
        del r['provenance']['required_clocks_mhz']
        with open(d, 'w') as f:
            json.dump(r, f)
        loaded = run.load(d)
        self.assertEqual(self.clock(loaded, loaded)['baseline']['state'], timing.REQUIREMENT_MISSING)


class TestClocks(Base):
    def test_multiple_clocks_with_different_requirements(self):
        vals = [{'a': 50.0, 'b': 100.0}, {'a': 52.0, 'b': 90.0}]
        r = self.side(vals, {'a': 48.0, 'b': 95.0})
        rows = {x['clock']: x['baseline'] for x in timing.compare_timing(r, r)['clocks']}
        self.assertEqual((rows['a']['state'], rows['b']['state']), (timing.MEETS, timing.MISSES))
        self.assertEqual((rows['a']['margin']['min']['absolute_mhz'], rows['b']['margin']['min']['absolute_mhz']), (2.0, -5.0))

    def test_requirement_for_only_one_of_two_clocks(self):
        r = self.side([{'a': 50.0, 'b': 100.0}, {'a': 52.0, 'b': 90.0}], {'a': 48.0})
        rows = {x['clock']: x['baseline']['state'] for x in timing.compare_timing(r, r)['clocks']}
        self.assertEqual(rows, {'a': timing.MEETS, 'b': timing.REQUIREMENT_MISSING})

    def test_requirement_for_a_clock_no_run_reports(self):
        r = self.side([50.0, 52.0], {'clok': 48.0})
        x = self.clock(r, r, 'clok')
        self.assertEqual(x['baseline']['state'], timing.NO_OBSERVATIONS)
        self.assertTrue(any('no run of that side reports it' in n for n in x['notes']))
        self.assertEqual(self.clock(r, r, 'clk')['baseline']['state'], timing.REQUIREMENT_MISSING)

    def test_renamed_clock_is_not_matched(self):
        b, c = self.side([50.0, 52.0], {'clk_a': 48.0}, clock='clk_a'), self.side([50.0, 52.0], {'clk_a': 48.0}, clock='clk_b')
        a = self.clock(b, c, 'clk_a')
        self.assertEqual((a['baseline']['state'], a['current']['state'], a['current']['observations']), (timing.MEETS, timing.NO_OBSERVATIONS, 0))
        other = self.clock(b, c, 'clk_b')
        self.assertEqual(other['current']['state'], timing.REQUIREMENT_MISSING)
        self.assertTrue(any('renamed clock' in n for n in other['notes']))

    def test_sides_with_different_requirements_disclosed(self):
        x = self.clock(self.side([50.0, 52.0], {'clk': 48.0}), self.side([50.0, 52.0], {'clk': 60.0}))
        self.assertEqual((x['baseline']['state'], x['current']['state']), (timing.MEETS, timing.MISSES))
        self.assertTrue(x['requirements_inconsistent'])

    def test_requirement_on_one_side_only_disclosed(self):
        x = self.clock(self.side([50.0, 52.0], {'clk': 48.0}), self.side([50.0, 52.0]))
        self.assertEqual(x['current']['state'], timing.REQUIREMENT_MISSING)
        self.assertTrue(any('only one side' in n for n in x['notes']))

    def test_unsafe_clock_name_escaped(self):
        n = 'a|b`c'
        r = self.side([50.0, 52.0], {n: 48.0}, clock=n)
        self.assertEqual(self.clock(r, r, n)['baseline']['state'], timing.MEETS)
        sec = self.section(r, r)
        self.assertNotIn(n, sec)
        self.assertIn(report.md_name(n), sec)


class TestFailedRuns(Base):
    def test_partial_failure_visible_and_not_in_figures(self):
        b, c = self.side([50.0, 52.0], {'clk': 48.0}), self.side([50.0, 52.0], {'clk': 48.0}, failed=2)
        s = self.clock(b, c)['current']
        self.assertEqual((s['attempted'], s['successful'], s['failed'], s['observations']), (4, 2, 2, 2))
        self.assertEqual(s['state'], timing.MEETS)
        sec = self.section(b, c)
        self.assertIn('| current | 4 | 2 | 2 | 2 |', sec)
        self.assertIn('so this does not cover every attempted run', sec)
        self.assertTrue(any('2 of 4 declared runs failed' in n for n in self.clock(b, c)['notes']))

    def test_failed_run_report_values_not_used(self):
        bad = self.report({'clk': 1.0})
        p = f'{self.t}/m.json'
        with open(p, 'w') as f:
            json.dump(dict(manifest_version=1, required_clocks_mhz={'clk': 48.0}, runs=[
                dict(report=self.report({'clk': 50.0}), seed=1, status='success'), dict(report=bad, seed=2, status='failed')]), f)
        r = run.capture(self.t + '/x', manifest=p)
        s = self.clock(r, r)['baseline']
        self.assertEqual((s['min'], s['state'], s['failed']), (50.0, timing.MEETS, 1))

    def test_all_failed_with_requirement(self):
        b, c = self.side([50.0, 52.0], {'clk': 48.0}), self.side([], {'clk': 48.0}, failed=3)
        s = self.clock(b, c)['current']
        self.assertEqual((s['state'], s['failed'], s['margin']), (timing.NO_OBSERVATIONS, 3, None))
        self.assertIn('no valid Fmax observation', self.section(b, c))

    def test_all_failed_no_clock_known_still_shows_counts(self):
        b, c = self.side([], failed=2), self.side([], failed=3)
        sec = self.section(b, c)
        self.assertIn('timing compliance cannot be assessed', sec)
        self.assertIn('| current | 3 | 0 | 3 |', sec)

    def test_incomplete_evidence_decisions_unchanged(self):
        ok, part = self.side([50.0, 52.0], {'clk': 48.0}), self.side([50.0, 52.0], {'clk': 48.0}, failed=1)
        res = compare.compare(ok, part, RULES)
        self.assertEqual((res['exit_code'], res['verdict']), (2, 'INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED'))
        res = compare.compare(ok, self.side([], {'clk': 48.0}, failed=1), RULES)
        self.assertEqual((res['exit_code'], res['verdict']), (2, 'REQUIRED CLOCK NOT EVALUATED + INCOMPLETE EVIDENCE: ALL DECLARED RUNS FAILED'))
        low = self.side([20.0, 21.0], {'clk': 48.0}, failed=1)
        res = compare.compare(ok, low, TIGHT)
        self.assertEqual((res['exit_code'], res['verdict']),
                         (1, 'THRESHOLD EXCEEDED + REQUIRED CLOCK NOT MET + INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED'))


class TestV1(Base):
    def frozen(self, name):
        d = os.path.join(FIXTURES, 'design_a')
        out = f'{self.t}/{name}'
        p = subprocess.run([sys.executable, '-I', '-B', FROZEN, 'capture', '--out', out, '--nextpnr',
                            *sorted(glob.glob(d + '/pnr_report_s*.json'))], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return run.load(out)

    def test_v1_vs_v1_not_available(self):
        v = self.frozen('a')
        self.assertEqual(timing.compare_timing(v, v)['available'], False)
        self.assertIn('Not available: both records are schema v1', self.section(v, v))

    def test_v1_vs_v2_invents_nothing(self):
        v1, v2 = self.frozen('a'), self.side([50.0, 52.0], {'clk': 48.0})
        for b, c, old in ((v1, v2, 'baseline'), (v2, v1, 'current')):
            x = self.clock(b, c)
            self.assertEqual((x[old]['state'], x[old]['required_mhz'], x[old]['min'], x[old]['margin']), (timing.NOT_STORED, None, None, None))
        self.assertIn('not stored (v1)', self.section(v1, v2))
        self.assertIn('A schema v1 record stores no required frequency', self.section(v1, v2))


class TestPrecision(Base):
    def test_margin_at_full_precision_displayed_rounded(self):
        a = [70.40169525146484, 70.49557495117188, 71.34234567891234]
        req = 70.1234567
        r = self.side(a, {'clk': req})
        s = self.clock(r, r)['baseline']
        self.assertEqual(s['margin']['min']['absolute_mhz'], a[0] - req)
        self.assertEqual(s['margin']['min']['percent'], (a[0] - req) / req * 100)
        self.assertEqual(s['margin']['median']['absolute_mhz'], a[1] - req)
        self.assertEqual(s['margin']['max']['absolute_mhz'], a[2] - req)
        sec = self.section(r, r)
        self.assertIn(f'{a[0] - req:+.3f} MHz ({(a[0] - req) / req * 100:+.2f}%)', sec)
        self.assertIn('| 70.1234567 |', sec)
        self.assertNotIn('70.40169525', sec)

    def test_miss_below_display_precision_is_still_a_miss(self):
        r = self.side([47.9999, 50.0], {'clk': 48.0})
        s = self.clock(r, r)['baseline']
        self.assertEqual(s['state'], timing.MISSES)
        self.assertIn('-0.000 MHz', self.section(r, r))

    def test_not_taken_from_rounded_metrics(self):
        r = self.side([47.99999, 50.0], {'clk': 48.0})
        self.assertEqual(r['metrics']['fmax_min[clk]']['value'], 48.0)      # rounding alone would look like a tie
        self.assertEqual(self.clock(r, r)['baseline']['state'], timing.MISSES)


class TestSeparation(Base):
    def test_overlap_does_not_imply_compliance(self):
        b, c = self.side([40.0, 42.0], {'clk': 48.0}), self.side([41.0, 43.0], {'clk': 48.0})
        self.assertEqual(ranges.compare_ranges(b, c)['clocks'][0]['state'], 'OVERLAP')
        self.assertEqual(self.clock(b, c)['current']['state'], timing.MISSES)
        self.assertIn('A range overlap says nothing about meeting a required frequency', self.section(b, c))

    def test_requirement_met_on_both_or_absent_from_both_passes(self):
        met, none = self.side([50.0, 52.0], {'clk': 48.0}), self.side([50.0, 52.0])
        for x in (met, none):
            res = compare.compare(x, x, RULES)
            self.assertEqual((res['exit_code'], res['verdict']), (0, 'PASS'))

    def test_decisions_and_ranges_ignore_met_requirements(self):
        with_req = self.side([20.0, 21.0], {'clk': 5.0})
        without = self.side([20.0, 21.0])
        base, base_req = self.side([30.0, 31.0]), self.side([30.0, 31.0], {'clk': 5.0})
        x, y = compare.compare(base_req, with_req, TIGHT), compare.compare(base, without, TIGHT)
        self.assertEqual((x['exit_code'], x['verdict']), (y['exit_code'], y['verdict']))
        self.assertEqual(x['rows'], y['rows'])
        self.assertEqual(x['ranges']['clocks'][0]['state'], y['ranges']['clocks'][0]['state'])


class TestFixtureRegression(Base):
    def test_margins_match_raw_values(self):
        d = os.path.join(FIXTURES, 'design_a')
        paths = sorted(glob.glob(d + '/pnr_report_s*.json'))
        clock = next(iter(json.load(open(paths[0]))['fmax']))
        raw = [json.load(open(p))['fmax'][clock]['achieved'] for p in paths]
        p = f'{self.t}/m.json'
        with open(p, 'w') as f:
            json.dump(dict(manifest_version=1, required_clocks_mhz={clock: 90.0},
                           runs=[dict(report=q, status='success') for q in paths]), f)
        r = run.capture(self.t + '/x', manifest=p)
        s = self.clock(r, r, clock)['baseline']
        self.assertEqual(s['observations'], 5)
        self.assertEqual(s['margin']['min']['absolute_mhz'], min(raw) - 90.0)
        self.assertEqual(s['margin']['median']['absolute_mhz'], statistics.median(raw) - 90.0)
        self.assertEqual(s['margin']['max']['absolute_mhz'], max(raw) - 90.0)
        self.assertEqual(s['observations_meeting'], sum(v >= 90.0 for v in raw))
        self.assertEqual(s['constraints'], [12.0])
        self.assertEqual(s['state'], timing.MEETS if min(raw) >= 90.0 else timing.MISSES)

    def test_no_manifest_fixture_cannot_be_assessed(self):
        d = os.path.join(FIXTURES, 'design_c')
        r = run.capture(self.t + '/x', nextpnr=sorted(glob.glob(d + '/pnr_report_s*.json')))
        x = timing.compare_timing(r, r)['clocks'][0]
        self.assertEqual(x['baseline']['state'], timing.REQUIREMENT_MISSING)


if __name__ == '__main__':
    unittest.main()
