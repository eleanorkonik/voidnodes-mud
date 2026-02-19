# Plan: Tutorial Quest System — The Verdant Wreck

## Context

The tutorial currently teaches combat, exploit, invoke, scavenge, artifact discovery, and recruitment — all via the debris_field zone. Eleanor wants a QUEST system that gates artifact discovery behind multi-step puzzle-solving: talk to an NPC, gather/use items contextually, unlock blocked passages. Inspired by Imperian Zones quest patterns. Should be "more interesting than just combat."

The new zone has NO enemies — pure exploration and environmental puzzle-solving, contrasting with debris_field's combat focus. This teaches the player that not all void nodes are hostile, and that items have contextual uses beyond combat.

New artifact: causes plants to instantly bear fruit, 5 uses before degrading, mote_value = 5.

## New Zone: The Verdant Wreck

A massive biodome ship fragment — the growing section of a colony ship. When it broke apart, the growth systems kept running, fueled by void energy. Now it's a small jungle floating in nothing. Warm, humid air. Bioluminescent flora. One optional enemy (a mutated tangle-vine), but the zone is primarily exploration and puzzle-solving.

Inspired by the Imperian zone designs — Latonin Island's multi-NPC quest structure (give item → get info → make choice with different consequences) and the Barrow/Cave of Tombs (hidden doors, keys, possessed creatures with a free-or-kill choice).

**Aspect:** `"Life That Outlasted Its Makers"`
**Difficulty:** `"easy"`
**Entry room:** `vw_airlock`

### Rooms (10 rooms)

```
                [vw_observation]
                      |
                  (up/down)
                      |
[vw_control] ← [vw_root_wall] → [vw_canopy]
  (hidden        |                  (enemy)
   exit)     [vw_greenhouse]
                  |
              [vw_promenade]
             /       |       \
    [vw_tanks]  [vw_airlock]  [vw_nursery]
                     |
              skerry_landing

              [vw_heart] — behind the root wall (north, LOCKED)
```

