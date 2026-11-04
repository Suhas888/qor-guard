"""Baseline vs current comparison with configurable thresholds.
Threshold config (JSON): {"rules": [{"metric": "lut4", "max_increase_pct": 2.0, "required": true}, ...]}
  metric may end in '*' to match a prefix, e.g. "fmax_min[*" applies to every clock.
  max_increase_pct  regression if current > baseline * (1 + pct/100)   (for "lower is better" metrics)
  max_decrease_pct  regression if current < baseline * (1 - pct/100)   (for "higher is better" metrics)
  required          if the metric is missing/unsupported in either run -> status MISSING counts as a failure
Exit codes: 0 = no regression; 1 = threshold exceeded; 2 = required metric missing (or both)."""
import fnmatch
import json

DEFAULT_RULES = [
    dict(metric='lut4', max_increase_pct=2.0, required=False),
    dict(metric='ff', max_increase_pct=2.0, required=False),
    dict(metric='carry', max_increase_pct=5.0, required=False),
    dict(metric='lc', max_increase_pct=2.0, required=False),
    dict(metric='fmax_min[*', max_decrease_pct=5.0, required=False),
    dict(metric='fmax_median[*', max_decrease_pct=3.0, required=False),
]


def load_rules(path=None):
    if not path:
        return DEFAULT_RULES
    cfg = json.load(open(path, encoding='utf-8'))
    rules = cfg.get('rules')
    if not isinstance(rules, list) or not rules:
        raise ValueError(f'{path}: needs a non-empty "rules" list')
    for r in rules:
        if 'metric' not in r or not ({'max_increase_pct', 'max_decrease_pct'} & set(r)):
            raise ValueError(f'{path}: each rule needs "metric" and max_increase_pct or max_decrease_pct: {r}')
        for k in ('max_increase_pct', 'max_decrease_pct'):
            if k in r and (not isinstance(r[k], (int, float)) or r[k] < 0):
                raise ValueError(f'{path}: {k} must be a non-negative number: {r}')
    return rules


def compare(base, cur, rules, comparison_type='unknown', lc_capacity=None):
    if comparison_type not in ('revision', 'configuration', 'unknown'):
        raise ValueError(f'comparison type must be revision, configuration or unknown, got {comparison_type!r}')
    rows, fail, missing = [], False, False
    names = sorted(set(base['metrics']) | set(cur['metrics']))
    matched = set()
    for rule in rules:
        targets = [n for n in names if fnmatch.fnmatchcase(n, rule['metric'].replace('[', '[[]'))] or [rule['metric']]
        for n in targets:
            matched.add(n)
            b, c = base['metrics'].get(n), cur['metrics'].get(n)
            row = dict(metric=n, rule=rule, baseline=b and b.get('value'), current=c and c.get('value'),
                       unit=(c or b or {}).get('unit', 'count'))
            if not b or not c or b.get('status') != 'OK' or c.get('status') != 'OK' or b.get('value') is None or c.get('value') is None:
                why = []
                for side, m in (('baseline', b), ('current', c)):
                    if not m:
                        why.append(f'{side}: not present')
                    elif m.get('status') != 'OK' or m.get('value') is None:
                        why.append(f"{side}: {m.get('status')} ({m.get('source')})")
                row.update(status='MISSING' if rule.get('required') else 'NOT_COMPARED', detail='; '.join(why))
                missing |= bool(rule.get('required'))
            else:
                bv, cv = float(b['value']), float(c['value'])
                # threshold decision: unchanged from 0.1 (a change from a zero baseline counts as an unbounded change)
                delta = (cv - bv) / bv * 100 if bv else (0.0 if cv == bv else float('inf'))
                row.update(_deltas(bv, cv))
                bad = ('max_increase_pct' in rule and delta > rule['max_increase_pct']) or \
                      ('max_decrease_pct' in rule and delta < -rule['max_decrease_pct'])
                row['status'] = 'REGRESSION' if bad else 'OK'      # internal status name kept for 0.1 compatibility
                fail |= bad
            rows.append(row)
    unchecked = [n for n in names if n not in matched and not n.startswith('fmax_constraint')
                 and n not in ('lc_capacity', 'ram_capacity')]
    code = 2 if missing else (1 if fail else 0)
    word = 'REGRESSION' if comparison_type == 'revision' else 'THRESHOLD EXCEEDED'
    verdict = {0: 'PASS', 1: word, 2: 'MISSING REQUIRED METRIC'}[code] if not (fail and missing) \
        else f'{word} + MISSING REQUIRED METRIC'
    return dict(rows=rows, unchecked=unchecked, exit_code=code, verdict=verdict, comparison_type=comparison_type,
                exceeded_word=word, all_metrics=all_metrics(base, cur),
                capacity={'baseline': capacity(base, lc_capacity), 'current': capacity(cur, lc_capacity)},
                warnings=run_warnings(base, cur))


