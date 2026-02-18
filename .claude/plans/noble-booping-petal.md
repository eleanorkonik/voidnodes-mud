# Plan: Extended Tutorial (Explorer + Steward Acts)

## Context

The tutorial currently ends at the "handoff" step when Miria switches focus to Sevarik. After that, the player is dumped into free play with just a seed hint ("Go south, ENTER VOID"). This leaves them to figure out combat, recruiting, artifact handling, crafting, and building on their own.

The tutorial needs to continue through Sevarik's first expedition (Act 2) and Miria's first steward turn (Act 3) before the player is on their own. Additionally, the artifact teaching (IH → PROBE → KEEP/OFFER) currently happens in Miria's prologue with a random starter artifact — Eleanor wants this moved to Sevarik's exploration when he finds a real artifact in the debris field.

## New Tutorial Steps

```python
STEPS = [
    # Act 1 — Miria Prologue (SIMPLIFIED — artifact steps removed)
    "awakening",
    "naming",
    "first_look",
    "movement",
    "exploring",
    "check_seed",           # CHECK SEED — learn about motes and seed mechanics
    "handoff",              # Tuft asks permission to switch focus to Sevarik

    # Act 2 — Sevarik Explorer (NEW)
    "explorer_navigate",     # guide to landing pad
    "explorer_void_cross",   # ENTER VOID — first FWOOM
    "explorer_free",         # flexible exploration: combat, invoke, artifact, recruit
    "explorer_return",       # ENTER VOID back to skerry
    "explorer_artifact",     # resolve artifact: KEEP, OFFER TO SEED, or GIVE TO MIRIA
    "explorer_stash",        # go to junkyard, DROP materials
    "explorer_handoff",      # SWITCH FOCUS TO MIRIA

    # Act 3 — Miria Steward (NEW)
    "steward_arrive",        # orientation narration
    "steward_recipes",       # RECIPES
    "steward_craft",         # CRAFT basic_tools
    "steward_assign",        # ASSIGN recruited NPC
    "steward_complete",      # tutorial done

    "complete",
]
```

## Act 1 — Miria Prologue (Changes)

### Remove artifact steps

Current steps `artifact_ih`, `artifact_examine`, `artifact_use`, `artifact_choice` are removed from the prologue.

### `_show_the_split()` changes

Remove the starter artifact placement code (lines 319-335 of `engine/tutorial.py`):
- Remove `random.choice(["silver_slippers", "red_clown_nose"])` and `state["starter_artifact"]`
- Remove `room.add_item(artifact_id)`
- Instead, after the Quick Reference, prompt the player to CHECK the seed:

```python
display.seed_speak("Before we go further — CHECK me. See how I'm doing.")
_tutorial_prompt(f"CHECK {seed_name.upper()} to see the seed's status.")
game.state["tutorial_step"] = "check_seed"
```

### New `check_seed` step

After the player does CHECK SEED/TUFT, the seed explains motes and what they mean, then asks permission to switch focus to the explorer:

```python
if step == "check_seed" and cmd == "check":
    seed_name = game.state.get("world_seed_name", "Tuft")
    explorer_name = game.state.get("explorer_name", "Sevarik")
    print()
    display.seed_speak("See? I have motes. That's what keeps us alive here.")
    display.seed_speak("Feed me artifacts and materials, and I grow stronger.")
    display.seed_speak("The more motes I have, the more I can do for all of us.")
    print()
    display.seed_speak(f"Now... is it OK if I switch my focus to {explorer_name}?")
    display.seed_speak("Now that you're here, it's safe to let him explore.")
    _tutorial_prompt(f"SWITCH FOCUS TO {explorer_name.upper()} when you're ready.")
    game.state["tutorial_step"] = "handoff"
    return False
```

### `handoff` step changes

Instead of completing the tutorial, it continues to Act 2:

```python
if step == "handoff" and cmd == "switch":
    words = [w for w in args if w not in ("focus", "to")]
    target = " ".join(words).lower() if words else ""
    explorer_name = game.state.get("explorer_name", "Sevarik").lower()
    if target in (explorer_name, "explorer"):
        game.state["tutorial_step"] = "explorer_navigate"
        game._transition_to_day1()  # tutorial calls it directly
```

## Act 2 — Sevarik Explorer

