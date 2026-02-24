# Voidnodes MUD → Comic Pipeline: Data Enrichment Plan

## Context

Eleanor generates comic pages from the Voidnodes fountain script using Gemini Nano Banana Pro. The current session proved this works — but only because the fountain script has rich visual prose (150+ word character descriptions, spatial layout instructions, lighting cues). The MUD's save files capture game state but lack the visual detail needed to generate consistent comic panels. This plan enriches the MUD data so that a **fully automated** pipeline can turn any completed playthrough into a retrospective comic — regardless of which characters the player chose (Sevarik/Miria are just defaults).

## Current State Assessment

### What exists and works
- **Room descriptions**: 60-120 words, good atmosphere/mood, weak on spatial specifics
- **Enemy descriptions**: Strong visual detail (colors, textures, behavior, movement)
- **Item descriptions**: Solid visual language, especially artifacts
- **NPC personality**: Extremely rich dialogue, recruit_flavor, mood states
- **Event log**: Exists but minimal — only 2 append points (day transition + recruitment)
- **Color palette**: Established (blue-green coral, white/red hound, pale rats, amber resin)

### What's missing
- **Character appearance**: Nearly zero. Sevarik = "khaki_jumpsuit" + "work_boots". No scars, build, face, hair
- **Spatial layout**: No foreground/mid/background, no camera angles, no scale references
- **Lighting**: "Glows" and "pulses" but no direction or shadow behavior
- **Narrative log**: Event log doesn't capture combat, discoveries, emotional beats
- **Reference images**: No character consistency mechanism
- **Comic generation script**: Nothing to transform save data → image prompts

## Plan

### Phase 1: Add `desc` blocks to character/NPC data

**Files:** `data/npcs.json` (+ README hook for player characters)

Add a `desc` string to every NPC. Shown when a player LOOKs at/PROBEs a character, and used as image generation prompt fragment for comics.

