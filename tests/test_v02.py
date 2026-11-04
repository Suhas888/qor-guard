"""QoR Guard 0.2 tests: capacity/utilisation/headroom, absolute & percentage deltas, comparison types, run-count
warnings, pre-pack vs packed explanation. The private UP5K check is in test_private_up5k.py.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import copy
import glob
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import cli, compare, report, run  # noqa: E402

FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'synthetic')
RULES = os.path.join(ROOT, 'config', 'thresholds.example.json')


def cli_run(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(list(args))
    return code, out.getvalue(), err.getvalue()


def fake_run(n_seeds=1, **vals):
    """SYNTHETIC in-memory run for unit tests of the comparison/report layer."""
    m = {k: dict(value=v, status='OK', source='synthetic', unit='MHz' if k.startswith('fmax') else 'count')
         for k, v in vals.items() if k not in ('lc_capacity',)}
    if 'lc_capacity' in vals:
        m['lc_capacity'] = dict(value=vals['lc_capacity'], status='INFO', source='synthetic')
    return dict(qorguard='synthetic', label='synthetic', created='-', tools=[], inputs=[], metrics=m, notes=[], n_seeds=n_seeds)


class TestCapacity(unittest.TestCase):
    def test_known_capacity_from_report(self):
        c = compare.capacity(fake_run(lc=5000, lc_capacity=5500))
        self.assertAlmostEqual(c['utilization_pct'], 90.909, places=3)
        self.assertEqual((c['headroom'], c['over_capacity'], c['source']), (500, False, 'nextpnr utilization.ICESTORM_LC.available'))

    def test_explicit_capacity_overrides_and_notes_conflict(self):
        c = compare.capacity(fake_run(lc=4800, lc_capacity=5500), explicit=7680)
        self.assertEqual((c['capacity'], c['headroom']), (7680, 2880))
        self.assertTrue(any('differs' in n for n in c['notes']))

    def test_unknown_capacity_no_invention(self):
        c = compare.capacity(fake_run(lc=5000))
        self.assertIsNone(c['capacity'])
        self.assertIsNone(c['utilization_pct'])
        self.assertIsNone(c['headroom'])
        self.assertTrue(any('unavailable' in n for n in c['notes']))

    def test_invalid_capacity(self):
        for bad in (0, -5, 3.5, True):
            with self.assertRaises(ValueError):
                compare.capacity(fake_run(lc=10), explicit=bad)
        p = subprocess.run([sys.executable, '-I', '-B', os.path.join(ROOT, 'qorguard.py'), 'compare', '--baseline', 'x',
                            '--current', 'y', '--lc-capacity', 'abc'], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 2)                                 # argparse usage error (documented)
        self.assertIn('invalid int value', p.stderr)

    def test_cli_invalid_capacity_exit3(self):
        t = tempfile.mkdtemp()
        for d in ('a', 'b'):
            run.capture(f'{t}/{d}', os.path.join(FIXTURES, 'design_c', 'ice40_stat.json'), None,
                        [os.path.join(FIXTURES, 'design_c', 'pnr_report_s1.json')], d)
        code, _, err = cli_run('compare', '--baseline', f'{t}/a', '--current', f'{t}/b', '--lc-capacity', '0')
        self.assertEqual(code, 3)
        self.assertIn('positive integer', err)

    def test_over_capacity_not_clamped(self):
        c = compare.capacity(fake_run(lc=6000, lc_capacity=5500))
        self.assertAlmostEqual(c['utilization_pct'], 109.091, places=3)
        self.assertEqual((c['headroom'], c['over_capacity']), (-500, True))
        md = report.markdown(fake_run(lc=6000, lc_capacity=5500), fake_run(lc=6000, lc_capacity=5500),
                             compare.compare(fake_run(lc=6000, lc_capacity=5500), fake_run(lc=6000, lc_capacity=5500), compare.DEFAULT_RULES))
        self.assertIn('109.09% **OVER CAPACITY**', md)

    def test_negative_lc_rejected(self):
        c = compare.capacity(fake_run(lc=-1, lc_capacity=5500))
        self.assertIsNone(c['utilization_pct'])
        self.assertTrue(any('invalid' in n for n in c['notes']))


class TestDeltas(unittest.TestCase):
    def test_positive_negative_zero(self):
        self.assertEqual(compare._deltas(5000, 4800)['delta_abs'], -200)
        self.assertAlmostEqual(compare._deltas(5000, 4800)['delta_pct'], -4.0, places=2)
        self.assertEqual(compare._deltas(10, 12)['delta_abs'], 2)
        self.assertEqual(compare._deltas(5, 5)['delta_pct'], 0.0)

    def test_zero_baseline_no_inf_nan(self):
        d = compare._deltas(0, 3)
        self.assertEqual(d['delta_abs'], 3)
        self.assertIsNone(d['delta_pct'])
        self.assertIn('baseline is 0', d['delta_pct_note'])
        res = compare.compare(fake_run(ram=0), fake_run(ram=2), [dict(metric='ram', max_increase_pct=10.0)])
        self.assertEqual(res['exit_code'], 1)                      # 0.1 decision semantics kept: 0 -> 2 exceeds
        md = report.markdown(fake_run(ram=0), fake_run(ram=2), res)
        self.assertIsNone(re.search(r'\b(inf|infinity|nan)\b', md, re.I))

    def test_missing_metric_delta_unavailable(self):
        rows = {r['metric']: r for r in compare.all_metrics(fake_run(lc=10), fake_run(lc=12, ram=3))}
        self.assertIsNone(rows['ram']['delta_abs'])
        self.assertIn('not available in baseline', rows['ram']['delta_pct_note'])

    def test_rule_rows_have_absolute_delta(self):
        res = compare.compare(fake_run(lc=5000), fake_run(lc=4800), [dict(metric='lc', max_increase_pct=2.0)])
        self.assertEqual(res['rows'][0]['delta_abs'], -200)


class TestComparisonTypes(unittest.TestCase):
    def setUp(self):
        self.b, self.c = fake_run(lc=100), fake_run(lc=120)
        self.rules = [dict(metric='lc', max_increase_pct=2.0)]

    def test_types_and_wording(self):
        for ct, word in (('revision', 'REGRESSION'), ('configuration', 'THRESHOLD EXCEEDED'), ('unknown', 'THRESHOLD EXCEEDED')):
            res = compare.compare(self.b, self.c, self.rules, ct)
            self.assertEqual(res['exit_code'], 1)
            self.assertEqual(res['rows'][0]['status'], 'REGRESSION')          # internal status unchanged (0.1 compat)
            md = report.markdown(self.b, self.c, res)
            self.assertIn(f'**Comparison type: {ct}.**', md)
            self.assertIn(f'**{word}**', md)
            if ct != 'revision':
                self.assertNotIn('REGRESSION', md.replace('regression', ''))
        md = report.markdown(self.b, self.c, compare.compare(self.b, self.c, self.rules, 'configuration'))
        self.assertIn('do not establish a code regression and do not prove what caused them', md)

    def test_default_is_unknown_and_invalid_rejected(self):
        self.assertEqual(compare.compare(self.b, self.c, self.rules)['comparison_type'], 'unknown')
        with self.assertRaises(ValueError):
            compare.compare(self.b, self.c, self.rules, 'regression')

    def test_cli_types(self):
        t = tempfile.mkdtemp()
        for d, n in (('a', 'design_d'), ('b', 'design_c')):
            run.capture(f'{t}/{d}', os.path.join(FIXTURES, n, 'ice40_stat.json'), None,
                        sorted(glob.glob(os.path.join(FIXTURES, n, 'pnr_report_s*.json'))), d)
        code, out, _ = cli_run('compare', '--baseline', f'{t}/a', '--current', f'{t}/b', '--config', RULES)
        self.assertEqual(code, 1)
        self.assertIn('THRESHOLD EXCEEDED', out)
        self.assertIn('Comparison type: unknown', out)
        code, out, _ = cli_run('compare', '--baseline', f'{t}/a', '--current', f'{t}/b', '--config', RULES, '--comparison-type', 'configuration')
        self.assertEqual(code, 1)
        self.assertIn('Comparison type: configuration', out)
        p = subprocess.run([sys.executable, '-I', '-B', os.path.join(ROOT, 'qorguard.py'), 'compare', '--baseline', f'{t}/a',
                            '--current', f'{t}/b', '--comparison-type', 'bogus'], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 2)                                 # argparse usage error (documented collision)
        self.assertIn('invalid choice', p.stderr)


class TestRunCountWarnings(unittest.TestCase):
    def test_single_multi_missing(self):
        self.assertTrue(any('only 1 nextpnr run' in w for w in compare.run_warnings(fake_run(1), fake_run(1))))
        self.assertEqual(compare.run_warnings(fake_run(5), fake_run(5)), [])
        self.assertTrue(any('no nextpnr report' in w for w in compare.run_warnings(fake_run(0), fake_run(5))))
        r = fake_run(5)
        del r['n_seeds']
        self.assertTrue(any('not recorded' in w for w in compare.run_warnings(r, fake_run(5))))

    def test_multi_seed_preserves_min_median_and_reports_count(self):
        t = tempfile.mkdtemp()
        r = run.capture(f'{t}/a', None, None, sorted(glob.glob(os.path.join(FIXTURES, 'design_a', 'pnr_report_s*.json'))), 'a')
        self.assertEqual(r['n_seeds'], 5)
        self.assertEqual(r['metrics']['fmax_min[clk$SB_IO_IN_$glb_clk]']['value'], 70.102)
        self.assertEqual(r['metrics']['fmax_median[clk$SB_IO_IN_$glb_clk]']['value'], 71.406)
        md = report.markdown(r, r, compare.compare(r, r, compare.DEFAULT_RULES))
        self.assertIn('5 nextpnr run(s)', md)
        self.assertNotIn('only 1 nextpnr run', md)
        self.assertNotIn('significan', md.replace('do not by themselves establish statistical significance', ''))


class TestPrepackExplanation(unittest.TestCase):
    def test_stage_labels_and_text(self):
        self.assertEqual(report.stage('lut4'), 'Yosys pre-pack')
        self.assertEqual(report.stage('lc'), 'nextpnr packed/routed')
        md = report.markdown(fake_run(lut4=10, lc=8), fake_run(lut4=10, lc=8),
                             compare.compare(fake_run(lut4=10, lc=8), fake_run(lut4=10, lc=8), compare.DEFAULT_RULES))
        self.assertIn('never interchangeable', md)
        self.assertIn('| `lut4` | Yosys pre-pack |', md)


class TestOldRunCompatibility(unittest.TestCase):
    def test_0_1_run_json_still_compares(self):
        """A run.json written by 0.1 (no lc_capacity/ram metrics) still compares; capacity is reported unavailable."""
        old = fake_run(5, lut4=10, ff=5, carry=1, lc=12)
        old['qorguard'] = 'qorguard 0.1.0'
        res = compare.compare(old, copy.deepcopy(old), compare.DEFAULT_RULES)
        self.assertEqual(res['exit_code'], 0)
        self.assertIsNone(res['capacity']['baseline']['utilization_pct'])


if __name__ == '__main__':
    unittest.main()
