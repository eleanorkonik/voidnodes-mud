# Create Zone Skill

Scaffold a new zone for Voidnodes MUD. Handles all file creation and wiring.

## Usage

Invoke when adding a new explorable zone to the game.

## Reference

See `ZONE-CREATION-GUIDE.md` in the project root for the full step-by-step, file schemas, naming conventions, and checklist.

## Quick Steps

1. Create `data/zones/<zone_id>.json` (rooms, enemies, zone metadata)
2. Add NPCs to `data/npcs.json` with `originZone` field
3. Add artifact to `data/artifacts.json` with `originZone` field
4. Wire landing pad exit in `data/skerry.json`
5. Register zone artifact in `commands/movement.py` `_ZONE_ARTIFACTS`
6. Add new items to `data/items.json` if needed
7. Validate: `python3 main.py` starts without errors
