---
shaping: true
---

# Zone-Centric Data Architecture — Shaping

## Source

> use the /shaping skill to see if there's maybe a better way to go about these patterns, like maybe we should re-organize the files so that ZONES are the main unit, not NPCs, since it's likely that we'll create lots of zones moreso than bulk create NPCs.. and this will allow us to 'archive' 'cleared' zones so that the game isn't actively reading the ENTIRE npc file to just deal with skerry_npcs for example.

> ugh i don't think this will work because there's going to be multiple playthrus and saves and it would be bad if the npcs moved files a lot.

Concern: with NPCs inside zone files, the source of truth splits — the zone file is the template, but the save file has the mutated runtime state (recruited/location/mood). Multiple saves with the same NPC in different states makes it unclear "where the NPC lives."

## Requirements (R)

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | Zone data is organized per-zone, not in one monolithic zones.json | Core goal |
| R1 | Cleared zones can be unloaded from runtime memory while data files remain for new playthroughs and comic pipeline | Must-have |
| R2 | Skerry NPC operations (ASSIGN, ORGANIZE, follower lookups) don't iterate unrecruited zone NPCs | Must-have |
| R3 | Existing save files load without data loss | Must-have |
| R4 | Items, recipes, events, characters, seed config remain global shared resources | Must-have |
| R5 | NPCs and artifacts have a single, unambiguous source-of-truth file that doesn't change based on zone lifecycle | Must-have |
| R6 | Minimal engine code changes — loader changes in save.py, not every command mixin | Nice-to-have |

## CURRENT

Global flat files loaded at startup into a single state dict:

| File | Contains |
|------|----------|
| `zones.json` | 4 zones with nested rooms + enemies_data (~26KB) |
| `npcs.json` | All 8 NPCs across all zones + tutorial (~31KB) |
| `artifacts.json` | All 6 artifacts across all zones (~3KB) |
| `items.json` | All items/materials/clothing (~6KB) |
| `skerry.json` | Home base rooms (~4KB) |
| `recipes.json`, `characters.json`, `tuft.json`, `events.json` | Global config |

**Zone creation requires editing:** zones.json + npcs.json + artifacts.json + (maybe) items.json + skerry.json landing pad. That's 4-5 files.

**Runtime:** All data loaded once by `new_game_state()`, stays in memory forever. `_find_follower()` iterates every NPC for every follower check.

**Unloading:** Not possible — rooms/enemies/NPCs are in flat dicts with no zone grouping at runtime.

## A: Per-zone files (NPCs inside zone files)

~~Previously explored.~~ **Rejected** — puts NPC definitions inside zone files, creating source-of-truth confusion across multiple save files. An NPC's template lives in the zone file, but its mutated state lives in the save file. "Where does Emmy live?" has two answers depending on context.

## C: Per-zone room files + global NPCs/artifacts with originZone tags

**Split zones.json into per-zone files for rooms/enemies. Keep NPCs and artifacts in their own global files with an `originZone` field for grouping.**

```
data/
  zones/
    debris_field.json     # rooms, enemies, scavenge_pool, zone metadata
    coral_thicket.json
    frozen_wreck.json
    verdant_wreck.json
  npcs.json               # ALL NPCs — single source of truth, tagged with originZone
  artifacts.json          # ALL artifacts — single source of truth, tagged with originZone
  items.json              # global
  skerry.json             # home base rooms
  recipes.json            # global
  characters.json         # global
  tuft.json               # global
  events.json             # global
```

**Zone file schema** (rooms + enemies only):
```json
{
  "id": "debris_field",
  "name": "The Debris Field",
  "description": "A slowly tumbling mass of wreckage...",
  "aspect": "A Dead Ship Still Full of Secrets",
  "difficulty": "easy",
  "scavenge_pool": ["metal_scraps", "wire", "torn_fabric"],
  "entry_room": "df_entrance",
  "rooms": [ { "id": "df_entrance", ... }, ... ],
  "enemies_data": [ { "id": "rat_swarm", ... }, ... ]
}
```

**NPC entries gain an `originZone` field** (npcs.json):
```json
{
  "emmy": { "name": "Emmy", "originZone": "debris_field", "location": "df_cargo_bay", ... },
  "varis": { "name": "Varis", "originZone": "skerry", "location": null, ... }
}
```

**Artifact entries gain an `originZone` field** (artifacts.json):
```json
{
  "stabilization_engine": { "originZone": "debris_field", "location": {"type": "room", "id": "df_engine_room"}, ... }
}
```

**Parts:**

