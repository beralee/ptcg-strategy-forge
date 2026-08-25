# PTCG Strategy Forge Agent Charter

## Mission

This repository is the standalone developer toolkit for authoring, testing,
validating, installing, and submitting PtcgDAP data-only `.ptcgai` strategies.
It must remain usable without a checkout of the PtcgDAP game repository.

The public policy boundary is always:

```text
agent(raw_observation) -> list[int]
```

The returned integers are indexes into the current immutable `select.option`
window. An author package is data, not executable Python/GDScript and not an
engine plugin.

## Required reading order

Before changing behavior, read:

1. `README.md`
2. `TODO.md`
3. `docs/01-QUICKSTART.md`
4. `docs/02-PACKAGE-AND-POLICY.md`
5. `docs/03-SCENARIO-TESTING.md`
6. `docs/04-DEBUGGING-AND-OPTIMIZATION.md`
7. `docs/06-SECURITY-AND-PRIVACY.md`
8. `docs/08-ARCHITECTURE.md`
9. `docs/09-STRATEGY-THINKING.md`
10. `docs/10-WORKSPACE-CHECK.md`
11. `docs/14-KAGGLE-STYLE-PTCGBOT-QUICKSTART.md`
12. `docs/15-UCIS-SDK-DEVELOPER-GUIDE.md`
13. `docs/LIMITATIONS.md`

Use `demo/marnie-forge` as the executable reference. The vendored SDK source,
contract hashes, and provenance are locked by
`vendor/ptcgdap-sdk-manifest.json`; the external PtcgDAP checkout is a design
and refresh source, not a runtime dependency.

## Repository map

- `forge.py` / `forge.ps1`: stable developer entrypoints.
- `src/ptcg_strategy_forge/`: Forge orchestration, scenario suites, and SDK
  provenance checks.
- `tools/ptcgdap/`, `scripts/ai/ptcgdap/`: reviewed vendored PtcgDAP tooling
  and policy runtime snapshot.
- `contracts/ptcgdap/`, `data/ptcgdap/`, `data/bundled_user/`: pinned contracts,
  catalog/deck sources, and the accepted template package.
- `demo/marnie-forge/`: RED→GREEN strategy example and strict scenario suite.
- `tests/`: unit, security, determinism, documentation, and workflow tests.
- `evidence/`: public-only reproducible acceptance receipts.

## Non-negotiable policy invariants

1. 当前 `select.option` list is the only legal action frontier.
2. Every accepted choice invalidates the old window. Reobserve, rebuild public
   facts, and rebind semantic intent before the next choice.
3. Never persist an old option index, score, hard tier, constraint, or proof.
   A plan may retain only public semantic goals, stable identities, or debts.
4. Base Graph owns legality, mandatory/terminal protection, hard tiers, veto,
   deterministic fallback, and final adjudication.
5. An adapter may only propose public goals, macros, preferences, or same-tier
   tie-breaks. It cannot execute engine actions or override Base authority.
6. Build public input from an allow-list. Opponent hidden cards, deck order,
   face-down prizes, private RNG, callbacks, tickets, commands, engine objects,
   and credentials never enter policy input or public evidence.
7. Keep identity domains separate. This toolkit's Windows author template uses
   `set_code + "_" + card_index`; it is not an official CABT Card ID, a card
   name, a translation, or a Godot object ID.
8. Unknown fields, enum values, UID mappings, or option shapes fail closed or
   use an audited deterministic fallback.
9. Interface conformance, Godot engine evidence, official CABT parity, device
   acceptance, and production approval are independent claims.
10. A test-fixture signature is never production authority.

## Strategy-thinking discipline

Do not reduce a PTCG turn to one greedy score. Capture strategy at four scales:

1. Match Agenda: win condition, fastest and robust prize schedules, engine and
   attacker roles.
2. Current route: exact resource payment, credible opponent response, current
   attack window, and next-attacker continuity.
