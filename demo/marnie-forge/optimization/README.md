# Optimization fixture

`baseline_adapter.json` keeps the same valid IR and rule identity but intentionally requires the wrong hand-card UID for `forge.morgrem.evolve`. The primary positive scenario therefore selects deterministic fallback index `0` and fails its expected index `1`.

The final package fixes that predicate to `CSV10C_147`. `python forge.py demo` proves the baseline RED, then builds the optimized package twice, validates byte identity, and runs the complete scenario suite GREEN.