| Room ID | Name | Aspects | Contents |
|---------|------|---------|----------|
| `vw_airlock` | Overgrown Airlock | `["Roots Through Steel"]` | Entry point. Roots cracking through hull plates, warm humid air. Exits: south→skerry_landing, north→vw_promenade |
| `vw_promenade` | The Promenade | `["Echoes of a Crew Long Gone"]` | Wide corridor, vine-covered benches, faded signs pointing to GREENHOUSE and AQUAPONICS. Exits: south→vw_airlock, north→vw_greenhouse, west→vw_tanks, east→vw_nursery |
| `vw_tanks` | Aquaponics Tanks | `["Still Water, Still Alive"]` | Cracked tanks, murky water, bioluminescent eels darting inside, mushroom clusters where water drips. Scavengeable: coral_fragments, luminous_moss. Exits: east→vw_promenade |
| `vw_nursery` | The Nursery | `["Seeds of a Dead World"]` | Shattered seed trays, seedlings grown into twisted ceiling-pressing trees, thick pollen. Scavengeable: seeds, resin. Item: `scattered_notes` (botanist's journal about the growth going wrong). Exits: west→vw_promenade |
| `vw_greenhouse` | The Greenhouse | `["Wild Growth", "Someone Has Been Tending This"]` | Main growing dome — transparent panels showing void overhead, riot of green, cleared paths between planter beds. **NPC: Lira** (quest giver). Exits: south→vw_promenade, north→vw_root_wall, east→vw_canopy |
| `vw_canopy` | The Canopy | `["Predators Adapt"]` | Trees grown so tall they form a canopy. Vines like curtains. Something rustles above. **Enemy: tangle_vine** (mutated predatory plant, optional combat). Exits: west→vw_greenhouse |
| `vw_root_wall` | Root Wall | `["Impenetrable Roots"]` | Corridor ends in interwoven roots thick as a person's torso, pulsing with green light. Something glows beyond. LOCKED exit north→vw_heart. Hidden exit west→vw_control (revealed after talking to Lira). Exits: south→vw_greenhouse, up→vw_observation |
| `vw_observation` | Observation Platform | `["The Whole Picture"]` | Metal platform above the tree line. Through cracked dome panels — void in every direction, skerry a speck of light. Can see the entire root system from here. NPC: a nesting void-swift (flavor creature). Exits: down→vw_root_wall |
| `vw_control` | Growth Control Room | `["The Machine Still Remembers"]` | Cramped room, dead consoles, one flickering panel — the Growth Controller. Automated system that directed biodome plant growth. USE BASIC_TOOLS to repair → roots retract (the careful path). Exits: east→vw_root_wall |
| `vw_heart` | The Verdant Heart | `["Crystallized Mid-Bloom", "The Last Garden"]` | Biodome core. Enormous plant crystallized mid-bloom, roots threading every wall. Bloom Catalyst at its base. Exits: south→vw_root_wall |

`vw_root_wall` aspects change to `["Charred Passage"]` after burning (forceful path) or `["Roots Retracted"]` after Growth Controller repair (careful path).

### Zone Connection

`skerry_landing` gets a new void crossing exit to `vw_airlock`. Zone aspect `"Life That Outlasted Its Makers"` is matched via SEEK — player types `SEEK LIFE` or `SEEK OUTLASTED`.

### Enemy: Tangle-Vine

In `vw_canopy`. A mutated predatory plant — optional combat encounter for players who explore east from the greenhouse. Teaches that void zones can have unexpected dangers even in "peaceful" areas.

```json
{
    "id": "tangle_vine",
    "name": "Tangle-Vine",
    "description": "Thick tendrils lash out from the canopy above — a plant that's learned to hunt.",
    "skills": {"Fight": 1, "Athletics": 2},
    "stress": [false, false, false],
    "consequences": {"mild": null},
    "aspects": ["Rooted But Reaching", "Slow to React"],
    "loot": ["resin", "seeds"],
    "aggressive": false
}
```

Not aggressive — only attacks if you ATTACK first. Low difficulty.

### Flavor Item: Scattered Notes

In `vw_nursery`. A botanist's journal fragment about the biodome's growth going haywire. LOOK/PROBE to read. Provides lore context. Not a quest item — pure environmental storytelling.

### The Quest: Two Paths (Inspired by Imperian Choices)

Like the Barrow's "free or kill Valkafor" and Latonin's "Captain or First Mate" choices, the quest has two valid approaches with different narrative consequences:

**Path A — The Careful Way (Growth Controller):**
1. TALK LIRA → learn about root wall + she mentions the Growth Controller
2. This reveals hidden west exit from `vw_root_wall` to `vw_control`
3. GO WEST to control room
4. USE BASIC_TOOLS → repair console → roots retract automatically
5. GO NORTH from root_wall to vw_heart → find artifact
6. Lira's reaction: impressed, offers to visit skerry someday, gives extra seeds as thanks
7. Root_wall aspect becomes `["Roots Retracted"]`

**Path B — The Forceful Way (Burn Through):**
1. TALK LIRA → same info (she mentions both options)
2. USE RESIN at `vw_root_wall` → weakens roots (consumes resin)
3. USE TORCH at `vw_root_wall` → burns through (torch NOT consumed)
4. GO NORTH to vw_heart → find artifact
5. Lira's reaction: "The root system... you've damaged something irreplaceable."
6. Root_wall aspect becomes `["Charred Passage"]`

**Both paths:** Artifact has 5 uses, mote_value 5. The consequence is narrative, not mechanical — this is a tutorial, so the player shouldn't be punished for either choice. They're learning that choices exist.

**Quest state tracks which path was taken:**
```python
state["quests"]["verdant_bloom"]["path"] = "careful" | "forceful" | None
```

## New Artifact: Bloom Catalyst

Added to `data/artifacts.json`:

- **name**: Bloom Catalyst
- **description**: A crystallized flower bud that pulses with deep green energy. When held near dormant plants, they erupt into instant growth — flowers, fruit, seeds, all at once. The crystal dims slightly each time it's used.
- **aspects**: `["Instant Harvest", "Five Blooms Remain"]`
- **mote_value**: 5
- **stat_bonuses**: `{}` (no passive bonus — its value is in the USE mechanic)
- **special**: `"bloom_catalyst"`
- **uses_remaining**: 5 (new field, specific to this artifact)
- **location**: `{"type": "room", "id": "vw_heart"}`
- **discovery_text**: "At the base of the crystallized plant, a single bud glows with concentrated life. The Bloom Catalyst. When you pick it up, every plant in the chamber shivers."
- **hint_sensory**: "concentrated life — a green pulse, like a heartbeat, deep inside the overgrowth"

### USE Mechanic

In `cmd_use` (main.py:1332), add handler for `bloom_catalyst`:

```python
elif art_id == "bloom_catalyst":
    uses = art.get("uses_remaining", 0)
    if uses <= 0:
        display.narrate("The crystal is spent. It crumbles to dust in your hands.")
        # remove from inventory + mark spent
        return
    art["uses_remaining"] = uses - 1
    # Generate food + seeds
    char.add_to_inventory("preserved_food")
    char.add_to_inventory("seeds")
    remaining = uses - 1
    display.success("The Bloom Catalyst pulses. Nearby vegetation erupts into")
    display.success("flower and fruit. You gather what you can.")
    display.info(f"  Gained: preserved food, seeds. ({remaining} bloom{'s' if remaining != 1 else ''} remaining)")
    # Update aspect text
    if remaining > 0:
        words = ["Zero", "One", "Two", "Three", "Four", "Five"]
        art["aspects"] = ["Instant Harvest", f"{words[remaining]} Bloom{'s' if remaining != 1 else ''} Remain{'s' if remaining == 1 else ''}"]
    else:
        display.narrate("The crystal dims and crumbles to dust. Its blooms are spent.")
        char.remove_from_inventory(art_id)
        self.state.get("artifacts_status", {})[art_id] = "spent"
```

FEED works normally — 5 motes regardless of remaining uses.

## New NPC: Lira

Added to `data/npcs.json`. Non-recruitable botanist who provides quest direction. Inspired by the Latonin Island sailor (shares info after TALK, gives both options).

- **location**: `vw_greenhouse`
- **recruited**: false
- **aspects**: `["Botanist Without a Ship", "Patient Observer"]`
- **skills**: `{"Commune": 3, "Craft": 2, "Lore": 2, "Rapport": 1}`
- **recruit_dc**: `null` (not recruitable during tutorial; future hook)
- **dialogue**:
  - `greeting`: "You have a world seed? I can feel it from here. The plants are leaning toward you."
  - `idle`: "Lira examines a vine, murmuring to herself about growth patterns."
  - `quest_intro`: "I've been studying this biodome for weeks. There's something incredible at the heart of it — a crystallized bloom that pulses with raw growth energy. But massive roots block the way north."
  - `quest_options`: "There are two ways through. There's a Growth Control room somewhere west of the root wall — the console might still work if you can repair it. The roots would retract cleanly. Or... you could weaken them with solvent and burn through. It would work, but these roots are the biodome's lifeline."
  - `quest_careful_done`: "You preserved the root system! This biodome might survive after all. Here — take these. And if you ever want a botanist on your skerry... I might come visit."
  - `quest_forceful_done`: "You got through. That crystal — it accelerates plant growth. Five uses, maybe. But the root system... you've damaged something irreplaceable."
  - `quest_complete`: "That crystal — I've been studying it from this side. It accelerates plant growth. Five uses, maybe, before the energy dissipates."

## Quest State

```python
state["quests"] = {
    "verdant_bloom": {
        "status": "inactive",     # inactive → active → complete
        "roots_weakened": False,   # True after USE RESIN at vw_root_wall
        "roots_cleared": False,    # True after clearing via either path
        "path": None,             # "careful" or "forceful" — tracks which approach
        "control_revealed": False, # True after Lira reveals hidden exit
    }
}
```

## Locked Exits & Hidden Exits

Two new mechanics, both inspired by Imperian patterns:

1. **Locked exits** — visible but impassable until a condition is met (Root Wall → Verdant Heart)
2. **Hidden exits** — invisible until revealed by quest progress (Root Wall → Control Room)

### Room Model Changes (`models/room.py`)

Add `locked_exits` field:

```python
def __init__(self, data):
    # ... existing fields ...
    self.locked_exits = dict(data.get("locked_exits", {}))

def to_dict(self):
    d = { ... }  # existing
    if self.locked_exits:
        d["locked_exits"] = self.locked_exits
    return d
```

Condition resolver (in `engine/quest.py`):

```python
def check_lock_condition(condition, game_state):
    """Resolve a locked_exit condition string against game state."""
    CONDITION_MAP = {
        "quest_roots_cleared": lambda s: s.get("quests", {}).get("verdant_bloom", {}).get("roots_cleared", False),
    }
    resolver = CONDITION_MAP.get(condition)
    return resolver(game_state) if resolver else False
```

### Hidden Exit Mechanic

When Lira reveals the Growth Controller, the quest handler adds the west exit to `vw_root_wall` at runtime:

```python
room = game_state["rooms"]["vw_root_wall"]  # or however rooms are accessed
room["exits"]["west"] = "vw_control"
# (Room objects are mutable and serialized on save, so this persists)
```

This matches the Imperian note: "coding-wise this would just 'reveal' the exits."

The `vw_control` room already has `"east": "vw_root_wall"` in its data — the return path always exists.

### cmd_go Changes (main.py:726)

After validating `direction in room.exits` (line 740), before cross-zone check (line 752):

```python
# Check locked exits
from engine.quest import check_lock_condition
lock = room.locked_exits.get(direction)
if lock:
    if not check_lock_condition(lock["condition"], self.state):
        display.narrate(lock["locked_desc"])
        return
```

### display_room Changes (engine/display.py:155)

Show locked exits with blocked indicator:

```python
for e in exits:
    lock = room.locked_exits.get(e)
    if lock and not check_lock_condition(lock["condition"], game_state):
        exit_parts.append(f"{DIM}{e.upper()} (blocked){RESET}")
    else:
        exit_parts.append(f"{BOLD}{e.upper()}{RESET}")
```

## Contextual USE at Locations

### New: `engine/quest.py` — `handle_quest_use()`

Handles both paths — forceful (resin+torch at root wall) and careful (basic_tools at control room):

```python
def handle_quest_use(item_id, room_id, game_state, character):
    """Handle location-specific item USE for quests.
    Returns (handled: bool, consumed: bool) — caller handles inventory removal if consumed.
    """
    quest = game_state.get("quests", {}).get("verdant_bloom", {})
    if quest.get("status") != "active":
        return False, False

    # PATH B (forceful) — resin + torch at root wall
    if room_id == "vw_root_wall":
        if item_id == "resin" and not quest.get("roots_weakened"):
            display.narrate("You spread the resin across the thick roots. The organic")
            display.narrate("solvent soaks in, and you hear faint cracking as the outer")
            display.narrate("layer softens. The roots sag but hold.")
            display.info("  Something hotter might finish the job.")
            quest["roots_weakened"] = True
            return True, True  # consume resin

        if item_id == "torch" and quest.get("roots_weakened") and not quest.get("roots_cleared"):
            display.narrate("You hold the torch to the weakened roots. They catch")
            display.narrate("instantly, curling and blackening. In moments, a narrow")
            display.narrate("passage opens to the north, revealing a green glow beyond.")
            quest["roots_cleared"] = True
            quest["path"] = "forceful"
            # Update room aspect
            _update_room_aspect(game_state, "vw_root_wall", ["Charred Passage"])
            return True, False  # torch not consumed

        if item_id == "torch" and not quest.get("roots_weakened"):
            display.narrate("You hold the torch to the roots, but they're too thick")
            display.narrate("and damp to catch. The surface barely singes.")
            return True, False

    # PATH A (careful) — basic_tools at control room
    if room_id == "vw_control":
        if item_id == "basic_tools" and not quest.get("roots_cleared"):
            display.narrate("You pry open the console panel and get to work. Corroded")
            display.narrate("connectors, frayed wiring — but the core logic board is intact.")
            display.narrate("You clean the contacts and bridge the broken circuits.")
            print()
            display.success("The Growth Controller hums to life. On the flickering screen,")
            display.success("you see the root network diagram shift — redirecting growth")
            display.success("away from the northern corridor.")
            print()
            display.narrate("Through the wall, you hear the groan of roots retracting.")
            quest["roots_cleared"] = True
            quest["path"] = "careful"
            _update_room_aspect(game_state, "vw_root_wall", ["Roots Retracted"])
            return True, False  # tools not consumed

    return False, False
```

### cmd_use Integration (main.py:1332)

Before the existing artifact/item checks, try quest use:

```python
# Check quest-contextual use first
from engine.quest import handle_quest_use
room = self.current_room()
item_id, item = self._find_entity(char.inventory, target, self.items_db)
if item and room:
    handled, consumed = handle_quest_use(item_id, room.id, self.state, char)
    if handled:
        if consumed:
            char.remove_from_inventory(item_id)
        return
```

## Quest-Aware TALK

### cmd_talk Changes (main.py:1292)

After finding an NPC, before showing standard dialogue, check for quest dialogue:

```python
from engine.quest import get_quest_talk, apply_quest_talk_effects

npc_id, npc = self._find_entity(room.npcs, target, self.npcs_db)
if npc:
    quest_result = get_quest_talk(npc_id, npc, self.state)
    if quest_result:
        for line in quest_result["lines"]:
            display.npc_speak(npc["name"], self._sub_dialogue(line))
        if quest_result.get("quest_started"):
            display.info("  [Quest started: The Verdant Heart]")
        # Apply side effects (reveal hidden exits, give items, etc.)
        apply_quest_talk_effects(quest_result, self.state, self.rooms, self.current_character())
        return
    # ... existing dialogue logic ...
```

### `get_quest_talk()` in engine/quest.py

```python
def get_quest_talk(npc_id, npc, game_state):
    """Get quest-specific dialogue for an NPC.
    Returns dict with lines + effects, or None if no quest dialogue.
    """
    if npc_id != "lira":
        return None

    quest = game_state.get("quests", {}).get("verdant_bloom", {})
    dialogue = npc.get("dialogue", {})

    # Quest complete — react based on path taken
    if quest.get("status") == "complete":
        path = quest.get("path")
        if path == "careful":
            return {"lines": [dialogue.get("quest_careful_done", "...")]}
        elif path == "forceful":
            return {"lines": [dialogue.get("quest_forceful_done", "...")]}
        return {"lines": [dialogue.get("quest_complete", "...")]}

    # Quest not started — activate + show both options + reveal hidden exit
    if quest.get("status") != "active":
        return {
            "lines": [
                dialogue.get("greeting", "..."),
                dialogue.get("quest_intro", "..."),
                dialogue.get("quest_options", "..."),
            ],
            "quest_started": True,
            "reveal_exit": ("vw_root_wall", "west", "vw_control"),
        }

    # Quest active, roots cleared — show completion dialogue
    if quest.get("roots_cleared"):
        return {"lines": [dialogue.get("quest_complete", "...")]}

    # Quest active, in progress — repeat options
    return {"lines": [dialogue.get("quest_options", "...")]}


def apply_quest_talk_effects(result, game_state, rooms, character):
    """Apply side effects from quest dialogue (reveal exits, give items, etc.)."""
    if result.get("quest_started"):
        game_state.setdefault("quests", {})["verdant_bloom"] = {
            "status": "active",
            "roots_weakened": False,
            "roots_cleared": False,
            "path": None,
            "control_revealed": False,
        }

    if result.get("reveal_exit"):
        room_id, direction, target_id = result["reveal_exit"]
        room = rooms.get(room_id)
        if room and direction not in room.exits:
            room.exits[direction] = target_id
            game_state["quests"]["verdant_bloom"]["control_revealed"] = True
            display.info(f"  [Lira points west — a hidden corridor behind the roots.]")
```

## Tutorial Integration

### New Objective: `tutorial_quest_done`

Add as 7th objective in `explorer_free` (tutorial.py:214):

```python
if (game.state.get("tutorial_combat_done") and
        game.state.get("tutorial_exploit_done") and
        game.state.get("tutorial_invoke_done") and
        game.state.get("tutorial_scavenge_done") and
        game.state.get("tutorial_artifact_found") and
        game.state.get("tutorial_recruit_done") and
        game.state.get("tutorial_quest_done")):
```

### Quest Completion Trigger

In `cmd_take` or artifact discovery: when bloom_catalyst is found, set `tutorial_quest_done = True`.

The existing `tutorial_artifact_found` flag is set by any artifact find. `tutorial_quest_done` is separate — it tracks that the player completed a quest specifically.

### Tutorial Hints for Quest Zone

In `_explorer_free_hints()` (tutorial.py:441), add hints after combat objectives are done:

```python
quest_done = game.state.get("tutorial_quest_done")

# After combat+scavenge done, not yet quested — hint about verdant wreck
if combat_done and scavenge_done and not quest_done:
    quest_status = game.state.get("quests", {}).get("verdant_bloom", {}).get("status", "inactive")
    if quest_status == "inactive" and room.zone == "skerry":
        # On skerry, hint about another node
        display.seed_speak("I sense life — real life — somewhere in the void.")
        display.seed_speak("Not like the debris. Something growing.")
        display.info("  SEEK LIFE from the landing pad to follow it.")
    elif quest_status == "active" and not game.state.get("quests", {}).get("verdant_bloom", {}).get("roots_cleared"):
        display.seed_speak("Lira's hint about the roots — resin to weaken, heat to burn.")
```

## Save System Changes

### `new_game_state()` (save.py:176)

Add to initial state dict:

```python
"tutorial_quest_done": False,
"quests": {},
```

### `_migrate_state()` (save.py:87)

Add defaults for old saves:

```python
state.setdefault("tutorial_quest_done", False)
state.setdefault("quests", {})
```

### Zone Data Loading

The verdant_wreck zone goes in `data/zones.json` alongside debris_field, coral_thicket, frozen_wreck. The `new_game_state()` function already loads all zones and builds room/enemy lookups from them — no loader changes needed.

### Skerry Connection

In `data/skerry.json`, add a void crossing exit from `skerry_landing` to `vw_airlock`:

```json
"exits": {
    "north": "skerry_central",
    "void_verdant": "vw_airlock"   // new crossing
}
```

(The existing pattern uses `void_*` prefixed exit keys for cross-zone connections.)

## New File: `engine/quest.py`

```
engine/quest.py
├── check_lock_condition(condition, game_state)   — resolve locked exit conditions
├── handle_quest_use(item_id, room_id, game_state, character)  — contextual USE
├── get_quest_talk(npc_id, npc, game_state)  — quest-aware TALK dialogue
├── activate_quest(quest_id, game_state)  — initialize quest state
├── is_quest_active(quest_id, game_state)  — status check
└── is_quest_complete(quest_id, game_state) — status check
```

## Files to Modify

| File | Changes |
|------|---------|
| `engine/quest.py` | **NEW** — locked exit conditions, contextual USE, quest TALK, quest state helpers |
| `data/zones.json` | Add `verdant_wreck` zone (4 rooms, locked_exits on vw_barrier, no enemies) |
| `data/artifacts.json` | Add `bloom_catalyst` (uses_remaining: 5, mote_value: 5) |
| `data/npcs.json` | Add `lira` (non-recruitable botanist with quest dialogue) |
| `data/skerry.json` | Add void crossing from skerry_landing to vw_airlock |
| `models/room.py` | Add `locked_exits` field, `is_exit_locked()` method, serialize in `to_dict()` |
| `main.py` | `cmd_go`: check locked exits before movement. `cmd_use`: call `handle_quest_use()` before standard handling; add bloom_catalyst USE handler. `cmd_talk`: call `get_quest_talk()` for quest NPCs. Set `tutorial_quest_done` on bloom_catalyst discovery. |
| `engine/tutorial.py` | Add `tutorial_quest_done` as 7th objective. Add verdant wreck hints to `_explorer_free_hints()`. |
| `engine/save.py` | `new_game_state()`: add `quests`, `tutorial_quest_done`. `_migrate_state()`: defaults for old saves. |
| `engine/display.py` | Show locked exits with `(blocked)` indicator. Pass `game_state` or quest check to exit display. |

## Verification

1. New game → skip tutorial prologue → explorer phase
2. Do some debris_field objectives (combat, scavenge)
3. Return to skerry → seed hints about life in the void
4. `SEEK LIFE` from landing pad → void crossing to verdant wreck
5. Explore airlock → `SCAVENGE` for seeds/moss
6. `GO EAST` to greenhouse → see Lira
7. `TALK LIRA` → quest activates, shows greeting + root barrier hint
8. `TALK LIRA` again → repeats hint
9. `GO WEST`, `GO NORTH` to barrier → see locked exit north (blocked)
10. `GO NORTH` → blocked, shows "Massive roots block the passage..."
11. `USE TORCH` → "too thick and damp to catch" (before resin)
12. `USE RESIN` → roots weaken, resin consumed from inventory
13. `USE TORCH` → roots burn, passage opens, aspect changes
14. `GO NORTH` → Root Chamber, bloom_catalyst discovery text
15. `tutorial_quest_done` flag set
16. `LOOK` at bloom catalyst → shows description, aspects, mote value
17. `USE BLOOM CATALYST` → generates preserved_food + seeds, 4 blooms remaining
18. Use 4 more times → crystal crumbles, removed from inventory
19. Alternatively: `FEED BLOOM CATALYST` → 5 motes to seed
20. `TALK LIRA` after quest complete → shows quest_complete dialogue
21. Save/reload → quest state persists, uses_remaining persists
22. Old save file → migration adds quests={}, tutorial_quest_done=False gracefully