### Step: `explorer_navigate`

**Trigger**: Prologue "handoff" step completes → `_transition_to_day1()` runs → seed gives direction.

**Advance when**: Player reaches `skerry_landing` (any `cmd == "go"` that lands them there).

**Seed guidance**: The seed already says "Go south to the landing pad, then ENTER VOID" in `_transition_to_day1()`. When the player arrives at landing pad, seed says: "Here. The edge of everything we have. ENTER VOID to cross."

### Step: `explorer_void_cross`

**Advance when**: Player's current room zone is NOT "skerry" (any `cmd == "enter"` that crosses zone boundary).

**Seed guidance**: After FWOOM and room display, seed says: "The debris field. Stay sharp. Explore carefully, and watch for danger."

### Step: `explorer_free`

This is the big flexible step. **Five objectives** tracked independently:

1. `tutorial_combat_done` — an enemy was defeated
2. `tutorial_invoke_done` — player successfully used INVOKE in combat
3. `tutorial_scavenge_done` — player successfully SCAVENGEd for materials
4. `tutorial_artifact_found` — player PROBEd and TAKEd an artifact (resolution deferred to skerry)
5. `tutorial_recruit_done` — player recruited an NPC

**FATE combat teaching flow:**

The tutorial teaches the full FATE combat loop: ATTACK to engage → INVOKE an aspect for +2 tactical advantage. This is the core FATE RPG mechanic.

Likely first encounter: the enemies in the Cargo Bay (Fight 2, 2 stress boxes + mild consequence). Sevarik has Fight 4, so expected +2 shifts on first ATTACK → absorbed by stress box 2, enemy survives. This lets the seed naturally prompt INVOKE after round 1.

**Enemy rename** in `zones.json`:
- `void_vermin_pack` → `rat_swarm` ("Rat Swarm") — cargo bay, Fight 2, the pack enemy
- `void_vermin_scout` → `hound_of_annwn` ("Hound of Annwn") — engine room, Fight 1, the lone enemy
- Update descriptions and aspects to match (rats = vermin swarm, hound = Welsh mythological spectral hound)
- Enemy aspects need updating: "You Can See Right Through Them" → something fitting for rats; "Separated From the Pack and Desperate" → something fitting for a lone otherworldly hound

Available aspects for the invoke tutorial (dynamically read from data):
- **Enemy**: First aspect of the current enemy — tutorial reads it dynamically
- **Sevarik**: "Battle-Scarred Veteran" — personal aspect
- **Room (cargo bay)**: "Something Moves When You're Not Looking"

**Artifact teaching flow:**

The stabilization_engine is in `df_engine_room` (along with an enemy). When Sevarik enters a room with a zone artifact, the seed detects it and guides:
1. IH to see what's here → PROBE to examine it → TAKE it → seed says "Bring it home. You'll decide what to do with it there."

KEEP/OFFER are **skerry-only** — the player can't resolve artifacts in the field. Resolution happens in the `explorer_artifact` step after returning home. The player can KEEP (stat bonus), OFFER TO SEED (motes), or GIVE TO MIRIA.

Bug fixes needed:
- **IH and display_room don't show zone artifacts** — they only check `room.items`, but zone artifacts are matched via `art.get("room") == room.id` in `artifacts_db`. Fix both `cmd_ih` and `display_room`.
- **TAKE doesn't work for zone artifacts** — same root cause. Fix `cmd_take` to also check `artifacts_db` for artifacts whose `room` field matches.
- **KEEP and OFFER need skerry restriction** — add zone check to `cmd_keep` and `cmd_offer`.

**Contextual hints** (after each command in this step):

