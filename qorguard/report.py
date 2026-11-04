"""Markdown report. States what was compared, what could not be, and where every number came from.
0.2 additions: comparison type, run-count warnings, absolute deltas, logic-cell utilisation/headroom, and an explicit
split between Yosys pre-pack metrics and nextpnr packed/routed metrics."""

import re

from . import timing
from .ranges import SMALL_SAMPLE

TYPE_TEXT = {
    'revision': 'Two revisions of the same design and configuration (relationship stated by the user). A threshold '
                'violation is reported as a regression between these revisions.',
    'configuration': 'Two different design configurations or parameter settings. Differences describe the two '
                     'configurations; they do not establish a code regression and do not prove what caused them.',
    'unknown': 'The relationship between the two runs was not stated (default). Differences are reported numerically '
               'only; they do not establish a regression or a cause.',
}
PREPACK = ('lut4', 'ff', 'carry')
PREPACK_TEXT = ('**Yosys pre-pack (synthesis)** metrics (`lut4`, `ff`, `carry`) count technology-mapped cells after '
                'synthesis, before placement. **nextpnr packed / routed** metrics (`lc`, `ram`, `fmax_*`) come from the '
                'implemented design: an iCE40 logic cell (`lc`) can hold a LUT4 and a flip-flop together, so `lut4` and '
                '`lc` are different quantities and are never interchangeable. Fmax values are nextpnr\'s post-route timing '
                'estimates for the given runs (stored to 0.001 MHz), not hardware measurements.')


_UNSAFE_NAME = re.compile(r'[`|\\\r\n]')
_PUNCTUATION = re.compile(r'([!-/:-@\[-`{-~])')
_METRIC_CLOCK = re.compile(r'^fmax_\w+\[(.*)\]$', re.S)


def md_name(name):
    """A metric or clock name for Markdown, safe in a table cell or a list. Presentation only: never use it for matching.
    A code span cannot reliably hold a pipe in a table cell, so names with these characters become escaped plain text."""
    if not _UNSAFE_NAME.search(name):
        return f'`{name}`'
    return _PUNCTUATION.sub(r'\\\1', ' '.join(name.splitlines()))


def _clean(text, clocks):
    """Escapes clock names with unsafe characters inside free text such as notes and metric sources."""
    for c in clocks:
        if _UNSAFE_NAME.search(c):
            text = text.replace(c, md_name(c))
    return text


def _fmt(v):
    return '—' if v is None else (f'{v:g}' if isinstance(v, (int, float)) else str(v))


def _signed(v):
    return '—' if v is None else (f'{v:+g}')


def _failed_run(x):
    seed = x['seed']['value']
    text = f"run {x['index']}, seed {'unavailable' if seed is None else seed}"
    if x.get('reason'):
        text += ': ' + ' '.join(x['reason'].split()).replace('|', '\\|')
    return text


def _mhz(v):
    return '—' if v is None else f'{v:.3f}'


def _count(v):
    return 'not declared' if v is None else str(v)


def _range_result(c):
    if c['state'] == 'INSUFFICIENT_DATA':
        return '**Insufficient data:** no range comparison is made. ' + '; '.join(c['insufficient_reasons']) + '.'
    text = {'OVERLAP': 'The observed ranges overlap',
            'NO_OVERLAP': 'The observed ranges do not overlap'}[c['state']]
    if c['direction']:
        text += ' (current ' + ('higher' if c['direction'] == 'current_higher' else 'lower') + ')'
    text = f'**{text}'
    return text + (', with the qualifications below.**' if c['qualified'] else '.**')


def _sample_counts(c):
    return ', '.join(f"{n} {c[n]['observations']}" for n in ('baseline', 'current') if c[n]['per_run_data'])