3. Information checkpoint: draw/search/reveal/random results invalidate stale
   assumptions and require 重观察 before choosing a conditional suffix.
4. Typed interaction: exact search, discard, assignment, pivot, target, and
   damage-allocation policy for the current window.

The current restricted author IR cannot express an arbitrary conditional
policy graph. Record richer intent in `STRATEGY-BLUEPRINT.md`, then compile only
the currently supported public, current-window portion into adapter rules. Do
not imply that documentation alone grants runtime behavior.

Treat existing Rule/Base behavior as the executable floor. Leave it only when
a public proof or focused scenario demonstrates the advantage. Evaluate prize
progress in attack windows, not only natural turns, and do not call a pivot
"safe" while a credible gust or bench-liability line remains.

## Required development workflow

For every behavior change:

1. Inspect `git status`; preserve unrelated or user-owned edits.
2. Identify the earliest owning layer: observation, identity, package,
   adapter, Base adjudication, interaction, Host, or publishing.
3. Add a focused failing test or scenario and confirm the RED reason.
4. Implement the smallest change in the owning layer.
5. Add the semantic option-reorder case and relevant negative gates.
6. Run targeted tests, then `check` for the affected workspace.
7. Record public evidence, exact hashes, known gaps, and rollback identity.
8. Update `TODO.md`, documentation, and changelog in the same change.

Every macro normally needs positive, missing prerequisite, wrong target,
reordered option, mandatory/terminal, hard-tier/veto, unknown UID, and hidden
field cases. Critical thresholds also need a metamorphic pair that changes one
fact and proves the expected decision flip.

## Standard commands

From the repository root:

```powershell
.\setup.ps1
.\forge.ps1 doctor
.\forge.ps1 check --workspace work\my-strategy --output work\my-strategy\build\my-strategy.ptcgai
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe forge.py demo --output "$env:TEMP\ptcg-strategy-forge-demo"
git diff --check
```

`check` is the default author acceptance lane: two exact builds, byte/hash
comparison, strict Host-path validation, and the entire scenario suite. Its
output remains development-only.

When modifying vendored SDK scope, state the reviewed PtcgDAP source and run:

```powershell
.\.venv\Scripts\python.exe tools\build_sdk_snapshot.py
.\.venv\Scripts\python.exe tools\build_sdk_snapshot.py --check
```

Never hand-edit manifest hashes or silently add vendored files.

## Process and machine safety

- Unit, contract, and current-window simulation tests precede benchmarks.
- Do not launch multiple high-memory Python training, benchmark, replay,
  simulation, or evaluation process pools in parallel on this Windows host.
- For `D:\ai\code\ptcgabc`, use at most `--workers 4` and obey its repository
  safeguards.
- Before a heavy Python run, inspect active Python processes, available
  physical memory, and system commit. Do not start if another heavy run is
  active, commit is at or above 70%, or available RAM is below 12 GiB.
- Never override `PTCGABC_MAX_WORKERS`, `PTCGABC_MAX_COMMIT_PERCENT`,
  `PTCGABC_MIN_AVAILABLE_GIB`, `PTCGABC_MAX_WORKER_PRIVATE_GIB`, or
  `PTCGABC_MAX_POOL_PRIVATE_GIB` without explicit user approval.
- Queue heavy work serially across agents. A passing win-rate benchmark cannot
  waive invalid-action, stale-window, privacy, dirty-game, schema, package, or
  signature failures.

## Evidence and completion

Use RED→GREEN evidence and stable error codes. A task is complete only when its
contract has executable evidence and the report distinguishes:

- implemented behavior;
- public-window simulation only;
- Godot engine witnessed behavior;
- CABT-aligned or engine-differential behavior;
- production-approved behavior;
- known unsupported scope and rollback.

Do not commit, push, publish a release, change an external repository, install a
production strategy, or claim higher authority unless the user explicitly asks.
