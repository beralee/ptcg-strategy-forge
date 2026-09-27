# Controlled outcome training (development research)

This optional research toolkit starts from an explicitly frozen rule package
and qualified public representation. It measures action-outcome comparisons
for a learned ranking head beyond behavior imitation.
Implementation and measured playing strength are separate gates.

## Single-action replay intervention

`tools/controlled_branch_policy.gd` is an isolated research-harness wrapper. It
delegates every normal decision to the exact frozen rule policy. At one specified
public window it binds a complete semantic option to the newly issued Base
frontier. Disabled, stale, ambiguous, multi-choice, or out-of-frontier requests
are rejected. The original Base audit is retained; a research intervention must
never be relabeled as an executed teacher action.

The wrapper has no access to the game state, RNG, hidden opponent information,
or engine execution methods. The regular development owner validates and
submits its current indexes. The harness rejects missing or repeated
interventions. No wrapper code is included in a `.ptcgai` package.

`controlled_branch.qualify_pair` requires matching runtime, packages, seed and
seat, a clean terminal result, an identical complete public observation/action
prefix, the same target frame, and the requested Host-accepted action. The
deterministic engine is replayed from initial seed; this is **not** a general
snapshot/restore API. No post-action RNG reset is performed. Different actions
may consume randomness differently.

A terminal win difference is a single-seed paired outcome sample, not proof of
expected action value. Tied outcomes remain unknown and produce no preference.
Related windows, alternatives and option permutations stay in the same seed
group. Independent confirmation seeds never supply training labels.

## Small output-head correction

`preference_head.fit_head` freezes the input encoding and hidden network. It
updates the 48 output weights using a BC retention term and a bounded-weight
pairwise logistic term. The output bias is also frozen because it cancels in
both objectives. Validation selects checkpoints; full-game confirmation is
separate. Frozen parameters are checked byte-for-byte after training.

This introduces no confidence claim, online learning, PPO, or private input.
Until a narrower deployment gate is implemented and tested, exported actors
retain the existing Base-authorized single-choice scope. A specialist training
task alone does not narrow the Host's deployment behavior.

## Reproducible scope

The public SDK ships the generic intervention binder, pair qualification,
preference-head trainer and tests. Personal packages, datasets, trained weights
and experiment directories are not distributed. Run contract and current-window
tests before any engine evaluation, and follow `30-TRAINING-MACHINE-STABILITY.md`
for serial supervised jobs.

`combined_loss` and exploratory `task_first` checkpoint policies are development
selectors. Preference accuracy is not full-frontier correctness or a win rate.
A single altered action followed by rule continuation does not prove repeated
model deployment helps; model continuation and a narrower deployment gate remain
separate work. The scheduler rejects model continuations. Independent grouped
confirmation is required for playing-strength claims.
