# QoR Guard v0.3.0 evaluation checklist

Thank you for trying QoR Guard. Short, honest answers help most, and "not useful" is a valuable answer. **Please don't send confidential design files or reports with local paths.**

## Setup
- [ ] Operating system and version:
- [ ] Python version (`python --version`):
- [ ] Did `python -I -B -m unittest discover -s tests -t .` end with `OK (skipped=3)`? If not, paste the last lines:
- [ ] Did the synthetic example in `docs/QUICKSTART.md` print `THRESHOLD EXCEEDED (exit 1)`?
- [ ] How long did it take to get this far?

## Your own design (optional)
- [ ] iCE40 part, Yosys version and nextpnr-ice40 version:
- [ ] Did your reports capture without errors? If not, paste the error message:
- [ ] Did the numbers match your own reports when you checked a few by hand?

## Usefulness
1. Which parts of the report were useful? For example: thresholds, deltas, utilisation and headroom, Fmax ranges, required-clock check.
2. Which parts were confusing or unnecessary?
3. How do you compare implementation results between revisions today?
4. Has an unnoticed change in area or Fmax ever cost you time? Roughly how often?
5. What's missing that would make you use it again?
6. Would you use it again? Why or why not?

## Anything else

---

**Known limits, so you don't have to report them:**
- iCE40 only; tested on Windows only.
- Example thresholds are illustrative.
- No CI integration.
- No ECP5, Vivado or Quartus support.
