# QoR Guard quick start

This guide walks you through installation, tests and a synthetic comparison. It's tested on **Windows 11 with Python 3.14.4 only**, and Linux and macOS are untested. QoR Guard needs no packages beyond Python's standard library.

## 1. Get the code

```console
git clone https://github.com/Suhas888/qor-guard.git
cd qor-guard
```

The application code is the same as tag `v0.3.0`. This guide and `docs/evaluation/` were added afterwards, so they aren't in the `v0.3.0` source archive.

## 2. Check it works

```console
python -I -B -m unittest discover -s tests -t .
```

The output should end with `Ran 259 tests` and `OK (skipped=3)`. The 3 skipped tests need private evaluation data that isn't distributed, so they aren't failures.

If `python` isn't found, try `py` on Windows or `python3` elsewhere. Platforms other than Windows are untested.

## 3. Run the synthetic example

These commands use invented reports in `tests/fixtures/synthetic/`. List each report file by name, because cmd and PowerShell don't expand wildcards for Python.

```console
python -I -B qorguard.py capture --out runs/base --label base --yosys-stat tests/fixtures/synthetic/design_b/ice40_stat.json --nextpnr tests/fixtures/synthetic/design_b/pnr_report_s1.json tests/fixtures/synthetic/design_b/pnr_report_s2.json tests/fixtures/synthetic/design_b/pnr_report_s3.json tests/fixtures/synthetic/design_b/pnr_report_s4.json tests/fixtures/synthetic/design_b/pnr_report_s5.json
python -I -B qorguard.py baseline --store .qorguard set runs/base
python -I -B qorguard.py capture --out runs/new --label new --yosys-stat tests/fixtures/synthetic/design_a/ice40_stat.json --nextpnr tests/fixtures/synthetic/design_a/pnr_report_s1.json tests/fixtures/synthetic/design_a/pnr_report_s2.json tests/fixtures/synthetic/design_a/pnr_report_s3.json tests/fixtures/synthetic/design_a/pnr_report_s4.json tests/fixtures/synthetic/design_a/pnr_report_s5.json
python -I -B qorguard.py compare --baseline .qorguard --current runs/new --config config/thresholds.example.json --report runs/qor_report.md --comparison-type configuration
```

The last command should print `THRESHOLD EXCEEDED (exit 1)`. Open `runs/qor_report.md` and compare it with `docs/evaluation/example_report_configuration.md`. Only timestamps and paths should differ. The input hashes in the Provenance section can also differ if Git converted line endings when you cloned, which Git for Windows does by default. The metric values should still match.

To see the exit code, run `$LASTEXITCODE` in PowerShell, `echo %ERRORLEVEL%` in cmd or `echo $?` in bash.

## 4. Use your own iCE40 design
1. **Synthesis:** in Yosys, after `synth_ice40`, add `tee -q -o stat.json stat -json`.
2. **Place and route:** run nextpnr-ice40 with `--report pnr_s1.json`, once per seed. Several comparable runs are useful, because Fmax can vary between runs.
3. **Baseline:** capture your baseline and set it, as in step 3.
4. **Compare:** capture your changed design and compare it.
5. **Thresholds:** write your own. The example file's values are illustrations only.

## 5. Before sharing anything
`runs/*/run.json` and every report contain **absolute local paths**, which can include your username. Keep output under `runs/`, which `.gitignore` covers, and remove paths before you share a report.

## Not supported
ECP5, Gowin, Xilinx, Vivado, Quartus and Diamond aren't supported, and Linux and macOS are untested. See `LIMITATIONS.md`.
