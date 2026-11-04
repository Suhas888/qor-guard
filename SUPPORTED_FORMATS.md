# Supported Formats (QoR Guard 0.3.0)

A report format is listed as **supported** only if the maintainer has tested it with real report files. **Those real reports are private and not distributed.** The public suite uses synthetic files in the same layouts, so it cannot reproduce the real-report checks. UP5K support has limited internal evaluation and is not yet covered by the reproducible public test suite. The UP5K tests skip publicly.

## Supported (tested with real reports)

| Format | Tool / version tested | Metrics extracted | Real reports |
|---|---|---|---|
| `stat -json` output (`creator`, `design` / `modules`) | Yosys 0.70+255 (git 72b0054f0) | `lut4` = SB_LUT4; `ff` = sum of SB_DFF*; `carry` = SB_CARRY | Private HX8K reports |
| `stat` table in a Yosys log (last `=== design hierarchy ===` block, else the last `=== <module> ===`) | Yosys 0.70+255 | Same as above | Private HX8K reports and a generic-synthesis log |
| nextpnr `--report` JSON (`fmax`, `utilization`) | nextpnr-ice40 0.11.1-83 (HX8K) | `lc`, `ram`, `lc_capacity`, `ram_capacity`; per clock `fmax_min`, `fmax_median`, `fmax_constraint` (MHz) | Private HX8K reports |


Capacity values are read exactly as reported, and no device table exists. If a field is absent, the metric is UNSUPPORTED and utilisation and headroom are unavailable, unless `--lc-capacity` is given.

## Manifest (`capture --manifest`)

A JSON file written by you, not a tool output. Fields:

| Field | Meaning |
|---|---|
| `manifest_version` | Required; must be 1 |
| `commit`, `branch`, `device`, `yosys_version`, `nextpnr_version` | Text, recorded as declared |
| `constraint_files` | Constraint files to record |
| `required_clocks_mhz` | Required frequency per exact clock name |
| `runs` | List of runs, each with `report`, `seed`, `status` and `reason` |

Unknown fields are rejected. Manifest behaviour is tested with synthetic manifests only.

## Recognised but UNSUPPORTED

Metrics are reported as UNSUPPORTED, never guessed:

- **Yosys stat with a non-iCE40 cell library.** Tested with a generic-synthesis log and a stat JSON.
- **nextpnr reports without `ICESTORM_LC`.** `lc` is UNSUPPORTED. Fmax would still be read, but **no non-iCE40 nextpnr report has been tested**.

## Rejected (exit 3)

Each of these is tested:

- simulation output (a simulation log and its runner JSON);
- invalid or truncated JSON;
- JSON without the expected keys;
- non-numeric, NaN, infinite, negative or true/false Fmax values;
- non-object `fmax` or `utilization`;
- multi-module stat JSON without a design summary and without `--top`;
- logs with no stat table.

## Not supported (untested; no claim)

- **Vivado, Quartus, Diamond and Gowin EDA** reports.
- **nextpnr-ecp5, -gowin, -himbaechel, -nexus** reports. They may parse, but they are untested and `lc` will be UNSUPPORTED.
- **Xilinx/openXC7** flows.
- **Yosys versions other than those listed above.** The text log layout is known to change between versions.
- **Critical-path details**, which are present in nextpnr reports but not used.
- **DSP and SPRAM counts**, and the Yosys `SB_RAM40_4K` count. BRAM use is read from nextpnr's `ICESTORM_RAM` only.