def _ranges(rg):
    L = ['', '## Observed Fmax ranges', '',
         'These figures describe only the runs supplied. An overlap does not establish that the two sides perform alike, '
         'that there is no regression, or that a difference comes from placement variation. This section does not affect '
         'the verdict or exit code. Ranges use successful runs only, calculated at full source precision and displayed to '
         '0.001 MHz.']
    if not rg['available']:
        return L + ['', f"Not available: {rg['reason']}."]
    if not rg['clocks']:
        L += ['', 'No clock has an Fmax value in any run, so there is no range comparison.', '',
              '| Side | Attempted | Successful | Failed |', '|---|---|---|---|']
        L += [f"| {n} | {_count(s['attempted'])} | {_count(s['successful'])} | {_count(s['failed'])} |" if s['per_run_data']
              else f'| {n} | not stored (v1) | not stored (v1) | not stored (v1) |' for n, s in rg['sides'].items()]
    for c in rg['clocks']:
        L += ['', f"### Clock {md_name(c['clock'])}", '',
              '| Side | Attempted | Successful | Failed | Valid Fmax observations | Min (MHz) | Median (MHz) | Max (MHz) | Insufficient data |',
              '|---|---|---|---|---|---|---|---|---|']
        for n in ('baseline', 'current'):
            s = c[n]
            if s['per_run_data']:
                L.append(f"| {n} | {_count(s['attempted'])} | {_count(s['successful'])} | {_count(s['failed'])} | {s['observations']} | "
                         f"{_mhz(s['min'])} | {_mhz(s['median'])} | {_mhz(s['max'])} | {'yes' if s['insufficient'] else 'no'} |")
            else:
                L.append(f'| {n} | not stored (v1) | not stored (v1) | not stored (v1) | not stored (v1) | — | — | — | yes |')
        L += ['', _range_result(c)]
        if c['small_sample']:
            L.append(f"**Small sample:** {_sample_counts(c)} valid Fmax observations, under {SMALL_SAMPLE} on at least one side. "
                     f"Reaching {SMALL_SAMPLE} would remove this label but would not establish confidence in the result.")
        if c['unequal_samples']:
            L.append(f'**Unequal samples:** {_sample_counts(c)} valid Fmax observations. A side with more runs has more chance '
                     'of a wider range, so these ranges are not directly comparable in terms of sampling coverage.')
        b, k = c['baseline'], c['current']
        if c['state'] == 'NO_OVERLAP' and (_mhz(b['max']) == _mhz(k['min']) or _mhz(k['max']) == _mhz(b['min'])):
            L.append('The ranges are separate only beyond the displayed 0.001 MHz.')
        L += [f'- {q}' for q in c['qualifiers']]
    L += ['', '### Compatibility of the two sides', '', '| Field | Baseline | Current | Status |', '|---|---|---|---|']
    for f in rg['compatibility']:
        show = lambda v: 'unavailable' if v['value'] is None else f"{_prov_value(v['value'])} ({v['status']})"
        L.append(f"| {f['field']} | {show(f['baseline'])} | {show(f['current'])} | {f['status']} |")
    return L


def _margin_cell(m):
    return f"{m['absolute_mhz']:+.3f} MHz ({m['percent']:+.2f}%)"


def _exact(v):
    return '—' if v is None else str(v)


def _timing_result(name, s):
    if s['state'] == timing.NOT_STORED:
        return f'{name}: timing compliance cannot be assessed. A schema v1 record stores no required frequency or per-run Fmax.'
    if s['state'] == timing.REQUIREMENT_MISSING:
        tool = f" The tool-reported constraint ({', '.join(map(str, s['constraints']))} MHz) is not used as a substitute." if s['constraints'] else ''
        return f'{name}: timing compliance cannot be assessed. No required frequency is declared for this clock.{tool}'
    if s['state'] == timing.NO_OBSERVATIONS:
        return (f'{name}: timing compliance cannot be assessed. There is no valid Fmax observation for this clock, so the '
                'required clock could not be evaluated because no matching observations exist. Clock names are never inferred.')
    seen = f"{s['observations_meeting']} of {s['observations']} observations meet the required frequency"
    if s['state'] == timing.MISSES:
        return f'**{name}: the observed minimum does not meet the required frequency.** {seen}.'
    text = f'**{name}: the observed minimum meets the required frequency.** {seen}. This covers these runs only and does not predict other runs or seeds.'
    if s['failed']:
        text += f" {s['failed']} declared run(s) failed, so this does not cover every attempted run."
    return text


