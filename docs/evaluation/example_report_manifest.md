<!-- SYNTHETIC EXAMPLE. Generated on 2026-11-09 by QoR Guard v0.3.0 (commit 1e32bcb) from the invented fixtures in tests/fixtures/synthetic/.
     The only edit: the local folder the example was run from was replaced with <repo>. All values are invented and describe no real design. -->

# QoR Guard report — MISSING REQUIRED METRIC

**Comparison type: unknown.** The relationship between the two runs was not stated (default). Differences are reported numerically only; they do not establish a regression or a cause.

- Baseline: `m1` captured 2026-11-09T06:41:37 (tool UNKNOWN; 5 nextpnr run(s); qorguard 0.3.0)
- Current: `m2` captured 2026-11-09T06:41:37 (tool UNKNOWN; 5 nextpnr run(s); qorguard 0.3.0)
- Exit code: **2** (0 pass, 1 threshold exceeded or required clock not met, 2 required metric or evidence missing)
- Delta convention: Δ = current − baseline; Δ % = Δ / baseline × 100 (undefined when the baseline is 0).

## Threshold checks

| Metric | Stage | Baseline | Current | Δ | Δ % | Threshold | Status |
|---|---|---|---|---|---|---|---|
| `lut4` | Yosys pre-pack | — | — | — | — | ≤ +5.0% (required) | **MISSING** |
| `ff` | Yosys pre-pack | — | — | — | — | ≤ +5.0% (required) | **MISSING** |
| `lc` | nextpnr packed/routed | 2900 | 2900 | +0 | +0 | ≤ +5.0% (required) | OK |
| `fmax_min[clk$SB_IO_IN_$glb_clk]` | nextpnr packed/routed | 70.102 | 70.102 | +0 | +0 | ≥ −10.0% (required) | OK |
| `fmax_median[clk$SB_IO_IN_$glb_clk]` | nextpnr packed/routed | 71.406 | 71.406 | +0 | +0 | ≥ −10.0% | OK |

## Observed Fmax ranges

These figures describe only the runs supplied. An overlap does not establish that the two sides perform alike, that there is no regression, or that a difference comes from placement variation. This section does not affect the verdict or exit code. Ranges use successful runs only, calculated at full source precision and displayed to 0.001 MHz.

### Clock `clk$SB_IO_IN_$glb_clk`

| Side | Attempted | Successful | Failed | Valid Fmax observations | Min (MHz) | Median (MHz) | Max (MHz) | Insufficient data |
|---|---|---|---|---|---|---|---|---|
| baseline | 5 | 5 | 0 | 5 | 70.102 | 71.406 | 73.188 | no |
| current | 5 | 5 | 0 | 5 | 70.102 | 71.406 | 73.188 | no |

**The observed ranges overlap, with the qualifications below.**
- constraint files unavailable on at least one side

### Compatibility of the two sides

| Field | Baseline | Current | Status |
|---|---|---|---|
| device | iCE40 HX8K (declared) | iCE40 HX8K (declared) | match |
| yosys_version | 0.70+255 (declared) | 0.70+255 (declared) | match |
| nextpnr_version | 0.11.1-83 (declared) | 0.11.1-83 (declared) | match |
| constraint_files | unavailable | unavailable | unavailable |

## Required-clock timing

A required frequency is only what a manifest explicitly declares; a tool constraint is shown separately and never replaces it. Absolute margin = achieved − required. Percentage margin = (achieved − required) / required × 100. These are frequency margins, not period slack. Figures use successful runs only, calculated at full source precision; achieved Fmax and margins are displayed rounded. A range overlap says nothing about meeting a required frequency. If the current side misses its declared requirement, the exit code is 1, even when every percentage threshold is met. If a current-side required clock has no matching observations, or the requirements for a clock differ, are declared on only one side, or cannot be compared with a v1 record, the exit code is 2 unless a known failure makes it 1. A baseline-side miss alone does not affect the exit code, and a clock neither side declares is informational. QoR Guard has no independent source for a required frequency, so it cannot tell whether a declared value is correct.

### Timing for clock `clk$SB_IO_IN_$glb_clk`

| Side | Attempted | Successful | Failed | Valid Fmax observations | Required (MHz) | Tool constraint (MHz) | Min (MHz) | Median (MHz) | Max (MHz) |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 5 | 5 | 0 | 5 | 60.0 | 12.0 | 70.102 | 71.406 | 73.188 |
| current | 5 | 5 | 0 | 5 | 60.0 | 12.0 | 70.102 | 71.406 | 73.188 |

| Side | Min margin | Median margin | Max margin |
|---|---|---|---|
| baseline | +10.102 MHz (+16.84%) | +11.406 MHz (+19.01%) | +13.188 MHz (+21.98%) |
| current | +10.102 MHz (+16.84%) | +11.406 MHz (+19.01%) | +13.188 MHz (+21.98%) |

**baseline: the observed minimum meets the required frequency.** 5 of 5 observations meet the required frequency. This covers these runs only and does not predict other runs or seeds.  
**current: the observed minimum meets the required frequency.** 5 of 5 observations meet the required frequency. This covers these runs only and does not predict other runs or seeds.  
- baseline: tool constraint [12.0] MHz differs from the required 60.0 MHz; they are kept separate
- current: tool constraint [12.0] MHz differs from the required 60.0 MHz; they are kept separate

