# QoR Guard 0.3.0

An experimental iCE40 implementation comparison CLI for Yosys and nextpnr reports. **It is not production-ready and has no established user base.**

QoR Guard reads reports you already produced; it does not run the tools. It compares two captured runs against configurable thresholds and optional required clock frequencies, writes a Markdown report, and sets an exit code.

## Included in 0.3.0

- **Capture:** Yosys `stat -json` or a Yosys log stat table, and one or more nextpnr-ice40 `--report` JSON files. Inputs are copied and hashed with SHA-256.
- **Manifest (`capture --manifest`):** declares seeds, failed runs, tool versions, device, commit, branch, constraint files and required clocks. Declared values are recorded as declared and are not verified.
- **Baseline:** one stored baseline. Overwriting is refused; `--replace` keeps the old one under a new name.
- **Compare:** percentage thresholds with absolute and percentage deltas, logic-cell utilisation and headroom, BRAM use, and a stated comparison type.
- **Observed Fmax ranges:** per-clock minimum, median, maximum and range overlap. These are for reporting only and never affect the exit code.
- **Required-clock checks:** frequency margin against a declared requirement, judged on the observed minimum. These are frequency margins, not period slack.
- **Failed-run reporting:** runs a manifest declares as failed can never produce PASS.

## Future work (not implemented)

- Named baselines
- Pull-request comments and CI integration
- BRAM headroom comparisons (BRAM use is shown, but headroom is calculated for logic cells only)
- Architectures other than iCE40

UP5K support has limited internal evaluation and is not yet covered by the reproducible public test suite.

See `LIMITATIONS.md` before relying on a result.

New here? Start with `docs/QUICKSTART.md`. A synthetic example and an evaluation checklist are in `docs/evaluation/README.md`.

## Requirements

Python standard library only, with no network access or account. **Tested only on Python 3.14.4 on Windows 11.** That is the tested version, not an established minimum. Linux, macOS and other Python versions are untested.

## Try it

Run these from the project root. They work unchanged in PowerShell and cmd, and use the synthetic reports included for testing. **Their values are invented and say nothing about real designs.**

Run the tests and the demo:

```console
python -I -B -m unittest discover -s tests -t .
python -I -B demo/run_demo.py
```

The tests should end with `OK (skipped=3)`. The 3 skipped tests need private evaluation data that is not distributed.

Capture a baseline and a second run, then compare them:

```console
python -I -B qorguard.py capture --out runs/base --label base --yosys-stat tests/fixtures/synthetic/design_b/ice40_stat.json --nextpnr tests/fixtures/synthetic/design_b/pnr_report_s1.json tests/fixtures/synthetic/design_b/pnr_report_s2.json tests/fixtures/synthetic/design_b/pnr_report_s3.json tests/fixtures/synthetic/design_b/pnr_report_s4.json tests/fixtures/synthetic/design_b/pnr_report_s5.json
python -I -B qorguard.py baseline --store .qorguard set runs/base
python -I -B qorguard.py capture --out runs/new --label new --yosys-stat tests/fixtures/synthetic/design_a/ice40_stat.json --nextpnr tests/fixtures/synthetic/design_a/pnr_report_s1.json tests/fixtures/synthetic/design_a/pnr_report_s2.json tests/fixtures/synthetic/design_a/pnr_report_s3.json tests/fixtures/synthetic/design_a/pnr_report_s4.json tests/fixtures/synthetic/design_a/pnr_report_s5.json
python -I -B qorguard.py compare --baseline .qorguard --current runs/new --config config/thresholds.example.json --report runs/qor_report.md --comparison-type configuration
```

The compare exits 1: the second synthetic design is larger.

Capture with a manifest, which adds seeds and a required clock:

```console
python -I -B qorguard.py capture --out runs/m1 --label m1 --manifest examples/hx8k_manifest.json
python -I -B qorguard.py capture --out runs/m2 --label m2 --manifest examples/hx8k_manifest.json
python -I -B qorguard.py compare --baseline runs/m1 --current runs/m2 --config config/thresholds.example.json --report runs/qor_manifest_report.md
```

