"""QoR Guard tests. Run (from the project root): python -I -B -m unittest discover -s tests -v
Fixtures: tests/fixtures/synthetic (see tests/fixtures/README.md).
SYNTHETIC inputs are created inside the tests (temp dirs) and are named 'synthetic_*'."""
import glob
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import cli, compare, parsers, run  # noqa: E402

FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'synthetic')
RULES = os.path.join(ROOT, 'config', 'thresholds.example.json')


def r(name, f):
    return os.path.join(FIXTURES, name, f)


def seeds(name):
    return sorted(glob.glob(r(name, 'pnr_report_s*.json')))


def cap(tmp, label, name, log=False, stat=True, pnr=True, nextpnr=None):
    return run.capture(os.path.join(tmp, label), r(name, 'ice40_stat.json') if stat else None,
                       r(name, 'synth.log') if log else None, nextpnr if nextpnr is not None else (seeds(name) if pnr else []), label)


def cli_run(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(list(args))
    return code, out.getvalue(), err.getvalue()


class TestParsersFixtures(unittest.TestCase):
    def test_yosys_stat_json(self):
        m = parsers.yosys_stat_json(open(r('design_a', 'ice40_stat.json')).read(), 'x')['metrics']
        self.assertEqual((m['lut4']['value'], m['ff']['value'], m['carry']['value']), (2600, 544, 180))

    def test_yosys_log_matches_json(self):
        for name in ('design_a', 'design_b', 'design_c', 'design_d'):
            j = parsers.yosys_stat_json(open(r(name, 'ice40_stat.json')).read(), 'j')['metrics']
            t = parsers.yosys_log_stat(open(r(name, 'synth.log'), encoding='utf-8').read(), 't')['metrics']
            for k in ('lut4', 'ff', 'carry'):
                self.assertEqual(j[k]['value'], t[k]['value'], f'{name} {k}')

    def test_nextpnr_report(self):
        p = parsers.nextpnr_report(open(r('design_a', 'pnr_report_s1.json')).read(), 'x')
        self.assertEqual(p['lc']['value'], 2900)
        self.assertAlmostEqual(p['fmax']['clk$SB_IO_IN_$glb_clk']['achieved'], 70.10, places=1)

    def test_generic_gate_library_is_unsupported(self):
        """Synthetic generic-synthesis log ($_AND_/$_XOR_ cells, not iCE40): every cell metric must be UNSUPPORTED."""
        m = parsers.yosys_log_stat(open(r('generic', 'generic.log'), encoding='utf-8').read(), 'generic.log')['metrics']
        self.assertEqual({v['status'] for v in m.values()}, {'UNSUPPORTED'})

    def test_log_without_stat_table_rejected(self):
        with self.assertRaises(parsers.ParseError):
            parsers.yosys_log_stat('Yosys 0.70\n1. Executing Verilog frontend.\n', 'synthetic_nostat.log')


class TestRejectNonReports(unittest.TestCase):
    def test_simulation_outputs_rejected(self):
        log = open(r('rejected', 'sim.log')).read()
        js = open(r('rejected', 'sim.json')).read()
        with self.assertRaises(parsers.ParseError):
            parsers.yosys_log_stat(log, 'sim.log')
        with self.assertRaises(parsers.ParseError):
            parsers.nextpnr_report(js, 'sim.json')
        with self.assertRaises(parsers.ParseError):
            parsers.yosys_stat_json(js, 'sim.json')

    def test_malformed(self):
        with self.assertRaises(parsers.ParseError):
            parsers.nextpnr_report('{"fmax": {', 'synthetic_trunc.json')
        with self.assertRaises(parsers.ParseError):
            parsers.nextpnr_report('{"fmax": {"clk": {"achieved": "fast"}}, "utilization": {}}', 'synthetic_bad.json')
        with self.assertRaises(parsers.ParseError):
            parsers.yosys_stat_json('{"creator": "Yosys", "modules": {"\\\\a": {}, "\\\\b": {}}}', 'synthetic_multi.json')

    def test_unsupported_library(self):
        syn = json.dumps({'creator': 'Yosys 0.70', 'modules': {'\\top': {'num_cells_by_type': {'$_AND_': 5, '$_DFF_P_': 2}}}})
        m = parsers.yosys_stat_json(syn, 'synthetic_generic.json')['metrics']
        self.assertEqual({v['status'] for v in m.values()}, {'UNSUPPORTED'})
        self.assertIsNone(m['lut4']['value'])


class TestCompareFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='qg_')
        self.rules = compare.load_rules(RULES)

    def test_regression_detected_exit1(self):
        base, cur = cap(self.tmp, 'other', 'design_b'), cap(self.tmp, 'base', 'design_a')
        res = compare.compare(base, cur, self.rules)
        self.assertEqual(res['exit_code'], 1)
        st = {x['metric']: x for x in res['rows']}
        self.assertEqual(st['lut4']['status'], 'REGRESSION')
        self.assertEqual((st['lc']['baseline'], st['lc']['current']), (2640, 2900))

    def test_improvement_passes(self):
        base, cur = cap(self.tmp, 'base', 'design_a'), cap(self.tmp, 'other', 'design_b')
        self.assertEqual(compare.compare(base, cur, self.rules)['exit_code'], 0)

    def test_identical_passes(self):
        a, b = cap(self.tmp, 'a', 'design_c'), cap(self.tmp, 'b', 'design_c')
        res = compare.compare(a, b, self.rules)
        self.assertEqual(res['exit_code'], 0)
        self.assertTrue(all(x['delta_pct'] == 0 for x in res['rows'] if 'delta_pct' in x))

    def test_threshold_configurable(self):
        base, cur = cap(self.tmp, 'other', 'design_d'), cap(self.tmp, 'base', 'design_c')
        loose = [dict(metric='lut4', max_increase_pct=50.0), dict(metric='lc', max_increase_pct=50.0),
                 dict(metric='fmax_min[*', max_decrease_pct=50.0)]
        self.assertEqual(compare.compare(base, cur, loose)['exit_code'], 0)
        tight = [dict(metric='lut4', max_increase_pct=0.0)]
        self.assertEqual(compare.compare(base, cur, tight)['exit_code'], 1)

    def test_required_metric_missing_exit2(self):
        base = cap(self.tmp, 'synthonly', 'design_a', pnr=False)          # no nextpnr report: no fmax/lc
        cur = cap(self.tmp, 'full', 'design_a')
        res = compare.compare(base, cur, self.rules)
        self.assertEqual(res['exit_code'], 2)
        self.assertIn('MISSING', {x['status'] for x in res['rows'] if x['metric'] == 'lc'})

    def test_optional_metric_missing_not_compared(self):
        base, cur = cap(self.tmp, 'a', 'design_a', pnr=False), cap(self.tmp, 'b', 'design_a')
        res = compare.compare(base, cur, [dict(metric='lc', max_increase_pct=2.0, required=False),
                                          dict(metric='lut4', max_increase_pct=2.0)])
        self.assertEqual(res['exit_code'], 0)
        self.assertEqual({x['metric']: x['status'] for x in res['rows']}['lc'], 'NOT_COMPARED')

    def test_clock_missing_in_some_seeds(self):
        d = os.path.join(self.tmp, 'synthetic_seed')
        os.makedirs(d)
        j = json.load(open(r('design_a', 'pnr_report_s2.json')))
        j['fmax'] = {}
        p = os.path.join(d, 'synthetic_noclk.json')
        json.dump(j, open(p, 'w'))
        rr = cap(self.tmp, 'mixed', 'design_a', nextpnr=[r('design_a', 'pnr_report_s1.json'), p])
        self.assertTrue(any('missing from 1 report' in n for n in rr['notes']))

    def test_bad_threshold_config(self):
        p = os.path.join(self.tmp, 'synthetic_rules.json')
        json.dump({'rules': [{'metric': 'lut4', 'max_increase_pct': -1}]}, open(p, 'w'))
        with self.assertRaises(ValueError):
            compare.load_rules(p)
        json.dump({'rules': [{'metric': 'lut4'}]}, open(p, 'w'))
        with self.assertRaises(ValueError):
            compare.load_rules(p)


class TestProvenanceAndCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='qg_')

    def test_raw_inputs_preserved_with_hash(self):
        rr = cap(self.tmp, 'a', 'design_a', log=True)
        self.assertEqual(len(rr['inputs']), 7)
        for i in rr['inputs']:
            stored = os.path.join(self.tmp, 'a', i['stored'])
            self.assertEqual(hashlib.sha256(open(stored, 'rb').read()).hexdigest(), i['sha256'])
            self.assertEqual(i['sha256'], hashlib.sha256(open(i['original_path'], 'rb').read()).hexdigest())
        for v in rr['metrics'].values():
            self.assertTrue(v['source'])

    def test_capture_refuses_overwrite(self):
        cap(self.tmp, 'a', 'design_a')
        with self.assertRaises(FileExistsError):
            cap(self.tmp, 'a', 'design_a')

    def test_cli_end_to_end_and_exit_codes(self):
        t = self.tmp
        self.assertEqual(cli_run('capture', '--out', f'{t}/b', '--yosys-stat', r('design_d', 'ice40_stat.json'),
                                 '--nextpnr', *seeds('design_d'))[0], 0)
        self.assertEqual(cli_run('capture', '--out', f'{t}/c', '--yosys-stat', r('design_c', 'ice40_stat.json'),
                                 '--nextpnr', *seeds('design_c'))[0], 0)
        self.assertEqual(cli_run('baseline', '--store', f'{t}/s', 'set', f'{t}/b')[0], 0)
        self.assertEqual(cli_run('baseline', '--store', f'{t}/s', 'set', f'{t}/c')[0], 3)      # no silent overwrite
        code, out, _ = cli_run('compare', '--baseline', f'{t}/s', '--current', f'{t}/c', '--config', RULES,
                               '--report', f'{t}/r.md', '--comparison-type', 'revision')   # 0.2: wording depends on type
        self.assertEqual(code, 1)
        md = open(f'{t}/r.md', encoding='utf-8').read()
        self.assertIn('REGRESSION', md)
        self.assertIn('sha256', md)
        self.assertEqual(cli_run('compare', '--baseline', f'{t}/s', '--current', f'{t}/b')[0], 0)

    def test_cli_parse_error_exit3(self):
        code, _, err = cli_run('capture', '--out', f'{self.tmp}/x', '--nextpnr', r('rejected', 'sim.json'))
        self.assertEqual(code, 3)
        self.assertIn('not a nextpnr', err)


if __name__ == '__main__':
    unittest.main()
