# Consequence Healing: Treat in Place

## Context

FATE tabletop uses a slot-downgrade model for consequences: severe→moderate→mild→auto-heal. When a lower slot is occupied, treatment is blocked. In a MUD, this means a fully injured player (all 3 slots filled) can do *nothing* except grind zone clears until mild auto-heals. That's terrible UX.

Switching to "treat in place": consequences stay in their original slot and recover through treatment steps. Same total resource investment as before, no slot conflicts ever.

**Key discovery:** Consequence penalties (-2/-4/-6) are NOT applied to any rolls. They're only used for damage absorption capacity. This means "treat in place" is purely about clearing slots over time — no penalty math needed.

---

## Design

### Recovery Model

Each consequence has a `recovery` counter (starts at 0). Each successful treatment increments it by 1. Treatment DC and gating are based on **effective severity** — the original severity shifted down by recovery steps.

| Original | recovery=0 | recovery=1 | recovery=2 |
|----------|-----------|-----------|-----------|
| **Severe** | severe (DC 4, 3-zone gate) | moderate-equiv (DC 2, no gate) | mild-equiv (auto-heals) |
| **Moderate** | moderate (DC 2, no gate) | mild-equiv (auto-heals) | — |
| **Mild** | mild (auto-heals) | — | — |

**Total effort is identical to the old downgrade model:**
- Severe: gate(3 clears) → treatment(DC 4) → treatment(DC 2) → auto-heal(3 clears)
- Moderate: treatment(DC 2) → auto-heal(3 clears)
- Mild: auto-heal(3 clears)

### Slot Occupation

The consequence stays in its original slot until fully cleared. A recovering severe consequence still blocks the severe slot — you can't absorb new severe-level damage there. Being injured still matters.

### Data Model

Add `recovery` field to `consequence_meta` entries:

```python
"explorer_severe": {
    "taken_at": 5,        # zones_cleared when taken or last treated
    "cure": "bandages",
    "recovery": 0          # 0=fresh, 1=one step done, 2=two steps done
}
```

### Display

**REQUEST TREATMENT:**
```
  Severe: Clawed by Drift Beast
    Recovering (1/2 treatments). Next: Bandages (have) + Lore check (Fair)

  Severe (healing): Clawed by Drift Beast
    Healing naturally. 2 zone clears remaining.

  Moderate: Wounded by Alpha Thorn
    Treatable. Needs: Bandages (have) + Lore check (Fair)
```

**STATUS:** Show `*` suffix on recovering consequences:
```
  Consequences: severe*: Clawed by Drift Beast, moderate: Wounded by Alpha Thorn
```

---

## Files to Modify

### `engine/aspects.py` — Core healing logic

- New helper `_effective_severity(original_sev, recovery)` — returns the effective severity tier
- Rewrite `can_treat_consequence()`: remove slot-occupied block, use effective severity for DC/gates. If effective severity is "mild" → "This injury is healing on its own."
- Rewrite `check_mild_auto_heal()` → `check_auto_heal()`: iterate ALL consequence slots, check if any have reached mild-equivalent via recovery, clear those if enough zone clears passed. Return list includes original severity for display.
- Update `TREATMENT_DIFFICULTY` lookup to use effective severity

### `commands/npcs.py` — REQUEST TREATMENT handler

- `cmd_request` display: show recovery progress (e.g., "1/2 treatments"), effective DC, next step
- Treatment success: increment `recovery` in meta, update `taken_at` to current zones_cleared
- Remove all slot-moving code (no more `char.consequences["moderate"] = con`). Consequence stays in its slot.
- When effective severity reaches mild-equivalent after treatment, display "It will heal on its own after a few zone clears."

### `engine/subtasks.py` — NPC auto-healing

- `_handler_tend_wounds()`: check ALL slots for mild-equivalent consequences (not just `cons["mild"]`), apply apothecary tier bonus (2 clears instead of 3)

### `commands/examine.py` + `engine/display.py` — Display

- STATUS display: add `*` to recovering consequences
- CHARACTER SHEET: show recovery status on consequence aspects

### `commands/combat.py` — Consequence naming

- When recording a new consequence in `consequence_meta`, include `"recovery": 0`

### `engine/save.py` — Migration

- Add `"recovery": 0` default to existing `consequence_meta` entries that lack it

### `commands/artifacts.py` — Auto-heal caller

- Update call to renamed `check_auto_heal()` function (was `check_mild_auto_heal`)
- Handle new return format that includes original severity

---

## Verification

1. Take a severe consequence in combat. REQUEST TREATMENT → verify DC 4 shown, zone gate applied
2. Clear 3 zones. REQUEST TREATMENT → verify treatment available, DC 4
3. Succeed treatment → verify "1/2 treatments done", consequence stays in severe slot
4. REQUEST TREATMENT again → verify DC 2 (moderate-equiv), no zone gate
5. Succeed treatment → verify "Healing naturally. X zone clears remaining."
6. Clear zones → verify consequence auto-clears
7. Fill all 3 slots (severe + moderate + mild). REQUEST TREATMENT → verify no treatment is blocked due to slot conflicts
8. Treat moderate → verify it stays in moderate slot, enters auto-heal
9. REST with apothecary NPC → verify `_handler_tend_wounds` picks up mild-equivalent consequences
10. STATUS → verify `*` suffix on recovering consequences
