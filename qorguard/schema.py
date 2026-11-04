"""Run-record schema v2 and the capture manifest (0.3).
A manifest is what the user states about a run; QoR Guard never derives seeds from filenames or runs git. Every
provenance value carries a status: 'extracted' (read from a report), 'declared' (stated in a manifest), 'unavailable'.
v1 records (no schema_version) stay as written: seed_data() reports their missing data as None, never a guess."""
import hashlib
import json
import math
import os
import re

SCHEMA_VERSION = 2
STATUSES = ('extracted', 'declared', 'unavailable')
RUN_STATUSES = ('success', 'failed')
FIELDS = ('yosys_version', 'nextpnr_version', 'device', 'clock_constraints_mhz', 'constraint_files', 'commit', 'branch')
_SHA = re.compile(r'^[0-9a-f]{64}$')
_COMMIT = re.compile(r'^[0-9a-fA-F]{7,64}$')
_TEXT_KEYS = ('nextpnr_version', 'yosys_version', 'device', 'branch', 'commit')
_MANIFEST_KEYS = {'manifest_version', 'runs', 'constraint_files', 'required_clocks_mhz'} | set(_TEXT_KEYS)
_RUN_KEYS = {'report', 'seed', 'status', 'reason'}


def _no_dup_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError(f'duplicate key in JSON object: {sorted(k for k in set(keys) if keys.count(k) > 1)}')
    return dict(pairs)


def _text(v):
    return isinstance(v, str) and v.strip() != ''


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def load_manifest(path):
    """Returns a validated manifest with paths resolved against the manifest's folder. Raises ValueError."""
    with open(path, encoding='utf-8-sig') as f:         # PowerShell's Out-File writes a BOM
        try:
            m = json.load(f, object_pairs_hook=_no_dup_keys)
        except ValueError as e:
            raise ValueError(f'{path}: not a valid manifest ({e})')
    if not isinstance(m, dict):
        raise ValueError(f'{path}: manifest must be a JSON object')
    unknown = set(m) - _MANIFEST_KEYS
    if unknown:
        raise ValueError(f'{path}: unknown manifest field(s) {sorted(unknown)}')
    if m.get('manifest_version') != 1 or isinstance(m.get('manifest_version'), bool):
        raise ValueError(f'{path}: manifest_version must be 1')
    for k in _TEXT_KEYS:
        if k in m and not _text(m[k]):
            raise ValueError(f'{path}: {k} must be a non-empty string')
    if 'commit' in m and not _COMMIT.match(m['commit']):
        raise ValueError(f'{path}: commit must be 7 to 64 hex digits')
    here = os.path.dirname(os.path.abspath(path))
    resolve = lambda p: os.path.normpath(os.path.join(here, p))
    out = {k: m[k] for k in _TEXT_KEYS if k in m}
    files = m.get('constraint_files', [])
    if not isinstance(files, list) or not all(_text(c) for c in files):
        raise ValueError(f'{path}: constraint_files must be a list of file paths')
    out['constraint_files'] = []
    for c in files:
        p = resolve(c)
        if not os.path.isfile(p):
            raise ValueError(f'{path}: constraint file not found: {c}')
        with open(p, 'rb') as f:
            out['constraint_files'].append(dict(name=os.path.basename(p), sha256=hashlib.sha256(f.read()).hexdigest()))
    if 'required_clocks_mhz' in m:
        out['required_clocks_mhz'] = _required_clocks(m['required_clocks_mhz'], path)
    out['runs'] = None
    if 'runs' in m:
        out['runs'] = _manifest_runs(m['runs'], path, resolve)
    return out


def _required_clocks(req, where):
    """{clock name: MHz}. Names are kept exactly as written; values must be positive and finite."""
    if not isinstance(req, dict) or not req:
        raise ValueError(f'{where}: required_clocks_mhz must be a non-empty object of clock name to MHz')
    for c, v in req.items():
        if not _text(c) or isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError(f'{where}: invalid required frequency for clock {c!r}: {v!r}')
    return req


def _manifest_runs(runs, path, resolve):
    if not isinstance(runs, list) or not runs:
        raise ValueError(f'{path}: runs must be a non-empty list')
    out, seeds, reports = [], set(), set()
    for i, r in enumerate(runs):
        where = f'{path}: runs[{i}]'
        if not isinstance(r, dict):
            raise ValueError(f'{where} must be an object')
        unknown = set(r) - _RUN_KEYS
        if unknown:
            raise ValueError(f'{where}: unknown field(s) {sorted(unknown)}')
        status = r.get('status')
        if status not in RUN_STATUSES:
            raise ValueError(f'{where}: status must be one of {RUN_STATUSES}')
        seed = r.get('seed')
        if 'seed' in r and not _int(seed):
            raise ValueError(f'{where}: seed must be an integer (omit it if unknown)')
        if seed is not None:
            if seed in seeds:
                raise ValueError(f'{where}: duplicate seed {seed}')
            seeds.add(seed)
        if 'reason' in r and (status != 'failed' or not _text(r['reason'])):
            raise ValueError(f'{where}: reason must be a non-empty string on a failed run')
        report = None
        if 'report' in r:
            if not _text(r['report']):
                raise ValueError(f'{where}: report must be a file path')
            report = resolve(r['report'])
            if not os.path.isfile(report):
                raise ValueError(f"{where}: report not found: {r['report']}")
            key = os.path.normcase(report)
            if key in reports:
                raise ValueError(f"{where}: report listed twice: {r['report']}")
            reports.add(key)
        elif status == 'success':
            raise ValueError(f'{where}: a successful run needs a report')
        out.append(dict(report=report, seed=seed, status=status, reason=r.get('reason')))
    return out


