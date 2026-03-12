# Rulebook Diffcheck Report (Provided Rulebook Text vs `rulebook.txt`)

This report is a full re-check against the provided rulebook text in the request, with emphasis on **ordering differences** and **content mismatches** (including Appendix B basics and Appendix C items).

## 1) Core rules / intro mismatches

1. **Intro wording**
   - `rulebook.txt`: "you have the **pocketbooks** to hire the best of the best"
   - Provided text: "you have the **pocketbook** to hire the best of the best"

2. **Class-count statement**
   - `rulebook.txt`: "Adventurers belong to one of **six** classes."
   - Provided text: "Adventurers belong to one of **eight** classes."

## 2) Appendix A — Adventurer definition mismatches

3. **Witch-Hunter Gretel — Crumb Trail (backline) heal amount**
   - `rulebook.txt`: bread crumb pickup heals **30 HP**
   - Provided text: bread crumb pickup heals **40 HP**

4. **Lucky Constantine — signature order differs**
   - `rulebook.txt`: Sig 1 = **Subterfuge**, Sig 2 = **Feline Gambit**
   - Provided text: Sig 1 = **Feline Gambit**, Sig 2 = **Subterfuge**

5. **Hunold the Piper — signature order and effect text differ**
   - `rulebook.txt`:
     - Sig 2 = **Hypnotic Aura** (passive redirection)
     - Sig 3 = **Dying Dance** (Frontline: 50 power, Weaken; Backline: Weaken)
   - Provided text:
     - Sig 2 = **Dying Dance** (Frontline: 60 power, shocks Weakened targets)
     - Sig 3 = **Hypnotic Aura**

6. **Reynard, Lupine Trickster — signature order differs**
   - `rulebook.txt`: Sig 1 = **Feign Weakness**, Sig 2 = **Size Up**
   - Provided text: Sig 1 = **Size Up**, Sig 2 = **Feign Weakness**

7. **Sea Wench Asha — signature order differs**
   - `rulebook.txt`: Sig 1 = **Misappropriate**, Sig 2 = **Abyssal Call**
   - Provided text: Sig 1 = **Abyssal Call**, Sig 2 = **Misappropriate**

## 3) Appendix B — Basic ability ordering mismatches (the part you called out)

8. **FIGHTER basic ordering differs**
   - `rulebook.txt` order: Strike, Rend, **Cleave**, **Feint**, Intimidate
   - Provided text order: Strike, Rend, **Feint**, **Cleave**, Intimidate

9. **RANGER basic ordering differs**
   - `rulebook.txt` order: Hawkshot, Volley, **Trapping Blow**, **Hunter’s Mark**, Hunter’s Badge
   - Provided text order: Hawkshot, Volley, **Hunter’s Mark**, **Trapping Blow**, Hunter’s Badge

## 4) Appendix C — Item list mismatch

10. **`Family Seal` missing from `rulebook.txt`**
   - Provided text includes:
     - **Family Seal** (Passive): "User's signature ability deals +10 damage"
   - `rulebook.txt` omits this item entry and goes from Ancient Hourglass to Holy Diadem.

## 5) Additional textual quality issues present in `rulebook.txt`

11. **Typo in Noble basics**
   - `rulebook.txt`: "target **gas** -10 speed" and "target **gas** -10 attack"
   - Provided text contains the same typo in the supplied text, but this is still a correctness issue in the canonical file.

---

## Summary
The previous report was incomplete. Beyond the earlier noted differences, there are additional verified mismatches in:
- Adventurer signature ordering (including **Sea Wench Asha**),
- Appendix B basic ability ordering (**Fighter** and **Ranger**),
- Appendix C item inclusion (**Family Seal** missing in `rulebook.txt`).

This report now captures those omissions explicitly.
