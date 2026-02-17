# Plan: Starter Artifact Tutorial + IH Command + Aspect Teaching

## Context

The tutorial currently jumps from the split explanation to "SWITCH FOCUS TO SEVARIK" without teaching key mechanics. This adds a guided artifact interaction between the split and the handoff, teaching IH, EXAMINE, aspects, and the KEEP/OFFER resource tension. Also makes IH its own command (focused room contents list) instead of a LOOK alias.

## Artifacts

Two starter artifacts, one chosen randomly per playthrough. Added to `data/artifacts.json`, placed in the player's current room dynamically during tutorial.

**Silver Slippers** — aspect: *There's No Place Like Home*
- Effect: emergency teleport back to skerry (like retreat but free)
- Mote value: 5
- Backend lore: Wizard of Oz (not exposed to player)

**Red Clown Nose** — aspect: *Uglier Than I Am*
- Effect: reduces NPC resentment/envy by 1
- Mote value: 5
- Backend lore: Harrison Bergeron (not exposed to player)

Both artifacts are placed dynamically into the player's current room when the tutorial reaches the artifact step. In `artifacts.json` they're stored without a room assignment until then.

## New Tutorial Steps

Insert 4 steps between split explanation and handoff:

```
... exploring → (sevarik encounter + split) →
  artifact_ih → artifact_examine → artifact_use → artifact_choice →
  handoff → complete
```

### Step: `artifact_ih`
Tuft: "Hold on. I can feel something nearby. Our bond lets you sense objects. Type IH to see what's here."
Player types **IH** → sees artifact listed.
Tuft: "See that? Look more closely. EXAMINE it."

### Step: `artifact_examine`
Player types **EXAMINE <artifact>** (aliases to PROBE).
Tuft describes it, reveals the aspect concept:
"See that shimmer? That's an aspect — *[aspect name]*. Aspects are the deeper nature of things. When you need strength, you can INVOKE an aspect for a bonus."
Then: "Take it. It shouldn't just sit on the ground."

### Step: `artifact_use`
Player types **TAKE <artifact>** → pickup message.
Then Tuft prompts: "Now try it on. USE it."
Player types **USE/WEAR <artifact>** → Tuft describes the effect:
- Slippers: Player clicks the heels together three times. Tuft: "You feel a tug — toward here, toward the skerry. Lost in the void, click your heels and these will pull you home."
- Nose: Player puts on the nose. "Something shifts. People's eyes slide right past you. Less sharp, less jealous."
Tuft then prompts the choice.

### Step: `artifact_choice`
Tuft: "Now. A choice. You can KEEP it — carry it, use its power. Or you can OFFER it TO me. I'll break it down into motes and grow stronger. Your power or mine. There's always a trade."
Player types **KEEP** → stays in inventory.
Player types **OFFER <artifact> TO <seed>** → removed from inventory, motes added.
After choice → advance to `handoff` → "SWITCH FOCUS TO <explorer>."

## IH Command

### Parser (`engine/parser.py`)
- Remove `"ih": "look"` from COMMAND_ALIASES
- Add to COMMANDS: `"ih": {"phases": ["explorer", "steward", "prologue"], "args": "optional"}`

### `cmd_ih` (`main.py`)
- **No args**: focused list of interactable room contents — items (checking both `items_db` and `artifacts_db` for names), NPCs, inactive agents. No room name/description, no exits. Just what you can interact with.
- **With args**: delegates to shared `_examine_target(target)` helper

### Refactor: extract `_examine_target(target)` from `cmd_look`
The target-examination logic (current lines 388-445 of cmd_look) becomes `_examine_target(target)`. Both `cmd_look <thing>` and `cmd_ih <thing>` call it. `cmd_look` with no args still shows full room via `display_room()`.

## Other Parser/Alias Changes

| Change | In `engine/parser.py` |
|--------|-----------------------|
| `"examine": "probe"` (currently `"examine": "look"`) | COMMAND_ALIASES |
| Add `"wear": "use"` | COMMAND_ALIASES |
| Add `"prologue"` to `take` phases | COMMANDS |
| Add `"prologue"` to `probe` phases | COMMANDS |
| Add `"prologue"` to `keep` phases | COMMANDS |

