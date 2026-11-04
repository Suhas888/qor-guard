"""Report parsers. Only formats with real, tested fixtures are claimed (see SUPPORTED_FORMATS.md):
  yosys_stat_json   output of `stat -json` (Yosys 0.70+255 tested): top-level 'creator' + 'design' or 'modules'
  yosys_log_stat    text `stat` table printed into a Yosys log (Yosys 0.70+255 tested)
  nextpnr_report    nextpnr `--report` JSON (nextpnr-ice40 0.11.1 tested): 'fmax' + 'utilization'
Cell-type metrics are mapped for the iCE40 primitive library only (SB_LUT4, SB_DFF*, SB_CARRY). Any other library
yields metrics with status UNSUPPORTED rather than a guess. Every parse result names its file and the exact key used."""
import json
import math
import re


class ParseError(ValueError):
    pass


ICE40_FF = re.compile(r'^SB_DFF\w*$')


def _cell_metrics(cells, where):
    """cells: {celltype: count}. Returns dict metric -> {value, status, source}."""
    out = {}
    ice40 = any(k.startswith('SB_') for k in cells)
    if not ice40:
        for m in ('lut4', 'ff', 'carry'):
            out[m] = dict(value=None, status='UNSUPPORTED',
                          source=f'{where}: no iCE40 SB_* primitives found; cell library not supported')
        return out
    out['lut4'] = dict(value=cells.get('SB_LUT4', 0), status='OK', source=f'{where}: SB_LUT4')
    ffs = {k: v for k, v in cells.items() if ICE40_FF.match(k)}
    out['ff'] = dict(value=sum(ffs.values()), status='OK', source=f'{where}: sum of {sorted(ffs)}')
    out['carry'] = dict(value=cells.get('SB_CARRY', 0), status='OK', source=f'{where}: SB_CARRY')
    return out


def yosys_stat_json(text, path, top=None):
    try:
        j = json.loads(text)
    except ValueError as e:
        raise ParseError(f'{path}: not valid JSON ({e})')
    if not isinstance(j, dict) or not str(j.get('creator', '')).startswith('Yosys') or 'modules' not in j:
        raise ParseError(f'{path}: not a Yosys `stat -json` report (missing creator/modules)')
    if top:
        key = top if top in j['modules'] else '\\' + top
        if key not in j['modules']:
            raise ParseError(f'{path}: module {top!r} not in report ({sorted(j["modules"])})')
        block, where = j['modules'][key], f"{path} modules[{key}]"
    elif 'design' in j and 'num_cells_by_type' in j['design']:
        block, where = j['design'], f'{path} design (whole hierarchy)'
    elif len(j['modules']) == 1:
        k = next(iter(j['modules']))
        block, where = j['modules'][k], f'{path} modules[{k}]'
    else:
        raise ParseError(f'{path}: several modules and no design summary; pass --top')
    cells = block.get('num_cells_by_type')
    if not isinstance(cells, dict):
        raise ParseError(f'{where}: no num_cells_by_type')
    m = _cell_metrics({k: int(v) for k, v in cells.items()}, where)
    return dict(tool=j['creator'], format='yosys_stat_json', metrics=m)


_BLOCK = re.compile(r'^=== (.+?) ===\s*$', re.M)
_CELLLINE = re.compile(r'^\s+(\d+)\s{2,}(\S+)\s*$')


def yosys_log_stat(text, path):
    """Uses the LAST '=== design hierarchy ===' block if present, else the last '=== <module> ===' block.
    Only indented '<count>  <celltype>' lines are read (Yosys 0.70 lists primitives under 'submodules')."""
    heads = list(_BLOCK.finditer(text))
    if not heads:
        raise ParseError(f'{path}: no Yosys `stat` table found (not a synthesis log with stat output?)')
    hier = [h for h in heads if h.group(1) == 'design hierarchy']
    h = hier[-1] if hier else heads[-1]
    nxt = [x.start() for x in heads if x.start() > h.start()]
    body = text[h.end(): nxt[0] if nxt else len(text)]
    body = re.split(r'\n\d+\.\d+\. Executing', body)[0]
    cells = {}
    for line in body.splitlines():
        mm = _CELLLINE.match(line)
        if mm and not mm.group(2).startswith(('wire', 'port', 'public', 'memor', 'process', 'submodule', 'cells')):
            cells[mm.group(2)] = int(mm.group(1))
    if not cells:
        raise ParseError(f'{path}: stat table found but no cell lines')
    ver = re.search(r'Yosys (\d+\.\d+\S*)', text)
    return dict(tool=f"Yosys {ver.group(1) if ver else 'UNKNOWN version'}", format='yosys_log_stat',
                metrics=_cell_metrics(cells, f"{path} [=== {h.group(1)} ===]"))


def nextpnr_report(text, path):
    try:
        j = json.loads(text)
    except ValueError as e:
        raise ParseError(f'{path}: not valid JSON ({e})')
    if not isinstance(j, dict) or 'fmax' not in j or 'utilization' not in j:
        raise ParseError(f'{path}: not a nextpnr --report JSON (missing fmax/utilization)')
    if not isinstance(j['fmax'], dict) or not isinstance(j['utilization'], dict):
        raise ParseError(f'{path}: fmax and utilization must be objects')
    fmax = {}
    for clk, v in j['fmax'].items():
        try:
            fmax[clk] = dict(achieved=float(v['achieved']), constraint=float(v['constraint']))
        except (KeyError, TypeError, ValueError):
            raise ParseError(f'{path}: malformed fmax entry for {clk!r}')
        # json accepts NaN and Infinity, and float() accepts true/false
        if isinstance(v['achieved'], bool) or isinstance(v['constraint'], bool) or \
                not all(math.isfinite(x) and x >= 0 for x in fmax[clk].values()):
            raise ParseError(f'{path}: invalid fmax value for {clk!r}')
    util = j['utilization']
    lc = util.get('ICESTORM_LC', {}).get('used') if isinstance(util.get('ICESTORM_LC'), dict) else None

    def _resource(key):
        """(used, available) as ints, or (None, None) if absent/malformed. Values are taken as reported, never assumed."""
        r = util.get(key)
        if not isinstance(r, dict):
            return None, None
        u, a = r.get('used'), r.get('available')
        return (u if isinstance(u, int) else None), (a if isinstance(a, int) else None)

    _, lc_avail = _resource('ICESTORM_LC')
    ram, ram_avail = _resource('ICESTORM_RAM')
    return dict(format='nextpnr_report', fmax=fmax,
                lc=dict(value=lc, status='OK' if lc is not None else 'UNSUPPORTED',
                        source=f'{path}: utilization.ICESTORM_LC.used' if lc is not None else
                        f'{path}: no ICESTORM_LC (only iCE40 logic-cell utilisation is supported)'),
                lc_available=lc_avail, ram=ram, ram_available=ram_avail)
