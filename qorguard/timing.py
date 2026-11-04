"""Required-clock timing and frequency margin (0.3). compare() exits 1 when the current side's state is MISSES. Otherwise, without another known
failure, it exits 2 when the current side's state is NO_OBSERVATIONS or the requirements for a clock are inconsistent: the two
sides declare different values, or only one side declares one. A clock neither side declares is informational. A v1 record
cannot store a requirement, which is not proof that none existed, so a v2 declaration against a v1 record is a comparison
that is unavailable. compare() treats that like inconsistent requirements.
A required frequency comes only from a manifest's required_clocks_mhz; a tool constraint is shown beside it and is never
used in its place. Margins are frequency margins in MHz and percent, not period slack:
  absolute margin = achieved - required;  percentage margin = (achieved - required) / required * 100"""
from . import ranges

MEETS, MISSES = 'MEETS_AT_OBSERVED_MINIMUM', 'MISSES_AT_OBSERVED_MINIMUM'
REQUIREMENT_MISSING, NO_OBSERVATIONS, NOT_STORED = 'REQUIREMENT_MISSING', 'NO_OBSERVATIONS', 'NOT_STORED_V1'


def _required(r):
    f = r['provenance'].get('required_clocks_mhz') or dict(status='unavailable', value=None, source='record has no required_clocks_mhz')
    return f


def _margin(achieved, required):
    return dict(absolute_mhz=achieved - required, percent=(achieved - required) / required * 100)


def _side(r, clock):
    s = ranges._side(r, clock)
    out = dict(per_run_data=s['per_run_data'], attempted=s['attempted'], successful=s['successful'], failed=s['failed'],
               observations=s['observations'], min=s['min'], median=s['median'], max=s['max'], constraints=s['constraints'],
               missing_from_runs=s['missing_from_runs'], required_mhz=None, required_status='unavailable', required_source=None,
               margin=None, observations_meeting=None, meets_at_observed_minimum=None)
    if not s['per_run_data']:
        out.update(state=NOT_STORED, required_source='schema v1 record stores no required frequency')
        return out
    f = _required(r)
    required = (f['value'] or {}).get(clock)
    out.update(required_status='declared' if required is not None else 'unavailable', required_mhz=required,
               required_source=f['source'] if required is not None else f'no required frequency declared for this clock')
    if required is None:
        out['state'] = REQUIREMENT_MISSING
    elif not s['observations']:
        out['state'] = NO_OBSERVATIONS
    else:
        meets = s['min'] >= required
        out.update(state=MEETS if meets else MISSES, meets_at_observed_minimum=meets,
                   observations_meeting=sum(v >= required for v in s['values']),
                   margin={k: _margin(s[k], required) for k in ('min', 'median', 'max')})
    return out


def _inconsistent(b, c):
    return b['required_mhz'] is not None and c['required_mhz'] is not None and b['required_mhz'] != c['required_mhz']


def _declaration_missing_on(b, c):
    if not b['per_run_data'] or not c['per_run_data'] or (b['required_mhz'] is None) == (c['required_mhz'] is None):
        return None
    return 'baseline' if b['required_mhz'] is None else 'current'


def _comparison_unavailable_on(b, c):
    """The v1 side, when the other side declares a requirement for this clock."""
    if not b['per_run_data'] and c['required_mhz'] is not None:
        return 'baseline'
    if not c['per_run_data'] and b['required_mhz'] is not None:
        return 'current'
    return None


def _clock_notes(clock, b, c, names):
    notes = []
    for name, other, s in (('baseline', 'current', b), ('current', 'baseline', c)):
        if not s['per_run_data']:
            continue
        if s['required_mhz'] is not None and clock not in names[name]:
            notes.append(f'{name}: required frequency declared for this clock, but no run of that side reports it')
        elif clock not in names[name] and clock in names[other]:
            notes.append(f'{name}: clock not in any run; names are not matched, so a renamed clock looks like two clocks')
        if s['failed']:
            notes.append(f"{name}: {s['failed']} of {s['attempted']} declared runs failed and are not in these figures")
        if s['failed'] is None:
            notes.append(f'{name}: attempted and failed runs were not declared; failed runs that left no report are unknown')
        if s['missing_from_runs']:
            notes.append(f"{name}: clock missing from {s['missing_from_runs']} of {s['successful']} successful run(s)")
        if s['observations'] and s['observations'] < ranges.SMALL_SAMPLE:
            notes.append(f"{name}: small sample of {s['observations']} observation(s)")
        if s['required_mhz'] is not None and s['constraints'] and s['constraints'] != [s['required_mhz']]:
            notes.append(f"{name}: tool constraint {s['constraints']} MHz differs from the required {s['required_mhz']} MHz; "
                         'they are kept separate')
    if not _inconsistent(b, c) and b['per_run_data'] and c['per_run_data'] and (b['required_mhz'] is None) != (c['required_mhz'] is None):
        notes.append('only one side declares a required frequency; none is copied to the other side')
    return notes


def compare_timing(base, cur):
    v2 = {n: r.get('schema_version') == 2 for n, r in (('baseline', base), ('current', cur))}
    if not any(v2.values()):
        return dict(available=False, clocks=[], sides={}, reason='both records are schema v1, which stores no required frequency')
    names, sides, declared = {}, {}, set()
    for n, r in (('baseline', base), ('current', cur)):
        names[n] = {c for x in r['runs'] for c in x.get('fmax', {})} if v2[n] else set()
        declared |= set((_required(r)['value'] or {})) if v2[n] else set()
        counts = r['run_counts'] if v2[n] else dict(attempted=None, successful=None, failed=None)
        sides[n] = dict(per_run_data=v2[n], attempted=counts['attempted'], successful=counts['successful'], failed=counts['failed'])
    clocks = []
    for clock in sorted(names['baseline'] | names['current'] | declared):
        b, c = _side(base, clock), _side(cur, clock)
        clocks.append(dict(clock=clock, baseline=b, current=c, requirements_inconsistent=_inconsistent(b, c) or _declaration_missing_on(b, c) is not None,
                           values_differ=_inconsistent(b, c), declaration_missing_on=_declaration_missing_on(b, c),
                           requirement_comparison_unavailable_on=_comparison_unavailable_on(b, c),
                           notes=_clock_notes(clock, b, c, names)))
    return dict(available=True, clocks=clocks, sides=sides, reason=None)
