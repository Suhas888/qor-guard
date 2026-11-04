"""Reproducible demonstration on synthetic iCE40-format reports. Uses only files under tests/fixtures/synthetic.
Usage (from the project root): python -I -B demo/run_demo.py
Writes demo/output/<timestamp>/ (never overwrites) and prints DEMO_RESULT.json. Deterministic fields: input hashes,
metric values, deltas, statuses, exit codes. Non-deterministic: 'created' timestamps, absolute paths."""
import glob
import hashlib
import io
import json
import os
import sys
import time
from contextlib import redirect_stdout

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from qorguard import cli  # noqa: E402

F = os.path.join(ROOT, 'tests', 'fixtures', 'synthetic')
CFG = os.path.join(ROOT, 'config', 'thresholds.example.json')
SCENARIOS = [
    ('A_regression', 'design_b', 'design_a', 1, 'baseline = design_b, current = design_a (larger, slower)'),
    ('B_improvement', 'design_a', 'design_b', 0, 'baseline = design_a, current = design_b'),
    ('C_identical', 'design_c', 'design_c', 0, 'same reports twice (determinism of the checker)'),
    ('D_missing_required', None, 'design_c', 2, 'baseline has Yosys stat only (no nextpnr report) -> required lc/fmax missing'),
]


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def cap(out, name, with_pnr=True):
    args = ['capture', '--out', out, '--label', name, '--yosys-stat', os.path.join(F, name, 'ice40_stat.json')]
    if with_pnr:
        args += ['--nextpnr'] + sorted(glob.glob(os.path.join(F, name, 'pnr_report_s*.json')))
    with redirect_stdout(io.StringIO()):
        assert cli.main(args) == 0
    return args


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')     # Windows console (cp1252)
    out = os.path.join(ROOT, 'demo', 'output', time.strftime('%Y%m%d_%H%M%S'))
    os.makedirs(out)
    result = dict(config=os.path.relpath(CFG, ROOT), config_sha256=sha(CFG), scenarios=[])
    for sid, base, cur, expect, desc in SCENARIOS:
        d = os.path.join(out, sid)
        bargs = cap(os.path.join(d, 'baseline'), base or cur, with_pnr=base is not None)
        cargs = cap(os.path.join(d, 'current'), cur)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(['compare', '--baseline', os.path.join(d, 'baseline'), '--current', os.path.join(d, 'current'),
                             '--config', CFG, '--report', os.path.join(d, 'report.md')])
        runs = {k: json.load(open(os.path.join(d, k, 'run.json'))) for k in ('baseline', 'current')}
        rows = []
        md = open(os.path.join(d, 'report.md'), encoding='utf-8').read()
        for line in md.splitlines():
            if line.startswith('| `'):
                rows.append([c.strip() for c in line.strip('|').split('|')])
        result['scenarios'].append(dict(
            id=sid, description=desc, expected_exit=expect, exit_code=code, as_expected=code == expect,
            inputs={k: {os.path.relpath(i['original_path'], ROOT).replace('\\', '/'): i['sha256'] for i in runs[k]['inputs']} for k in runs},
            rows=rows, report=os.path.relpath(os.path.join(d, 'report.md'), ROOT).replace('\\', '/')))
    json.dump(result, open(os.path.join(out, 'DEMO_RESULT.json'), 'w'), indent=1)
    for s in result['scenarios']:
        print(f"{s['id']:22s} expected exit {s['expected_exit']} got {s['exit_code']} -> {'OK' if s['as_expected'] else 'MISMATCH'}")
        for r in s['rows']:
            print('    ', ' | '.join(r))
    print('output:', os.path.relpath(out, ROOT))
    return 0 if all(s['as_expected'] for s in result['scenarios']) else 1


if __name__ == '__main__':
    sys.exit(main())
