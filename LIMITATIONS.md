# Limitations (QoR Guard 0.3.0, experimental)

## Scope

1. **iCE40 only for cell metrics.** LUT4, FF and CARRY come from `SB_*` primitives, and logic cells from `ICESTORM_LC`. Other libraries yield UNSUPPORTED.
2. **Tested tools:** Yosys 0.70+255 (git 72b0054f0) and nextpnr-ice40 0.11.1-83 on HX8K. Other versions are untested, and the Yosys text stat layout changes between versions.
3. **Tested devices:** HX8K (7680 LCs, 32 RAM). UP5K support has limited internal evaluation and is not yet covered by the reproducible public test suite. Other iCE40 parts are untested.
4. **Unsupported:** ECP5, Gowin, Nexus, Himbaechel, Xilinx/openXC7, Vivado, Quartus and Diamond.
5. **Platform:** tested only on Windows 11 with Python 3.14.4. No minimum Python version has been established. Linux, macOS and other Python versions are untested.
6. **Metrics not extracted:** DSP, SPRAM and IO counts, the Yosys `SB_RAM40_4K` count, per-module attribution, critical-path differences and power. No root-cause analysis is attempted.

## Not implemented (future work)

- Named baselines (only one stored baseline per store)
- Pull-request comments, GitHub Actions or other CI integration
- BRAM headroom comparisons, and a default BRAM threshold rule
- History across several baselines, dashboards, and automatic tool runs

## Evidence

7. **No real pull-request pair.** No real change to one design has been compared.
8. **No real multi-clock data.** Multi-clock tests are synthetic.
9. **Failed-run tests are synthetic.** What nextpnr writes when a run fails has not been checked.
10. **Thresholds are unvalidated.** Their false-alarm rate on real changes has not been measured. This includes the built-in defaults described below. Seed-aware thresholds remain experimental, and no validated public preset is provided.
11. **The test suite shows logic behaviour, not hardware results.** Fmax is nextpnr's timing estimate for the seeds given, not a measurement.
12. **No established users or customer need.**

## Built-in default thresholds

`compare` uses these rules when it runs without `--config`. None of them is marked as required.

| Metric | Limit |
|---|---|
| `lut4` | +2% |
| `ff` | +2% |
| `carry` | +5% |
| `lc` | +2% |
| `fmax_min` (each clock) | −5% |
| `fmax_median` (each clock) | −3% |

- These are legacy defaults, retained for behavioural compatibility.
- Their original rationale and statistical validity are unknown.
- They must not be interpreted as validated engineering recommendations.
- Configure thresholds explicitly for your own designs and requirements.
- `config/thresholds.example.json` holds separate, illustrative values. It is not used unless you pass it with `--config`.

## What it cannot detect

13. **Undeclared failed runs.** A failed run is known only if a manifest declares it. Without one, a run that left no report goes unnoticed, and the comparison can still pass.
14. **Wrong declarations.** Seeds, tool versions, device, commit, branch and requirements are recorded as declared and not verified. A requirement that is wrong on both sides is not detected, and removing it from both sides removes the check.
15. **Altered stored reports.** Stored hashes are not rechecked when a run is loaded.
16. **Unanalysed paths.** Gaps in nextpnr's timing model pass through unchanged.

## Behaviour

17. **Exit-code collision.** Command-line syntax errors exit 2 (from argparse), the same code as incomplete evidence. Read stderr to tell them apart.
18. **Change from 0.2.0.** A threshold violation plus a missing required metric now exits 1, where 0.2.0 exited 2. This applies to v1 records too.
19. **Required clocks.**
    - A current-side miss exits 1, judged only on the runs supplied, so meeting a requirement does not predict other seeds.
    - A requirement that differs between sides, or appears on one v2 side only, cannot pass. It exits 2, or 1 with a known failure.
    - A declared requirement against a v1 record cannot be compared and cannot pass in the same way. Only v1 vs v1 has no requirement check.
    - A required clock with no matching observation exits 2.
    - With no declared requirement, timing compliance is not assessed.
20. **Clock names match exactly.** A renamed clock appears as two clocks with insufficient data.
21. **Ranges need at least 2 observations per side.** Under 5 is labelled a small sample, and reaching 5 establishes no confidence. Ranges never affect the exit code.
22. **Fmax precision.** Threshold metrics store Fmax rounded to 0.001 MHz, so their deltas are accurate to about ±0.001 MHz. Per-run values and ranges use unrounded values.
23. **Capacity** comes only from `--lc-capacity` or nextpnr's `ICESTORM_LC.available`. No device table exists.
24. **Comparison type** is whatever you state. QoR Guard cannot verify that two runs are revisions of one design.
25. **Zero baselines.** A change from zero still trips a percentage threshold, but Δ % is shown as undefined.
26. **Report escaping** is tested on the generated text, not in a real Markdown renderer.

## Parser behaviour

27. The Yosys 0.70 text stat lists primitives under "submodules", so the parser reads per-type lines and does not report a total cell count.
28. The stat JSON parser uses the `design` summary by default. Use `--top` for one module. Multi-module JSON without a summary is rejected.
29. When the stat JSON and log disagree, the JSON value is kept and a note is recorded.
30. If logic-cell counts differ between seed reports, the maximum is kept and a note is recorded.

## Privacy

31. **Reports and `run.json` contain absolute local paths** (`original_path`, metric `source`, the report's Provenance section). `raw/` keeps your input reports, which can contain paths and design names. Inspect them before sharing.

## Public test coverage

32. **The public suite uses synthetic reports only.** It shows the code handles the expected file layouts, not that real tool output parses correctly. Real HX8K reports were checked privately and are not distributed, so that check cannot be reproduced from this release. UP5K support has limited internal evaluation and is not yet covered by the reproducible public test suite. Three tests that need private evaluation data skip publicly.
33. **Seed-variation results are not published.** The dataset and numerical findings are not in this release. See `FALSE_ALARM_RESEARCH.md`.