## All extracted metrics

| Stage | Metric | Unit | Baseline | Current | Δ | Δ % |
|---|---|---|---|---|---|---|
| nextpnr packed/routed | `fmax_constraint[clk$SB_IO_IN_$glb_clk]` | MHz | 12 | 12 | +0 | +0 |
| nextpnr packed/routed | `fmax_median[clk$SB_IO_IN_$glb_clk]` | MHz | 71.406 | 71.406 | +0 | +0 |
| nextpnr packed/routed | `fmax_min[clk$SB_IO_IN_$glb_clk]` | MHz | 70.102 | 70.102 | +0 | +0 |
| nextpnr packed/routed | `lc` | count | 2900 | 2900 | +0 | +0 |
| nextpnr packed/routed | `lc_capacity` | count | 7680 | 7680 | +0 | +0 |
| nextpnr packed/routed | `ram` | count | 0 | 0 | +0 | +0 |
| nextpnr packed/routed | `ram_capacity` | count | 32 | 32 | +0 | +0 |

## Logic-cell utilisation and headroom (nextpnr packed)

| Run | LC used | LC capacity | Capacity source | Utilisation | Headroom |
|---|---|---|---|---|---|
| baseline | 2900 | 7680 | nextpnr utilization.ICESTORM_LC.available | 37.76% | 4780 |
| current | 2900 | 7680 | nextpnr utilization.ICESTORM_LC.available | 37.76% | 4780 |

## Pre-pack vs packed metrics

**Yosys pre-pack (synthesis)** metrics (`lut4`, `ff`, `carry`) count technology-mapped cells after synthesis, before placement. **nextpnr packed / routed** metrics (`lc`, `ram`, `fmax_*`) come from the implemented design: an iCE40 logic cell (`lc`) can hold a LUT4 and a flip-flop together, so `lut4` and `lc` are different quantities and are never interchangeable. Fmax values are nextpnr's post-route timing estimates for the given runs (stored to 0.001 MHz), not hardware measurements.

## Not compared / missing metrics
- `lut4`: baseline: not present; current: not present
- `ff`: baseline: not present; current: not present

## Metrics present but not covered by any threshold rule

- `ram`

## Provenance
**Baseline** inputs:
- nextpnr_report: `raw\00_pnr_report_s1.json` sha256 `5adc0515c2224bae…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s1.json`)
- nextpnr_report: `raw\01_pnr_report_s2.json` sha256 `b708e492a78c66b8…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s2.json`)
- nextpnr_report: `raw\02_pnr_report_s3.json` sha256 `049134446692b7d5…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s3.json`)
- nextpnr_report: `raw\03_pnr_report_s4.json` sha256 `01db6abff1ccdd50…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s4.json`)
- nextpnr_report: `raw\04_pnr_report_s5.json` sha256 `95219dcba1866d6a…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s5.json`)
- manifest: `raw\05_hx8k_manifest.json` sha256 `31ea91af24fbb1b7…` (from `<repo>\examples\hx8k_manifest.json`)
**Current** inputs:
- nextpnr_report: `raw\00_pnr_report_s1.json` sha256 `5adc0515c2224bae…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s1.json`)
- nextpnr_report: `raw\01_pnr_report_s2.json` sha256 `b708e492a78c66b8…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s2.json`)
- nextpnr_report: `raw\02_pnr_report_s3.json` sha256 `049134446692b7d5…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s3.json`)
- nextpnr_report: `raw\03_pnr_report_s4.json` sha256 `01db6abff1ccdd50…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s4.json`)
- nextpnr_report: `raw\04_pnr_report_s5.json` sha256 `95219dcba1866d6a…` (from `<repo>\tests\fixtures\synthetic\design_a\pnr_report_s5.json`)
- manifest: `raw\05_hx8k_manifest.json` sha256 `31ea91af24fbb1b7…` (from `<repo>\examples\hx8k_manifest.json`)

## Metric sources (current run)
- `fmax_constraint[clk$SB_IO_IN_$glb_clk]`: nextpnr fmax[clk$SB_IO_IN_$glb_clk].constraint over 5/5 reports
- `fmax_median[clk$SB_IO_IN_$glb_clk]`: nextpnr fmax[clk$SB_IO_IN_$glb_clk].achieved over 5/5 reports (median)
- `fmax_min[clk$SB_IO_IN_$glb_clk]`: nextpnr fmax[clk$SB_IO_IN_$glb_clk].achieved over 5/5 reports (worst seed)
- `lc`: <repo>\tests\fixtures\synthetic\design_a\pnr_report_s1.json: utilization.ICESTORM_LC.used (n=5 reports)
- `lc_capacity`: nextpnr utilization.ICESTORM_LC.available (n=5 reports)
- `ram`: nextpnr utilization.ICESTORM_RAM.used (n=5 reports)
- `ram_capacity`: nextpnr utilization.ICESTORM_RAM.available (n=5 reports)
