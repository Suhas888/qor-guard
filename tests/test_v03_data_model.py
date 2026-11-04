"""QoR Guard 0.3 Phase 1 tests: schema v2, manifest, per-run records, provenance and v1 compatibility.
All reports are SYNTHETIC, including the HX8K-format fixtures, manifests and malformed records, built in temp dirs.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import copy
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import cli, compare, parsers, report, run, schema  # noqa: E402

FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'synthetic')
FIX_A = os.path.join(FIXTURES, 'design_a')
FROZEN = os.path.join(ROOT, 'tests', 'legacy_v020', 'qorguard.py')
RULES = os.path.join(ROOT, 'config', 'thresholds.example.json')
CLK = 'clk$SB_IO_IN_$glb_clk'


def reports(d=FIX_A):
    return sorted(glob.glob(os.path.join(d, 'pnr_report_s*.json')))


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix='qg03_')
        self.addCleanup(shutil.rmtree, self.t)

    def manifest(self, name='m.json', raw=None, **fields):
        p = os.path.join(self.t, name)
        fields.setdefault('manifest_version', 1)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(raw if raw is not None else json.dumps(fields))
        return p

    def good_runs(self):
        return [dict(report=p, seed=i + 1, status='success') for i, p in enumerate(reports())]

    def frozen_capture(self, out, *args):
        p = subprocess.run([sys.executable, '-I', '-B', FROZEN, 'capture', '--out', out, *args], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return os.path.join(out, 'run.json')


class TestPrecisionAndRuns(Base):
    def test_every_seed_kept_at_source_precision(self):
        run.capture(self.t + '/a', nextpnr=reports())
        r = run.load(self.t + '/a')                      # from disk, after a JSON round trip
        self.assertEqual(len(r['runs']), 5)
        for rec, p in zip(r['runs'], reports()):
            raw = json.load(open(p))['fmax'][CLK]['achieved']
            self.assertEqual(rec['fmax'][CLK]['achieved'], raw)
            self.assertNotEqual(raw, round(raw, 3))

    def test_report_hash_per_run_matches_source_and_stored_copy(self):
        r = run.capture(self.t + '/a', nextpnr=reports())
        for rec, p in zip(r['runs'], reports()):
            h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
            self.assertEqual(rec['report']['sha256'], h)
            self.assertEqual(hashlib.sha256(open(os.path.join(self.t, 'a', rec['report']['stored']), 'rb').read()).hexdigest(), h)

    def test_v1_metrics_stay_rounded_and_equal_frozen_020(self):
        for d in ('design_a', 'design_b', 'design_c', 'design_d'):
            src = os.path.join(FIXTURES, d)
            args = dict(yosys_stat=os.path.join(src, 'ice40_stat.json'), yosys_log=os.path.join(src, 'synth.log'), nextpnr=reports(src))
            new = run.capture(f'{self.t}/n{d}', **args)
            old = json.load(open(self.frozen_capture(f'{self.t}/o{d}', '--yosys-stat', args['yosys_stat'], '--yosys-log',
                                                     args['yosys_log'], '--nextpnr', *args['nextpnr'])))
            self.assertEqual(new['metrics'], old['metrics'])
            self.assertEqual(new['n_seeds'], old['n_seeds'])

    def test_no_manifest_means_unknown_attempts_and_seeds(self):
        r = run.capture(self.t + '/a', nextpnr=reports())
        self.assertEqual(r['run_counts'], dict(attempted=None, successful=5, failed=None, basis='reports_supplied'))
        for rec in r['runs']:                # files are named *_s1.json etc.; that must not become a seed
            self.assertEqual(rec['seed']['status'], 'unavailable')
            self.assertIsNone(rec['seed']['value'])

    def test_declared_seeds_recorded_as_declared(self):
        r = run.capture(self.t + '/a', manifest=self.manifest(runs=self.good_runs()))
        self.assertEqual([x['seed']['value'] for x in r['runs']], [1, 2, 3, 4, 5])
        self.assertTrue(all(x['seed']['status'] == 'declared' for x in r['runs']))
        self.assertEqual(r['run_counts'], dict(attempted=5, successful=5, failed=0, basis='declared'))

    def test_cli_manifest_with_bom_and_relative_report(self):
        shutil.copy(reports()[0], self.t + '/r.json')
        p = self.t + '/m.json'
        with open(p, 'w', encoding='utf-8-sig') as f:
            json.dump(dict(manifest_version=1, runs=[dict(report='r.json', seed=7, status='success')]), f)
        self.assertEqual(cli.main(['capture', '--out', self.t + '/a', '--manifest', p]), 0)
        self.assertEqual(run.load(self.t + '/a')['runs'][0]['seed']['value'], 7)


class TestFailedRuns(Base):
    def test_failed_run_without_report_is_counted_and_excluded(self):
        runs = self.good_runs()[:4] + [dict(seed=5, status='failed', reason='routing failed')]
        r = run.capture(self.t + '/a', manifest=self.manifest(runs=runs))
        self.assertEqual(r['run_counts'], dict(attempted=5, successful=4, failed=1, basis='declared'))
        self.assertEqual(r['n_seeds'], 4)
        self.assertEqual(r['runs'][4]['reason'], 'routing failed')
        self.assertIsNone(r['runs'][4]['report'])
        self.assertTrue(any('1 of 5' in n for n in r['notes']))
        self.assertTrue(any('1 of 5 declared nextpnr runs failed' in x for x in compare.run_warnings(r, r)))

    def test_failed_run_report_is_kept_but_not_aggregated(self):
        runs = self.good_runs()
        vals = [json.load(open(p))['fmax'][CLK]['achieved'] for p in reports()]
        worst = vals.index(min(vals))
        runs[worst]['status'] = 'failed'
        r = run.capture(self.t + '/a', manifest=self.manifest(runs=runs))
        self.assertEqual(r['runs'][worst]['fmax'][CLK]['achieved'], min(vals))
        self.assertIn('sha256', r['runs'][worst]['report'])
        self.assertGreater(r['metrics'][f'fmax_min[{CLK}]']['value'], round(min(vals), 3))

    def test_failed_run_with_unparseable_report_is_kept(self):
        bad = self.manifest('broken.json', raw='{"fmax": {')
        r = run.capture(self.t + '/a', manifest=self.manifest(runs=[dict(report=bad, seed=1, status='failed')]))
        self.assertIn('report_parse_error', r['runs'][0])
        self.assertIn('sha256', r['runs'][0]['report'])

    def test_all_failed_is_recorded_and_warned(self):
        r = run.capture(self.t + '/a', manifest=self.manifest(runs=[dict(seed=1, status='failed')]))
        self.assertEqual(r['run_counts'], dict(attempted=1, successful=0, failed=1, basis='declared'))
        self.assertEqual(run.load(self.t + '/a')['n_seeds'], 0)
        w = compare.run_warnings(r, r)
        self.assertTrue(any('1 of 1' in x for x in w) and any('no nextpnr report' in x for x in w))


class TestManifestRejected(Base):
    def rejected(self, **fields):
        with self.assertRaises(ValueError):
            run.capture(self.t + '/a', manifest=self.manifest(**fields))
        self.assertFalse(os.path.exists(self.t + '/a'))

    def test_bad_values(self):
        one = reports()[0]
        for runs in ([], 'x', [1], [dict(report=one, seed=1)], [dict(report=one, seed=1, status='maybe')],
                     [dict(report=one, seed='1', status='success')], [dict(report=one, seed=1.5, status='success')],
                     [dict(report=one, seed=True, status='success')], [dict(report=one, seed=None, status='success')],
                     [dict(report=one, seed=1, status='success', reason='x')], [dict(status='failed', reason='')],
                     [dict(report=one, seed=1, status='success', extra=1)], [dict(report='', status='success')]):
            with self.subTest(runs=runs):
                self.rejected(runs=runs)

    def test_duplicate_seed_including_failed_runs(self):
        a, b = reports()[:2]
        self.rejected(runs=[dict(report=a, seed=1, status='success'), dict(report=b, seed=1, status='success')])
        self.rejected(runs=[dict(report=a, seed=1, status='success'), dict(seed=1, status='failed')])

    def test_same_report_twice(self):
        a = reports()[0]
        self.rejected(runs=[dict(report=a, seed=1, status='success'), dict(report=a, seed=2, status='success')])

    def test_missing_report(self):
        self.rejected(runs=[dict(seed=1, status='success')])
        self.rejected(runs=[dict(report=self.t + '/gone.json', seed=1, status='success')])
        self.rejected(runs=[dict(report=self.t + '/gone.json', seed=1, status='failed')])

    def test_bad_provenance(self):
        for f in (dict(commit='not-hex!'), dict(commit='abc'), dict(commit=123), dict(branch=''), dict(device=None),
                  dict(nextpnr_version=1), dict(unknown='x'), dict(manifest_version=2), dict(manifest_version=True),
                  dict(constraint_files=['gone.pcf']), dict(constraint_files='top.pcf')):
            with self.subTest(f=f):
                self.rejected(**f, runs=self.good_runs())

    def test_malformed_files(self):
        for raw in ('{', '[]', '{"manifest_version": 1, "manifest_version": 1}', '{}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                run.capture(self.t + '/a', manifest=self.manifest(raw=raw))

    def test_runs_and_nextpnr_together(self):
        with self.assertRaises(ValueError):
            run.capture(self.t + '/a', nextpnr=reports(), manifest=self.manifest(runs=self.good_runs()))

    def test_successful_run_with_bad_report_is_an_error_not_an_omission(self):
        bad = self.manifest('broken.json', raw='{"fmax": {')
        with self.assertRaises(parsers.ParseError):
            run.capture(self.t + '/a', manifest=self.manifest(runs=[dict(report=bad, seed=1, status='success')]))

    def test_invalid_fmax_in_report(self):
        for v in ('NaN', 'Infinity', '-1', 'true'):
            with self.subTest(v=v), self.assertRaises(parsers.ParseError):
                parsers.nextpnr_report('{"fmax": {"clk": {"achieved": %s, "constraint": 12}}, "utilization": {}}' % v, 'synthetic')
        with self.assertRaises(parsers.ParseError):
            parsers.nextpnr_report('{"fmax": [], "utilization": {}}', 'synthetic')


class TestProvenance(Base):
    def test_unavailable_without_manifest(self):
        p = run.capture(self.t + '/a', yosys_log=FIX_A + '/synth.log', nextpnr=reports())['provenance']
        self.assertEqual(p['yosys_version']['status'], 'extracted')
        self.assertTrue(p['yosys_version']['value'].startswith('0.70+255'))
        self.assertEqual(p['clock_constraints_mhz']['status'], 'extracted')
        self.assertEqual(p['clock_constraints_mhz']['value'], {CLK: 12.0})
        self.assertIn('tool default', p['clock_constraints_mhz']['source'])
        for k in ('nextpnr_version', 'device', 'constraint_files', 'commit', 'branch'):
            self.assertEqual((p[k]['status'], p[k]['value']), ('unavailable', None), k)

    def test_declared_values_and_constraint_hash(self):
        pcf = self.manifest('top.pcf', raw='set_io clk 1\n')
        p = run.capture(self.t + '/a', nextpnr=reports(), manifest=self.manifest(
            commit='abc1234', branch='main', device='HX8K', nextpnr_version='0.11.1-83', constraint_files=['top.pcf']))['provenance']
        for k, v in (('commit', 'abc1234'), ('branch', 'main'), ('device', 'HX8K'), ('nextpnr_version', '0.11.1-83')):
            self.assertEqual((p[k]['status'], p[k]['value']), ('declared', v))
        self.assertEqual(p['constraint_files']['value'],
                         [dict(name='top.pcf', sha256=hashlib.sha256(open(pcf, 'rb').read()).hexdigest())])

    def test_extracted_beats_conflicting_declaration(self):
        r = run.capture(self.t + '/a', yosys_log=FIX_A + '/synth.log', manifest=self.manifest(yosys_version='9.9'))
        y = r['provenance']['yosys_version']
        self.assertEqual((y['status'], y['declared_value']), ('extracted', '9.9'))
        self.assertTrue(any('9.9' in n for n in r['notes']))

    def test_manifest_is_preserved_and_new_blocks_hold_no_absolute_paths(self):
        r = run.capture(self.t + '/a', manifest=self.manifest(runs=self.good_runs()))
        self.assertEqual(r['inputs'][-1]['kind'], 'manifest')
        self.assertNotIn(os.path.basename(self.t), json.dumps([r['runs'], r['run_counts'], r['provenance']]))


class TestLoadV2(Base):
    def test_each_corruption_rejected(self):
        run.capture(self.t + '/a', manifest=self.manifest(runs=self.good_runs()))
        good = json.load(open(self.t + '/a/run.json'))

        def set_(*path, v):
            def f(r):
                o = r
                for k in path[:-1]:
                    o = o[k]
                o[path[-1]] = v
            return f

        def drop(k):
            return lambda r: r.pop(k)

        cases = dict(
            version=set_('schema_version', v=3), version_str=set_('schema_version', v='2'), version_bool=set_('schema_version', v=True),
            no_runs=drop('runs'), no_counts=drop('run_counts'), no_prov=drop('provenance'), runs_type=set_('runs', v={}),
            count=set_('run_counts', 'failed', v=9), attempted=set_('run_counts', 'attempted', v=None), basis=set_('run_counts', 'basis', v='x'),
            n_seeds=set_('n_seeds', v=4), dup_seed=set_('runs', 1, 'seed', 'value', v=1), status=set_('runs', 0, 'status', v='x'),
            seed_status=set_('runs', 0, 'seed', 'status', v='guessed'), seed_type=set_('runs', 0, 'seed', 'value', v='1'),
            fabricated=set_('runs', 0, 'seed', 'status', v='unavailable'), bad_sha=set_('runs', 0, 'report', 'sha256', v='zz'),
            no_report=set_('runs', 0, 'report', v=None), nan=set_('runs', 0, 'fmax', CLK, 'achieved', v=float('nan')),
            fmax_str=set_('runs', 0, 'fmax', CLK, 'achieved', v='88'), prov_missing=lambda r: r['provenance'].pop('commit'),
            prov_status=set_('provenance', 'commit', 'status', v='guessed'),
            prov_invented=set_('provenance', 'commit', 'value', v='abc1234'))
        p = os.path.join(self.t, 'bad.json')
        for name, change in cases.items():
            with self.subTest(name):
                r = copy.deepcopy(good)
                change(r)
                with open(p, 'w') as f:
                    json.dump(r, f)
                with self.assertRaises(ValueError):
                    run.load(p)

    def test_top_level_not_object_and_bad_json(self):
        for raw in ('[]', '{'):
            p = self.manifest('x.json', raw=raw)
            with self.assertRaises(ValueError):
                run.load(p)


class TestV1Compatibility(Base):
    def v1(self, name='old', src=FIX_A):
        return self.frozen_capture(f'{self.t}/{name}', '--yosys-log', src + '/synth.log', '--nextpnr', *reports(src))

    def test_loads_unmodified_and_nothing_invented(self):
        p = self.v1()
        before = open(p, 'rb').read()
        raw = json.loads(before)
        self.assertNotIn('schema_version', raw)
        r = run.load(os.path.dirname(p))
        self.assertEqual(r, raw)
        self.assertEqual(open(p, 'rb').read(), before)
        self.assertEqual(schema.seed_data(r), dict(schema_version=1, runs=None, run_counts=None, provenance=None, reports_supplied=5))

    def test_mixed_v1_v2_compare_matches_v1_v1(self):
        old_a = run.load(self.v1('a'))
        old_b = run.load(self.v1('b', FIXTURES + '/design_b'))
        new_b = run.capture(self.t + '/c', yosys_log=FIXTURES + '/design_b/synth.log', nextpnr=reports(FIXTURES + '/design_b'))
        rules = compare.load_rules(RULES)
        x, y = compare.compare(old_a, old_b, rules), compare.compare(old_a, new_b, rules)
        pick = lambda res: [(q['metric'], q['status'], q['baseline'], q['current'], q.get('delta_pct')) for q in res['rows']]
        self.assertEqual(pick(x), pick(y))
        self.assertEqual(x['exit_code'], y['exit_code'])
        self.assertIn('QoR Guard report', report.markdown(old_a, new_b, y))

    def test_frozen_020_can_read_v2(self):
        run.capture(self.t + '/n', yosys_log=FIX_A + '/synth.log', nextpnr=reports())
        p = subprocess.run([sys.executable, '-I', '-B', FROZEN, 'compare', '--baseline', self.t + '/n', '--current', self.t + '/n',
                            '--config', RULES], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)


if __name__ == '__main__':
    unittest.main()
