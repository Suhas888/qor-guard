"""Markdown report. States what was compared, what could not be, and where every number came from.
0.2 additions: comparison type, run-count warnings, absolute deltas, logic-cell utilisation/headroom, and an explicit
split between Yosys pre-pack metrics and nextpnr packed/routed metrics."""

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


def _fmt(v):
    return '—' if v is None else (f'{v:g}' if isinstance(v, (int, float)) else str(v))


def _signed(v):
    return '—' if v is None else (f'{v:+g}')


def stage(name):
    if name in PREPACK:
        return 'Yosys pre-pack'
    if name in ('lc', 'ram', 'lc_capacity', 'ram_capacity') or name.startswith('fmax'):
        return 'nextpnr packed/routed'
    return 'other'


def markdown(base, cur, res):
    ct = res.get('comparison_type', 'unknown')
    word = res.get('exceeded_word', 'REGRESSION')
    L = [f"# QoR Guard report — {res['verdict']}", '',
         f"**Comparison type: {ct}.** {TYPE_TEXT[ct]}", '',
         f"- Baseline: `{base.get('label') or '(no label)'}` captured {base['created']} ({', '.join(base['tools']) or 'tool UNKNOWN'}; {base['n_seeds']} nextpnr run(s); {base.get('qorguard')})",
         f"- Current: `{cur.get('label') or '(no label)'}` captured {cur['created']} ({', '.join(cur['tools']) or 'tool UNKNOWN'}; {cur['n_seeds']} nextpnr run(s); {cur.get('qorguard')})",
         f"- Exit code: **{res['exit_code']}** (0 pass, 1 threshold exceeded, 2 required metric missing)",
         "- Delta convention: Δ = current − baseline; Δ % = Δ / baseline × 100 (undefined when the baseline is 0)."]
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
        L.append(f"| `{r['metric']}` | {stage(r['metric'])} | {_fmt(r['baseline'])} | {_fmt(r['current'])} | "
                 f"{_signed(r.get('delta_abs'))} | {_signed(r.get('delta_pct'))} | {th.strip()} | {st} |")
    if res.get('all_metrics'):
        L += ['', '## All extracted metrics', '',
              '| Stage | Metric | Unit | Baseline | Current | Δ | Δ % |', '|---|---|---|---|---|---|---|']
        for r in sorted(res['all_metrics'], key=lambda r: (stage(r['metric']), r['metric'])):
            pct = _signed(r['delta_pct']) if r['delta_pct'] is not None else (r.get('delta_pct_note') or '—')
            L.append(f"| {stage(r['metric'])} | `{r['metric']}` | {r['unit']} | {_fmt(r['baseline'])} | {_fmt(r['current'])} | "
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
        L += [f"- `{r['metric']}`: {r['detail']}" for r in miss]
    if res['unchecked']:
        L += ['', '## Metrics present but not covered by any threshold rule', ''] + [f'- `{n}`' for n in res['unchecked']]
    L += ['', '## Provenance']
    for name, run in (('Baseline', base), ('Current', cur)):
        L.append(f'**{name}** inputs:')
        L += [f"- {i['kind']}: `{i['stored']}` sha256 `{i['sha256'][:16]}…` (from `{i['original_path']}`)" for i in run['inputs']]
        L += [f'- note: {n}' for n in run['notes']]
    L += ['', '## Metric sources (current run)']
    L += [f"- `{k}`: {v['source']}" for k, v in sorted(cur['metrics'].items())]
    return '\n'.join(L) + '\n'
