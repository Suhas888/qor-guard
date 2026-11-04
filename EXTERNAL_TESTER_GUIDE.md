# QoR Guard 0.3.0: external tester guide

Thank you for evaluating QoR Guard.

**What it is:** an experimental CLI that compares Yosys and nextpnr results between two runs of an **iCE40** design. It exits non-zero when area or Fmax get worse than your thresholds, or when a declared required clock is missed.

**What it is not:**
- not production-ready;
- no CI integration or pull-request comments;
- no named baselines or BRAM headroom comparisons;
- no ECP5, Gowin, Xilinx/openXC7, Vivado or Quartus support.

## 1. Prerequisites

- **Python.** Standard library only, nothing to install. Tested only on Python 3.14.4 on Windows 11. That is not an established minimum. Linux, macOS and other Python versions are untested, so please report what happens.
- **For your own project:** Yosys and nextpnr-ice40. Tested versions are Yosys 0.70+255 and nextpnr-ice40 0.11.1-83. The Yosys text log layout is known to change between versions.
- **No network access or account** is needed.

## 2. Step 1: run the tests and demo

From the project root:

```console
python -I -B -m unittest discover -s tests -t .
python -I -B demo/run_demo.py
```

The tests should end with `Ran 258 tests` and `OK (skipped=3)`. The 3 skipped tests need private evaluation data that is not distributed. A skip is expected and is not a pass.

The demo uses synthetic iCE40-format reports with invented values, and writes `demo/output/<timestamp>/`. It should exit 0.

| Scenario | Expected exit | Key result |
|---|---|---|
| A_regression | 1 | area limits exceeded |
| B_improvement | 0 | all checks met |
| C_identical | 0 | all deltas 0 |
| D_missing_required | 2 | `lc` and `fmax_min` missing |

## 3. Step 2: test on your own iCE40 project

**1. Produce the inputs.** In your Yosys script, after `synth_ice40`, add:

```text
tee -q -o stat.json stat -json
```

Run nextpnr once per seed. Fmax can vary between implementation runs, so several comparable runs are useful. The commands below show 5 as an example:

```text
nextpnr-ice40 <your usual options> --seed 1 --report pnr_s1.json
nextpnr-ice40 <your usual options> --seed 5 --report pnr_s5.json
```

**2. Capture the baseline**, for example on your main branch. List every report by name: cmd and PowerShell do not expand wildcards for Python.

```text
python -I -B <path>/qorguard.py capture --out runs/main --label main --yosys-stat stat.json --nextpnr pnr_s1.json pnr_s2.json pnr_s3.json pnr_s4.json pnr_s5.json
python -I -B <path>/qorguard.py baseline --store .qorguard set runs/main
```

**3. Capture the changed version and compare:**

```text
python -I -B <path>/qorguard.py capture --out runs/change --label change --yosys-stat stat.json --nextpnr pnr_s1.json pnr_s2.json pnr_s3.json pnr_s4.json pnr_s5.json
python -I -B <path>/qorguard.py compare --baseline .qorguard --current runs/change --config <path>/config/thresholds.example.json --report qor_report.md --comparison-type revision
```

**4. Read the exit code:** `$LASTEXITCODE` in PowerShell, `echo %ERRORLEVEL%` in cmd, `echo $?` in bash.

**Other options:**
- `--manifest M.json` on `capture` declares seeds, failed runs, tool versions, device, commit, branch and `required_clocks_mhz`. See `README.md`. Please declare failed runs: without a manifest they cannot be detected.
- `--yosys-log synth.log` reads the stat table from a Yosys log.
- `--top <module>` selects one module from a multi-module `stat -json`.
- `--comparison-type revision|configuration|unknown` on `compare` states what the two runs are. The default is `unknown`. Only `revision` reports a threshold violation as a "REGRESSION".
- `--lc-capacity N` on `compare` overrides the logic-cell capacity.

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | every applicable check was evaluated and met |
| 1 | a threshold was exceeded, or the current side missed a required clock |
| 2 | no known failure, but evidence is incomplete or requirements are inconsistent or unavailable |
| 3 | an input file is unreadable or not a supported report |

**Known issue:** a command-line syntax mistake also exits **2**. Check the error message.

**What you should see:**
- On a non-iCE40 design, `lut4`, `ff` and `carry` show **UNSUPPORTED**. The tool does not guess.
- A simulation log or other non-report file exits 3 with an error naming the file.

## 4. About the thresholds (please read)

| Config file | Status |
|---|---|
| `config/thresholds.example.json` | Illustrative limits (+5% area, −10% worst-seed and median Fmax). **Examples only: not validated recommendations or statistically calibrated thresholds.** |

Seed-aware thresholds remain experimental, and no validated public preset is provided.

See `FALSE_ALARM_RESEARCH.md`. **Your real-world false alarms and missed regressions are exactly the data we lack.**

## 5. Before you share anything: check for local paths

`runs/*/run.json` and `qor_report.md` contain the **absolute paths of your input files** (`original_path`, metric `source` text, and the Provenance section). These can reveal user names, project names and folder layout.

Search them before sending:

| Shell | Command |
|---|---|
| PowerShell | `Select-String -Path qor_report.md -Pattern "from ``"` |
| PowerShell | `Select-String -Path runs\main\run.json -Pattern "original_path","source"` |
| cmd | `findstr "original_path source" runs\main\run.json` |
| bash | `grep -n -e original_path -e source runs/main/run.json` |

Those searches only find the known fields, so read the file as well. If needed, share only the metrics table, or replace the paths by hand. The stored `raw/` copies are your own report files, so do not share them if your design is confidential.

## 6. Reporting problems

Please send a plain-text note containing:
- your OS and Python version (`python --version`);
- your Yosys and nextpnr versions;
- the exact command you ran;
- the exit code and error message;
- if possible, the failing report file, **after checking it for confidential content**.

## 7. Feedback template

```text
QoR Guard 0.3.0 feedback
1. Setup: how long did a first comparison on your project take? What was hard or confusing?
2. Metrics: which of lut4 / ff / carry / lc / ram / fmax_min / fmax_median were useful? What is missing?
3. False alarms: did it report a problem you believe was not real? Which metric, how large, how many seeds?
4. Missed regressions: did a real regression pass without being flagged?
5. Ranges and required clocks: were they useful, or confusing?
6. Thresholds: which values would you actually use?
7. Real problem? How do you track Fmax and area between commits today? How often does a regression slip through, and what does it cost you?
8. Would you keep using it? What would have to change?
9. Anything else:
```

**Honest answers that it is not useful are just as valuable as positive ones.**