This compares a run with itself. A missing Yosys input leaves required metrics missing, so it exits 2, which shows that absent evidence does not pass. The report includes the ranges and required-clock sections.

To see an exit code:

| Shell | Command |
|---|---|
| PowerShell | `$LASTEXITCODE` |
| cmd | `echo %ERRORLEVEL%` |
| bash | `echo $?` |

**List each report file by name.** cmd and PowerShell do not expand wildcards for Python, so a pattern such as `pnr_s*.json` fails on those shells.

## Your own project

- **Yosys:** add `tee -q -o stat.json stat -json` after synthesis. The stat table in the normal log is also accepted through `--yosys-log`.
- **nextpnr-ice40:** pass `--report pnr_s1.json`, once per seed. Fmax can vary between implementation runs, so several comparable runs are useful.

## Manifest

Relative paths resolve from the manifest's folder, and unknown fields are rejected. Reports come from `runs` or `--nextpnr`, not both.

```json
{
  "manifest_version": 1,
  "commit": "abc1234",
  "branch": "main",
  "device": "iCE40 HX8K",
  "yosys_version": "0.70+255",
  "nextpnr_version": "0.11.1-83",
  "constraint_files": ["top.pcf"],
  "required_clocks_mhz": {"clk": 48.0},
  "runs": [
    {"report": "pnr_s1.json", "seed": 1, "status": "success"},
    {"seed": 2, "status": "failed", "reason": "routing failed"}
  ]
}
```

Without a manifest, a failed run that left no report cannot be detected.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Every applicable check was evaluated and met |
| 1 | A threshold was exceeded, or the current side missed a required clock |
| 2 | No known failure, but evidence is incomplete: failed runs, a missing required metric, an unevaluated required clock, or inconsistent or unavailable requirements |
| 3 | An input file is unreadable or unsupported, or a value is invalid |

A known failure (exit 1) outranks incomplete evidence (exit 2). Every condition present is named in the verdict.

**Known issue:** command-line syntax errors also exit 2. Read stderr to tell them apart.

Exit 0 means the configured checks were met. It does not prove that anything improved.

## Thresholds

- `config/thresholds.example.json` is the only shipped preset. Examples only: not validated recommendations or statistically calibrated thresholds. They may flag harmless changes or miss real ones.
- Seed-aware thresholds remain experimental, and no validated public preset is provided. Choose limits from your own results. See `FALSE_ALARM_RESEARCH.md`.

## Privacy: check before sharing

**Reports and `run.json` files contain absolute local paths** in `original_path`, in metric `source` text and in the report's Provenance section. These can reveal user names, project names and folder layout. The `raw/` folder in a run keeps your input reports, which can themselves contain paths and design names. Inspect everything before sharing it.

**Custom report paths:** `.gitignore` covers `runs/`, `.qorguard/`, `demo/output/` and `qor_report.md`. A report or run written anywhere else is not ignored, so Git could commit its local paths. Keep them under `runs/`, or check them before committing.

## Documentation

- `docs/QUICKSTART.md`: first-time setup and a synthetic example
- `docs/evaluation/README.md`: expected example results and a tester checklist
- `docs/release-notes/v0.3.0.md`: release notes for v0.3.0
- `SUPPORTED_FORMATS.md`: what is and is not parsed
- `LIMITATIONS.md`: known limits
- `CHANGELOG_0.3.md`: changes, including one intentional exit-code change from 0.2.0
- `EXTERNAL_TESTER_GUIDE.md`: how to evaluate it on your own project
- `FALSE_ALARM_RESEARCH.md`: why seed variation matters
- `tests/fixtures/README.md`: how test data was prepared

## Licence

Project code is under the MIT License (`LICENSE`). The fixtures under `tests/fixtures/` and `tests/fixture_generator.py` are not covered by it; see `tests/fixtures/README.md`.
