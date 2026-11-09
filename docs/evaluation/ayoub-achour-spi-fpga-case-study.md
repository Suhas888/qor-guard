# External evaluation: spi-fpga-core (Ayoub Achour)

**Evaluator:** Ayoub Achour ([@ayoub-ac](https://github.com/ayoub-ac))

**Project:** [spi-fpga-core](https://github.com/ayoub-ac/spi-fpga-core), an SPI master and slave IP core with an AXI4-Lite wrapper

**QoR Guard version:** v0.3.0

This page records an independent evaluation that Ayoub ran on his own design, published with his permission. **The QoR Guard maintainer didn't run these builds.** Every figure and verdict below was supplied by Ayoub.

> **Read these limitations first.**
> - **One device:** the evaluation covers iCE40 UP5K only.
> - **Out-of-context Fmax:** each core was measured inside a register-chain wrapper, so Fmax isn't an in-system result.
> - **Wrapper cells:** `lc` (logic cells) includes the wrapper's flip-flops.
> - **Not hardware:** all figures come from synthesis and place-and-route. None are physical hardware measurements.
> - **ECP5 was found manually:** Ayoub also found a regression on ECP5 by hand. QoR Guard wasn't evaluated on ECP5 and doesn't support it.
> - **Example thresholds:** the 10% Fmax limits come from QoR Guard's example configuration. They're illustrative, not validated engineering limits.
>
> These results don't establish hardware performance, statistical significance, compatibility beyond this setup, or adoption by anyone else.

## Setup (as reported by Ayoub)
- **Device:** iCE40 UP5K, SG48 package
- **Tools:** Yosys 0.70+286 and nextpnr-ice40 0.11.1-85. These are close to, but not the same as, the versions QoR Guard was tested with (0.70+255 and 0.11.1-83).
- **Clock constraint:** 50 MHz
- **Seeds:** 1 to 5 for each build
- **Inputs:** the core's `stat -json` output, plus one nextpnr `--report` JSON per seed
- **Baseline:** every comparison uses v1.0 as the baseline, as in Ayoub's results table, "QoR Guard vs v1.0".
- **Test suite:** Ayoub also ran QoR Guard's tests under WSL on Ubuntu 26.04 with Python 3.11.6, and reports 258 tests: 255 passed and 3 skipped. That is one reported run, not maintainer-tested Linux support.

## Results (as reported by Ayoub)

> Same limitations apply: iCE40 UP5K only, out-of-context Fmax on a register-chain wrapper, `lc` includes wrapper flip-flops, synthesis and place-and-route figures rather than hardware, and illustrative 10% limits.

Fmax across seeds 1 to 5, shown as minimum / median / maximum in MHz:

| Core | v1.0 (baseline) | v1.1, before the timing restructure | v1.1.0 |
|---|---|---|---|
| `spi_top` | 39.9 / 42.3 / 43.6 | 36.5 / 37.1 / 38.3 | 53.4 / 55.6 / 61.5 |
| `spi_axi4lite` | 36.3 / 37.2 / 38.1 | 34.8 / 36.5 / 38.8 | 51.2 / 52.3 / 53.4 |

### spi_top: v1.1 before the restructure, against v1.0
- **Worst seed (`fmax_min`):** 39.9 → 36.5 MHz, −8.5%. That's within the −10% example limit, so **this rule passed**.
- **Median (`fmax_median`):** 42.3 → 37.1 MHz, −12.3%. That's beyond the −10% example limit, so **this rule failed**.
- **Overall: the comparison failed.** QoR Guard checks each rule on its own and fails the comparison if any rule fails, so the median rule alone was enough. Ayoub reports the result as a regression.

The worst-seed rule alone would have passed this change. The median rule caught a drop the worst seed didn't show.

### Later comparisons
Ayoub reports that QoR Guard passed:
- `spi_top` v1.1.0, after the timing restructure, against v1.0;
- `spi_axi4lite` v1.1 before the restructure, against v1.0. The reported figures give −4.1% worst seed and −1.9% median, both within the −10% example limits;
- `spi_axi4lite` v1.1.0 against v1.0.

The overall verdict also depends on the area rules (`lut4`, `ff`, `lc`), whose results aren't reproduced here.

## What this shows, and what it doesn't
**It shows** that, on one UP5K design with five seeds per build, QoR Guard v0.3.0 read Ayoub's own Yosys and nextpnr outputs and flagged a median Fmax drop that a worst-seed check alone wouldn't have.

**It doesn't show:**
- that the Fmax figures reflect hardware performance;
- that the drop was statistically significant: five seeds per side is a small sample;
- that the 10% limits are appropriate for other designs;
- support for other devices, tool versions, operating systems or architectures.

## How QoR Guard reached these verdicts
- **Worst seed:** for each clock, the lowest achieved Fmax across the successful runs supplied.
- **Median:** the middle value after sorting those successful-run Fmax values. With five seeds, that's the third value. With an even count, it's the mean of the two middle values. Both statistics are rounded to 0.001 MHz.
- **Threshold rules:** each Fmax rule compares one statistic between baseline and current, and fails if it falls by more than the configured percentage. The comparison fails if any rule fails.
- **Maximum Fmax:** used only in the report's "Observed Fmax ranges" section. It never affects the verdict.
- **Verdict wording:** a failed comparison prints `REGRESSION` only when run with `--comparison-type revision`, and `THRESHOLD EXCEEDED` otherwise. Which option Ayoub used isn't confirmed, so this page doesn't quote his exact CLI output.

## Maintainer's synthetic check (not a reproduction)
The maintainer doesn't have Ayoub's report files. To check the verdict logic, the test `tests/test_v03_fmax_rules.py` builds **synthetic** reports whose minimum and median match the `spi_top` figures above. The other seed values are invented. It confirms that QoR Guard's code passes the worst-seed rule, fails the median rule and fails the comparison for those numbers.

It isn't an independent reproduction of Ayoub's five-seed results, and it says nothing about his design.

Thanks to Ayoub for taking the time to run this evaluation and share the results.