## OFFER Command (new, NOT an alias)

OFFER is its own verb — `"offer": {"phases": ["explorer", "steward", "prologue"], "args": "required"}`. Syntax: `OFFER <item> TO <target>`.

**`cmd_offer` in main.py**: Parses `OFFER <item> TO <target>`. Splits args on "to" to get item name and target name. If target matches the world seed name → does the same logic as feeding (remove from inventory, add motes, show Tuft's reaction). If target is an NPC → future functionality, for now: `"They don't seem interested."` This keeps OFFER extensible for NPC gifting later without being a dumb alias for FEED.

## cmd_keep: Bug fix

Line 1223: `self.explorer.add_to_inventory(art_id)` → `self.current_character().add_to_inventory(art_id)`. Currently hardcoded to explorer; steward can't keep artifacts.

## display_room: Artifact name fallback

When an item ID in `room.items` isn't in `items_db`, also check `artifacts_db` before falling back to title-case formatting. Needed for starter artifacts to display with proper names.

## Starting Inventory (`data/characters.json`)

- **Sevarik**: `["preserved_food"]` (restores 1 stress — already in items_db — plausible for a scout)
- **Miria**: stays empty (she'll learn INVENTORY from the artifact interaction)

## Tutorial Implementation (`engine/tutorial.py`)

### `_show_the_split` ending
Replace current ending (sets step to `handoff`) with artifact setup:
1. Pick random artifact from `["silver_slippers", "red_clown_nose"]`
2. Store in `game.state["starter_artifact"]`
3. Set artifact's `room` in `artifacts_db` to player's current room
4. Add artifact ID to current room's `items` list
5. Set step to `artifact_ih`
6. Tuft: "Hold on. I can feel something nearby..."

### New `after_command` branches
Handle each artifact step: `artifact_ih` + `ih`, `artifact_examine` + `probe`, `artifact_use` + `take`/`use`, `artifact_choice` + `keep`/`offer`.

The `artifact_use` step handles TWO commands in sequence — first TAKE, then USE/WEAR. After TAKE, show pickup and prompt USE. After USE, advance to `artifact_choice`.

### New `get_current_hint` entries
Add resume hints for all 4 artifact steps.

## cmd_use: Handle artifact effects in tutorial

Extend `cmd_use` to handle artifacts by ID. When artifact is in inventory: show the artifact-specific effect narration for the tutorial. Slippers show teleport tug, nose shows camouflage effect.

## Help Text Updates (`engine/display.py`)

Split the current `"LOOK / IH [thing]"` entry into:
- `"LOOK [thing]"` → "Examine surroundings or a specific thing"
- `"IH [thing]"` → "List objects here, or examine something"

## Files Summary

| File | Changes |
|------|---------|
| `data/artifacts.json` | Add `silver_slippers` + `red_clown_nose` |
| `data/characters.json` | Starting inventory for Sevarik and Miria |
| `engine/parser.py` | IH as own command; OFFER as own command; examine→probe; wear→use aliases; prologue phases for take/probe/keep |
| `engine/tutorial.py` | 4 new steps in STEPS list; `_show_the_split` ending; `after_command` branches; `get_current_hint` entries |
| `engine/display.py` | Help text; `display_room` artifact name fallback |
| `main.py` | `cmd_ih`; `cmd_offer`; `_examine_target` refactor; `cmd_keep` bug fix; `cmd_use` artifact handling; `"ih"` + `"offer"` in handlers |

## Verification

1. New game → prologue flows through all 4 artifact steps
2. IH no args → lists room contents (items, NPCs, agents — not full room desc)
3. IH <thing> → examines same as LOOK <thing>
4. EXAMINE <artifact> → probe with Tuft aspect commentary
5. TAKE <artifact> → picks up, shows in inventory
6. USE/WEAR <artifact> → Tuft describes effect
7. KEEP → stays in inventory | OFFER TO <seed> → motes added
8. After choice → handoff → SWITCH FOCUS works
9. LOOK still shows full room description as before
10. Both characters have starting inventory items
