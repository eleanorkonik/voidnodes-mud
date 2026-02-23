# Zone Creation Guide

How to add a new void zone to Voidnodes MUD.

## Architecture

Zones are split across multiple files:

| File | Contains |
|------|----------|
| `data/zones/<zone_id>.json` | Rooms, enemies, zone metadata (aspect, difficulty, scavenge pool) |
| `data/npcs.json` | All NPCs across all zones, tagged with `originZone` |
| `data/artifacts.json` | All artifacts across all zones, tagged with `originZone` |
| `data/skerry.json` | Landing pad exits (wire new zone entry room here) |
| `commands/movement.py` | `_ZONE_ARTIFACTS` dict (zone-to-artifact mapping) |

## Step-by-step

### 1. Create the zone file

Create `data/zones/<zone_id>.json`:

```json
{
    "id": "my_zone",
    "name": "The My Zone",
    "description": "Description visible when...",
    "aspect": "Zone-Level Aspect Phrase",
    "difficulty": "easy|medium|hard",
    "scavenge_pool": ["item_id_1", "item_id_2"],
    "entry_room": "mz_entrance",
    "rooms": [
        {
            "id": "mz_entrance",
            "name": "Zone Entrance",
            "description": "What the player sees.",
            "zone": "my_zone",
            "exits": {"south": "skerry_landing", "north": "mz_next_room"},
            "aspects": ["Aspect One", "Aspect Two"],
            "items": [],
            "npcs": [],
            "enemies": [],
            "discovered": false
        }
    ],
    "enemies_data": [
        {
            "id": "enemy_id",
            "name": "Enemy Name",
            "description": "What the player sees.",
            "aspects": ["Aspect"],
            "skills": {"Fight": 2},
            "stress": [false, false],
            "consequences": {"mild": null},
            "loot": ["item_id"]
        }
    ]
}
```

**Rules:**
- Room IDs use a 2-letter zone prefix (e.g., `mz_` for "my zone")
- Entry room must have `"south": "skerry_landing"` exit
- Every room needs a `"zone"` field matching the zone ID
- All rooms start with `"discovered": false`
- Enemy `stress` array length = number of stress boxes

### 2. Add NPCs to npcs.json

Add NPC entries to the global `data/npcs.json` with an `originZone` field:

```json
{
    "npc_id": {
        "name": "NPC Name",
        "originZone": "my_zone",
        "location": "mz_some_room",
        "recruited": false,
        ...
    }
}
```

Also add the NPC ID to the room's `"npcs"` array in the zone file.

### 3. Add artifact to artifacts.json

Add the zone's artifact to `data/artifacts.json` with an `originZone` field:

```json
{
    "my_artifact": {
        "id": "my_artifact",
        "originZone": "my_zone",
        "location": {"type": "room", "id": "mz_boss_room"},
        ...
    }
}
```

### 4. Wire the landing pad

In `data/skerry.json`, add an exit from `skerry_landing` to the new zone's entry room:

```json
"exits": {"north": "df_entrance", "east": "ct_entrance", "west": "fw_entrance", "northeast": "vw_airlock", "southeast": "mz_entrance"}
```

Also add the reverse exit in the zone's entry room: `"south": "skerry_landing"`.

### 5. Register zone artifact

In `commands/movement.py`, add to `_ZONE_ARTIFACTS`:

```python
_ZONE_ARTIFACTS = {
    "debris_field": "stabilization_engine",
    "coral_thicket": "growth_lattice",
    "frozen_wreck": "eliok_house",
    "verdant_wreck": "bloom_catalyst",
    "my_zone": "my_artifact",
}
```

### 6. Add new items (if any)

If the zone uses items not in `data/items.json`, add them there.

## Runtime behavior

- Zone rooms/enemies load from `data/zones/*.json` at game start
- When a zone's artifact is resolved (kept/fed), the zone is "cleared"
- Cleared zones have their rooms (except entry) and enemies removed from runtime
- NPCs stay in `npcs_db` permanently (source of truth is always `npcs.json`)
- The landing pad shows cleared zones as `(depleted)` and blocks travel to them

## Checklist

- [ ] Zone file created in `data/zones/`
- [ ] All room IDs use consistent zone prefix
- [ ] Entry room links to `skerry_landing`
- [ ] NPCs added to `npcs.json` with `originZone`
- [ ] NPCs referenced in room `npcs` arrays
- [ ] Artifact added to `artifacts.json` with `originZone`
- [ ] Landing pad exit added in `skerry.json`
- [ ] `_ZONE_ARTIFACTS` updated in `movement.py`
- [ ] New items added to `items.json` if needed
- [ ] All JSON files valid
- [ ] Game starts without errors
