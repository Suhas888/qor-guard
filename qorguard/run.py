"""Capture a run: parse reports, copy every raw input into the run directory with sha256, write run.json.
Multiple nextpnr reports = multiple placement seeds of the SAME netlist; per clock, the run stores worst (min) and
median achieved Fmax across seeds. A clock missing from some seeds is recorded as such (never filled in).
0.3 (schema v2): adds per-run records, run counts and provenance beside the v1 fields; a manifest states what the reports
cannot (see schema.py). Thresholds still read the rounded v1 metrics, computed from successful runs only."""
import hashlib
import json
import os
import re
import shutil
import statistics
import time

from . import parsers, schema

VERSION = 'qorguard 0.3.0'


def _read(p):
    with open(p, encoding='utf-8', errors='replace') as f:
        return f.read()


def _provenance(man, tools, successes, notes):
    def stated(key, what):
        if key in man:
            return schema.field('declared', man[key], f'manifest {key}')
        return schema.field('unavailable', None, f'{what} not stated in a manifest')

    found = [m.group(1) for m in (re.search(r'Yosys (\d+\.\d+\S*)', t) for t in tools) if m]
    if found:
        yosys = schema.field('extracted', found[0], 'Yosys stat JSON creator or log')
        if len(set(found)) > 1:
            notes.append(f'Yosys version differs between inputs: {sorted(set(found))}; first kept')
        if 'yosys_version' in man and man['yosys_version'] != found[0]:
            notes.append(f"manifest declares Yosys {man['yosys_version']}, reports say {found[0]}; extracted value kept")
            yosys['declared_value'] = man['yosys_version']
    else:
        yosys = stated('yosys_version', 'Yosys version')
    constraints = {}
    for c in sorted({c for s in successes for c in s['fmax']}):
        vals = {s['fmax'][c]['constraint'] for s in successes if c in s['fmax']}
        if len(vals) > 1:
            notes.append(f'clock {c}: constraint differs between reports: {sorted(vals)}; see per-run records')
        constraints[c] = vals.pop() if len(vals) == 1 else None
    files = man.get('constraint_files')
    return dict(yosys_version=yosys, nextpnr_version=stated('nextpnr_version', 'nextpnr version'),
                device=stated('device', 'device'),
                clock_constraints_mhz=schema.field('extracted', constraints, 'nextpnr fmax[*].constraint; may be the '
                                                   'tool default, not a design requirement') if constraints else
                schema.field('unavailable', None, 'no successful nextpnr report'),
                constraint_files=schema.field('declared', files, 'manifest constraint_files; sha256 computed here') if files
                else schema.field('unavailable', None, 'constraint files not stated in a manifest'),
                commit=stated('commit', 'commit'), branch=stated('branch', 'branch'),
                required_clocks_mhz=stated('required_clocks_mhz', 'required clock frequencies'))