def _timing(tm):
    L = ['', '## Required-clock timing', '',
         'A required frequency is only what a manifest explicitly declares; a tool constraint is shown separately and never '
         'replaces it. Absolute margin = achieved − required. Percentage margin = (achieved − required) / required × 100. '
         'These are frequency margins, not period slack. Figures use successful runs only, calculated at full source '
         'precision; achieved Fmax and margins are displayed rounded. A range overlap says nothing about meeting a required '
         'frequency. If the current side misses its declared requirement, the exit code is 1, even when every percentage '
         'threshold is met. If a current-side required clock has no matching observations, or the requirements for a clock '
         'differ, are declared on only one side, or cannot be compared with a v1 record, the exit code is 2 unless a known '
         'failure makes it 1. A baseline-side miss '
         'alone does not affect the exit code, and a clock neither side declares is informational. QoR Guard has no '
         'independent source for a required frequency, so it cannot tell whether a declared value is correct.']
    if not tm['available']:
        return L + ['', f"Not available: {tm['reason']}."]
    if not tm['clocks']:
        L += ['', 'No clock has an Fmax value or a declared required frequency, so timing compliance cannot be assessed.', '',
              '| Side | Attempted | Successful | Failed |', '|---|---|---|---|']
        L += [f"| {n} | {_count(s['attempted'])} | {_count(s['successful'])} | {_count(s['failed'])} |" if s['per_run_data']
              else f'| {n} | not stored (v1) | not stored (v1) | not stored (v1) |' for n, s in tm['sides'].items()]
    for c in tm['clocks']:
        L += ['', f"### Timing for clock {md_name(c['clock'])}", '',
              '| Side | Attempted | Successful | Failed | Valid Fmax observations | Required (MHz) | Tool constraint (MHz) | Min (MHz) | Median (MHz) | Max (MHz) |',
              '|---|---|---|---|---|---|---|---|---|---|']
        for n in ('baseline', 'current'):
            s = c[n]
            if s['per_run_data']:
                tool = ', '.join(map(str, s['constraints'])) or '—'
                L.append(f"| {n} | {_count(s['attempted'])} | {_count(s['successful'])} | {_count(s['failed'])} | {s['observations']} | "
                         f"{_exact(s['required_mhz']) if s['required_mhz'] is not None else 'not declared'} | {tool} | {_mhz(s['min'])} | {_mhz(s['median'])} | {_mhz(s['max'])} |")
            else:
                L.append(f'| {n} | not stored (v1) | not stored (v1) | not stored (v1) | not stored (v1) | not stored (v1) | — | — | — | — |')
        rows = [(n, c[n]) for n in ('baseline', 'current') if c[n]['margin']]
        if rows:
            L += ['', '| Side | Min margin | Median margin | Max margin |', '|---|---|---|---|']
            L += [f"| {n} | {_margin_cell(s['margin']['min'])} | {_margin_cell(s['margin']['median'])} | {_margin_cell(s['margin']['max'])} |" for n, s in rows]
        L.append('')
        L += [_timing_result(n, c[n]) + '  ' for n in ('baseline', 'current')]
        if c['declaration_missing_on']:
            has = 'current' if c['declaration_missing_on'] == 'baseline' else 'baseline'
            L += ['', f"**Inconsistent requirements:** {has} declares {c[has]['required_mhz']} MHz for this clock and "
                      f"{c['declaration_missing_on']} declares none. No requirement is copied or inferred, the two sides were "
                      'not held to the same requirement, and this comparison cannot pass.']
        if c['requirement_comparison_unavailable_on']:
            old = c['requirement_comparison_unavailable_on']
            new = 'current' if old == 'baseline' else 'baseline'
            L += ['', f"**Requirement comparison unavailable:** {new} declares {c[new]['required_mhz']} MHz for this clock, and "
                      f'{old} is a schema v1 record, which cannot store a requirement. This is not taken to mean that no '
                      'requirement existed. Nothing is copied or inferred, and this comparison cannot pass.']
        if c['values_differ']:
            L += ['', f"**Inconsistent requirements:** baseline {c['baseline']['required_mhz']} MHz, current {c['current']['required_mhz']} MHz. "
                      'The two margins are not like-for-like, so no timing improvement or decline is implied. The current '
                      "side's requirement governs its compliance check, and this comparison cannot pass while the requirements differ."]
        L += [f'- {q}' for q in c['notes']]
    return L


def _prov_value(v):
    return ', '.join(f"{x['name']} {x['sha256'][:16]}…" for x in v) if isinstance(v, list) else str(v)


def stage(name):
    if name in PREPACK:
        return 'Yosys pre-pack'
    if name in ('lc', 'ram', 'lc_capacity', 'ram_capacity') or name.startswith('fmax'):
        return 'nextpnr packed/routed'
    return 'other'


