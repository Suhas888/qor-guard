<!-- SYNTHETIC EXAMPLE. Generated on 2026-11-09 by QoR Guard v0.3.0 (commit 1e32bcb) from the invented fixtures in tests/fixtures/synthetic/.
     The only edit: the local folder the example was run from was replaced with <repo>. All values are invented and describe no real design. -->

# QoR Guard report — THRESHOLD EXCEEDED

**Comparison type: configuration.** Two different design configurations or parameter settings. Differences describe the two configurations; they do not establish a code regression and do not prove what caused them.

- Baseline: `base` captured 2026-11-09T06:41:36 (Yosys 0.70+255 (synthetic test fixture, not tool output); 5 nextpnr run(s); qorguard 0.3.0)
- Current: `new` captured 2026-11-09T06:41:36 (Yosys 0.70+255 (synthetic test fixture, not tool output); 5 nextpnr run(s); qorguard 0.3.0)
- Exit code: **1** (0 pass, 1 threshold exceeded or required clock not met, 2 required metric or evidence missing)
- Delta convention: Δ = current − baseline; Δ % = Δ / baseline × 100 (undefined when the baseline is 0).

## Warnings
- ⚠ baseline: no manifest declared the attempted runs, so a failed run that left no report cannot be detected.
- ⚠ current: no manifest declared the attempted runs, so a failed run that left no report cannot be detected.

## Threshold checks

| Metric | Stage | Baseline | Current | Δ | Δ % | Threshold | Status |
|---|---|---|---|---|---|---|---|
| `lut4` | Yosys pre-pack | 2340 | 2600 | +260 | +11.11 | ≤ +5.0% (required) | **THRESHOLD EXCEEDED** |
| `ff` | Yosys pre-pack | 544 | 544 | +0 | +0 | ≤ +5.0% (required) | OK |
| `lc` | nextpnr packed/routed | 2640 | 2900 | +260 | +9.85 | ≤ +5.0% (required) | **THRESHOLD EXCEEDED** |
| `fmax_min[clk$SB_IO_IN_$glb_clk]` | nextpnr packed/routed | 72.5 | 70.102 | -2.398 | -3.31 | ≥ −10.0% (required) | OK |
| `fmax_median[clk$SB_IO_IN_$glb_clk]` | nextpnr packed/routed | 75 | 71.406 | -3.594 | -4.79 | ≥ −10.0% | OK |

## Observed Fmax ranges

These figures describe only the runs supplied. An overlap does not establish that the two sides perform alike, that there is no regression, or that a difference comes from placement variation. This section does not affect the verdict or exit code. Ranges use successful runs only, calculated at full source precision and displayed to 0.001 MHz.

### Clock `clk$SB_IO_IN_$glb_clk`

| Side | Attempted | Successful | Failed | Valid Fmax observations | Min (MHz) | Median (MHz) | Max (MHz) | Insufficient data |
|---|---|---|---|---|---|---|---|---|
| baseline | not declared | 5 | not declared | 5 | 72.500 | 75.000 | 76.500 | no |
| current | not declared | 5 | not declared | 5 | 70.102 | 71.406 | 73.188 | no |

**The observed ranges overlap, with the qualifications below.**
- device unavailable on at least one side
- nextpnr version unavailable on at least one side
- constraint files unavailable on at least one side
- baseline: attempted and failed runs were not declared; failed runs that left no report are unknown
- current: attempted and failed runs were not declared; failed runs that left no report are unknown
- seed values are unavailable for at least one observation; no claim is made that the sides used the same seeds

### Compatibility of the two sides

| Field | Baseline | Current | Status |
|---|---|---|---|
| device | unavailable | unavailable | unavailable |
| yosys_version | 0.70+255 (extracted) | 0.70+255 (extracted) | match |
| nextpnr_version | unavailable | unavailable | unavailable |
| constraint_files | unavailable | unavailable | unavailable |

