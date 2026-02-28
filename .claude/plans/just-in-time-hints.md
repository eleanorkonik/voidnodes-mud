# Just-in-Time Hints: Kill the State Machine, Keep the Story

## Context

The tutorial is an 841-line rigid state machine that gates progression (must do combat → exploit → invoke → scavenge → artifact → recruit → quest in order before you can SWITCH). Eleanor wants the seed to be opinionated but not a hall monitor. Hints should fire on first encounter with a mechanic, regardless of order. The prologue narrative (awakening, bonding, naming, meeting Sevarik) stays — that's story, not tutorial.

## What Changes

**Keep:** Prologue narrative (Act 1: awakening through handoff). Seed voice. `_tutorial_prompt()` helper. `garden_walkthrough()`.

**Kill:** The `explorer_free` 7-objective gate. The `explorer_return/settle/artifact/stash/handoff` rigid sequence. The `steward_build/assign` gates. The `after_command()` hook for Acts 2/3. The SWITCH blocking in main.py.

**Move:** Combat/exploit/invoke/scavenge/artifact hints → into command handlers as one-shot contextual triggers.

## Approach: Slim tutorial.py to prologue-only, hints in handlers

### Step 1: Rewrite tutorial.py

Keep only:
- `STEPS` = prologue steps only (awakening through handoff)
- `show_prologue_intro()` — unchanged
- `show_skip_message()` — unchanged
- `_show_sevarik_encounter()` / `_show_the_split()` — unchanged
- `_tutorial_prompt()` — unchanged (used by handlers too)
- `garden_walkthrough()` — unchanged (already non-blocking)
- `after_command()` — prologue steps only (awakening → naming → first_look → movement → exploring → check_seed → handoff)
- `get_current_hint()` — prologue steps only

**Change in handoff step:** After `_transition_to_day1()`, set `tutorial_complete = True` immediately. No more Acts 2/3.

**Add to `_transition_to_day1()` output** (story.py:412-416): After the seed's "I can send you beyond the skerry" line, add a non-blocking landing pad hint: "Head south to the landing pad. SEEK to follow an aspect into the void."

Delete: `_explorer_free_hints()`, `_explorer_free_resume_hint()`, `_advance_to_artifact_or_stash()`, `_advance_to_stash()`, `_steward_arrive()`, `_first_buildable_name()`, `_player_has_unresolved_artifact()`. All Act 2/3 branches in `after_command()` and `get_current_hint()`.

### Step 2: Remove SWITCH gates from main.py

Lines 720-757 in `cmd_switch()`:
- **Keep** prologue gate (lines 723-729): Can only switch at handoff step — that's story pacing.
- **Remove** explorer gate (lines 730-757): The rigid "must reach explorer_handoff step" + "must have enough materials to build" blocks. After prologue, SWITCH is always allowed.

The seed can still be *opinionated* without *blocking*. When switching to steward for the first time and the player has no materials in the junkyard, the seed can say "You haven't brought much back yet..." but still allow the switch.

### Step 3: Add first-use hints to command handlers

All hints use one-shot `state["_hint_X"]` flags. Fire once, never block.

**commands/combat.py — `_start_combat()`:**
- Flag: `_hint_first_combat`
- Seed: "Those creatures! ATTACK to engage."

**commands/combat.py — after first successful exploit (where `tutorial_exploit_done` gets set):**
- Flag: `_hint_exploit_payoff`
- Seed: "Now ATTACK — your exploit advantage fires automatically. +2, no fate point."

**commands/combat.py — after first combat win (where `tutorial_combat_done` gets set):**
- Flag: `_hint_invoke_contrast`
- Seed: "EXPLOIT is free but takes a turn. INVOKE costs a fate point for instant +2. Type INVOKE with no arguments to see your options."

**commands/examine.py — `cmd_scavenge()` after first successful scavenge (where `tutorial_scavenge_done` gets set):**
- Flag: `_hint_first_scavenge`
- Seed: "Good haul. RECIPES to see what you can make, CRAFT to build it."

