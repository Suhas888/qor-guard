# Test fixtures

Everything under `synthetic/` is synthetic. `tests/fixture_generator.py` generates the files from invented values and names, and `synthetic/FIXTURE_HASHES.json` lists their hashes.

**They are not tool output and contain no data from a real design.** They follow the layouts QoR Guard parses, so passing tests show that the code handles those layouts. They do not show that real tool output parses correctly, and they validate no hardware behaviour.

The `0.70+255` version text and the HX8K capacity of 7680 logic cells are there so the parsers have realistic values to read. Short labels such as `=== design hierarchy ===` follow the wording in Yosys output, because the parsers look for them.

## Terms

These fixtures and `tests/fixture_generator.py` are supplied for running this project's tests. They are **not covered by the project's MIT License, and no separate reuse licence is granted.**
