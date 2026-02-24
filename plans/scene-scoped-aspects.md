## Context

Aspects can be invoked repeatedly across encounters within the same zone visit — the per-combat and per-recruitment tracking resets when each encounter ends. This makes broad aspects (especially the high concept) feel like a free +2 button rather than a tactical resource. Eleanor wants aspects to be **scene-scoped**: once invoked anywhere during a day, they're used up until the next day.

## Design

**Single set `self.scene_invoked_aspects`** replaces both `self.invoked_aspects` (per-combat) and `recruit_state["invoked_aspects"]` (per-recruitment). All invoke contexts write to and check this one set.

**Scene boundary = day change.** The set resets in `_day_transition()` (commands/story.py). Day increments happen via REST (steward), SEEK/ENTER home (returning to skerry from void), and seed extraction (emergency teleport) — all call sites funnel through `_day_transition()`.

**Compels count as usage.** When an enemy compels an aspect and the player accepts OR refuses, that aspect is marked used for the scene.

**New ASPECTS command.** Shows all invokable aspects with used ones dimmed: `✗ Aspect Name (source) (used)` in `display.DIM`. INVOKE menu gets the same treatment (already has this pattern for per-combat; just needs to use the scene set).

**Saved.** The set persists across save/load so quitting mid-zone doesn't reset cooldowns. Stored as a list in `state["scene_invoked_aspects"]`, hydrated back to a set on load.

## Files to Change

### 1. `main.py` — Rename field + save/load

Line 83: `self.invoked_aspects = set()` → `self.scene_invoked_aspects = set()`

**`_hydrate()`:** Load from state: `self.scene_invoked_aspects = set(self.state.get("scene_invoked_aspects", []))`

**`_dehydrate()`:** Save to state: `self.state["scene_invoked_aspects"] = list(self.scene_invoked_aspects)`

### 2. `commands/combat.py` — Biggest change surface

**`_start_combat` (~line 462):** Remove `self.invoked_aspects = set()` — scene set must NOT reset on fight start.

**`_end_combat` (~line 480):** Remove `self.invoked_aspects = set()` — scene set must NOT reset on fight end.

**`_combat_invoke` (238–307):** All `self.invoked_aspects` → `self.scene_invoked_aspects`. The "already invoked this fight" error text changes to "already invoked this scene."

**`_general_invoke` (192–236):**
- Add scene-used check after fuzzy match (currently has none):
  ```python
  if found in self.scene_invoked_aspects:
      display.error(f"You've already invoked {display.aspect_text(found)} this scene.")
      # show remaining
      return
  ```
- After spending FP: `self.scene_invoked_aspects.add(found)`
- Menu display (lines 197–208): split into available/used like `_display_invoke_menu` already does

**`_display_invoke_menu` (309–344):** Line 316 currently branches on context (`self.invoked_aspects` vs `recruit_state`). Replace with just `self.scene_invoked_aspects` always.

**`_handle_compel_input` (~line 597):** After compel resolves (both ACCEPT and REFUSE branches), add `self.scene_invoked_aspects.add(compel["aspect"])`.

**`_seed_extraction` (~line 715):** Currently does NOT increment the day. Add day increment + `_day_transition()` call after relocating to skerry (before the narration). This makes extraction a proper scene boundary and aligns it with SEEK home.

### 3. `commands/npcs.py` — Merge recruitment tracking

**`_recruit_invoke` (304–386):**
- Remove `state["invoked_aspects"]` init and all references
- Replace with `self.scene_invoked_aspects` throughout
- Error text: "already invoked this scene" (not "this conversation")

### 4. `commands/story.py` — Reset on day change

**`_day_transition()` (~line 166):** Add `self.scene_invoked_aspects = set()` at the top. This is the single reset point — REST, SEEK home, and ENTER home all funnel through here.

### 5. `engine/parser.py` — Register ASPECTS command

```python
"aspects":   {"phases": ["explorer", "steward"], "args": "none"},
```

### 6. `commands/examine.py` — New `cmd_aspects()`

```python
def cmd_aspects(self, args):
    """ASPECTS — Show all invokable aspects, with used ones dimmed."""
    char = self.current_character()
    context = "combat" if self.in_combat else "recruit" if self.in_recruit else "combat"
    all_aspects = aspects.collect_invokable_aspects(self, context=context)

    available = [(a, s) for a, s in all_aspects if a not in self.scene_invoked_aspects]
    used = [(a, s) for a, s in all_aspects if a in self.scene_invoked_aspects]

    # Header + available + used (dimmed) + FP info
```

### 7. `engine/display.py` — Add ASPECTS to help text

Line 333 area, add to `universal` list:
```python
("ASPECTS", "Show your aspects (used ones dimmed)"),
```

## Edge Cases

- **Steward phase:** Steward can INVOKE for craft/treatment checks. The scene set persists from the explorer's day. SWITCH FOCUS does NOT trigger a day change, so invokes carry across phases within the same day — which is correct.
- **Seed extraction:** Now increments the day and calls `_day_transition()`, so aspects reset. Extraction is traumatic but a new day begins.
- **Save/load:** Set is persisted in `state["scene_invoked_aspects"]` as a list, hydrated to a set on load. Quitting mid-zone doesn't reset cooldowns.
- **Pending floating invoke:** If the player invoked an aspect (general context) and hasn't consumed the +2 yet, the aspect is already in `scene_invoked_aspects`. The floating bonus is consumed by `_consume_invoke_bonus()` as before — no change needed there.

## Verification

1. Start of day → `ASPECTS` shows all available, none used
2. `INVOKE <aspect>` in combat → that aspect dimmed in `ASPECTS` and `INVOKE` menu
3. End combat → start new fight in same zone → aspect still dimmed
4. `INVOKE <aspect>` during recruitment → same scene set applies
5. `INVOKE <aspect>` outside combat → scene-used check fires, aspect dimmed
6. Enemy compel triggers → compelled aspect now dimmed in `ASPECTS`
7. Return home (day change) → all aspects reset to available
8. Seed extraction (no day change) → aspects stay used
