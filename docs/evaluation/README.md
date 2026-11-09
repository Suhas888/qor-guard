# Evaluation kit

**Everything here is a synthetic example.** The reports come from the invented fixtures in `tests/fixtures/synthetic/`, so they describe no real design and aren't validation results.

| File | What it is |
|---|---|
| `example_report_configuration.md` | Expected report from step 3 of `docs/QUICKSTART.md`: two synthetic designs compared |
| `example_report_manifest.md` | Expected report from the README's manifest example |
| `EVALUATION_CHECKLIST.md` | Questions for testers |

Both reports were generated on 2026-11-09 by v0.3.0 (commit `1e32bcb`). The folder they were run from was replaced with `<repo>`, and nothing else was edited.

## Expected results

| Example | Command result | Why |
|---|---|---|
| Configuration comparison | `THRESHOLD EXCEEDED (exit 1)` | `lut4` +11.11% and `lc` +9.85% exceed the illustrative +5% limit. Fmax changes (−3.31% worst seed, −4.79% median) are within the illustrative −10% limits. The observed ranges overlap |
| Manifest comparison | `MISSING REQUIRED METRIC (exit 2)` | The manifest has no Yosys input, so required `lut4` and `ff` are missing. Missing evidence never passes. The report still shows ranges, and a 60 MHz required-clock check met by all five runs |

Both results were confirmed on Windows 11 in PowerShell, cmd and bash. Your timestamps and paths will differ. Input hashes also differ if Git converted line endings when you cloned, which Git for Windows does by default. Metric values and verdicts don't change.

## How to reproduce
Follow steps 1 to 3 of `docs/QUICKSTART.md`. For the second example, run the "Capture with a manifest" commands in `README.md`.