**commands/movement.py — `_on_room_enter()` (explorer entering room with enemies for first time):**
- Flag: `_hint_first_enemies`
- Already partially exists — the room entry code handles enemy encounters. Add a seed warning before combat starts if enemies are present and flag not set.

**commands/movement.py — first arrival at landing pad:**
- Flag: `_hint_first_landing`
- Already handled — `_show_landing_pad_destinations()` fires on entry. Just add a seed line: "SEEK <aspect words> to follow an aspect into the void."

**main.py — `_switch_focus()` first switch to steward:**
- Flag: `_hint_first_steward`
- Seed: "CHECK SKERRY to see what we can build. Then BUILD something — pick a direction off an existing room."

**main.py — `_switch_focus()` first switch to steward with opinion about materials:**
- If junkyard has no materials AND no NPC recruited: seed says "You haven't brought much back yet. But we'll make do." (non-blocking)

### Step 4: Clean up main.py game loop

- Remove the `after_command` hook check (lines 420-423) when `tutorial_complete` is True — it already short-circuits, but the `_pre_cmd_location` stashing (lines 412-415) can be simplified.
- Actually, the `after_command` hook is still needed for prologue. Keep it as-is — it already returns True and stops when `tutorial_complete`.

## Files Changed

| File | Change |
|------|--------|
| `engine/tutorial.py` | Gut Acts 2/3. Keep prologue + garden_walkthrough + _tutorial_prompt. ~400 lines removed. |
| `main.py` | Remove SWITCH explorer/steward gates (keep prologue gate). Add first-steward hint in `_switch_focus()`. |
| `commands/combat.py` | Add first-combat, exploit-payoff, invoke-contrast one-shot hints. |
| `commands/examine.py` | Add first-scavenge one-shot hint. |
| `commands/movement.py` | Add first-landing-pad SEEK hint. |
| `commands/story.py` | Add landing pad hint to `_transition_to_day1()` output. |

## Existing hints that already work (no changes needed)

- Building hints on first room entry (`commands/movement.py`) ✓
- "I sense a survivor" on first NPC room (`commands/movement.py`) ✓
- Recruit hint on first GREET of unrecruited NPC (`commands/npcs.py`) ✓
- Garden walkthrough on first garden build (`engine/tutorial.py`) ✓

## Flag reference (set in handlers, checked by hints)

| Flag | Set in | Used for |
|------|--------|----------|
| `tutorial_combat_done` | combat.py:767 | First combat win |
| `tutorial_exploit_done` | combat.py:163,170 | First exploit |
| `tutorial_invoke_done` | tutorial.py (being removed) → move to combat.py | First invoke |
| `tutorial_scavenge_done` | examine.py:794 | First scavenge |
| `tutorial_artifact_found` | items.py:81 | First artifact TAKE |
| `tutorial_recruit_done` | npcs.py:742 | First recruit |
| `_hint_first_combat` | NEW in combat.py | First combat seed hint |
| `_hint_exploit_payoff` | NEW in combat.py | Exploit→attack hint |
| `_hint_invoke_contrast` | NEW in combat.py | EXPLOIT vs INVOKE hint |
| `_hint_first_scavenge` | NEW in examine.py | First scavenge celebration |
| `_hint_first_steward` | NEW in main.py | First steward orientation |
| `_hint_first_landing` | NEW in movement.py | First landing pad SEEK hint |

## Verification

1. New game → prologue plays normally (BOND, name seed, LOOK, GO, find Sevarik, CHECK SKERRY, SWITCH)
2. After prologue handoff → Day 1 explorer, `tutorial_complete = True`
3. Explorer can SWITCH to steward immediately (no "do 7 things first" gate)
4. First switch to steward → seed gives orientation hint (non-blocking)
5. Switch back to explorer → no gate, free movement
6. First combat → seed warns about enemies, suggests ATTACK
7. First exploit → seed celebrates, suggests ATTACK to use the advantage
8. First combat win → seed explains EXPLOIT vs INVOKE contrast
9. First scavenge → seed celebrates, mentions RECIPES/CRAFT
10. Player can do these in ANY order — no sequencing required
11. Each hint fires exactly once (one-shot flags)
12. SKIP still works from prologue
