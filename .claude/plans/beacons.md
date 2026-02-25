# Feature: Beacon/Seek Mechanic for Miria

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | Miria can travel to cleared zones | Core goal |
| R1 | Tuft growth stage gates the ability | Must-have |
| R2 | Beacon creation mechanic exists | Must-have |
| R3 | Miria uses SEEK (or variant) to travel | Must-have |
| R4 | Miria has something to DO in cleared zones | Must-have |
| R5 | Does not couple the two characters | Must-have |
| R6 | Zone crossing remains explicit | Must-have |

## Shape: Player-Placed Beacons

Craftable beacon item. Sevarik places in entry rooms. Limited slots = tuft stage count. Strategic choice of which zones to beacon.

| Part | Mechanism | Files |
|------|-----------|-------|
| **B1** | Craftable `beacon` item + recipe (crystal_shards + luminous_moss + wire) | `data/items.json`, `data/recipes.json` |
| **B2** | `state["beacons"]` dict: `{zone_id: entry_room_id}` | `engine/save.py` |
| **B3** | `cmd_place()`: PLACE BEACON in entry room of cleared zone. Max capacity = tuft growth_stage. | `commands/items.py` or new mixin |
| **B4** | `cmd_reclaim()`: RECLAIM BEACON returns beacon to inventory. | Same |
| **B5** | `max_beacons()` on WorldSeed returns `growth_stage` | `models/world_seed.py` |
| **B6** | Steward SEEK: landing pad shows beaconed zones. `cmd_seek()` allows depleted zones if beaconed. | `commands/movement.py` |
| **B7** | Zone partial-reload: entry room + 1-2 salvage rooms with post-clear descriptions | `main.py` |
| **B8** | SCAVENGE unlocked for steward in beaconed zones | `commands/examine.py` |
| **B9** | Steward return via SEEK HOME — does NOT advance day | `commands/movement.py` |
| **B10** | CHECK BEACONS shows active beacons and capacity | `commands/examine.py` |
| **B11** | Register `place`, `reclaim` in parser | `engine/parser.py` |

## Design Details

- **Beacons only placeable in fully cleared zones** (prevents Miria entering active combat zones)
- **Max beacons = growth_stage** (0 Baby, 1 Tendril, 2 Aura, 3 Voyager, 4 Sun)
- **Beacon travel costs 1 mote** (same as explorer SEEK)
- **What Miria does:** SCAVENGE (zone pool, higher DC), TALK unrecruited NPCs, PROBE
- **Beacon items transferable** via junkyard (shared storage on skerry)

## Dependencies

- Needs at least 1 clearable zone to be useful
- Needs beacon recipe and item in data files (beacon item already exists in items.json, recipe in recipes.json)

## Implementation Status

Beacon item and recipe exist in data files. `cmd_place`/`cmd_reclaim` handlers NOT implemented. `state["beacons"]` NOT wired. Steward SEEK integration NOT done.
