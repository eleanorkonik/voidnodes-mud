# Feature: Programmable Aspects (Skill Affinities)

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | Aspects declare which skills they naturally align with | Core goal |
| R1 | Invocation is context-aware (knows if aspect matches the skill being rolled) | Must-have |
| R2 | Generic INVOKE still works for any aspect + any skill (FATE flexibility preserved) | Must-have |
| R3 | Mechanical differentiation: matching invoke is better than non-matching | Must-have |
| R4 | Data-driven: skill associations in JSON, not hardcoded | Must-have |
| R5 | Backward compatible: untagged aspects work exactly as today (+2) | Must-have |

## Shape: Affinity Tags with Tiered Bonuses

New file `data/aspect_affinities.json` maps aspect strings to skill lists. Central lookup — one source of truth.

**Bonus tiers:** +3 for affinity match, +2 for non-match or untagged.

| Part | Mechanism | Files |
|------|-----------|-------|
| **A1** | New `data/aspect_affinities.json`: maps ~40-50 aspect strings to skill lists | New file |
| **A2** | Load affinities in `Game.__init__`, store as `self.aspect_affinities` | `main.py` |
| **A3** | `pending_invoke_affinities` field alongside existing `pending_invoke_bonus` | `main.py` |
| **A4** | `_consume_invoke_bonus(skill_name)` gains a parameter. Returns +3 if match, +2 otherwise. | `main.py` + 6 call sites |
| **A5** | INVOKE menu shows skill affinities inline next to aspect names | `commands/combat.py` |
| **A6** | Narration flavor: "your training surges" (match) vs "not your strongest angle" (stretch) | `commands/combat.py` |

## Implementation Status

`aspect_affinities.json` has NOT been created. Engine code and invoke handler exist but don't check affinities yet.
