"""Capture a run: parse reports, copy every raw input into the run directory with sha256, write run.json.
Multiple nextpnr reports = multiple placement seeds of the SAME netlist; per clock, the run stores worst (min) and
median achieved Fmax across seeds. A clock missing from some seeds is recorded as such (never filled in)."""
import hashlib
import json
import os
import shutil
import statistics
import time

from . import parsers

VERSION = 'qorguard 0.2.0'


def _read(p):
    with open(p, encoding='utf-8', errors='replace') as f:
        return f.read()


def capture(out_dir, yosys_stat=None, yosys_log=None, nextpnr=(), label='', top=None):
    if os.path.exists(os.path.join(out_dir, 'run.json')):
        raise FileExistsError(f'{out_dir} already holds a run; choose a new directory')
    if not (yosys_stat or yosys_log or nextpnr):
        raise ValueError('give at least one report')
    os.makedirs(os.path.join(out_dir, 'raw'), exist_ok=True)
    inputs, metrics, notes = [], {}, []

    def keep(p, kind):
        dst = os.path.join(out_dir, 'raw', f'{len(inputs):02d}_{os.path.basename(p)}')
        shutil.copyfile(p, dst)
        inputs.append(dict(kind=kind, original_path=os.path.abspath(p), stored=os.path.relpath(dst, out_dir),
                           sha256=hashlib.sha256(open(p, 'rb').read()).hexdigest(), bytes=os.path.getsize(p)))

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
    for p in nextpnr:
        seeds.append(parsers.nextpnr_report(_read(p), p))
        keep(p, 'nextpnr_report')
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
            if len(vals) < len(seeds):
                notes.append(f'clock {c} missing from {len(seeds) - len(vals)} report(s)')
            metrics[f'fmax_min[{c}]'] = dict(value=round(min(vals), 3), status='OK', source=src + ' (worst seed)', unit='MHz')
            metrics[f'fmax_median[{c}]'] = dict(value=round(statistics.median(vals), 3), status='OK', source=src + ' (median)', unit='MHz')
            metrics[f'fmax_constraint[{c}]'] = dict(value=seeds[0]['fmax'][c]['constraint'] if c in seeds[0]['fmax'] else None,
                                                    status='INFO', source=src.replace('achieved', 'constraint'), unit='MHz')
    else:
        notes.append('no nextpnr report given: no routed metrics (Fmax, logic cells)')
    run = dict(qorguard=VERSION, label=label, created=time.strftime('%Y-%m-%dT%H:%M:%S'), tools=tool, inputs=inputs,
               metrics=metrics, notes=notes, n_seeds=len(seeds))
    json.dump(run, open(os.path.join(out_dir, 'run.json'), 'w', encoding='utf-8'), indent=1, sort_keys=True)
    return run


def load(path):
    p = os.path.join(path, 'run.json') if os.path.isdir(path) else path
    r = json.load(open(p, encoding='utf-8'))
    if 'metrics' not in r or 'qorguard' not in r:
        raise ValueError(f'{p}: not a qorguard run.json')
    return r
