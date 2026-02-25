# Split main.py into Domain Mixins

## Context

`main.py` is 5111 lines with 100+ methods on a single `Game` class. The rest of the project is already well-structured (~5200 lines across `engine/` and `models/`), but `Game` is a god object handling combat, movement, inventory, NPCs, artifacts, examination, building, skerry management, farming, and story scripting all in one file. It needs to be broken up.

## Approach: Mixin Classes

The command dispatch uses `getattr(self, f"cmd_{cmd}", None)` — any method on `self` gets routed. **Mixins** let us cut-paste methods into separate files with zero dispatch changes. `Game` inherits from all mixins, every `self.*` reference keeps working.

```python
# main.py after split
from commands.combat import CombatMixin
from commands.movement import MovementMixin
# ...

class Game(CombatMixin, MovementMixin, ItemsMixin, ...):
    # Core only: init, run, save/load, handle_command, switch, utilities
```

## Proposed Split

New directory: `commands/` (parallel to `engine/` and `models/`).

| File | ~Lines | What moves there |
|------|--------|------------------|
| `commands/combat.py` | 650 | cmd_attack, cmd_defend, cmd_exploit, cmd_invoke, cmd_concede, cmd_retreat, _combat_invoke, _invoke_attack/defend/setup, _display_invoke_menu, _general_invoke, _start_combat, _end_combat, _enemy_turn, _check_compel, _present_compel, _handle_compel_input, _apply_enemy_damage |
| `commands/movement.py` | 420 | cmd_go, cmd_seek, cmd_enter, _narrate_void_crossing, _get_void_crossings, _show_landing_pad_destinations, _match_zone_by_aspect, _on_room_enter |
| `commands/items.py` | 375 | cmd_take, cmd_drop, cmd_wear, cmd_remove, cmd_use, cmd_give, cmd_inventory |
| `commands/npcs.py` | 430 | cmd_talk, cmd_recruit, _handle_recruit_input, _recruit_invoke, _resolve_recruit, _move_followers, _followers_to_skerry, _followers_rejoin_explorer |
| `commands/artifacts.py` | 270 | cmd_feed, cmd_keep, cmd_offer, _on_artifact_resolved, _locate_artifact, _move_artifact, _artifacts_in_room, _get_artifact_hint |
| `commands/examine.py` | 620 | cmd_look, _examine_target, cmd_ih, cmd_status, cmd_check, cmd_probe, cmd_scavenge, cmd_map, cmd_quests |
| `commands/building.py` | 380 | cmd_craft, cmd_recipes, cmd_build, _get_build_sites, _parse_build_location |
| `commands/skerry_mgmt.py` | 310 | cmd_settle, cmd_assign, cmd_organize, cmd_tasks, cmd_rest, cmd_trade, cmd_store, _role_to_task, _count_settled_in_room, _deactivate_agent, _activate_agent, _find_agent_in_room |
| `commands/farming.py` | 350 | cmd_plant, cmd_harvest, cmd_survey, cmd_uproot, cmd_select, cmd_clone, _handle_cross_pollinate, cmd_bank, cmd_withdraw |
| `commands/story.py` | 390 | _quest_room_hints, _lira_blocks_torch, _lira_attacks, _handle_lira_defeat, _lira_fire_reaction, _seed_extraction, _day_transition, _transition_to_day1 |
| **main.py (core)** | ~900 | Game.__init__, properties, start, new_game, load/save, _hydrate/_dehydrate, run, handle_command, current_character/room, game_context, cmd_help/save/quit/done/fix/skip, cmd_switch + _switch_focus*, cmd_bond, cmd_request, _sub_dialogue, _find_entity/follower/in_db, _inventory_counts, _record_consequence, _consume_invoke_bonus, _get_zone_aspect* |

## Steps

1. Create `commands/__init__.py` (empty)
2. For each domain (combat first — it's the most self-contained):
   - Create `commands/<domain>.py` with `class <Domain>Mixin:`
   - Move the methods (preserving exact indentation/logic)
   - Add any needed imports at the top of the mixin file (display, dice, etc.)
   - Remove moved methods from main.py
3. Update `main.py`:
   - Import all mixins
   - `class Game(CombatMixin, MovementMixin, ItemsMixin, NpcsMixin, ArtifactsMixin, ExamineMixin, BuildingMixin, SkerryMgmtMixin, FarmingMixin, StoryMixin):`
   - Keep core methods in Game directly
4. Run the game to verify nothing broke

## What stays in main.py

- All `__init__` state setup (combat flags, recruit flags, etc.) stays — mixins don't define `__init__`
- The main loop (`run()`) stays — it's the core orchestrator
- `handle_command()` stays — unchanged, still uses getattr
- Character switching (`cmd_switch`, `_switch_focus*`) — cross-cutting, touches multiple domains
- `cmd_bond` — tutorial-specific, small
- `cmd_request` (healing, 150 lines) — could go in npcs.py but it's half healing-system, half story. Fine either way.
- Utility helpers (`_find_entity`, `_sub_dialogue`, `_inventory_counts`, etc.) — used by multiple domains

## Shared state note

All `self.*` state lives in `Game.__init__`. Mixins access it via `self`. No state duplication. If a combat method needs `self.in_combat`, it just reads it — same as today.

## Verification

1. `cd projects/voidnodes-mud && python3 main.py` — load a save, walk around, fight something, recruit, craft, farm
2. Verify command dispatch still works for every domain
3. Run any existing tests
