# Voidnodes MUD — Session Learnings

Extracted from Claude Code session logs. Things learned through building, playtesting, and iterating that aren't obvious from reading the code.

## Eleanor's Hard Rules

1. **Don't alias new commands to existing ones.** OFFER is NOT a FEED alias. Each verb gets its own `cmd_*` handler so they can diverge later. "I give you full commands FOR A REASON."

2. **Zone crossing must be an explicit, affirmative command.** Eleanor said "what the fuck, no no no" when GO auto-forwarded to ENTER VOID. SEEK is always deliberate. Never auto-cross zones.

3. **Don't show the Quick Reference command dump during gameplay.** It breaks immersion. Tutorials teach commands contextually; `HELP` exists for those who want it.

4. **NPCs and enemies must NOT share rooms.** Eleanor found it narratively incoherent for Emmy to stand next to a rat swarm. Each room is either safe (NPCs) or dangerous (enemies). This required moving enemies and NPCs to separate rooms in the Debris Field.

5. **Recruit puzzle must require genuine strategy.** "If it's winnable with locally optimal decisions instead of needing to think ahead it's boring." Validated with DFS solver — greedy solver fails 12/19 boards, confirming real lookahead is needed.

6. **KEEP and OFFER are skerry-only.** Can't resolve artifacts in the field. Must bring them home first.

7. **Tutorial starts with the protagonist (Miria), not "the explorer."** Frame the player's connection to the story before splitting into roles.

## Naming & Terminology

- **Stage 0** renamed from "Mote" to "Seed" — avoids confusion with mote currency.
- **"Scavenging" -> "Salvage"** for NPC task assignment verb.
- **Removed hardcoded "tuft" references** — use player-chosen seed name everywhere.
- **`tuft_speak` -> `seed_speak`** throughout codebase.
- **Removed "Type" from tutorial prompts** — "Try BOND" not "Type BOND". More natural.
- **Phase framing uses seed name**, not "You're X right now."
- **Growth stage names match cosmology lore**, not generic fantasy labels.
- **Recruit board hex** shown as "Conversation variant: A7F3B2" (dim text) — "Board: A7F3B2" "completely breaks immersion."
- **Recruit movement verbs:** Wheedle/Appeal/Suggest/Describe (personality-flavored), not compass directions.

## Display & Formatting

- **Zone aspect goes in the single "Aspects:" line** — NOT a separate "Zone:" line. Eleanor explicitly rejected the separate line.
- **1 aspect per room** — each room gets exactly one situation aspect as its high concept (physical feature, positioning, obstacle, or contextual detail). The zone aspect displays alongside it automatically, so the player sees 2 total.
- **No commas in aspect names** — comma-separated display makes them ambiguous. Use parentheses instead.
- **Aspects should ALWAYS be magenta** (`display.aspect_text()`). Seed dialogue mentioning aspects must color them.
- **Mote economy is visible** — no hidden numbers. Player always knows exact mote count and distance to next stage.
- **Remove stage names from player-facing display** — show "motes to maturation" instead.
- **Quit text must be in-character.** "Farewell, wanderer. The void remembers." was "pretty terrible." Now: seed puts player in stasis.

## Bugs & Gotchas

### Unicode Banner Misalignment
Unicode characters (sparkles etc.) have different byte width vs display width. Fixed with `unicodedata.east_asian_width()`. Don't trust `len()` for display width.

### cmd_go Silent Teleport
Setting `explorer_location` BEFORE the zone boundary check caused silent location corruption when the move was rejected. Always validate before mutating state.

### SEEK "A" Bug
`aspect.split()[0].upper()` on "A Dead Ship Still Full of Secrets" produced "A" as the hint word. Fixed with `_aspect_hint_words()` helper that skips articles and prepositions.

### Double Output on Zone Boundary
`cmd_go` zone rejection AND tutorial `_show_sensed_nodes` both firing when player tries to walk off the zone edge. Only one should fire.

### ENTER VOID Loop
At landing pad: `e` -> "use ENTER VOID" -> `enter void` -> picker -> `e` -> infinite loop. Fixed by showing the exact full command needed.

### OFFER Not Finding Worn Items
Items in the `worn` dict weren't checked when looking up artifacts for OFFER. Both `inventory` and `worn` must be searched.

### Tutorial Advancing on Failed Commands
Tutorial step was advancing even when GO failed (invalid direction, blocked exit). Only advance on successful execution.

### Recruit Gray/Green Confusion
Gray (W) tiles visually confused with Green (G) in terminal. Replaced Gray with Orange (O).

### Dynamic Dispatch Eliminated Wiring Bugs
SEEK existed as `cmd_seek()` but wasn't in the dispatch table. Switching to `getattr(self, f"cmd_{cmd}")` eliminates the entire class of "forgot to wire up" bugs.

### Tutorial Recruit Hint Gating
Hint was gated on `combat_done and exploit_done`, but an early return in the artifact check prevented it from ever showing. Loosened the gate conditions.

### Scavenge Hint Repeating
"Good haul" hint fired on every scavenge attempt, not just the first. Need to track whether hint was already shown.

## Architecture Patterns

### Dynamic Dispatch (commit c87f539)
`getattr(self, f"cmd_{cmd}", None)` replaces explicit dispatch dictionary. Any method named `cmd_X` is automatically a command. Eliminates forgotten-wiring bugs.

### Game Loop Intercept
State flags (`self.in_combat`, `self.in_recruit`) intercept the normal game loop for special input modes. The recruit minigame reuses the same pattern as combat.