**Description rules** (per [Lusternia's HELP DESCRIPTION](https://www.lusternia.com/in-game-help-files/?id=144)):
- **Static and always-true** — no movements, poses, or actions. The character might be asleep, sitting, or fighting. The description must apply regardless.
- **No clothing or weapons** — outfit comes from `worn` dict + item `desc` at render time. Baking clothes into the description will contradict actual equipment.
- **Physical appearance only** — build, face, hair, skin, scars, distinguishing physical marks.
- **Format:** `"{name} is a {size} {species/type}. {Physical details}."`

```json
{
  "varis": {
    "desc": "Varis is a lean, wiry man of average height with sharp features, watchful grey eyes, and olive skin. A thin scar crosses the bridge of his nose. His black hair is tied back in a short tail, streaked with grey at the temples. He looks to be in his early forties."
  }
}
```

**Player characters (Sevarik/Miria):** Don't add `desc` to `characters.json` — players should set their own during character creation. Add a `TODO: character creation — player sets desc via DESCRIBE SELF` hook in `README.md` so we build that later.

Outfit is derived at comic-generation time from `worn` dict → items.json `desc`, plus event log context. Outfit changes during gameplay are automatically reflected.

NPCs to write descriptions for: **Varis, Emmy, Chris, Dax, Eudora, Tilly, Callum, Petra, Fen** (npcs.json) = 9 total.

### Phase 2: Add `visual` to clothing items

**File:** `data/items.json`

Add a `visual` field to every wearable item so outfits can be assembled from worn dict:

```json
{
  "khaki_jumpsuit": {
    "desc": "Sturdy khaki canvas jumpsuit, zippered front, scuffed at knees and elbows. Sleeves can roll up. Utilitarian, no ornamentation."
  },
  "red_sundress": {
    "desc": "Simple crimson-red cotton sundress, thin straps, knee-length with a slight A-line flare. Practical but feminine."
  }
}
```

This means when the pipeline reads a save file and sees `worn.torso = "khaki_jumpsuit"`, it can look up the visual description automatically.

### Phase 3: Add `desc` blocks to rooms and zones

**Files:** `data/zones.json`, `data/skerry.json`

Add to each zone (inherited defaults):
```json
{
  "debris_field": {
    "desc": {
      "atmosphere": "Cold void exposure. Jagged metal silhouettes against cosmic darkness.",
      "palette": "Dark steel, void black, occasional amber sparks",
      "lighting": "No ambient source. Objects lit by residual glow and void-light."
    }
  }
}
```

Add to each room (overrides zone defaults):
```json
{
  "id": "df_cargo_bay",
  "desc": {
    "composition": "Wide interior shot. Massive space, high ceiling. Cargo crates in uneven rows, some floating.",
    "lighting": "Dim amber glow from cracked emergency strips on ceiling. Shadows pool between crates.",
    "palette": "Steel grey, rust brown, emergency-strip amber",
    "scale": "Cathedral-sized. Characters small against the space.",
    "landmarks": ["Floating cargo crates", "Peeled-open hull walls", "Emergency light strips"]
  }
}
```

Total rooms to enrich: ~30 (debris field 6, coral thicket 6, frozen wreck 6, biodome 6, skerry 10+).

### Phase 4: Enrich event_log into structured narrative journal — TOP PRIORITY

**Files:** ALL command files + `engine/save.py`

This is the most important phase. Every state-changing action in the game should be logged. Migrate event_log entries from strings to dicts. Add a helper function (e.g. `self._log_event(type, **kwargs)`) to avoid duplicating the logging pattern everywhere.

```json
{
  "day": 2, "phase": "explorer", "type": "combat_victory",
  "actor": "sevarik", "target": "rat_swarm", "location": "df_hull_breach",
  "details": "Won by invoking 'Battle-Scarred Veteran'. Took 2 stress.",
  "comic_weight": 3
}
```

`comic_weight` (1-5) indicates narrative importance for the automatic pipeline:
- **5**: Artifact discovery/resolution, boss fights, NPC recruitment, seed growth milestones
- **4**: First room/zone discovery, combat with consequences, character taken out
- **3**: Regular combat victories, quest progress, structure building, crafting
- **2**: Room discoveries, mood changes, equipment changes, scavenging
- **1**: Routine actions, minor state changes, movement

**Complete event type table** (every cmd_* action in the codebase):

#### combat.py
| Type | Function | Weight | Details to capture |
|------|----------|--------|--------------------|
| `combat_start` | cmd_attack + _on_room_enter | 2 | enemy type, location, ambush? |
| `combat_victory` | combat resolution | 3 | enemy, aspect invoked, stress taken |
| `combat_defeat` | combat resolution | 4 | enemy, consequences taken |
| `consequence_taken` | damage resolution | 4 | severity (mild/mod/severe), description |
| `stress_taken` | damage resolution | 1 | boxes filled |
| `aspect_invoked` | cmd_invoke | 2 | which aspect, fate points spent |

#### movement.py
| Type | Function | Weight | Details to capture |
|------|----------|--------|--------------------|
| `zone_entered` | cmd_seek / cmd_enter | 4 (first visit) / 2 | zone name, motes spent by seed |
| `room_entered` | cmd_go | 1 | room id, first visit? |
| `room_discovered` | cmd_go / _on_room_enter | 2 (4 if first in zone) | room id, zone |
| `ambush` | _on_room_enter | 3 | enemy type, initiative result |

#### items.py
| Type | Function | Weight | Details to capture |
|------|----------|--------|--------------------|
| `item_taken` | cmd_take | 1 | item id, from room |
| `item_dropped` | cmd_drop | 1 | item id, at room |
| `item_worn` | cmd_wear | 2 | item id, slot |
| `item_removed` | cmd_remove | 1 | item id, slot |
| `item_used` | cmd_use | 2 | item id, target, effect |
| `item_given` | cmd_give | 2 | item id, from→to character |
| `food_consumed` | cmd_use (food) | 1 | item, stress healed |

#### artifacts.py
| Type | Function | Weight | Details to capture |
|------|----------|--------|--------------------|
| `artifact_probed` | cmd_probe (examine.py) | 3 | artifact id, aspects revealed |
| `artifact_found` | cmd_take (items.py) | 5 | artifact id, location |
| `artifact_kept` | cmd_keep | 5 | artifact id, bonuses applied |
| `artifact_fed` | cmd_feed / cmd_offer | 5 | artifact id, motes gained |
| `seed_growth` | cmd_feed / cmd_offer | 5 | new stage, total motes |

#### npcs.py
| Type | Function | Weight | Details to capture |
|------|----------|--------|--------------------|
| `recruit_started` | cmd_recruit | 2 | NPC name, difficulty |
| `recruit_success` | _resolve_recruit | 5 | NPC name, loyalty tier |
| `recruit_failed` | _resolve_recruit | 3 | NPC name, reason |
| `npc_talked` | cmd_talk | 1 | NPC name, dialogue type |
| `npc_mood_change` | various | 2 | NPC, old→new mood, cause |
| `treatment_given` | cmd_request | 3 | target, consequence healed |

#### building.py
| Type | Function | Weight | Details to capture |
|------|----------|--------|--------------------|
| `item_crafted` | cmd_craft | 3 | recipe, success/fail, masterwork? |
| `structure_built` | cmd_build | 3 | room id, materials used |
| `house_built` | cmd_build (NPC house) | 3 | NPC name, level |

#### farming.py
| Type | Function | Weight | Details to capture |
|------|----------|--------|--------------------|
| `specimen_planted` | cmd_plant | 2 | specimen, plot |
| `harvest` | cmd_harvest | 2 | plot, yield |
| `plant_uprooted` | cmd_uproot | 1 | specimen, plot |
| `selective_breed` | cmd_select | 2 | trait adjusted |
| `cross_pollinate` | cmd_cross_pollinate | 3 | parents, offspring traits |
| `specimen_banked` | cmd_bank | 1 | specimen, vault entry |
| `specimen_withdrawn` | cmd_withdraw | 1 | specimen, vault entry |

#### skerry_mgmt.py
| Type | Function | Weight | Details to capture |
|------|----------|--------|--------------------|
| `npc_settled` | cmd_settle | 3 | NPC, room assigned |
| `npc_assigned` | cmd_assign | 2 | NPC, task/subtask |
| `food_stored` | cmd_store | 1 | item, quantity |

#### story.py
| Type | Function | Weight | Details to capture |
|------|----------|--------|--------------------|
| `day_transition` | _day_transition (exists) | 1 | day number, food consumed, events |
| `npc_departed` | _day_transition (starvation) | 4 | NPC name, cause |
| `random_event` | _day_transition | 2 | event type, outcome |
| `phase_change` | _transition_to_day1 | 3 | prologue→explorer |
| `quest_started` | various | 3 | quest id |
| `quest_completed` | various | 5 | quest id |
| `artifact_resolved` | story resolution | 5 | artifact, choice made |
| `lira_encounter` | _lira_* functions | 4 | which event, outcome |
| `character_switched` | cmd_switch | 1 | from→to character |

Migrate existing string entries to dict format in `engine/save.py:_migrate_state()`.

### Future: Comic generation script + reference images

Deferred — build `tools/generate_comic.py` and `data/references/` later once the data and logging foundation is solid.

## Files to modify

### Priority 1: Event logging (Phase 4)
| File | Change |
|------|--------|
| `main.py` or `engine/save.py` | Add `_log_event()` helper method |
| `engine/save.py` | Migrate event_log string→dict in `_migrate_state()` |
| `commands/combat.py` | Log combat start/victory/defeat, consequences, stress, invokes |
| `commands/movement.py` | Log zone entry, room discovery, ambushes |
| `commands/items.py` | Log take/drop/wear/remove/use/give |
| `commands/artifacts.py` | Log feed/keep/offer |
| `commands/examine.py` | Log probe (artifact discovery), scavenge |
| `commands/npcs.py` | Log recruit start/success/fail, talk, mood changes, treatment |
| `commands/building.py` | Log craft (success/fail), build structures, build houses |
| `commands/farming.py` | Log plant/harvest/uproot/select/cross-pollinate/bank/withdraw |
| `commands/skerry_mgmt.py` | Log settle, assign, store, rest |
| `commands/story.py` | Log day transition details, phase changes, quest progress, lira events, switch |

### Priority 2: Data enrichment (Phases 1-3)
| File | Change |
|------|--------|
| `data/npcs.json` | Add `desc` block to all 9 NPCs |
| `data/items.json` | Add `desc` to wearable items |
| `data/zones.json` | Add zone-level + per-room `desc` blocks (~30 rooms) |
| `data/skerry.json` | Add `desc` blocks to skerry rooms (~10 rooms) |
| `README.md` | Add TODO hook for player character `desc` during character creation |

### Deferred: Comic generation (Phases 5-6) — build later

## Execution order

1. **Phase 4 FIRST (event logging)** — highest priority, Python changes across all command files, needs playtesting
2. Phases 1-3 (data enrichment) — can be done in parallel, pure JSON edits
3. Phases 5-6 (comic generation) — deferred, build later

## Verification

1. `python -c "import json; d=json.load(open('data/npcs.json')); assert 'desc' in d['varis']"` — desc blocks present on NPCs
2. Start new game → play through prologue → SEEK to debris field → one combat → SCAVENGE → SWITCH → CRAFT → save → check event_log has structured dicts for ALL actions taken
3. Count event_log entries vs actions taken — should be 1:1 (every state change logged)
4. Spot-check: `desc` blocks on NPCs render sensibly if shown to player via PROBE