def markdown(base, cur, res):
    clocks = {m.group(1) for r in (base, cur) for m in map(_METRIC_CLOCK.match, r['metrics']) if m}
    ct = res.get('comparison_type', 'unknown')
    word = res.get('exceeded_word', 'REGRESSION')
    L = [f"# QoR Guard report — {res['verdict']}", '',
         f"**Comparison type: {ct}.** {TYPE_TEXT[ct]}", '',
         f"- Baseline: `{base.get('label') or '(no label)'}` captured {base['created']} ({', '.join(base['tools']) or 'tool UNKNOWN'}; {base['n_seeds']} nextpnr run(s); {base.get('qorguard')})",
         f"- Current: `{cur.get('label') or '(no label)'}` captured {cur['created']} ({', '.join(cur['tools']) or 'tool UNKNOWN'}; {cur['n_seeds']} nextpnr run(s); {cur.get('qorguard')})",
         f"- Exit code: **{res['exit_code']}** (0 pass, 1 threshold exceeded or required clock not met, 2 required metric or evidence missing)",
         "- Delta convention: Δ = current − baseline; Δ % = Δ / baseline × 100 (undefined when the baseline is 0)."]
    if res.get('incomplete'):
        L += ['', '## Incomplete evidence', '',
              'Declared runs failed, so this comparison cannot pass. Fmax figures use successful runs only and do not '
              'represent the failed runs. Exit code 2 here means required evidence is missing.', '',
              '| Run | Attempted | Successful | Failed | Failed runs |', '|---|---|---|---|---|']
        for side, s in res['incomplete']['sides'].items():
            detail = '; '.join(_failed_run(x) for x in s['runs'])
            L.append(f"| {side} | {s['attempted']} | {s['successful']} | {s['failed']} | {detail} |")
    if res.get('warnings'):
        L += ['', '## Warnings'] + [f'- ⚠ {w}' for w in res['warnings']]
        if any('only 1 nextpnr run' in w for w in res['warnings']):
            L.append('- Run counts are the number of nextpnr reports supplied; nextpnr report JSON does not record the seed '
                     'value itself. Multiple runs give worst-case and median Fmax but do not by themselves establish '
                     'statistical significance.')
    L += ['', '## Threshold checks', '',
          '| Metric | Stage | Baseline | Current | Δ | Δ % | Threshold | Status |', '|---|---|---|---|---|---|---|---|']
    for r in res['rows']:
        th = (f"≤ +{r['rule']['max_increase_pct']}%" if 'max_increase_pct' in r['rule'] else '') + \
             (f" ≥ −{r['rule']['max_decrease_pct']}%" if 'max_decrease_pct' in r['rule'] else '') + \
             (' (required)' if r['rule'].get('required') else '')
        st = {'REGRESSION': f'**{word}**', 'MISSING': '**MISSING**'}.get(r['status'], r['status'])
        L.append(f"| {md_name(r['metric'])} | {stage(r['metric'])} | {_fmt(r['baseline'])} | {_fmt(r['current'])} | "
                 f"{_signed(r.get('delta_abs'))} | {_signed(r.get('delta_pct'))} | {th.strip()} | {st} |")
    if res.get('ranges'):
        L += _ranges(res['ranges'])
    if res.get('timing'):
        L += _timing(res['timing'])
    if res.get('all_metrics'):
        L += ['', '## All extracted metrics', '',
              '| Stage | Metric | Unit | Baseline | Current | Δ | Δ % |', '|---|---|---|---|---|---|---|']
        for r in sorted(res['all_metrics'], key=lambda r: (stage(r['metric']), r['metric'])):
            pct = _signed(r['delta_pct']) if r['delta_pct'] is not None else (r.get('delta_pct_note') or '—')
            L.append(f"| {stage(r['metric'])} | {md_name(r['metric'])} | {r['unit']} | {_fmt(r['baseline'])} | {_fmt(r['current'])} | "
                     f"{_signed(r['delta_abs'])} | {pct} |")
    cap = res.get('capacity')
    if cap:
        L += ['', '## Logic-cell utilisation and headroom (nextpnr packed)', '',
              '| Run | LC used | LC capacity | Capacity source | Utilisation | Headroom |', '|---|---|---|---|---|---|']
        for side in ('baseline', 'current'):
            c = cap[side]
            util = '—' if c['utilization_pct'] is None else f"{c['utilization_pct']:.2f}%" + (' **OVER CAPACITY**' if c['over_capacity'] else '')
            L.append(f"| {side} | {_fmt(c['lc'])} | {_fmt(c['capacity'])} | {c['source'] or 'unavailable'} | {util} | {_fmt(c['headroom'])} |")
        for side in ('baseline', 'current'):
            L += [f'- {side}: {n}' for n in cap[side]['notes']]
    L += ['', '## Pre-pack vs packed metrics', '', PREPACK_TEXT]
    miss = [r for r in res['rows'] if r['status'] in ('MISSING', 'NOT_COMPARED')]
    if miss:
        L += ['', '## Not compared / missing metrics']
        L += [f"- {md_name(r['metric'])}: {_clean(r['detail'], clocks)}" for r in miss]
    if res['unchecked']:
        L += ['', '## Metrics present but not covered by any threshold rule', ''] + [f'- {md_name(n)}' for n in res['unchecked']]
    L += ['', '## Provenance']
    for name, run in (('Baseline', base), ('Current', cur)):
        L.append(f'**{name}** inputs:')
        L += [f"- {i['kind']}: `{i['stored']}` sha256 `{i['sha256'][:16]}…` (from `{i['original_path']}`)" for i in run['inputs']]
        L += [f'- note: {_clean(n, clocks)}' for n in run['notes']]
    L += ['', '## Metric sources (current run)']
    L += [f"- {md_name(k)}: {_clean(v['source'], clocks)}" for k, v in sorted(cur['metrics'].items())]
    return '\n'.join(L) + '\n'