def field(status, value, source):
    return dict(status=status, value=value, source=source)


def _check_field(f, where):
    if not isinstance(f, dict) or f.get('status') not in STATUSES or 'value' not in f or not _text(f.get('source')):
        raise ValueError(f'{where}: needs status (one of {STATUSES}), value and source')
    if (f['value'] is None) != (f['status'] == 'unavailable'):
        raise ValueError(f"{where}: status {f['status']!r} does not fit value {f['value']!r}")


def _check_fmax(fmax, where):
    if not isinstance(fmax, dict):
        raise ValueError(f'{where}: fmax must be an object')
    for c, v in fmax.items():
        if not isinstance(v, dict):
            raise ValueError(f'{where}: malformed fmax[{c}]')
        for k in ('achieved', 'constraint'):
            x = v.get(k)
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0:
                raise ValueError(f'{where}: invalid fmax[{c}].{k}: {x!r}')


def validate_v2(r, where='run.json'):
    """Raises ValueError unless r is an internally consistent schema v2 record."""
    runs, counts, prov = r.get('runs'), r.get('run_counts'), r.get('provenance')
    if not isinstance(runs, list) or not isinstance(counts, dict) or not isinstance(prov, dict):
        raise ValueError(f'{where}: schema v2 needs runs, run_counts and provenance')
    seeds = set()
    for i, x in enumerate(runs):
        w = f'{where}: runs[{i}]'
        if not isinstance(x, dict) or x.get('status') not in RUN_STATUSES:
            raise ValueError(f'{w}: status must be one of {RUN_STATUSES}')
        _check_field(x.get('seed'), f'{w}.seed')
        s = x['seed']['value']
        if s is not None:
            if not _int(s):
                raise ValueError(f'{w}: seed must be an integer')
            if s in seeds:
                raise ValueError(f'{w}: duplicate seed {s}')
            seeds.add(s)
        rep = x.get('report')
        if rep is None:
            if x['status'] == 'success':
                raise ValueError(f'{w}: a successful run needs a report')
        elif not isinstance(rep, dict) or not _SHA.match(str(rep.get('sha256'))) or not _text(rep.get('stored')):
            raise ValueError(f'{w}: report needs stored and a sha256')
        if x['status'] == 'success' and 'fmax' not in x:
            raise ValueError(f'{w}: a successful run needs fmax')
        if 'fmax' in x:
            _check_fmax(x['fmax'], w)
    ok = sum(x['status'] == 'success' for x in runs)
    basis = counts.get('basis')
    if basis == 'declared':
        want = dict(attempted=len(runs), successful=ok, failed=len(runs) - ok)
    elif basis == 'reports_supplied':
        if ok != len(runs):
            raise ValueError(f'{where}: basis reports_supplied cannot hold failed runs')
        want = dict(attempted=None, successful=ok, failed=None)    # runs that left no report are unknowable here
    else:
        raise ValueError(f'{where}: run_counts.basis must be declared or reports_supplied')
    for k, v in want.items():
        if counts.get(k, 'missing') != v:
            raise ValueError(f'{where}: run_counts.{k} is {counts.get(k)!r}, expected {v!r}')
    if r.get('n_seeds') != ok:
        raise ValueError(f"{where}: n_seeds {r.get('n_seeds')!r} differs from {ok} successful run(s)")
    for k in FIELDS:
        _check_field(prov.get(k), f'{where}: provenance.{k}')
    if 'required_clocks_mhz' in prov:             # optional: earlier v2 records do not have it
        req = prov['required_clocks_mhz']
        _check_field(req, f'{where}: provenance.required_clocks_mhz')
        if req['status'] == 'extracted':
            raise ValueError(f'{where}: a required frequency can only be declared')
        if req['value'] is not None:
            _required_clocks(req['value'], f'{where}: provenance')


def seed_data(r):
    """Per-run data of any loaded record. For v1 the fields v1 never stored are None; only n_seeds is passed on."""
    if r.get('schema_version') == SCHEMA_VERSION:
        return dict(schema_version=SCHEMA_VERSION, runs=r['runs'], run_counts=r['run_counts'], provenance=r['provenance'],
                    reports_supplied=r['n_seeds'])
    return dict(schema_version=1, runs=None, run_counts=None, provenance=None, reports_supplied=r.get('n_seeds'))
