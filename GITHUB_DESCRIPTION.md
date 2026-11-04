# QoR Guard

An experimental iCE40 implementation comparison CLI. It compares Yosys and nextpnr-ice40 reports between two runs and exits non-zero when area or Fmax change beyond your thresholds, or when a declared required clock is missed.

**Status:** version 0.3.0, experimental and not production-ready. It has no established users. No CI integration is provided or tested.

**Tested on:** privately, the maintainer's own HX8K reports, which are not distributed. The public test suite uses synthetic reports, so it does not validate compatibility with real tool output. UP5K support has limited internal evaluation and is not yet covered by the reproducible public test suite.

## What it does today

- Reads Yosys `stat -json` or a log stat table, and nextpnr-ice40 `--report` JSON.
- Compares against a stored baseline with configurable percentage thresholds, showing absolute and percentage changes.
- Reports BRAM use, plus logic-cell utilisation and headroom.
- Records seeds, failed runs, tool versions and required clocks declared in a manifest. Declared values are not verified.
- Reports observed Fmax ranges per clock, for information only.
- Checks declared required clocks using frequency margin, judged on the observed minimum.
- Never passes a comparison with declared failed runs.
- Writes a Markdown report and keeps copies and SHA-256 hashes of input reports.

**Exit codes:**
- 0: every applicable check was evaluated and met
- 1: threshold exceeded or required clock not met
- 2: no known failure, but evidence is incomplete or requirements are inconsistent or unavailable
- 3: bad input file or invalid value

**Known issue:** command-line syntax errors also exit 2.

## Supported

**iCE40 only.** Tested with Yosys 0.70+255 and nextpnr-ice40 0.11.1-83 on HX8K. Other parts and versions are untested.

## Not supported

- ECP5, Gowin, Xilinx/openXC7, Vivado and Quartus
- DSP and SPRAM metrics, per-module attribution, power and root-cause analysis

**Future work:** named baselines, pull-request comments and BRAM headroom comparisons.

## Known issue: Fmax variation

Fmax can vary between implementation runs, so several comparable runs are useful. A threshold can flag a harmless change. The shipped thresholds are examples only, not validated recommendations or statistically calibrated thresholds. Seed-aware thresholds remain experimental, and no validated public preset is provided. See `FALSE_ALARM_RESEARCH.md`.

## Try it

Works in PowerShell, cmd and bash. List each report by name, because cmd and PowerShell do not expand wildcards for Python.

```console
python -I -B qorguard.py capture --out runs/base --yosys-stat stat.json --nextpnr pnr_s1.json pnr_s2.json pnr_s3.json pnr_s4.json pnr_s5.json
python -I -B qorguard.py capture --out runs/new --yosys-stat stat_new.json --nextpnr new_s1.json new_s2.json new_s3.json new_s4.json new_s5.json
python -I -B qorguard.py compare --baseline runs/base --current runs/new --config config/thresholds.example.json --comparison-type revision
```

**Requirements:** Python standard library, with no network access and no dependencies. Tested only on Python 3.14.4 on Windows 11; no minimum version has been established.

**Privacy:** reports and `run.json` contain absolute local paths. Check them before sharing.
