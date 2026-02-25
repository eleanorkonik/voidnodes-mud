# Unify Phase-Gated Command System

## Problem

Two systems gate commands by phase:

1. **Parser** (`parser.py`): Each command has a `phases` list. Wrong phase → generic error: `"'CMD' is not available during the X phase."`
2. **Help display** (`display.py`): Separate `explorer_cmds` and `steward_cmds` lists — you can't even see the other phase's commands.

Eleanor wants: all commands visible and dispatchable in both phases, with **narrative rejections** (seed speaks, not system errors) when a command doesn't apply.

## Command Inventory by Difficulty

### EASY — just needs a narrative rejection at the top

**Steward commands (explorer gets narrative rejection):**
- `rest` → seed: "Rest? Out here, rest means death."
- `build` → seed: "{steward_name} handles the building. You handle the void."
- `assign` → seed: "The people answer to {steward_name} here."
- `organize` → could just open up (it's a display command)
- `tasks` → could just open up (display command)
- `trade` → seed: "Trading is {steward_name}'s strength, not yours."
- `plant`, `harvest`, `survey`, `uproot`, `select`, `clone`, `cross-pollinate` → seed: "That's {steward_name}'s domain."
- `store`, `bank`, `withdraw` → seed: "{steward_name} manages the stores."

**Explorer commands (steward gets narrative rejection):**
- `attack` → narrate: "There's nothing to fight here. The skerry is safe."
- `scavenge` → seed: "The skerry's been picked clean. {explorer_name} can find materials out there."
- `recruit` → narrate: "Everyone here has already chosen to stay."
- `retreat` → seed: "Retreat where? You're already home."

**Already work for both (just open up the parser gate):**
- `defend`, `exploit`, `concede` — already check `in_combat` internally
- `keep`, `take` — already have zone/inventory checks
- `organize`, `tasks` — pure display

### MEDIUM — hardcoded `self.explorer`/`self.steward` references

| Command | File | Issue |
|---------|------|-------|
| `scavenge` | examine.py | Uses `self.explorer` directly for inventory |
| `recruit` | npcs.py | Uses `self.explorer` for FP/skill checks |
| `retreat` | combat.py | Uses `self.state["explorer_location"]` |
| `build` | building.py | Uses `self.steward` for material counting |

Fix: replace with `self.current_character()` + add narrative guard.

### HARD — fundamentally different behavior per phase

| Command | File | Issue |
|---------|------|-------|
| `cmd_go` (cross-zone) | movement.py:349 | Explorer gets SEEK hints, steward gets blocked |
| `_show_landing_pad_destinations` | movement.py:75 | Only shows for explorer |

Fix: Replace steward's `"You can't go that way."` with seed: `"The void crossing is too dangerous. {explorer_name} can handle it."` Keep landing pad destinations silent for steward (showing nodes she can't reach is noise).

## Implementation Steps (incremental, each independently deployable)

### Step 1: Add `_wrong_phase_narrate()` helper to `main.py`

```python
def _wrong_phase_narrate(self, intended_role, context=None):
    """Narrative rejection when a command is used by the wrong character."""
    phase = self.state["current_phase"]
    other = self.steward_name if phase == "explorer" else self.explorer_name
    messages = {
        ("steward", "farming"): f"That's {other}'s domain. Your hands are better suited to a blade.",
        ("steward", "building"): f"{other} handles the building. You handle the void.",
        ("steward", "management"): f"The people answer to {other} here. Focus on what's out there.",
        ("steward", "stores"): f"{other} manages the stores.",
        ("explorer", "combat"): None,  # use narrate instead
        ("explorer", "scavenge"): f"The skerry's been picked clean. {other} can find materials out there.",
        ("explorer", "void"): f"The void is {other}'s domain. I need you here.",
    }
    key = (intended_role, context)
    msg = messages.get(key)
    if msg:
        display.seed_speak(msg)
    elif intended_role == "explorer" and context == "combat":
        display.narrate("There's nothing to fight here. The skerry is safe.")
    else:
        display.seed_speak(f"Leave that to {other}.")
```

### Step 2: Open parser phase gates

Change all `phases` lists in `COMMANDS` dict to `["explorer", "steward", "prologue"]` (except `skip`).

### Step 3: Remove phase gate from main loop

Delete the `is_valid_for_phase()` check in `main.py` dispatch (around line 365-367).

### Step 4: Add narrative guards to command handlers

One `if` check at the top of each handler. Do one file at a time:
- `farming.py` — 9 commands, all context "farming" or "stores"
- `building.py` — `cmd_build`, context "building"
- `skerry_mgmt.py` — `cmd_assign`, context "management"
- `combat.py` — `cmd_attack`, context "combat"
- `examine.py` — `cmd_scavenge`, context "scavenge"
- `npcs.py` — `cmd_recruit`, context "void"
- `movement.py` — cross-zone in `cmd_go`, context "void"

### Step 5: Fix hardcoded character references

Replace `self.explorer` / `self.steward` with `self.current_character()` in scavenge, recruit, retreat, build.

### Step 6: Unify `display_help()`

Replace separate explorer/steward sections with domain-grouped commands:
- **Movement & Exploration**: GO, SEEK, ENTER, RETREAT, SCAVENGE, INVESTIGATE
- **Combat**: ATTACK, DEFEND, EXPLOIT, CONCEDE, INVOKE
- **Artifacts & Items**: PROBE, KEEP, FEED, TAKE, OFFER
- **Settlement**: BUILD, CRAFT, RECIPES, ASSIGN, ORGANIZE, TASKS
- **Farming**: PLANT, HARVEST, SURVEY, UPROOT, STORE
- **Information**: IH, LOOK, STATUS, CHECK, MAP, QUESTS

Show all commands to both phases. The narrative rejections handle the rest.

### Step 7: Test

Verify every command in both phases — each should either work or give an immersive narrative rejection. Check prologue phase separately (tutorial state machine handles most gating there).

## Edge Cases

- **Prologue**: Tutorial state machine gates commands via `after_command` hook, not parser phases. Keep `skip` prologue-only. Everything else handled by tutorial.
- **Combat**: `in_combat` checks inside handlers already prevent wrong-phase weirdness. No changes needed.
- **Recruit/Compel minigames**: Intercept raw input before parser dispatch. No changes needed.
