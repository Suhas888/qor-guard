# Third-party notices

QoR Guard uses only the Python standard library. It bundles no third-party code and has no dependencies. `tests/legacy_v020/` is an unmodified copy of this project's own 0.2.0 code, used to create older-format records for compatibility tests.

No Yosys or nextpnr output is distributed. Yosys and nextpnr are not bundled, and their own licences apply to those tools. The synthetic fixtures are written to match the file layouts those tools produce, and reuse short labels from Yosys output so the parsers can read them.

See `tests/fixtures/README.md` for fixture terms.