def capture(out_dir, yosys_stat=None, yosys_log=None, nextpnr=(), label='', top=None, manifest=None):
    if os.path.exists(os.path.join(out_dir, 'run.json')):
        raise FileExistsError(f'{out_dir} already holds a run; choose a new directory')
    man = schema.load_manifest(manifest) if manifest else {}
    planned = man.get('runs')
    if planned and nextpnr:
        raise ValueError('give nextpnr reports through --nextpnr or the manifest runs list, not both')
    if not (yosys_stat or yosys_log or nextpnr or planned):
        raise ValueError('give at least one report')
    planned = planned or [dict(report=p, seed=None, status='success', reason=None) for p in nextpnr]
    os.makedirs(os.path.join(out_dir, 'raw'), exist_ok=True)
    inputs, metrics, notes = [], {}, []

    def keep(p, kind):
        dst = os.path.join(out_dir, 'raw', f'{len(inputs):02d}_{os.path.basename(p)}')
        shutil.copyfile(p, dst)
        inputs.append(dict(kind=kind, original_path=os.path.abspath(p), stored=os.path.relpath(dst, out_dir),
                           sha256=hashlib.sha256(open(p, 'rb').read()).hexdigest(), bytes=os.path.getsize(p)))
        return inputs[-1]

    tool = []
    if yosys_stat:
        r = parsers.yosys_stat_json(_read(yosys_stat), yosys_stat, top)
        keep(yosys_stat, r['format'])
        metrics.update(r['metrics'])
        tool.append(r['tool'])
    if yosys_log:
        r = parsers.yosys_log_stat(_read(yosys_log), yosys_log)
        keep(yosys_log, r['format'])
        for k, v in r['metrics'].items():
            if k in metrics and metrics[k]['value'] != v['value']:
                notes.append(f"{k}: stat JSON says {metrics[k]['value']}, log says {v['value']} (JSON kept)")
            metrics.setdefault(k, v)
        tool.append(r['tool'])
    seeds = []
    runs = []
    for i, e in enumerate(planned):
        rec = dict(index=i, status=e['status'], report=None,
                   seed=schema.field('declared', e['seed'], 'manifest runs') if e['seed'] is not None else
                   schema.field('unavailable', None, 'seed is not in the nextpnr report and was not declared'))
        if e['reason']:
            rec['reason'] = e['reason']
        parsed = None
        if e['report']:
            try:
                parsed = parsers.nextpnr_report(_read(e['report']), e['report'])
            except parsers.ParseError as err:
                if e['status'] == 'success':
                    raise
                rec['report_parse_error'] = str(err)
            kept = keep(e['report'], 'nextpnr_report' if e['status'] == 'success' else 'nextpnr_report_failed_run')
            rec['report'] = {k: kept[k] for k in ('stored', 'sha256', 'bytes')}
        if parsed:
            rec['fmax'], rec['lc'] = parsed['fmax'], parsed['lc']['value']
        if e['status'] == 'success':
            seeds.append(parsed)
        runs.append(rec)
    n_failed = len(runs) - len(seeds)
    if n_failed:
        notes.append(f'{n_failed} of {len(runs)} declared nextpnr run(s) failed; they are in runs[] and excluded from '
                     f'the Fmax aggregates, which use {len(seeds)} successful run(s)')
    hashes = [r['report']['sha256'] for r in runs if r['report']]
    if len(set(hashes)) < len(hashes):
        notes.append('two or more nextpnr reports are byte-identical; check that they are separate runs')
    if seeds:
        lcs = {s['lc']['value'] for s in seeds}
        lc = seeds[0]['lc']
        if len(lcs) > 1:
            notes.append(f'logic-cell count differs between seed reports: {sorted(lcs, key=str)}; max kept')
            lc = dict(lc, value=max(v for v in lcs if v is not None))
        metrics['lc'] = dict(lc, source=lc['source'] + f' (n={len(seeds)} reports)')
        # 0.2: device capacity and block-RAM use exactly as reported by nextpnr (utilization.*.available / .used)
        for key, field, unit_note in (('lc_capacity', 'lc_available', 'ICESTORM_LC.available'),
                                      ('ram', 'ram', 'ICESTORM_RAM.used'),
                                      ('ram_capacity', 'ram_available', 'ICESTORM_RAM.available')):
            vals = {s[field] for s in seeds}
            if vals == {None}:
                metrics[key] = dict(value=None, status='UNSUPPORTED',
                                    source=f'nextpnr report(s) have no utilization.{unit_note}')
            elif len(vals) > 1:
                notes.append(f'{unit_note} differs between reports: {sorted(vals, key=str)}; not used')
                metrics[key] = dict(value=None, status='CONFLICT', source=f'nextpnr utilization.{unit_note} differs between reports')
            else:
                metrics[key] = dict(value=vals.pop(), status='OK' if key == 'ram' else 'INFO',
                                    source=f'nextpnr utilization.{unit_note} (n={len(seeds)} reports)')
        clocks = sorted({c for s in seeds for c in s['fmax']})
        for c in clocks:
            vals = [s['fmax'][c]['achieved'] for s in seeds if c in s['fmax']]
            src = f'nextpnr fmax[{c}].achieved over {len(vals)}/{len(seeds)} reports'
            if n_failed:
                src += f'; {n_failed} failed run(s) excluded'
            if len(vals) < len(seeds):
                notes.append(f'clock {c} missing from {len(seeds) - len(vals)} report(s)')
            metrics[f'fmax_min[{c}]'] = dict(value=round(min(vals), 3), status='OK', source=src + ' (worst seed)', unit='MHz')
            metrics[f'fmax_median[{c}]'] = dict(value=round(statistics.median(vals), 3), status='OK', source=src + ' (median)', unit='MHz')
            metrics[f'fmax_constraint[{c}]'] = dict(value=seeds[0]['fmax'][c]['constraint'] if c in seeds[0]['fmax'] else None,
                                                    status='INFO', source=src.replace('achieved', 'constraint'), unit='MHz')
    else:
        notes.append('no nextpnr report given: no routed metrics (Fmax, logic cells)')
    declared_runs = bool(man.get('runs'))
    counts = dict(attempted=len(runs) if declared_runs else None, successful=len(seeds),
                  failed=n_failed if declared_runs else None, basis='declared' if declared_runs else 'reports_supplied')
    provenance = _provenance(man, tool, seeds, notes)
    if manifest:
        keep(manifest, 'manifest')
    run = dict(schema_version=schema.SCHEMA_VERSION, qorguard=VERSION, label=label, created=time.strftime('%Y-%m-%dT%H:%M:%S'),
               tools=tool, inputs=inputs, metrics=metrics, notes=notes, n_seeds=len(seeds), runs=runs, run_counts=counts,
               provenance=provenance)
    schema.validate_v2(run, os.path.join(out_dir, 'run.json'))
    json.dump(run, open(os.path.join(out_dir, 'run.json'), 'w', encoding='utf-8'), indent=1, sort_keys=True, allow_nan=False)
    return run


def load(path):
    p = os.path.join(path, 'run.json') if os.path.isdir(path) else path
    r = json.load(open(p, encoding='utf-8'))
    if not isinstance(r, dict) or 'metrics' not in r or 'qorguard' not in r:
        raise ValueError(f'{p}: not a qorguard run.json')
    if 'schema_version' in r:                     # v1 records have no such field and are returned exactly as written
        if r['schema_version'] != schema.SCHEMA_VERSION or isinstance(r['schema_version'], (bool, float)):
            raise ValueError(f"{p}: unsupported schema_version {r['schema_version']!r}")
        schema.validate_v2(r, p)
    return r