| Part | Mechanism | Flag |
|------|-----------|:----:|
| **C1** | Split `zones.json` → per-zone files in `data/zones/` (rooms + enemies_data + metadata only). | |
| **C2** | Add `"originZone"` field to each NPC in `npcs.json` and each artifact in `artifacts.json`. | |
| **C3** | Update `save.py:new_game_state()` to iterate `data/zones/*.json` instead of loading one `zones.json`. NPCs and artifacts load from their existing global files as before. | |
| **C4** | Use `state["recruited_npcs"]` list + NPC `originZone` field for efficient iteration. `_find_follower()` only scans recruited NPCs. Skerry management filters by `originZone == "skerry"` or `recruited == true`. | |
| **C5** | Runtime zone unloading: on zone clear, remove zone rooms from `self.rooms`, zone enemies from `self.enemies_db`. NPCs stay in `npcs_db` (source of truth), but unrecruited zone NPCs are skipped in iteration via the `originZone` tag + `recruited` flag. | |

**Zone creation workflow:** Create zone file in `data/zones/` + add NPCs to `npcs.json` + add artifact to `artifacts.json` + wire landing pad in `skerry.json`. 3-4 files, but the zone creation **skill** orchestrates all of it as one unit of work.

**Source of truth:** NPCs always live in `npcs.json`. Artifacts always live in `artifacts.json`. No ambiguity. Save files store mutated runtime state, but the template definitions have one canonical home.

**Runtime unloading:** Zone rooms and enemies are removed from runtime dicts on clear. NPCs stay loaded but are efficiently skippable via `originZone` tag + `recruited` flag. Event log preserves all zone history.

## Fit Check

| Req | Requirement | Status | CURRENT | C |
|-----|-------------|--------|---------|---|
| R0 | Zone data organized per-zone, not monolithic | Core goal | ❌ | ✅ |
| R1 | Cleared zones can be unloaded from runtime | Must-have | ❌ | ✅ |
| R2 | Skerry NPC ops don't iterate zone NPCs | Must-have | ❌ | ✅ |
| R3 | Existing saves load without data loss | Must-have | ✅ | ✅ |
| R4 | Items/recipes/events remain global | Must-have | ✅ | ✅ |
| R5 | NPCs/artifacts have single unambiguous source-of-truth file | Must-have | ✅ | ✅ |
| R6 | Minimal engine code changes | Nice-to-have | ✅ | ✅ |

**Notes:**
- R1: C5 removes zone rooms/enemies from runtime dicts. NPCs stay loaded but are efficiently filtered.
- R2: C4 uses `recruited_npcs` list (already exists in state) + `originZone` field for fast filtering.
- R3: Save files store full state, never re-read data files. File reorg only affects `new_game_state()`.
- R5: NPCs stay in npcs.json, artifacts stay in artifacts.json. One file = one source of truth.
- R6: Changes are in `save.py:new_game_state()` (~30 lines) + `main.py:_find_follower()` (~10 lines). No command mixin changes.

## Recommendation

**Shape C** — per-zone room/enemy files + global NPCs/artifacts with originZone tags.

Tradeoff vs Shape A: zone creation touches 3-4 files instead of 2, but NPCs have a clear single source of truth. The zone creation skill handles the multi-file orchestration.

## Implementation plan (after approval)

### Phase 1: Data file reorganization (C1 + C2)
- Create `data/zones/` directory
- Split `zones.json` into 4 zone files (rooms + enemies_data + metadata only)
- Add `"originZone"` field to every NPC in `npcs.json`
- Add `"originZone"` field to every artifact in `artifacts.json`
- Delete `zones.json`
- Update `skerry.json` landing pad exits if room IDs changed (they shouldn't)

### Phase 2: Loader update (C3)
- Update `save.py:new_game_state()` to glob `data/zones/*.json`
- NPCs/artifacts/items load from global files as before

### Phase 3: NPC iteration optimization (C4)
- Change `_find_follower()` to only scan `recruited_npcs`
- Change skerry management iterations to filter by recruited/zone

### Phase 4: Runtime unloading (C5)
- Add zone-clear detection (artifact status → all zone artifacts resolved)
- Remove zone rooms from `self.rooms`, enemies from `self.enemies_db`
- Skip unrecruited zone NPCs in iteration

### Phase 5: Zone creation skill
- Write `ZONE-CREATION-GUIDE.md` in project root (reflects per-zone-file + global NPCs structure)
- Write skeleton pointer at `.claude/skills/voidnodes-create-zone/SKILL.md`

### Verification
- `python3 main.py` — new game starts correctly
- Load existing save file — works unchanged
- All zone files parse as valid JSON
- Each NPC in npcs.json has an `originZone` field
- Each artifact in artifacts.json has an `originZone` field
- Follower lookup uses recruited_npcs fast path
- Zone clear triggers room/enemy unloading
