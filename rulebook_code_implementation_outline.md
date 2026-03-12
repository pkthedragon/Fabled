# Rulebook Sync — Code Implementation Outline

This outlines all code updates required after aligning `rulebook.txt` to the provided rules text.

## A) Data layer updates (`data.py`)

1. **Reorder class basic ability pools to match Appendix B order**
   - Update `CLASS_BASICS["Fighter"]` from `[STRIKE, REND, CLEAVE, FEINT, INTIMIDATE]` to `[STRIKE, REND, FEINT, CLEAVE, INTIMIDATE]`.
   - Update `CLASS_BASICS["Ranger"]` from `[HAWKSHOT, VOLLEY, TRAPPING_BLOW, HUNTERS_MARK, HUNTERS_BADGE]` to `[HAWKSHOT, VOLLEY, HUNTERS_MARK, TRAPPING_BLOW, HUNTERS_BADGE]`.

2. **Lucky Constantine signature option order**
   - Change `sig_options` order from `[CONSTANTINE_S1, CONSTANTINE_S2, CONSTANTINE_S3]` (Subterfuge first) to the rulebook order with Feline Gambit first.
   - Either:
     - swap definitions so `CONSTANTINE_S1` = Feline Gambit / `CONSTANTINE_S2` = Subterfuge, or
     - keep IDs but change `sig_options` list ordering safely.

3. **Hunold signature definition/order and effect update**
   - Reorder so Dying Dance is Sig 2 and Hypnotic Aura is Sig 3.
   - Update Dying Dance frontline mode to: 60 power + "Shock Weakened targets for 2 rounds".
   - Keep backline as Weaken 2 rounds.

4. **Reynard signature option order**
   - Reorder so Size Up is Sig 1 and Feign Weakness is Sig 2 (currently inverse).

5. **Sea Wench Asha signature option order**
   - Reorder so Abyssal Call is Sig 1 and Misappropriate is Sig 2 (currently inverse).

6. **Add missing item: Family Seal**
   - Add new `Item` constant (e.g., `FAMILY_SEAL`) with passive effect:
     - description: "User's signature ability deals +10 damage"
     - implementation key/field for +10 signature-only damage.
   - Insert `FAMILY_SEAL` into `ITEMS` list in Appendix C order.

## B) Logic layer updates (`logic.py`)

7. **Crumb Trail pickup heal amount**
   - Change Crumb Trail pickup healing from 30 to 40 HP in swap-resolution handling.
   - Update any combat-log text for this event to `(+40 HP)`.

8. **Implement Family Seal damage modifier**
   - Add a signature-ability damage bonus path (+10 flat damage) that applies only when:
     - source has Family Seal equipped,
     - action is a signature ability,
     - action actually deals damage.
   - Ensure it does not affect:
     - basic abilities,
     - items,
     - status-only abilities with no damage,
     - retaliation/proc damage unless explicitly intended as signature-instance damage.

9. **Implement Hunold Dying Dance conditional Shock**
   - Add or update special handling so frontline Dying Dance:
     - deals 60 power,
     - applies Shock (2 rounds) only if target is currently Weakened.
   - Confirm this interacts correctly with existing Shock/recharge systems.

## C) UI/selection & content integrity (`main.py` and loaders)

10. **Signature and basics presentation order consistency**
   - Ensure draft/loadout menus present signatures and basics in the same order as `rulebook.txt`.
   - Verify no hard-coded assumptions depend on the old ordering indices.

11. **Saved-team compatibility audit**
   - Validate that existing saved loadouts referencing signature by ID remain valid after reordering.
   - If any code stores signature by index instead of ID, add migration or index-stability guardrails.

## D) Tests / audit coverage to add or update

12. **Unit/integration tests for updated rulebook deltas**
   - Add tests for:
     - Crumb Trail pickup heals exactly 40.
     - Hunold Dying Dance frontline conditional Shock behavior.
     - Family Seal gives +10 only to signature damage.
     - Signature ordering for Constantine/Hunold/Reynard/Asha.
     - Class basic order for Fighter/Ranger.

13. **Update existing audits**
   - Extend `audit_game_systems.py` (or add new audit module) with assertions for the above.
   - Include regression checks to prevent order regressions in future edits.

## E) Documentation and parity checks

14. **Re-run rulebook parity pass after code changes**
   - Confirm `rulebook.txt`, `data.py`, and user-facing selection/order are synchronized.
   - Optionally add a script that compares rulebook-driven expected ordering against data structures.

---

## Suggested implementation order (lowest risk)
1. Data ordering changes + Family Seal definition (`data.py`).
2. Logic updates (Crumb Trail heal, Family Seal effect, Dying Dance condition) (`logic.py`).
3. UI/selection consistency checks (`main.py`).
4. Tests/audits.
5. Final parity verification and release notes.
