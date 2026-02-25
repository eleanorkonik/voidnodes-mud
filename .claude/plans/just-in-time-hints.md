# Feature: Just-in-Time Hints (Replace Tutorial)

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | No formal tutorial phase — game feels like "real play" from keystroke one | Core goal |
| R1 | Hints triggered by context, not sequence | Must-have |
| R2 | Player never blocked (existing hard rule, extended) | Must-have |
| R3 | Hints feel like the world seed speaking naturally | Must-have |
| R4 | First-time players still learn all core mechanics | Must-have |
| R5 | Prologue narrative (awakening, bonding, meeting Sevarik) preserved as story, not tutorial | Must-have |

## Shape: Dissolve Tutorial into Command Handlers

Delete `engine/tutorial.py`. Each command handler checks a one-time flag and shows a seed hint on first relevant encounter. Several handlers already do this (recruit INVOKE hint, garden walkthrough).

| Part | Mechanism | Files |
|------|-----------|-------|
| **B1** | Delete `engine/tutorial.py` and all imports/references | `engine/tutorial.py`, `main.py` |
| **B2** | First-use hints in combat: ATTACK → combat hint, EXPLOIT → advantage hint, INVOKE → contrast with EXPLOIT | `commands/combat.py` |
| **B3** | First-use hints in movement: first enemy room → danger hint, first NPC room → "survivor here", first artifact room → "something powerful" | `commands/movement.py` |
| **B4** | First-use hints in social: RECRUIT → puzzle hint, SCAVENGE → crafting hint, SWITCH → dual-character rhythm | `commands/npcs.py`, `commands/story.py`, `main.py` |
| **B5** | Central `HINT_TEXT` dict for all hint copy (editable in one place) | New `engine/hints.py` or inline |
| **B6** | Remove prologue phase from parser. Game starts in explorer phase, Day 1. BOND/naming/Sevarik-meeting as scripted opening events. | `main.py`, `engine/parser.py` |
| **B7** | Remove SWITCH blocking and all tutorial gate logic | `main.py` |
| **B8** | Rewrite all hint text from imperative ("Try ATTACK") to seed-voice ("Those creatures look dangerous") | All hint text |
| **B9** | Save migration: convert old `tutorial_step` to `hints_shown` flags | `main.py` |

## Open Questions

1. Does "no tutorial" mean removing the prologue phase entirely? Proposed: yes, fold the narrative (BOND, naming, Sevarik meeting) into Day 1 explorer phase as scripted events.

## Implementation Status

Tutorial still exists as `engine/tutorial.py`. Some handlers already have first-use hints (building hints, recruit hints, NPC greeting hints). Prologue phase still active.
