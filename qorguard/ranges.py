"""Observed Fmax ranges (0.3). Reporting only: nothing here affects a threshold decision or an exit code.
Values come from the unrounded per-run records of schema v2, successful runs only, and failed-run counts travel with every
range. v1 records store no per-run values, so they get no range. An overlap describes the observed values and nothing more."""
import math
import statistics

MIN_OBSERVATIONS = 2
SMALL_SAMPLE = 5
OVERLAP, NO_OVERLAP, INSUFFICIENT = 'OVERLAP', 'NO_OVERLAP', 'INSUFFICIENT_DATA'
COMPAT_FIELDS = ('device', 'yosys_version', 'nextpnr_version', 'constraint_files')


def _valid(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0


def _is_v2(r):
    return r.get('schema_version') == 2


def _side(r, clock):
    """Statistics of one side for one clock. Everything is None for a v1 record, which never stored these values."""
    if not _is_v2(r):
        return dict(per_run_data=False, attempted=None, successful=None, failed=None, observations=None, min=None,
                    median=None, max=None, insufficient=True, missing_from_runs=None, invalid=None, seeds=None, constraints=[])
    ok = [x for x in r['runs'] if x['status'] == 'success']
    entries = [x['fmax'][clock] for x in ok if clock in x.get('fmax', {})]
    used = [x for x in ok if clock in x.get('fmax', {}) and _valid(x['fmax'][clock]['achieved'])]
    vals = [x['fmax'][clock]['achieved'] for x in used]
    counts = r['run_counts']
    return dict(per_run_data=True, attempted=counts['attempted'], successful=counts['successful'], failed=counts['failed'],
                observations=len(vals), min=min(vals) if vals else None, median=statistics.median(vals) if vals else None,
                max=max(vals) if vals else None, insufficient=len(vals) < MIN_OBSERVATIONS,
                missing_from_runs=len(ok) - len(entries), invalid=len(entries) - len(vals),
                values=vals, seeds=[x['seed']['value'] for x in used], constraints=sorted({e['constraint'] for e in entries}))


def _seed_relation(b, c):
    if not b['per_run_data'] or not c['per_run_data'] or not b['seeds'] or not c['seeds']:
        return 'unavailable'
    if None in b['seeds'] or None in c['seeds']:
        return 'unavailable'
    return 'same_seed_values' if set(b['seeds']) == set(c['seeds']) else 'different_seed_values'


def _insufficient_reasons(name, s, clock_seen):
    if not s['per_run_data']:
        return [f'{name}: schema v1 record stores no per-run Fmax']
    if s['insufficient']:
        where = '' if clock_seen else ' (clock not in any of its runs)'
        return [f"{name}: {s['observations']} valid Fmax observation(s), {MIN_OBSERVATIONS} needed{where}"]
    return []


def _qualifiers(b, c, seeds, general):
    q = list(general)
    for name, s in (('baseline', b), ('current', c)):
        if not s['per_run_data']:
            continue
        if s['failed']:
            q.append(f"{name}: {s['failed']} of {s['attempted']} declared runs failed and are not in the range")
        if s['failed'] is None:
            q.append(f'{name}: attempted and failed runs were not declared; failed runs that left no report are unknown')
        if s['missing_from_runs']:
            q.append(f"{name}: clock missing from {s['missing_from_runs']} of {s['successful']} successful run(s)")
        if s['invalid']:
            q.append(f"{name}: {s['invalid']} invalid Fmax value(s) not used")
    if seeds == 'unavailable':
        q.append('seed values are unavailable for at least one observation; no claim is made that the sides used the same seeds')
    elif seeds == 'different_seed_values':
        q.append('the two sides have different seed values')
    if b['constraints'] and c['constraints'] and b['constraints'] != c['constraints']:
        q.append(f"clock constraint differs: baseline {b['constraints']} MHz, current {c['constraints']} MHz")
    return q


def _sample_cautions(b, c):
    """Labels only: they never change the state or the qualified flag. v1 records have no observation count to judge."""
    out = dict(small_sample=False, unequal_samples=False)
    counts = [s['observations'] for s in (b, c) if s['per_run_data']]
    if counts and min(counts) < SMALL_SAMPLE:
        out['small_sample'] = True
    if len(counts) == 2 and counts[0] != counts[1]:
        out['unequal_samples'] = True
    return out


def _compat(base, cur):
    rows = []
    for k in COMPAT_FIELDS:
        vals = []
        for r in (base, cur):
            f = r['provenance'][k] if _is_v2(r) else None
            vals.append(f if f else dict(status='unavailable', value=None))
        bv, cv = vals[0]['value'], vals[1]['value']
        status = 'unavailable' if bv is None or cv is None else ('match' if bv == cv else 'differs')
        rows.append(dict(field=k, baseline=vals[0], current=vals[1], status=status))
    return rows


def compare_ranges(base, cur):
    if not _is_v2(base) and not _is_v2(cur):
        return dict(available=False, clocks=[], compatibility=[], sides={},
                    reason='both records are schema v1, which stores no per-run Fmax')
    compat = _compat(base, cur)
    general = [f"{c['field'].replace('_', ' ')} {'differs' if c['status'] == 'differs' else 'unavailable on at least one side'}"
               for c in compat if c['status'] != 'match']
    sides = {}
    names = {}
    for name, r in (('baseline', base), ('current', cur)):
        names[name] = {c for x in r.get('runs', []) if _is_v2(r) for c in x.get('fmax', {})}
        counts = r['run_counts'] if _is_v2(r) else dict(attempted=None, successful=None, failed=None)
        sides[name] = dict(per_run_data=_is_v2(r), attempted=counts['attempted'], successful=counts['successful'], failed=counts['failed'])
    clocks = []
    for clock in sorted(names['baseline'] | names['current']):
        b, c = _side(base, clock), _side(cur, clock)
        seeds = _seed_relation(b, c)
        general_here = list(general)
        for name, other, s in (('baseline', 'current', b), ('current', 'baseline', c)):
            if s['per_run_data'] and clock not in names[name] and _is_v2(cur if name == 'baseline' else base):
                general_here.append(f'clock appears only in {other} runs; names are not matched, so a renamed clock looks like two clocks')
        reasons = _insufficient_reasons('baseline', b, clock in names['baseline']) + _insufficient_reasons('current', c, clock in names['current'])
        out = dict(clock=clock, baseline=b, current=c, seed_relation=seeds, insufficient_reasons=reasons, direction=None)
        if reasons:
            out['state'] = INSUFFICIENT
        elif b['min'] <= c['max'] and c['min'] <= b['max']:     # inclusive: ranges that touch at one value overlap
            out['state'] = OVERLAP
        else:
            out['state'] = NO_OVERLAP
            out['direction'] = 'current_higher' if c['min'] > b['max'] else 'current_lower'
        out['qualifiers'] = _qualifiers(b, c, seeds, general_here)
        out['qualified'] = bool(out['qualifiers'])
        out.update(_sample_cautions(b, c))
        clocks.append(out)
    return dict(available=True, clocks=clocks, compatibility=compat, sides=sides, reason=None)