| Situation | Seed Says |
|-----------|-----------|
| Room has enemies, not in combat, combat not done | "Those creatures! ATTACK them before they swarm you." |
| Just ATTACKed, enemy survived, invoke not done | "They're tough. Look — their aspects betray weaknesses. See '{first_enemy_aspect}'? INVOKE {aspect_shorthand} to use it against them. Costs a fate point, gives +2." (Dynamically reads the enemy's first aspect.) |
| Just ATTACKed, enemy died first hit, invoke not done | "Well fought. But aspects are your real weapon. Find another enemy and try INVOKE [aspect] during combat." |
| Just INVOKEd successfully | "That's it! Invoking aspects is the heart of combat. Use your aspects, the room's, even your enemy's." |
| Enemy defeated, loot on floor | "Don't leave that behind — TAKE it." |
| Combat+invoke done, scavenge not done | "Good fighting. Now SCAVENGE this area — Miria needs materials to work with." |
| Just SCAVENGEd successfully | "Good haul. Keep an eye out for artifacts and survivors too." |
| Room has undiscovered artifact, artifact not found | "I sense something powerful here. Try IH to see what's around, then PROBE it." |
| Just PROBEd an artifact | "Take it with you. TAKE it. We'll decide what to do with it back home." |
| Just TAKEd an artifact (artifact found) | "Good. Carry it home. You can decide its fate on the skerry." |
| Combat+invoke done, artifact found, room has NPCs, recruit not done | "Survivors! They could use a safe place. Try RECRUIT." |
| Combat+invoke done, artifact found, no NPCs visible, recruit not done | "There are survivors somewhere in this debris field. Find them and RECRUIT." |
| Just recruited | "Good. We could use the help. Head home — south and ENTER VOID." |
| All five objectives done | "You've done well. Head back to the skerry. South, then ENTER VOID." |

**Edge case — enemy one-shotted before invoke:** Seed guides player to find another enemy. Debris field has 3 enemies total across cargo bay, control room, and engine room.

**Advance when**: All five flags are True.

### Step: `explorer_return`

**Advance when**: Player's current room zone is "skerry" (after ENTER VOID back).

**What happens on advance:**
1. Move Miria's agent to `skerry_landing` (she comes to greet Sevarik):
   ```python
   miria_id = game.steward_name.lower()
   if miria_id in game.agents_db:
       game.agents_db[miria_id]["location"] = "skerry_landing"
   ```
2. Narration: `"Miria hurries out to the landing pad as you arrive."`
3. Advances to `explorer_artifact` (seed guides artifact resolution).

### Step: `explorer_artifact`

**Triggered** after `explorer_return` narration.

**Seed guidance**: "Now, what about that artifact you brought back? You have three choices: KEEP it for the stat bonus. OFFER it TO me for motes. Or GIVE it TO {steward_name}."

**Advance when**: `tutorial_artifact_resolved` is True — set by:
- `cmd_keep` (when artifact status set to "kept")
- `cmd_offer` (when artifact fed to seed)
- `cmd_give` (when artifact given to another character)

**Skip if**: Player has no unresolved artifacts in inventory (unlikely — seed guided them to TAKE one).

### Step: `explorer_stash`

**Seed guidance**: After artifact resolved: "Drop your salvage at the junkyard — Miria will know where to find it. Head west from the clearing."

**Advance when**: Player is in `skerry_junkyard` and does `cmd == "drop"` (materials dropped).

**Note**: Player should have materials from SCAVENGE (required objective) + combat loot. If somehow empty, skip — seed says "Nothing to stash. SWITCH FOCUS TO MIRIA."

### Step: `explorer_handoff`

**Advance when**: `cmd == "switch"` and phase changed to "steward".

## Act 3 — Miria Steward

### Step: `steward_arrive`

**Triggered immediately** when explorer_handoff advances. NOT waiting for a command.

**What happens**:
1. Seed: "Good haul. Head to the junkyard and see what you can make. Type RECIPES to check."

**Advance**: Immediately to `steward_recipes`.

### Step: `steward_recipes`

**Advance when**: `cmd == "recipes"`.

**Seed guidance**: After recipes display, seed says: "See anything you can make? Head to the junkyard — GO WEST — and try CRAFT BASIC TOOLS."

### Step: `steward_craft`

**Advance when**: `cmd == "craft"` and crafting succeeded. (Craft now checks room items too, so Miria can craft in the junkyard using stored materials.)

**Seed guidance**: On success: "Well done. Now put your recruit to work. ASSIGN {npc_name} SALVAGE — she can sort what comes in."
**On failure**: "That didn't work. Make sure you're in the junkyard with the materials."

### Step: `steward_assign`

**Advance when**: `cmd == "assign"` and an NPC has a non-idle assignment.

**Seed guidance**: On success: "Perfect. They'll process salvage while you focus on other things."

Closing speech: "That's the rhythm. Explorer gathers, steward builds. Keep going — you know what to do now. HELP is always there if you need it."

### Step: `steward_complete`

Set `tutorial_complete = True`. Tutorial done.

## New: GIVE Command (`main.py`)

Replace the stub `cmd_give` (line 866) with a working command. GIVE is for non-material items (artifacts, tools, etc.) between characters. Materials go to the junkyard via DROP.

**Syntax**: `GIVE <item> TO <name>`

**Implementation**:
```python
def cmd_give(self, args):
    if not args:
        display.error("Give what to whom? Usage: GIVE <item> TO <name>")
        return

    raw = " ".join(args)
    parts = raw.split(" to ", 1)
    if len(parts) < 2:
        display.error("Give what to whom? Usage: GIVE <item> TO <name>")
        return

    item_part = parts[0].strip().lower()
    target_name = parts[1].strip().lower()
    room = self.current_room()
    char = self.current_character()

    if not item_part:
        display.error("Give what? Usage: GIVE <item> TO <name>")
        return

    # Find target agent in room
    agent_id, agent_data = self._find_agent_in_room(target_name, room.id)
    if not agent_data:
        display.error(f"There's nobody called '{target_name}' here to give things to.")
        return

    # Determine target character object
    target_role = agent_data.get("role")
    target_char = self.steward if target_role == "steward" else self.explorer

    # Check artifacts first, then items
    art_id, art = self._find_entity(char.inventory, item_part, self.artifacts_db)
    if art:
        char.remove_from_inventory(art_id)
        target_char.add_to_inventory(art_id)
        self.state.setdefault("artifacts_status", {})[art_id] = "given"
        display.success(f"You give the {art['name']} to {agent_data['name']}.")
        return

    item_id, item = self._find_entity(char.inventory, item_part, self.items_db)
    if not item:
        display.error(f"You don't have anything called '{item_part}'.")
        return

    char.remove_from_inventory(item_id)
    target_char.add_to_inventory(item_id)
    display.success(f"You give {item['name']} to {agent_data['name']}.")
```

**Parser**: `give` is already registered in COMMANDS (line 49 of parser.py).

## New: DROP Command (`main.py`)

See Junkyard/Warehouse section below for implementation.

**Parser**: Add `"drop"` to COMMANDS dict and COMMAND_ALIASES.

## Bug Fixes: Zone Artifacts + Skerry-Only Restrictions

### `cmd_ih` (`main.py` ~line 526)

After showing `room.items`, also check `artifacts_db` for artifacts whose `room` matches:

```python
# Zone artifacts (not in room.items but matched by room field)
for art_id, art in self.artifacts_db.items():
    if art.get("room") == room.id and art_id not in room.items:
        status = self.state.get("artifacts_status", {}).get(art_id)
        if status not in ("kept", "fed"):
            print(f"  {display.item_name(art['name'])}")
            has_contents = True
```

### `display_room` (`engine/display.py` ~line 109)

Similar addition after the items section. Add after the items display:

```python
# Zone artifacts
artifacts = game_state.get("artifacts_db", {})
artifacts_status = game_state.get("artifacts_status", {})
for art_id, art in artifacts.items():
    if art.get("room") == room.id and art_id not in room.items:
        if artifacts_status.get(art_id) not in ("kept", "fed"):
            print(f"  You see: {item_name(art['name'])}")
```

Also need `artifacts_status` in `game_context()` return dict.

### `cmd_take` (`main.py` ~line 1594)

After the existing `room.items` artifact check (which only catches artifacts placed directly in room.items), add a check for zone artifacts:

```python
# Check zone artifacts (not in room.items but matched by room field)
art_id, art = self._find_in_db(target, self.artifacts_db)
if art and art.get("room") == room.id:
    status = self.state.get("artifacts_status", {}).get(art_id)
    if status not in ("kept", "fed"):
        art["room"] = None  # Remove from room
        self.current_character().add_to_inventory(art_id)
        display.success(f"You pick up the {art.get('name', art_id)}.")
        return
```

### `cmd_keep` (`main.py` ~line 1494) — skerry restriction

Add zone check at the top, after finding the artifact:

```python
room = self.current_room()
if room and room.zone != "skerry":
    display.error("You need to be back at the skerry to decide what to do with artifacts.")
    return
```

### `cmd_offer` (`main.py` ~line 1522) — skerry restriction for artifacts

When offering an artifact to the seed, add zone check:

```python
room = self.current_room()
if room and room.zone != "skerry":
    display.error(f"You need to be near {self.seed_name} on the skerry to offer artifacts.")
    return
```

Note: OFFER for regular items (feeding materials to seed) should also be skerry-only since the seed is physically there.

## Junkyard/Warehouse Room

Materials are stored in a **physical junkyard room** on the skerry, not transferred between characters. Sevarik drops materials there; Miria crafts there.

### New room in `data/skerry.json`

Add to `rooms` array:

```json
{
    "id": "skerry_junkyard",
    "name": "The Junkyard",
    "description": "A rough clearing where salvage gets piled. Metal scraps, wire coils, torn fabric — everything Sevarik drags back from the void ends up here, sorted by Miria into rough categories. It's not pretty, but it's organized enough to find what you need.",
    "zone": "skerry",
    "exits": {"east": "skerry_central"},
    "aspects": ["One Person's Trash Is Another's Foundation", "It Smells Like Rust and Ambition"],
    "items": [],
    "npcs": [],
    "enemies": [],
    "discovered": true,
    "structures": ["junkyard"],
    "assigned_npcs": [],
    "resources": {}
}
```

Add `"west": "skerry_junkyard"` to `skerry_central` exits.

### New DROP command

**Parser**: Add `"drop"` to COMMANDS dict with phases `["explorer", "steward", "prologue"]`, args `"required"`.

**Syntax**: `DROP <item>` or `DROP ALL` / `DROP MATERIALS`

```python
def cmd_drop(self, args):
    if not args:
        display.error("Drop what? DROP <item> or DROP ALL.")
        return

    target = " ".join(args).lower()
    char = self.current_character()
    room = self.current_room()

    if target in ("all", "materials"):
        dropped = []
        for item_id in list(char.inventory):
            if self.items_db.get(item_id, {}).get("type") == "material":
                char.remove_from_inventory(item_id)
                room.add_item(item_id)
                dropped.append(item_id)
        if dropped:
            counts = {}
            for mid in dropped:
                name = self.items_db.get(mid, {}).get("name", mid)
                counts[name] = counts.get(name, 0) + 1
            display.narrate("You pile your salvage on the ground.")
            for name, count in counts.items():
                if count > 1:
                    display.info(f"  {display.item_name(name)} x{count}")
                else:
                    display.info(f"  {display.item_name(name)}")
        else:
            display.narrate("You don't have any materials to drop.")
        return

    # Drop specific item
    item_id, item = self._find_entity(char.inventory, target, self.items_db)
    if item:
        char.remove_from_inventory(item_id)
        room.add_item(item_id)
        display.success(f"You set down the {item['name']}.")
        return

    display.error(f"You don't have anything called '{target}'.")
```

### Craft modification (`main.py` cmd_craft ~line 1700)

Craft now checks both inventory AND current room items for materials:

```python
# Check materials — inventory + room items
char = self.steward
room = self.current_room()
inv_counts = self._inventory_counts(char)
# Also count materials in the room
for item_id in (room.items if room else []):
    inv_counts[item_id] = inv_counts.get(item_id, 0) + 1
```

When consuming materials, prefer room items first (since that's where the junkyard stock is):

```python
# Consume materials — take from room first, then inventory
for mat, needed in recipe["materials"].items():
    for _ in range(needed):
        if room and mat in room.items:
            room.remove_item(mat)
        else:
            char.remove_from_inventory(mat)
```

### No auto-transfer

Remove any auto-transfer of materials between characters. The junkyard IS the transfer mechanism.

## Recipe Change (`engine/save.py`)

Add `"basic_tools"` to starting `discovered_recipes`:

```python
"discovered_recipes": ["rope", "torch", "basic_tools"],
```

## ASSIGN Task Rename: "scavenging" → "salvage" (`main.py`)

### `cmd_assign` (~line 1839)

Replace "scavenging" with "salvage" in `valid_tasks`:

```python
valid_tasks = ["salvage", "building", "gardening", "guarding", "crafting", "idle"]
```

Also update the error message:
```python
display.error("Usage: ASSIGN <npc> <task>  (tasks: salvage, building, gardening, guarding, crafting)")
```

### NPC task yields — deposit in junkyard room (~line 2056)

Change "scavenging" yield to "salvage" yield. Instead of adding to steward inventory, deposit in junkyard room:

```python
if task == "salvage":
    if random.random() < 0.6:
        loot = random.choice(["metal_scraps", "wire", "torn_fabric", "coral_fragments"])
        # Deposit in junkyard room, not steward inventory
        junkyard = self._get_room("skerry_junkyard")
        if junkyard:
            junkyard.add_item(loot)
        loot_name = self.items_db.get(loot, {}).get("name", loot)
        display.success(f"  {npc['name']} (salvage) processed: {loot_name}")
```

### `display_help` (~line 314)

Update steward ASSIGN description:
```python
("ASSIGN <npc> <task>", "Assign an NPC to a task"),
```
Valid tasks shown in error message, not help text.

### Save migration

Add migration for old saves with "scavenging" assignments:
```python
# Rename old "scavenging" task to "salvage"
for npc_id, npc in state.get("npcs_db", {}).items():
    if npc.get("assignment") == "scavenging":
        npc["assignment"] = "salvage"
```

## Tutorial Detection Hooks (`main.py`)

### Combat — in `_apply_enemy_damage()`, when enemy defeated:

```python
if not self.state.get("tutorial_complete"):
    self.state["tutorial_combat_done"] = True
```

### Invoke — in `cmd_invoke()`, after `spend_fate_point()` succeeds:

```python
if not self.state.get("tutorial_complete"):
    self.state["tutorial_invoke_done"] = True
```

### Scavenge — in `cmd_scavenge()`, when scavenge succeeds (shifts >= 0):

```python
if not self.state.get("tutorial_complete"):
    self.state["tutorial_scavenge_done"] = True
```

### Artifact found — in `cmd_take()`, when a zone artifact is picked up:

```python
if not self.state.get("tutorial_complete"):
    self.state["tutorial_artifact_found"] = True
```

### Artifact resolved — in `cmd_keep()`, `cmd_offer()`, and `cmd_give()` (when artifact transferred):

```python
if not self.state.get("tutorial_complete"):
    self.state["tutorial_artifact_resolved"] = True
```

### Recruit — detected in `after_command()` via `len(game.state.get("recruited_npcs", [])) > 0`.

## Game Loop Changes (`main.py`)

```python
# Before:
if phase == "prologue" and not self.state.get("tutorial_complete"):
    complete = tutorial.after_command(cmd, args, self)
    if complete:
        self._transition_to_day1()

# After:
if not self.state.get("tutorial_complete"):
    tutorial.after_command(cmd, args, self)
```

Tutorial runs during ALL phases while `tutorial_complete` is False. Transitions handled inside tutorial.

## Save Migration (`engine/save.py`)

Add to `_migrate_state`:
```python
state.setdefault("tutorial_combat_done", False)
state.setdefault("tutorial_invoke_done", False)
state.setdefault("tutorial_scavenge_done", False)
state.setdefault("tutorial_artifact_found", False)
state.setdefault("tutorial_artifact_resolved", False)
state.setdefault("tutorial_recruit_done", False)
if "basic_tools" not in state.get("discovered_recipes", []):
    state.setdefault("discovered_recipes", []).append("basic_tools")
```

## get_current_hint Updates

| Step | Hint |
|------|------|
| `exploring` | "Keep looking. There's someone here you need to meet." |
| `check_seed` | "CHECK {seed_name} to see the seed's status." |
| `handoff` | "SWITCH FOCUS TO {explorer} when you're ready." |
| `explorer_navigate` | "Head south to the landing pad." |
| `explorer_void_cross` | "ENTER VOID to cross to the debris field." |
| `explorer_free` | Contextual based on 5 objective flags (see hint matrix above) |
| `explorer_return` | "Head back south and ENTER VOID to go home." |
| `explorer_artifact` | "What will you do with the artifact? KEEP it, OFFER it TO {seed}, or GIVE it TO {steward}." |
| `explorer_stash` | "Drop your salvage at the junkyard. GO WEST from the clearing." |
| `explorer_handoff` | "SWITCH FOCUS TO {steward}." |
| `steward_arrive` | (auto-advances) |
| `steward_recipes` | "Type RECIPES to see what you can make." |
| `steward_craft` | "Head to the junkyard and try CRAFT BASIC TOOLS." |
| `steward_assign` | "ASSIGN {npc} SALVAGE." |

## Files Summary

| File | Changes |
|------|---------|
| `engine/tutorial.py` | Remove artifact steps from STEPS. Add Act 2+3 steps (including `check_seed`, `explorer_artifact`, `explorer_stash`). Remove starter artifact placement from `_show_the_split`. New handlers in `after_command()`. Updated `get_current_hint()`. |
| `main.py` | Game loop: tutorial runs all phases. Implement `cmd_give` (non-materials). New `cmd_drop`. Fix `cmd_ih` and `cmd_take` for zone artifacts. Skerry-only restriction on `cmd_keep`/`cmd_offer`. Craft checks room items. Tutorial detection hooks in `_apply_enemy_damage`, `cmd_invoke`, `cmd_scavenge`, `cmd_keep`, `cmd_offer`, `cmd_give`, `cmd_take`. Rename "scavenging" → "salvage" in `cmd_assign` valid_tasks. NPC "salvage" yield deposits in junkyard room. Add `artifacts_status` to `game_context()`. |
| `engine/display.py` | Fix `display_room` to show zone artifacts. |
| `engine/parser.py` | Add `drop` command. |
| `engine/save.py` | `basic_tools` in starting discovered_recipes. Migration for new tutorial state fields. Migration: rename NPC "scavenging" → "salvage". |
| `data/skerry.json` | Add `skerry_junkyard` room. Add west exit from `skerry_central`. |
| `data/zones.json` | Rename `void_vermin_pack` → `rat_swarm`, `void_vermin_scout` → `hound_of_annwn`. Update names, descriptions, aspects. |
| `data/artifacts.json` | No changes — stabilization_engine already has `room: "df_engine_room"`. |

## Verification

1. New game → prologue: awakening → bond → name → look → move → meet Sevarik → CHECK TUFT (learn about motes) → Tuft asks permission → SWITCH FOCUS TO SEVARIK
2. As Sevarik: GO SOUTH twice to landing pad → seed prompts ENTER VOID
3. ENTER VOID → FWOOM → arrive at debris field → seed says explore
4. GO NORTH to cargo bay → seed warns about enemies → ATTACK enemies
5. **Enemy survives first hit → seed teaches INVOKE, shows enemy aspects**
6. **INVOKE YOU CAN SEE → +2 bonus attack, seed celebrates**
7. Enemy defeated → loot drops → seed says "TAKE it" → seed says "SCAVENGE this area"
8. **SCAVENGE → find materials → seed says "Good haul"**
9. Navigate to engine room → **IH shows Stabilization Engine** (bug fix verified)
9. **PROBE STABILIZATION ENGINE → discovery text → seed says "TAKE it home"**
10. **TAKE STABILIZATION ENGINE → picked up, seed says "decide its fate on the skerry"**
11. RECRUIT EMMY or VARIS → seed says head home
12. Navigate south, ENTER VOID back → Miria comes to landing pad
13. **Seed prompts: KEEP, OFFER TO TUFT, or GIVE TO MIRIA**
14. **Player resolves artifact (KEEP, OFFER, or GIVE TO MIRIA) → tutorial_artifact_resolved**
15. **Seed prompts: drop salvage at junkyard**
16. **GO WEST to junkyard → DROP MATERIALS → materials stored in room**
17. **Seed prompts: SWITCH FOCUS TO MIRIA**
18. SWITCH FOCUS TO MIRIA → seed prompts RECIPES
19. RECIPES → see basic_tools → seed says head to junkyard
20. **GO WEST to junkyard → CRAFT BASIC TOOLS (uses room materials)** → seed prompts ASSIGN
21. ASSIGN {npc} SALVAGE → seed wraps up, tutorial_complete = True
22. Free play begins
23. Edge case: enemy one-shotted → seed mentions INVOKE for next fight
24. Edge case: KEEP/OFFER attempted in the field → error message tells player to go home
25. Old saves load without crash
26. Save mid-tutorial → resume shows correct hint
