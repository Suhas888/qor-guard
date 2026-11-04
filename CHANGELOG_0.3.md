# QoR Guard 0.3.0 changelog

**Status:** experimental iCE40 implementation comparison CLI.

**Included:** schema v2 records, capture manifests, failed-run reporting, observed Fmax ranges, and required-clock checks.

**Moved to future work, not implemented:** named baselines, pull-request comments, BRAM headroom comparisons, and architectures other than iCE40.

**Release preparation:** the public test suite uses synthetic reports and an unmodified copy of the 0.2.0 code for older-format records. Three tests that need private evaluation data are skipped. Seed-aware thresholds remain experimental, and no validated public preset is provided.

The sections below record how the work was built.

## Phase 1: data model (schema v2)

New captures write `schema_version: 2`. All v1 fields stay, and threshold decisions still read the rounded v1 metrics.

**Added to `run.json`:**
- `runs[]`: one record per nextpnr run, with status, seed, report hash, unrounded per-clock Fmax and logic cells.
- `run_counts`: attempted, successful, failed and their basis.
- `provenance`: Yosys and nextpnr versions, device, clock constraints, constraint files, commit and branch.

Seeds and provenance values are `extracted`, `declared` or `unavailable`. No seed is `extracted` today, because nextpnr's report does not contain one. Seeds are never read from filenames, and QoR Guard does not run git.

**Run counts:** with `--nextpnr` alone, `attempted` and `failed` are `null`, because a run that left no report cannot be known. Only a manifest `runs` list establishes them.

**Manifest (`capture --manifest M.json`):** relative paths resolve from the manifest's folder. Unknown fields are rejected. Reports come from `runs` or `--nextpnr`, not both.

```json
{
  "manifest_version": 1,
  "commit": "abc1234",
  "branch": "main",
  "device": "iCE40 HX8K ct256",
  "nextpnr_version": "0.11.1-83",
  "constraint_files": ["top.pcf"],
  "runs": [
    {"report": "pnr_s1.json", "seed": 1, "status": "success"},
    {"seed": 2, "status": "failed", "reason": "routing failed"}
  ]
}
```

**v1 records** load unchanged and are never rewritten. `schema.seed_data()` returns `None` for what v1 did not store.

**Failed runs in `compare` (v2 records with a manifest `runs` list), on either side:**

| Situation | Exit | Verdict contains |
|---|---|---|
| All declared runs failed | 2 | `INCOMPLETE EVIDENCE: ALL DECLARED RUNS FAILED` |
| Some failed, thresholds met | 2 | `INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED` |
| Some failed, threshold violated | 1 | the violation and `INCOMPLETE EVIDENCE: SOME DECLARED RUNS FAILED` |

None of these show PASS. The exit-code scheme is unchanged: 2 means required evidence is missing. v1 and all-success v2 decisions are unchanged. Failures are never inferred, so without a manifest a failed run that left no report cannot be detected.

**Parser change:** nextpnr reports with NaN, infinite, negative or true/false Fmax values, or non-object `fmax`/`utilization`, are now rejected as unsupported input (exit 3).

## Phase 2: observed Fmax ranges

`compare` adds an "Observed Fmax ranges" report section and `res['ranges']` (`qorguard/ranges.py`). It is reporting only: thresholds, verdicts and exit codes do not read it.

**Definitions, per clock and side:**
- **Observation:** a positive, finite `achieved` value from a successful run in `runs[]`. Failed runs and the rounded v1 `metrics` are never used.
- **Min, median, max:** calculated on unrounded values. The median of an even count is the mean of the middle two. Display rounds to 0.001 MHz.
- **Insufficient data:** fewer than 2 observations on either side, or a v1 record on either side. No overlap result is given.
- **Overlap:** `baseline_min <= current_max` and `current_min <= baseline_max`, so ranges touching at one value overlap.

**Qualified results:** an overlap or no-overlap result carries qualifications if:
- device, Yosys version, nextpnr version or constraint files differ or are unavailable;
- clock constraints differ;
- runs failed or attempted runs were not declared;
- seeds are unavailable or differ;
- a clock is missing from some runs.

Clock names are matched exactly, so a renamed clock appears as two clocks with insufficient data.

**Reporting hardening:**
- **Small sample label:** shown when either side has fewer than 5 valid observations. The minimum of 2 for an overlap result is unchanged, and reaching 5 establishes no confidence.
- **Unequal samples label:** shown when the two sides have different observation counts.
- **Escaping:** metric and clock names with a backtick, pipe, backslash or line break are shown as escaped text everywhere in the report. Other names are unchanged. Stored names and matching are unaffected.

## Phase 3: required-clock timing and frequency margin

**Manifest:** `"required_clocks_mhz": {"clk": 48.0}` gives a required frequency per exact clock name. It is recorded in `provenance.required_clocks_mhz` as `declared` or `unavailable`, with its source. It can never be `extracted`, and records from before this phase remain valid without it.

**Formulas, per clock and side, on unrounded values from successful runs:**
- Absolute margin = achieved − required (MHz).
- Percentage margin = (achieved − required) / required × 100.
- Min, median and max margins use the minimum, median and maximum achieved Fmax.
- An observation meets the requirement when achieved >= required. The result is judged on the observed minimum.

These are frequency margins, not period slack.

**Exit code:** a current-side miss exits 1 and the verdict includes `REQUIRED CLOCK NOT MET`, even when every percentage threshold is met. This is the only way timing affects the exit code:
- An exact tie meets the requirement.
- A baseline-side miss alone has no effect.
- A partial failure with a miss exits 1 and keeps the incomplete-evidence section.
- If all current runs failed there is no observation to judge, so it stays exit 2.
- An observed miss also exits 1 when a required metric is missing or all baseline runs failed; the verdict names both.
- A clock neither side declares is informational and does not affect the exit code.
- With no declared requirement, or a v1 record, behaviour is unchanged.

**Requirements that cannot give a clean result (exit 2, unless a known failure makes it 1):**
- `REQUIRED CLOCK NOT EVALUATED`: the current manifest declares a clock with no matching valid observation. Names are never inferred, so a renamed clock lands here. This stays separate from a miss.
- `INCONSISTENT REQUIREMENTS`: the sides declare different values for one clock, or only one v2 side declares one. The report names the clock and the side, and nothing is copied or inferred. It implies no improvement or decline, and the current side's value governs its check. 
- `REQUIREMENT COMPARISON UNAVAILABLE`: one side is a v1 record and the other declares a requirement. A v1 record cannot store one, which is not proof that none existed. Nothing is copied or inferred.

**Exit-code precedence:**
1. A current-side required-clock miss or a threshold violation exits 1, even if all declared runs failed on either side. A threshold row can only fail on values present on both sides, such as Yosys metrics when all nextpnr runs failed.
2. Otherwise, incomplete or all-failed runs, missing evidence, an unevaluated clock, or inconsistent or unavailable requirements exit 2.
3. Exit 0 only when every applicable check was evaluated and met.

**Intentional behaviour change from 0.2.0, on v1 records too:** a threshold violation plus a missing required metric used to exit 2 and now exits 1, with both in the verdict. Not every v1 decision is unchanged. v1 vs v1 comparisons without that combination keep their decision.

Every condition present is named in the verdict.

Tool constraints are shown separately and never replace a requirement. Without a declared requirement, the report says timing compliance cannot be assessed.