# ------------------------------------------------------------------ 0.2 additions (reporting context only)

COMPARISON_TYPES = ('revision', 'configuration', 'unknown')


def _deltas(bv, cv):
    """delta = current - baseline. Percentage only when the baseline is non-zero (never inf/NaN)."""
    d = cv - bv
    return dict(delta_abs=round(d, 6), delta_pct=round(d / bv * 100, 2) if bv else (0.0 if d == 0 else None),
                delta_pct_note=None if bv or d == 0 else 'percentage undefined: baseline is 0')


def all_metrics(base, cur):
    """Every metric with a numeric value in either run, with deltas where both values exist (rules not required)."""
    out = []
    for n in sorted(set(base['metrics']) | set(cur['metrics'])):
        b, c = base['metrics'].get(n), cur['metrics'].get(n)
        bv, cv = (b or {}).get('value'), (c or {}).get('value')
        num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
        row = dict(metric=n, baseline=bv if num(bv) else None, current=cv if num(cv) else None,
                   unit=(c or b or {}).get('unit', 'count'))
        if num(bv) and num(cv):
            row.update(_deltas(float(bv), float(cv)))
        else:
            row.update(delta_abs=None, delta_pct=None,
                       delta_pct_note='not available in ' + ' and '.join(s for s, v in (('baseline', bv), ('current', cv)) if not num(v)))
        out.append(row)
    return out


def capacity(run, explicit=None):
    """Logic-cell utilisation and headroom. Capacity source, in order: explicit --lc-capacity, else nextpnr's own
    utilization.ICESTORM_LC.available for this run. Never assumed from the device family."""
    if explicit is not None and (not isinstance(explicit, int) or isinstance(explicit, bool) or explicit <= 0):
        raise ValueError(f'--lc-capacity must be a positive integer, got {explicit!r}')
    lc = (run['metrics'].get('lc') or {})
    used = lc.get('value') if lc.get('status') == 'OK' else None
    rep = (run['metrics'].get('lc_capacity') or {}).get('value')
    out = dict(lc=used, capacity=None, source=None, utilization_pct=None, headroom=None, over_capacity=None, notes=[])
    if explicit is not None:
        out.update(capacity=explicit, source='explicit --lc-capacity')
        if isinstance(rep, int) and rep != explicit:
            out['notes'].append(f'explicit capacity {explicit} differs from nextpnr-reported {rep}')
    elif isinstance(rep, int) and rep > 0:
        out.update(capacity=rep, source='nextpnr utilization.ICESTORM_LC.available')
    else:
        out['notes'].append('capacity unavailable (not in the nextpnr report and no --lc-capacity given)')
    if used is None:
        out['notes'].append('logic-cell count unavailable')
    elif not isinstance(used, int) or used < 0:
        out['notes'].append(f'invalid logic-cell count {used!r}')
        out['lc'] = None
    if out['capacity'] and out['lc'] is not None:
        out.update(utilization_pct=round(out['lc'] / out['capacity'] * 100, 3), headroom=out['capacity'] - out['lc'],
                   over_capacity=out['lc'] > out['capacity'])
    return out


def run_warnings(base, cur):
    w = []
    for side, r in (('baseline', base), ('current', cur)):
        n = r.get('n_seeds')
        if n is None:
            w.append(f'{side}: number of nextpnr runs not recorded')
        elif n == 0:
            w.append(f'{side}: no nextpnr report, so no timing or logic-cell data')
        elif n == 1:
            w.append(f'{side}: only 1 nextpnr run. Seed-to-seed variability cannot be estimated; a single Fmax result '
                     'is not a statistically robust timing comparison.')
    return w
