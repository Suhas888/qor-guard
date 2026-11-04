"""QoR Guard 0.3 Phase 1 correction: declared failed runs never produce a PASS verdict.
All reports are SYNTHETIC, including the HX8K-format fixtures, manifests and the lowered-Fmax report, built in temp dirs. Everything runs through the CLI.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import cli, run  # noqa: E402

FIX_A = os.path.join(ROOT, 'tests', 'fixtures', 'synthetic', 'design_a')
LOG = os.path.join(FIX_A, 'synth.log')
FROZEN = os.path.join(ROOT, 'tests', 'legacy_v020', 'qorguard.py')
RULES = os.path.join(ROOT, 'config', 'thresholds.example.json')
REPORTS = sorted(glob.glob(os.path.join(FIX_A, 'pnr_report_s*.json')))
ALL = 'INCOMPLETE EVIDENCE: ALL DECLARED RUNS FAILED'
SOME = 'INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED'


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix='qg03i_')
        self.addCleanup(shutil.rmtree, self.t)
        self.n = 0

    def capture(self, runs=None, with_log=True):
        """runs=None: no manifest, all five reports through --nextpnr."""
        self.n += 1
        out = f'{self.t}/run{self.n}'
        args = ['capture', '--out', out] + (['--yosys-log', LOG] if with_log else [])
        if runs is None:
            args += ['--nextpnr'] + REPORTS
        else:
            m = f'{self.t}/m{self.n}.json'
            with open(m, 'w') as f:
                json.dump(dict(manifest_version=1, runs=runs), f)
            args += ['--manifest', m]
        self.assertEqual(self.cli(*args)[0], 0)
        return out

    def cli(self, *args):
        o, e = io.StringIO(), io.StringIO()
        with redirect_stdout(o), redirect_stderr(e):
            code = cli.main(list(args))
        return code, o.getvalue(), e.getvalue()

    def compare(self, base, cur, *extra):
        code, md, _ = self.cli('compare', '--baseline', base, '--current', cur, '--config', RULES, *extra)
        return code, md.splitlines()[0].replace('# QoR Guard report — ', ''), md

    def success(self, report=None):
        return [dict(report=report or p, seed=i + 1, status='success') for i, p in enumerate(REPORTS)]

    def partial(self):
        return self.success()[:4] + [dict(seed=5, status='failed', reason='routing failed')]

    def lowered(self, factor=0.5):
        """Five reports with every Fmax scaled down, so an example-threshold violation is certain."""
        out = []
        for i, p in enumerate(REPORTS):
            j = json.load(open(p))
            for v in j['fmax'].values():
                v['achieved'] *= factor
            q = f'{self.t}/low{i}.json'
            with open(q, 'w') as f:
                json.dump(j, f)
            out.append(q)
        return out


class TestFailedRunsNeverPass(Base):
    def test_all_failed_current(self):
        code, verdict, md = self.compare(self.capture(), self.capture([dict(seed=1, status='failed')]))
        self.assertEqual(code, 2)
        self.assertIn(ALL, verdict)
        self.assertNotIn('PASS', md)

    def test_all_failed_with_synthesis_data_and_lenient_rules_is_still_2(self):
        rules = f'{self.t}/r.json'
        with open(rules, 'w') as f:
            json.dump(dict(rules=[dict(metric='lut4', max_increase_pct=50.0)]), f)
        cur = self.capture([dict(seed=1, status='failed')])
        code, md, _ = self.cli('compare', '--baseline', self.capture(), '--current', cur, '--config', rules)
        self.assertEqual(code, 2)
        self.assertEqual(md.splitlines()[0], f'# QoR Guard report — {ALL}')
        self.assertNotIn('PASS', md)

    def test_all_failed_baseline(self):
        code, verdict, md = self.compare(self.capture([dict(seed=1, status='failed')]), self.capture())
        self.assertEqual(code, 2)
        self.assertIn(ALL, verdict)
        self.assertNotIn('PASS', md)

    def test_all_failed_beats_a_threshold_violation_for_the_exit_code(self):
        low = self.lowered()
        cur = self.capture([dict(report=low[0], seed=1, status='success')])
        base = self.capture(self.success()[:1] + [dict(seed=2, status='failed')])
        self.assertEqual(self.compare(base, cur)[0], 1)
        allfail = self.capture([dict(seed=1, status='failed')])
        code, verdict, _ = self.compare(allfail, cur)
        self.assertEqual(code, 2)
        self.assertIn(ALL, verdict)

    def test_partial_failure_otherwise_passing(self):
        code, verdict, md = self.compare(self.capture(self.success()[:4]), self.capture(self.partial()))
        self.assertEqual((code, verdict), (2, SOME))
        self.assertNotIn('PASS', md)
        self.assertIn('## Incomplete evidence', md)
        self.assertIn('| current | 5 | 4 | 1 | run 4, seed 5: routing failed |', md)

    def test_partial_failure_on_baseline_otherwise_passing(self):
        code, verdict, md = self.compare(self.capture(self.partial()), self.capture(self.success()[:4]))
        self.assertEqual((code, verdict), (2, SOME))
        self.assertIn('| baseline | 5 | 4 | 1 |', md)

    def test_partial_failure_with_observed_violation_discloses_both(self):
        low = self.lowered()
        cur = self.capture([dict(report=low[i], seed=i + 1, status='success') for i in range(4)] + [dict(seed=5, status='failed')])
        for kind, word in (('revision', 'REGRESSION'), ('configuration', 'THRESHOLD EXCEEDED'), ('unknown', 'THRESHOLD EXCEEDED')):
            code, verdict, md = self.compare(self.capture(), cur, '--comparison-type', kind)
            self.assertEqual((code, verdict), (1, f'{word} + {SOME}'))
            self.assertIn(f'**{word}**', md)
            self.assertIn('## Incomplete evidence', md)
            self.assertNotIn('PASS', md)

    def test_failed_seed_cannot_flatter_fmax_silently(self):
        vals = [json.load(open(p))['fmax'] for p in REPORTS]
        clk = next(iter(vals[0]))
        worst = min(range(5), key=lambda i: vals[i][clk]['achieved'])
        runs = self.success()
        runs[worst]['status'] = 'failed'
        cur = self.capture(runs)
        self.assertIn('1 failed run(s) excluded', run.load(cur)['metrics'][f'fmax_min[{clk}]']['source'])
        code, verdict, md = self.compare(self.capture(), cur)
        self.assertEqual((code, verdict), (2, SOME))
        self.assertIn('do not represent the failed runs', md)
        self.assertIn(f'seed {worst + 1}', md)

    def test_stored_report_of_failed_run_keeps_its_value_in_runs(self):
        runs = self.success()
        runs[0]['status'] = 'failed'
        r = run.load(self.capture(runs))
        self.assertEqual(r['run_counts']['failed'], 1)
        self.assertIn('fmax', r['runs'][0])


class TestUnchangedBehaviour(Base):
    def frozen_capture(self, name):
        out = f'{self.t}/{name}'
        p = subprocess.run([sys.executable, '-I', '-B', FROZEN, 'capture', '--out', out, '--yosys-log', LOG, '--nextpnr'] + REPORTS,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return out

    def test_v1_vs_v1_passes_with_no_new_text(self):
        code, verdict, md = self.compare(self.frozen_capture('a'), self.frozen_capture('b'))
        self.assertEqual((code, verdict), (0, 'PASS'))
        self.assertNotIn('Incomplete evidence', md)
        self.assertNotIn('no manifest declared', md)

    def test_v1_baseline_with_partial_failed_v2(self):
        code, verdict, md = self.compare(self.frozen_capture('a'), self.capture(self.partial()))
        self.assertEqual((code, verdict), (2, SOME))
        self.assertNotIn('PASS', md)

    def test_all_success_declared_v2_passes(self):
        code, verdict, md = self.compare(self.capture(self.success()), self.capture(self.success()))
        self.assertEqual((code, verdict), (0, 'PASS'))
        self.assertNotIn('Incomplete evidence', md)
        self.assertNotIn('no manifest declared', md)

    def test_all_success_v2_violation_is_plain(self):
        low = self.lowered()
        cur = self.capture([dict(report=p, seed=i, status='success') for i, p in enumerate(low)])
        code, verdict, md = self.compare(self.capture(), cur, '--comparison-type', 'revision')
        self.assertEqual((code, verdict), (1, 'REGRESSION'))
        self.assertNotIn('Incomplete evidence', md)

    def test_no_manifest_infers_nothing_and_states_the_limitation(self):
        code, verdict, md = self.compare(self.capture(), self.capture())
        self.assertEqual((code, verdict), (0, 'PASS'))
        self.assertNotIn('Incomplete evidence', md)
        self.assertIn('a failed run that left no report cannot be detected', md)

    def test_missing_report_file_named_like_a_seed_gap_is_not_a_failure(self):
        code, verdict, _ = self.compare(self.capture(), self.capture_two_reports())
        self.assertEqual((code, verdict), (0, 'PASS'))

    def capture_two_reports(self):
        out = f'{self.t}/two'                 # s1 and s5 only: the gap in the names must not be read as failed runs
        self.assertEqual(self.cli('capture', '--out', out, '--yosys-log', LOG, '--nextpnr', REPORTS[0], REPORTS[4])[0], 0)
        return out


if __name__ == '__main__':
    unittest.main()
