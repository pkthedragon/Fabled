# Battle Log vs Rulebook Discrepancy Report

## Scope
This report compares `battle_log.txt` to `rulebook.txt` for the exact party composition and actions shown in the provided combat log.

## Confirmed discrepancies / likely implementation bugs

1. **Swap action limit is violated (multiple swaps in one turn).**
   - Rulebook: each adventurer can select one action, and swap can only be selected once per turn.
   - Log evidence: P1 executes two separate swaps in the same turn in Round 2 (`Aldric ... swap ↔ Porcus III` appears twice in the same action block), and the same pattern repeats in later rounds.
   - Impact: players can gain illegal extra movement tempo and action economy.

2. **Action execution identity/order appears to drift after swaps (same unit acts twice).**
   - Rulebook: action order resolves clockwise starting from frontline, with one action per adventurer.
   - Log evidence: in multiple rounds, one adventurer appears to act twice while another does not (e.g., Round 2 and Round 3 P1 action blocks).
   - Impact: deterministic turn resolution is broken; outcomes become inconsistent with intended rules.

3. **Aldric's `Sanctuary` heal values do not match the documented formula.**
   - Rulebook (`Sanctuary`): frontline = allies heal 1/10 max HP each round; backline = frontline ally heals 1/8 max HP each round.
   - Log evidence: end-of-round heals are variable and often equal recent damage taken (e.g., Porcus heals 24 after taking 24, Aldric heals 33 after taking 33), not fixed fractions of max HP.
   - Impact: major sustain balance bug for Cleric comps.

4. **`Medic` cleansing behavior is applied globally through passive round healing flow.**
   - Rulebook (`Medic`): only the **user's healing effects** remove statuses/debuffs.
   - Log evidence: recurring end-of-round sequence applies healing + cleansing to all allies every round via passive flow (`Medic: ... cleansed ...`) even when no explicit active healing was cast by Aldric that turn.
   - Impact: status-heavy strategies are unintentionally hard-countered.

5. **`Protection` (+Defense passive) appears duplicated on Aurora (self double-count bookkeeping).**
   - Rulebook (`Protection` backline): allies have +5 Defense.
   - Log evidence: round snapshots repeatedly show Aurora with two `defense+5` buff entries while teammates have one.
   - Impact: buff bookkeeping/state tracking inconsistency; can create duration/tick side effects.

6. **`Innocent Heart` is triggered by nonstandard/ambiguous status expiry (`reflecting_pool`).**
   - Rulebook: trigger occurs when Aurora/allies lose a **status condition**.
   - Log evidence: `Innocent Heart` procs when `reflecting_pool` expires, although Lake's Gift grants "effects of Reflecting Pool" and Reflecting Pool is a talent effect, not listed among standard status conditions.
   - Impact: unintended extra healing/defense procs over long fights.

7. **`Innocent Heart` proc multiplicity likely over-triggers in the same round.**
   - Rulebook default stat rule: buffs generally do not stack unless stated otherwise.
   - Log evidence: one adventurer losing multiple statuses in one end phase causes repeated `Innocent Heart` procs and multiple +10 Defense buff instances to be added in parallel.
   - Impact: excessive proc volume; even if only highest buff applies, repeated heals to Aurora inflate sustain.

8. **Illegal targeting against Ashen Ella in backline (`Two Lives` untargetable clause).**
   - Rulebook (`Two Lives`): Ella is untargetable while in backline.
   - Log evidence: Round 9 includes `Dictate of Nature` targeting Ashen Ella while she is in backline.
   - Impact: core character identity is bypassed; target validation bug.

9. **Round-start passive guard from `Porcine Honor` is inconsistently represented in duration/state timing.**
   - Rulebook: frontline Porcus (or frontline ally when Porcus is backline) is guarded at beginning of round for 1 round.
   - Log evidence: guard is frequently reapplied/cleansed/reapplied through end-round passive chains, creating hard-to-reconcile state timing and intermittent disappearance of expected guard holder.
   - Impact: mitigation windows are difficult to reason about and likely diverge from design intent.

## Secondary observations (possibly intended, but worth verifying)

- Damage arithmetic itself generally matches formula + modifiers (spread, Guard reduction, Fleetfooted reduction, etc.).
- Duplicate buff entries often still evaluate to the highest value only, which suggests the evaluator partly follows non-stacking stat rules even while state storage is noisy.

## Suggested fix order

1. Fix action selection/execution integrity first (one action per adventurer; one swap per turn).
2. Fix passive end-of-round healing pipeline (`Sanctuary`, `Medic`, `All-Caring`) to strictly follow rulebook trigger ownership.
3. Normalize status model (what is a status vs. effect), then gate `Innocent Heart` triggers accordingly.
4. Enforce targeting validation for `Two Lives` before action resolution.
5. Clean buff bookkeeping (dedupe/refresh behavior) to avoid duplicate instances of equivalent buffs.
