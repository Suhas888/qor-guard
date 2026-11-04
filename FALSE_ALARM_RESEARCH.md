# False-alarm research: nextpnr seed variation

**This release does not include the experimental dataset or its numerical findings.** They come from private experiments and cannot be reproduced from this release, so this document explains the question and method only.

## The question

How much do implementation results vary across placement-and-routing seeds, and how often could that variation trigger a threshold rule on a change that does not really alter quality of results?

## Why single-run comparisons can mislead

nextpnr's placement and routing depend on a seed. Changing the seed can change the achieved Fmax of the same netlist. A small source change can also disturb placement, even if it doesn't change what the design does.

With one run per side, a change in Fmax can come from the design change, from this variation, or from both, and the comparison can't separate them. A run count per side lets QoR Guard show an observed range, but it doesn't remove the problem.

## General method

1. Run place and route on the same netlists with several seeds.
2. Measure the spread of Fmax across seeds for each netlist.
3. Resample those results to estimate how often a threshold rule would fire when comparing two sets of seeds.

Step 3 relies on an **unverified assumption**: that a functionally trivial change disturbs placement about as much as choosing new seeds. If small changes disturb placement less, the estimate would be too high. If they also change synthesis results, it could be too low.

## What ranges do and do not show

QoR Guard's observed Fmax ranges report the minimum, median and maximum of the runs you supply. They describe those runs only:

- Overlapping ranges don't show that two sides perform alike.
- Separate ranges don't show that one side is really faster.
- Neither is a statistical confidence result, and more seeds alone don't make it one.

Threshold results are also not validated regression detection.

## Status of the shipped thresholds

The values in `config/thresholds.example.json` are illustrative. **Examples only: not validated recommendations or statistically calibrated thresholds.** Their false-alarm and missed-regression rates on real changes haven't been measured. Seed-aware thresholds remain experimental, and no validated public preset is provided. Choose limits using your own results.

## Proposed experiment (not started)

To measure false alarms directly:

1. Take several designs of different sizes.
2. Create semantics-preserving variants of each, such as renamed nets, reordered ports, equivalent expressions or a split module, and prove equivalence formally.
3. Run synthesis and place and route for each variant across several seeds.
4. Measure how often each threshold rule fires, and whether variant Fmax falls within the original's seed distribution.
5. Choose thresholds from those measurements, then check that they still detect real regressions.
