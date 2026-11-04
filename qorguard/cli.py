"""QoR Guard 0.3.0 CLI (local only, standard library).
  capture  --out RUN_DIR [--yosys-stat F.json] [--yosys-log synth.log] [--nextpnr R.json ...] [--label L] [--top T]
           [--manifest M.json]   seeds, failed runs and provenance you state; see CHANGELOG_0.3.md   (0.3)
  baseline --store DIR set RUN_DIR          copy a captured run as the baseline (refuses to overwrite unless --replace)
  compare  --baseline RUN_DIR|STORE --current RUN_DIR [--config thresholds.json] [--report out.md]
           [--comparison-type revision|configuration|unknown (default unknown)] [--lc-capacity N]   (0.2)
Exit codes (compare): 0 pass, 1 threshold exceeded or current side missed a declared required clock, 2 no known failure, but
required evidence is missing or requirements are inconsistent or unavailable; 3 = bad/unreadable input or invalid
value (e.g. --lc-capacity 0). Command-line syntax errors are reported by argparse and also exit 2 (known collision)."""
import argparse
import os
import shutil
import sys

from . import compare as C
from . import parsers, report, run


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8', errors='replace')   # Windows consoles default to cp1252
    ap = argparse.ArgumentParser(prog='qorguard')
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('capture')
    c.add_argument('--out', required=True)
    c.add_argument('--yosys-stat')
    c.add_argument('--yosys-log')
    c.add_argument('--nextpnr', nargs='*', default=[])
    c.add_argument('--label', default='')
    c.add_argument('--top')
    c.add_argument('--manifest', help='JSON stating seeds, failed runs, tool versions, device, commit and branch')
    b = sub.add_parser('baseline')
    b.add_argument('--store', required=True)
    b.add_argument('action', choices=['set'])
    b.add_argument('run_dir')
    b.add_argument('--replace', action='store_true')
    k = sub.add_parser('compare')
    k.add_argument('--baseline', required=True)
    k.add_argument('--current', required=True)
    k.add_argument('--config')
    k.add_argument('--report')
    k.add_argument('--comparison-type', choices=['revision', 'configuration', 'unknown'], default='unknown',
                   help='relationship between the runs, stated by you (never inferred); default: unknown')
    k.add_argument('--lc-capacity', type=int,
                   help='device logic-cell capacity; overrides the value reported by nextpnr (must be > 0)')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'capture':
            r = run.capture(a.out, a.yosys_stat, a.yosys_log, a.nextpnr, a.label, a.top, a.manifest)
            print(f"captured {len(r['metrics'])} metrics from {len(r['inputs'])} input(s) -> {a.out}/run.json")
            for n in r['notes']:
                print('note:', n)
            for k2, v in sorted(r['metrics'].items()):
                if v['status'] not in ('OK', 'INFO'):
                    print(f"{v['status']}: {k2}: {v['source']}")
            return 0
        if a.cmd == 'baseline':
            run.load(a.run_dir)
            dst = os.path.join(a.store, 'baseline')
            if os.path.exists(dst):
                if not a.replace:
                    print(f'{dst} exists; use --replace to change the baseline', file=sys.stderr)
                    return 3
                old = os.path.join(a.store, f'baseline_replaced_{len(os.listdir(a.store))}')
                os.rename(dst, old)                       # keep the old baseline (non-destructive)
                print(f'previous baseline kept at {old}')
            shutil.copytree(a.run_dir, dst)
            print(f'baseline set: {dst}')
            return 0
        if a.cmd == 'compare':
            bpath = os.path.join(a.baseline, 'baseline') if os.path.isdir(os.path.join(a.baseline, 'baseline')) else a.baseline
            base, cur = run.load(bpath), run.load(a.current)
            res = C.compare(base, cur, C.load_rules(a.config), a.comparison_type, a.lc_capacity)
            md = report.markdown(base, cur, res)
            if a.report:
                open(a.report, 'w', encoding='utf-8').write(md)
            print(md if not a.report else f"{res['verdict']} (exit {res['exit_code']}); report: {a.report}")
            return res['exit_code']
    except (parsers.ParseError, ValueError, OSError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 3
    return 3
