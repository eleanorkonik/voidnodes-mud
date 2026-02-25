# Feature: Inventory Slots System

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | Explorer can only carry limited items from zones: 1 large, 2 medium, 20 small | Core goal |
| R1 | Items have a size classification (small/medium/large) | Must-have |
| R2 | Base slots are free — no check needed to fill them | Must-have |
| R3 | Overflow slots available via skill checks with escalating difficulty | Must-have |
| R4 | Endure maps to "strength" (large overflow), Navigate/Scavenge maps to "dexterity" (small overflow) | Leaning yes |
| R5 | Artifacts can modify capacity (free tool carrying, increased large slots) | Nice-to-have |
| R6 | Worn items don't count against inventory slots | Must-have |
| R7 | Stackable items: 1 stack = 1 slot, stacks cap at 5 | **Decided** |
| R8 | Zone limits (1L/2M/20S) for expeditions. Skerry has generous storage (e.g. 5L/10M/100S), upgradable via BUILD | **Decided** |
| R9 | Miria has her own zone capacity when visiting via beacons | Must-have |

## Shape: Size-Tagged Items with Overflow Skill Checks

| Part | Mechanism | Files |
|------|-----------|-------|
| **A1** | Add `"size": "small"|"medium"|"large"` field to every item in `items.json`. Default untagged = "small". | `data/items.json` |
| **A2** | `Character.slot_capacity` dict: `{"large": 1, "medium": 2, "small": 20}`. Tracked in character state. | `engine/models.py` |
| **A3** | `_check_capacity(item)` helper in items.py. Counts current inventory by size. If at cap, triggers overflow check. If overflow fails, TAKE is denied with message. | `commands/items.py` |
| **A4** | Overflow skill checks: Endure for large items (DC starts at 2, +2 per extra), Navigate for small items (DC starts at 2, +2 per extra). Medium uses the higher of Endure/Navigate. Each overflow costs 1 FP. | `commands/items.py` |
| **A5** | INVENTORY display shows slot usage: `[Large: 1/1] [Medium: 0/2] [Small: 8/20]` | `commands/examine.py` |
| **A6** | Artifact capacity bonuses: add `"capacity_bonus"` field to artifacts. E.g., Stabilization Engine KEEP: `{"small": +5}`. Applied in `_on_artifact_kept()`. | `data/artifacts.json`, `commands/artifacts.py` |
| **A7** | Save migration: `setdefault` for `slot_capacity` on characters, `size` on items. | `main.py` `_migrate_state()` |

## Implementation Status

Items already have `size` field tagged (19 items). Overflow check with FP cost + skill check already wired in `commands/items.py`. INVENTORY slot display and artifact bonuses may still be needed.
