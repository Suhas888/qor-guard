"""Generates tests/fixtures/synthetic from the invented values below. No value or name comes from a real design or tool run.
The file layouts follow what the parsers read: Yosys `stat -json`, the Yosys log stat table, and nextpnr `--report` JSON.
Run (from the project root): python -I -B tests/fixture_generator.py"""
import json
import os

CLOCK = 'clk$SB_IO_IN_$glb_clk'
TOP = 'synthetic_top'
VERSION = '0.70+255 (synthetic test fixture, not tool output)'
DESIGNS = {
    'design_a': dict(cells={'$scopeinfo': 8, 'SB_CARRY': 180, 'SB_DFF': 300, 'SB_DFFESR': 240, 'SB_DFFSR': 4, 'SB_LUT4': 2600}, lc=2900,
                     fmax=[70.1015625, 70.90625, 72.59375, 71.40625, 73.1875]),
    'design_b': dict(cells={'$scopeinfo': 8, 'SB_CARRY': 210, 'SB_DFF': 300, 'SB_DFFESR': 240, 'SB_DFFSR': 4, 'SB_LUT4': 2340}, lc=2640,
                     fmax=[74.25, 75.0, 76.5, 72.5, 75.75]),
    'design_c': dict(cells={'$scopeinfo': 2, 'SB_CARRY': 18, 'SB_DFF': 40, 'SB_DFFESR': 20, 'SB_LUT4': 340}, lc=390,
                     fmax=[60.5, 64.25, 61.75, 59.5, 62.25]),
    'design_d': dict(cells={'$scopeinfo': 2, 'SB_CARRY': 20, 'SB_DFF': 40, 'SB_DFFESR': 20, 'SB_LUT4': 310}, lc=360,
                     fmax=[61.0, 65.5, 63.5, 62.75, 63.75]),
}
GENERIC_CELLS = {'$_AND_': 40, '$_MUX_': 2, '$_NAND_': 90, '$_NOT_': 3, '$_OR_': 5, '$_XOR_': 60}


def stat_json(cells):
    block = dict(num_cells=sum(cells.values()), num_submodules=0, num_cells_by_type=cells)
    return json.dumps(dict(creator=f'Yosys {VERSION}', invocation='stat -json ', modules={'\\' + TOP: block}, design=block), indent=3) + '\n'


def _rows(cells):
    return ''.join(f'{v:>9}   {k}\n' for k, v in sorted(cells.items()))


def stat_log(cells):
    """Holds what the log parser meets in a real table: an earlier module block, a total that is not the cell count, and a following pass."""
    scope = cells.get('$scopeinfo', 0)
    prims = {k: v for k, v in cells.items() if k != '$scopeinfo'}
    return (f' Yosys {VERSION}\n\n1. Executing script.\n\n1.1. Printing statistics.\n\n=== {TOP} ===\n\n'
            f'        +----------Local Count, excluding submodules.\n        | \n       10 wires\n       10 wire bits\n'
            f'{sum(cells.values()):>9} cells\n{_rows(cells)}\n'
            f'=== design hierarchy ===\n\n        +----------Count including submodules.\n        | \n{scope:>9} {TOP}\n\n'
            f'        +----------Count including submodules.\n        | \n       10 wires\n       10 wire bits\n        - memories\n'
            f'{scope:>9} cells\n{scope:>9}   $scopeinfo\n{sum(prims.values()):>9} submodules\n{_rows(prims)}\n'
            f'1.2. Executing CHECK pass (checking for obvious problems).\nChecking module {TOP}...\n\nEnd of script.\n Yosys {VERSION}\n')


def generic_log(cells):
    return (f' Yosys {VERSION}\n\n1. Executing script.\n\n1.1. Printing statistics.\n\n=== generic_top ===\n\n'
            f'        +----------Local Count, excluding submodules.\n        | \n       10 wires\n{sum(cells.values()):>9} cells\n{_rows(cells)}\n'
            f'1.2. Executing CHECK pass (checking for obvious problems).\nChecking module generic_top...\n')


def report(achieved, lc, clock=CLOCK, utilization=None):
    util = utilization or dict(ICESTORM_LC=dict(available=7680, used=lc), ICESTORM_RAM=dict(available=32, used=0))
    return json.dumps(dict(fmax={clock: dict(achieved=achieved, constraint=12)}, utilization=util), indent=1, sort_keys=True) + '\n'


def files():
    out = {}
    for name, d in DESIGNS.items():
        out[f'{name}/ice40_stat.json'] = stat_json(d['cells'])
        out[f'{name}/synth.log'] = stat_log(d['cells'])
        for i, f in enumerate(d['fmax'], 1):
            out[f'{name}/pnr_report_s{i}.json'] = report(f, d['lc'])
    out['generic/generic.log'] = generic_log(GENERIC_CELLS)
    out['rejected/sim.log'] = 'DONE cycles=1000 compared=1000 errors=0\nsim_tb.v:10: $finish called at 2000 (1ps)\n'
    out['rejected/sim.json'] = json.dumps(dict(step='sim', rc=0, timeout=False, seconds=1.5)) + '\n'
    return out


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'synthetic')
    for rel, text in files().items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)


if __name__ == '__main__':
    main()
