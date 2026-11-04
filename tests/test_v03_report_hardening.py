"""QoR Guard 0.3 reporting hardening: small and unequal sample labels, and Markdown escaping of clock names.
All reports here are SYNTHETIC (temp dirs, invented values) and validate no hardware behaviour. No Markdown library is
installed, so _split and _decode model the GFM rules this depends on: a backslash escapes the next punctuation character.
Run (from the project root): python -I -B -m unittest discover -s tests -t . -v"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import compare, ranges, report, run  # noqa: E402

FIX_A = os.path.join(ROOT, 'tests', 'fixtures', 'synthetic', 'design_a')
FROZEN = os.path.join(ROOT, 'tests', 'legacy_v020', 'qorguard.py')
PROV = dict(device='synthetic-device', yosys_version='1.0', nextpnr_version='2.0')
RULES = [dict(metric='fmax_min[*', max_decrease_pct=99.0)]
TIGHT = [dict(metric='fmax_min[*', max_decrease_pct=1.0)]
NASTY = ['a`b', '``x``', 'a|b', 'a\\b', 'a\\|b', 'a]b[c', 'clk[3]', '[x](http://y)', '`|\\[]', 'a\\']


def _split(row):
    """Splits a table row on unescaped pipes."""
    row = row.strip()[1:-1]
    cells, cur, i = [], '', 0
    while i < len(row):
        if row[i] == '\\' and i + 1 < len(row):
            cur += row[i:i + 2]
            i += 2
        elif row[i] == '|':
            cells.append(cur.strip())
            cur, i = '', i + 1
        else:
            cur, i = cur + row[i], i + 1
    return cells + [cur.strip()]


def _decode(text):
    if text.startswith('`') and text.endswith('`'):
        return text[1:-1]
    return re.sub(r'\\([!-/:-@\[-`{-~])', r'\1', text)


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix='qg03h_')
        self.addCleanup(shutil.rmtree, self.t)
        self.n = 0

    def side(self, vals, failed=0, clock='clk'):
        runs = []
        for i, v in enumerate(vals):
            self.n += 1
            p = f'{self.t}/synthetic_{self.n}.json'
            with open(p, 'w') as f:
                json.dump(dict(fmax={clock: dict(achieved=v, constraint=12)}, utilization=dict(ICESTORM_LC=dict(used=10, available=100))), f)
            runs.append(dict(report=p, seed=i + 1, status='success'))
        runs += [dict(seed=len(vals) + i + 1, status='failed') for i in range(failed)]
        self.n += 1
        m = f'{self.t}/m{self.n}.json'
        with open(m, 'w') as f:
            json.dump(dict(manifest_version=1, runs=runs, **PROV), f)
        return run.capture(f'{self.t}/run{self.n}', manifest=m)

    def md(self, b, c, rules=RULES):
        return report.markdown(b, c, compare.compare(b, c, rules))

    def clock(self, b, c):
        return ranges.compare_ranges(b, c)['clocks'][0]


class TestSmallSample(Base):
    def test_four_is_small_on_either_side(self):
        for x, y in (([10.0, 11.0, 12.0, 13.0], [10.0, 11.0, 12.0, 13.0, 14.0]), ([10.0, 11.0, 12.0, 13.0, 14.0], [10.0, 11.0, 12.0, 13.0])):
            b, c = self.side(x), self.side(y)
            self.assertTrue(self.clock(b, c)['small_sample'])
            self.assertIn('**Small sample:**', self.md(b, c))

    def test_five_each_has_no_label_and_no_confidence_claim(self):
        vals = [10.0, 11.0, 12.0, 13.0, 14.0]
        md = self.md(self.side(vals), self.side(vals))
        self.assertNotIn('**Small sample:**', md)
        self.assertNotIn('confidence', md.split('## Observed Fmax ranges')[1].split('\n## ')[0])

    def test_label_itself_denies_confidence(self):
        self.assertIn('would not establish confidence', self.md(self.side([10.0, 11.0]), self.side([10.0, 11.0])))

    def test_minimum_for_overlap_is_still_two(self):
        self.assertEqual(ranges.MIN_OBSERVATIONS, 2)
        c = self.clock(self.side([10.0, 11.0]), self.side([10.5, 11.5]))
        self.assertEqual((c['state'], c['small_sample']), ('OVERLAP', True))
        self.assertFalse(any('sample' in q for q in c['qualifiers']))
        self.assertEqual(self.clock(self.side([10.0]), self.side([10.0, 11.0]))['state'], 'INSUFFICIENT_DATA')

    def test_failed_runs_do_not_count_as_observations(self):
        b, c = self.side([10.0, 11.0, 12.0, 13.0], failed=1), self.side([10.0, 11.0, 12.0, 13.0, 14.0])
        self.assertTrue(self.clock(b, c)['small_sample'])


class TestUnequal(Base):
    def test_disclosed_with_counts(self):
        b, c = self.side([10.0, 11.0, 12.0, 13.0, 14.0, 15.0]), self.side([10.0, 11.0, 12.0, 13.0, 14.0])
        self.assertTrue(self.clock(b, c)['unequal_samples'])
        md = self.md(b, c)
        self.assertIn('**Unequal samples:** baseline 6, current 5 valid Fmax observations', md)
        self.assertIn('not directly comparable in terms of sampling coverage', md)
        self.assertNotIn('**Small sample:**', md)

    def test_equal_counts_have_no_label(self):
        self.assertNotIn('**Unequal samples:**', self.md(self.side([10.0, 11.0]), self.side([10.0, 11.0])))

    def test_labels_do_not_change_the_range_result(self):
        b, c = self.side([10.0, 11.0]), self.side([20.0, 21.0, 22.0])
        k = self.clock(b, c)
        self.assertEqual((k['state'], k['direction'], k['baseline']['min'], k['current']['max']), ('NO_OVERLAP', 'current_higher', 10.0, 22.0))


class TestEscaping(Base):
    def test_ordinary_names_are_byte_identical(self):
        for n in ('clk', 'clk$SB_IO_IN_$glb_clk', 'fmax_min[clk$x]', 'bus[3]'):
            self.assertEqual(report.md_name(n), f'`{n}`')

    def test_round_trip_and_single_table_cell(self):
        for n in NASTY:
            with self.subTest(n):
                shown = report.md_name(n)
                cells = _split(f'| {shown} | next |')
                self.assertEqual(len(cells), 2, shown)
                self.assertEqual(_decode(cells[0]), n)

    def test_full_report_keeps_every_table_row_intact(self):
        for n in NASTY:
            with self.subTest(n):
                b, c = self.side([10.0, 11.0], clock=n), self.side([10.5, 11.5], clock=n)
                md = self.md(b, c)
                widths = None
                for line in md.splitlines():
                    if line.startswith('|'):
                        count = len(_split(line))
                        widths = count if widths is None else widths
                        if set(line) <= set('|-'):
                            widths = count
                        self.assertEqual(count, widths, line)
                    else:
                        widths = None
                metric = f'fmax_min[{n}]'
                rows = [l for l in md.splitlines() if l.startswith('|') and _decode(_split(l)[0]) == metric]
                self.assertEqual(len(rows), 1, md)

    def test_no_raw_unsafe_name_in_notes_or_sources(self):
        n = 'a`b|c'
        x = run.capture(self.t + '/x', nextpnr=[self._report(n, 10.0), self._report('other', 11.0)])
        md = self.md(x, x)
        self.assertTrue(any('clock' in note and n in note for note in x['notes']))
        self.assertNotIn(n, md)
        self.assertIn(report.md_name(n), md)

    def _report(self, clock, v):
        self.n += 1
        p = f'{self.t}/rep{self.n}.json'
        with open(p, 'w') as f:
            json.dump(dict(fmax={clock: dict(achieved=v, constraint=12)}, utilization={}), f)
        return p

    def test_identity_and_matching_are_unchanged(self):
        for n in NASTY:
            with self.subTest(n):
                b, c = self.side([10.0, 11.0], clock=n), self.side([10.5, 11.5], clock=n)
                self.assertEqual(self.clock(b, c)['clock'], n)
                self.assertEqual(self.clock(b, c)['state'], 'OVERLAP')
                self.assertEqual(b['provenance']['clock_constraints_mhz']['value'], {n: 12.0})
                self.assertEqual(b['runs'][0]['fmax'][n]['achieved'], 10.0)
                row = [r for r in compare.compare(b, c, RULES)['rows'] if r['metric'] == f'fmax_min[{n}]']
                self.assertEqual(row[0]['status'], 'OK')

    def test_similar_names_that_escape_differently_stay_separate(self):
        rg = ranges.compare_ranges(self.side([10.0, 11.0], clock='a|b'), self.side([10.0, 11.0], clock='a\\|b'))
        self.assertEqual([c['state'] for c in rg['clocks']], ['INSUFFICIENT_DATA', 'INSUFFICIENT_DATA'])


class TestUnchanged(Base):
    def test_v1_gets_no_sample_labels_or_invented_counts(self):
        out = self.t + '/v1'
        reports = [os.path.join(FIX_A, f'pnr_report_s{i}.json') for i in range(1, 6)]
        p = subprocess.run([sys.executable, '-I', '-B', FROZEN, 'capture', '--out', out, '--nextpnr', *reports], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        v1 = run.load(out)
        md = self.md(v1, v1)
        self.assertNotIn('**Small sample:**', md)
        self.assertNotIn('**Unequal samples:**', md)
        v2 = self.side([10.0, 11.0])
        c = self.clock(v1, v2)
        self.assertFalse(c['unequal_samples'])
        self.assertEqual(c['state'], 'INSUFFICIENT_DATA')

    def test_verdicts_and_exit_codes(self):
        cases = (
            (([10.0, 11.0],), ([10.0, 11.0],), RULES, (0, 'PASS')),
            (([20.0, 21.0],), ([10.0, 11.0],), TIGHT, (1, 'THRESHOLD EXCEEDED')),
            (([10.0, 11.0],), ([10.0, 11.0], 1), RULES, (2, 'INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED')),
            (([20.0, 21.0],), ([10.0, 11.0], 1), TIGHT, (1, 'THRESHOLD EXCEEDED + INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED')),
            (([10.0, 11.0],), ([], 2), RULES, (2, 'INCOMPLETE EVIDENCE: ALL DECLARED RUNS FAILED')),
        )
        for x, y, rules, want in cases:
            res = compare.compare(self.side(*x), self.side(*y), rules)
            self.assertEqual((res['exit_code'], res['verdict']), want)


if __name__ == '__main__':
    unittest.main()