## Required-clock timing

A required frequency is only what a manifest explicitly declares; a tool constraint is shown separately and never replaces it. Absolute margin = achieved − required. Percentage margin = (achieved − required) / required × 100. These are frequency margins, not period slack. Figures use successful runs only, calculated at full source precision; achieved Fmax and margins are displayed rounded. A range overlap says nothing about meeting a required frequency. If the current side misses its declared requirement, the exit code is 1, even when every percentage threshold is met. If a current-side required clock has no matching observations, or the requirements for a clock differ, are declared on only one side, or cannot be compared with a v1 record, the exit code is 2 unless a known failure makes it 1. A baseline-side miss alone does not affect the exit code, and a clock neither side declares is informational. QoR Guard has no independent source for a required frequency, so it cannot tell whether a declared value is correct.

### Timing for clock `clk$SB_IO_IN_$glb_clk`

| Side | Attempted | Successful | Failed | Valid Fmax observations | Required (MHz) | Tool constraint (MHz) | Min (MHz) | Median (MHz) | Max (MHz) |
|---|---|---|---|---|---|---|---|---|---|
| baseline | not declared | 5 | not declared | 5 | not declared | 12.0 | 72.500 | 75.000 | 76.500 |
| current | not declared | 5 | not declared | 5 | not declared | 12.0 | 70.102 | 71.406 | 73.188 |

baseline: timing compliance cannot be assessed. No required frequency is declared for this clock. The tool-reported constraint (12.0 MHz) is not used as a substitute.  
current: timing compliance cannot be assessed. No required frequency is declared for this clock. The tool-reported constraint (12.0 MHz) is not used as a substitute.  
- baseline: attempted and failed runs were not declared; failed runs that left no report are unknown
- current: attempted and failed runs were not declared; failed runs that left no report are unknown

## All extracted metrics

| Stage | Metric | Unit | Baseline | Current | Δ | Δ % |
|---|---|---|---|---|---|---|
| Yosys pre-pack | `carry` | count | 210 | 180 | -30 | -14.29 |
| Yosys pre-pack | `ff` | count | 544 | 544 | +0 | +0 |
| Yosys pre-pack | `lut4` | count | 2340 | 2600 | +260 | +11.11 |
| nextpnr packed/routed | `fmax_constraint[clk$SB_IO_IN_$glb_clk]` | MHz | 12 | 12 | +0 | +0 |
| nextpnr packed/routed | `fmax_median[clk$SB_IO_IN_$glb_clk]` | MHz | 75 | 71.406 | -3.594 | -4.79 |
| nextpnr packed/routed | `fmax_min[clk$SB_IO_IN_$glb_clk]` | MHz | 72.5 | 70.102 | -2.398 | -3.31 |
| nextpnr packed/routed | `lc` | count | 2640 | 2900 | +260 | +9.85 |
| nextpnr packed/routed | `lc_capacity` | count | 7680 | 7680 | +0 | +0 |
| nextpnr packed/routed | `ram` | count | 0 | 0 | +0 | +0 |
| nextpnr packed/routed | `ram_capacity` | count | 32 | 32 | +0 | +0 |

## Logic-cell utilisation and headroom (nextpnr packed)

| Run | LC used | LC capacity | Capacity source | Utilisation | Headroom |
|---|---|---|---|---|---|
| baseline | 2640 | 7680 | nextpnr utilization.ICESTORM_LC.available | 34.38% | 5040 |
| current | 2900 | 7680 | nextpnr utilization.ICESTORM_LC.available | 37.76% | 4780 |

## Pre-pack vs packed metrics

**Yosys pre-pack (synthesis)** metrics (`lut4`, `ff`, `carry`) count technology-mapped cells after synthesis, before placement. **nextpnr packed / routed** metrics (`lc`, `ram`, `fmax_*`) come from the implemented design: an iCE40 logic cell (`lc`) can hold a LUT4 and a flip-flop together, so `lut4` and `lc` are different quantities and are never interchangeable. Fmax values are nextpnr's post-route timing estimates for the given runs (stored to 0.001 MHz), not hardware measurements.