### Dual Database Pattern
`items_db` for regular items, `artifacts_db` for artifacts. Both must be checked in display, take, probe, and other commands that work with "things in a room."

### Tutorial Step Machine
Linear `STEPS` list. `after_command()` hook fires after every command. Steps advance based on what the player actually did. Commands always execute regardless of tutorial state — the tutorial observes and reacts, it doesn't block.

### Save Migration
`_migrate_state()` uses `setdefault()` to add new fields to old saves. Renames are done with `state.pop("old_key")` -> `state["new_key"]`. This has been used for:
- homekeeper -> steward
- tuft -> seed
- scavenging -> salvage (NPC assignment)
- Adding tutorial flags
- Adding `basic_tools` to discovered recipes
- Adding `worn` dict to characters
- Adding `recruit_attempts` to NPCs

### Artifact Location — Single Source of Truth
Artifact availability tracked in `room.items`, not duplicated across a separate tracking dict. `artifacts_status` was removed in favor of just checking whether the item exists in the room it's supposed to be in.

### NPC Flavor in Data, Not Code
`recruit_flavor` and `recruit_hint` live in `npcs.json`, not hardcoded in `recruit.py`. Each NPC has per-color dialogue lines. `_GENERIC_FLAVOR` provides fallback for NPCs without custom flavor.

## Recruit Minigame Details

- Ported from `proselytize.jsx` (React prototype, 642 lines)
- Board is NxN grid of colored tiles. Step on adjacent tile = +1 point. Stepping on color X resets X's counter to 7; all others decrement. Counter at 0 = eliminated. No valid adjacent moves = game over.
- FATE integration: Roll Rapport vs NPC's `recruit_dc`. Shifts adjust threshold (lower = easier).
- First attempt is free. Each retry costs 1 Fate Point.
- Board seeds shown as hex for reproducibility.
- Solvability validated with DFS solver.
- Difficulty scaling by `recruit_dc`:
  - DC 0: 7x7, 3 colors, threshold 20
  - DC 1: 6x6, 3 colors, threshold 20
  - DC 2: 6x6, 4 colors, threshold 22
  - DC 3: 5x5, 4 colors, threshold 20
- After reaching threshold, minigame continues with bonus tiers.
- Recruited NPCs follow the explorer (don't teleport to skerry).

## World-Building Context

The MUD lives in Eleanor's "Colonization Cycle" — four stages of the same universe:

1. **Genocide Draft** — Earth to void. Humans given to a behemoth. Sci-fi with GeneEs.
2. **Skerry** (this game) — Void survival with a runt world seed, building from flotsam.
3. **Border Lord** — Baby behemoth hatching. Maven picture book.
4. **Verraine** — Pulled back to its own separate thing ("that's getting too complicated").

**Key lore insight:** World seeds and behemoths are the same entity at different lifecycle stages. This unified three previously separate fiction projects.

### Core Characters (Fiction Context)
- **Miria:** Montana rancher's granddaughter, sucked into void with mysterious parcels
- **Sevarik:** Biotech soldier/explorer, accidental husband via translation artifact
- **Tuft:** Default name for the world seed, a baby cosmic entity

### The Gardener
A cosmic entity referenced in endgame lore. Not yet mechanically relevant in the MUD.

## Combat System Evolution

Combat went through a major overhaul (commit `05d3c07`):

- **EXPLOIT** = FATE's "Create an Advantage" renamed for MUD brevity. Roll Notice vs difficulty. Success = 1 exploit advantage on that aspect.
- **Exploit advantages** auto-consumed on next ATTACK for +2. Don't cost Fate Points. Can stack (EXPLOIT twice = +4).
- **EXPLOIT targets:** Room aspects (difficulty 1), enemy aspects (enemy Notice skill). NOT your own aspects — that's what INVOKE is for.
- **INVOKE** = Spend 1 FP for +2. Works anywhere (not just combat). Floating bonus consumed by next roll (attack, scavenge, craft, treatment, recruitment, initiative).
- **Enemy turns** happen independently after player actions. Some enemies are aggressive (attack first).
- **Boosts:** Ties on attack give attacker a one-use +2.
- **Success with Style on EXPLOIT** grants 2 exploit advantages instead of 1.
- **Teaching order:** ATTACK -> EXPLOIT (free!) -> exploit advantages -> INVOKE (paid). This progression from free to costly was deliberate tutorial design.

## Quest System (Verdant Wreck)

Newest addition. Two-path quest design inspired by Imperian MUD zones:

- **Path A (Careful):** Talk to Lira -> Use BASIC_TOOLS at control room -> Repair Growth Controller -> roots retract, ecology preserved
- **Path B (Forceful):** Talk to Lira -> Use RESIN + TORCH at root wall -> burn through -> ecological damage

Both paths are valid with different narrative outcomes. Uses locked exits (visible but blocked by condition) and hidden exits (revealed by quest dialogue).

Contextual USE: same item has different effects in different rooms (TORCH burns roots at root wall, lights dark areas elsewhere).

## Misc Technical Notes

- **proselytize.jsx** is a React prototype of the recruit puzzle. Not integrated into the main game — it was the design exploration that got ported to Python.
- **Save files** named after world seed (kebab-case). `_migrate_save_filenames()` auto-fixes if seed name changes.
- **Pokemon-style failure:** When Explorer is taken out, Tuft spends motes to extract them (5 base + 2 per extraction). Total mote depletion = game over.
- **Failure cost for crafting:** Materials consumed even on failed craft check. Harsh but flavorful.
- **The `systems/` directory is empty** — combat, exploration, etc. were planned as separate modules but all live in main.py instead. The 3000-line main.py is the real architecture.