## Metrics present but not covered by any threshold rule

- `carry`
- `ram`

## Provenance
**Baseline** inputs:
- yosys_stat_json: `raw\00_ice40_stat.json` sha256 `f3dbb4ffaddaaac9…` (from `<repo>\tests\fixtures\synthetic\design_b\ice40_stat.json`)
- nextpnr_report: `raw\01_pnr_report_s1.json` sha256 `90c1b25cc7967c1a…` (from `<repo>\tests\fixtures\synthetic\design_b\pnr_report_s1.json`)
- nextpnr_report: `raw\02_pnr_report_s2.json` sha256 `f5469b84dceab33e…` (from `<repo>\tests\fixtures\synthetic\design_b\pnr_report_s2.json`)
- nextpnr_report: `raw\03_pnr_report_s3.json` sha256 `84e5378e9708fa29…` (from `<repo>\tests\fixtures\synthetic\design_b\pnr_report_s3.json`)
- nextpnr_report: `raw\04_pnr_report_s4.json` sha256 `7d79635019609f87…` (from `<repo>\tests\fixtures\synthetic\design_b\pnr_report_s4.json`)
- nextpnr_report: `raw\05_pnr_report_s5.json` sha256 `e0882addda84b801…` (from `<repo>\tests\fixtures\synthetic\design_b\pnr_report_s5.json`)
**Current** inputs:
- yosys_stat_json: `raw\00_ice40_stat.json` sha256 `709e2007a6b2ed90…` (from `<repo>\tests\fixtures\synthetic\design_a\ice40_stat.json`)
- nextpnr_report: `raw\01_pnr_report_s1.json` sha256 `5adc0515c2224bae…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s1.json`)
- nextpnr_report: `raw\02_pnr_report_s2.json` sha256 `b708e492a78c66b8…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s2.json`)
- nextpnr_report: `raw\03_pnr_report_s3.json` sha256 `049134446692b7d5…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s3.json`)
- nextpnr_report: `raw\04_pnr_report_s4.json` sha256 `01db6abff1ccdd50…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s4.json`)
- nextpnr_report: `raw\05_pnr_report_s5.json` sha256 `95219dcba1866d6a…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s5.json`)

## Metric sources (current run)
- `carry`: tests/fixtures/synthetic/design_a/ice40_stat.json design (whole hierarchy): SB_CARRY
- `ff`: tests/fixtures/synthetic/design_a/ice40_stat.json design (whole hierarchy): sum of ['SB_DFF', 'SB_DFFESR', 'SB_DFFSR']
- `fmax_constraint[clk$SB_IO_IN_$glb_clk]`: nextpnr fmax[clk$SB_IO_IN_$glb_clk].constraint over 5/5 reports
- `fmax_median[clk$SB_IO_IN_$glb_clk]`: nextpnr fmax[clk$SB_IO_IN_$glb_clk].achieved over 5/5 reports (median)
- `fmax_min[clk$SB_IO_IN_$glb_clk]`: nextpnr fmax[clk$SB_IO_IN_$glb_clk].achieved over 5/5 reports (worst seed)
- `lc`: tests/fixtures/synthetic/design_a/pnr_report_s1.json: utilization.ICESTORM_LC.used (n=5 reports)
- `lc_capacity`: nextpnr utilization.ICESTORM_LC.available (n=5 reports)
- `lut4`: tests/fixtures/synthetic/design_a/ice40_stat.json design (whole hierarchy): SB_LUT4
- `ram`: nextpnr utilization.ICESTORM_RAM.used (n=5 reports)
- `ram_capacity`: nextpnr utilization.ICESTORM_RAM.available (n=5 reports)
