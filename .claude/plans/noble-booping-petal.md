# Plan: Wearable Item System

## Context

Adding a WEAR/REMOVE system inspired by Lusternia's unified item handling. Any item with a `slot` field can be worn — clothing, artifacts, crafted gear, whatever. Both characters start wearing clothes. EXAMINE SELF shows worn items alongside character aspects. Artifacts like Silver Slippers (feet) and Red Clown Nose (head) are wearable too.

## Body Slots

Five slots: `head`, `torso`, `legs`, `feet`, `hands`. Defined as `BODY_SLOTS` constant in `models/character.py`.

## New Clothing Items (`data/items.json`)

Four items with `"type": "clothing"` and a `"slot"` field. No stat bonuses. `mote_value: 2`. These are normal Earth clothes — the characters arrived from a regular world.

**Sevarik:**
- `khaki_jumpsuit` — torso — "A sturdy khaki jumpsuit, the kind you'd wear for fieldwork. Scuffed at the knees and elbows but still holding together."
- `work_boots` — feet — "Worn-in leather work boots. They've seen better days but they're broken in just right."

**Miria:**
- `red_sundress` — torso — "A cheerful red sundress, incongruous against the void. It's the kind of thing you'd wear to a garden party, not the end of the world."
- `canvas_flats` — feet — "Simple canvas flats, slightly muddy. Comfortable enough for a long day on your feet."

## Artifact Slot Updates (`data/artifacts.json`)

Add `"slot"` field to wearable artifacts:
- `silver_slippers` → `"slot": "feet"`
- `red_clown_nose` → `"slot": "head"`

Other artifacts (stabilization_engine, growth_lattice, eliok_house) get no slot — they're carried, not worn.

## Character Model (`models/character.py`)

```python
BODY_SLOTS = ["head", "torso", "legs", "feet", "hands"]
```

**Constructor** (after `self.inventory`): `self.worn = dict(data.get("worn", {}))`

**New methods:**
- `wear_item(item_id, slot)` — remove from inventory, set `worn[slot] = item_id`. Returns False if slot occupied or item not in inventory.
- `remove_worn(slot)` — set `worn[slot] = None`, add item back to inventory. Returns item_id or None.
- `get_worn_item(slot)` — return item_id or None.
- `get_all_worn()` — return `{slot: item_id}` for occupied slots only.
- `find_worn_by_item(item_id)` — return slot name or None.

**`to_dict`**: Add `"worn": self.worn`.

## Item Model (`models/item.py`)

Add `self.slot = data.get("slot", None)` and include in `to_dict()`. Keeps the model consistent with the JSON schema even though items_db entries are accessed as raw dicts.

## Starting Outfits (`data/characters.json`)

Add `worn` field to both characters:
- **Sevarik**: `{"torso": "khaki_jumpsuit", "feet": "work_boots"}`
- **Miria**: `{"torso": "red_sundress", "feet": "canvas_flats"}`

## Parser (`engine/parser.py`)

- **Remove** `"wear": "use"` from COMMAND_ALIASES
- **Add** to COMMANDS:
  - `"wear": {"phases": ["explorer", "steward", "prologue"], "args": "required"}`
  - `"remove": {"phases": ["explorer", "steward", "prologue"], "args": "required"}`
- **Add** to COMMAND_ALIASES: `"equip": "wear"`, `"unequip": "remove"`, `"unwear": "remove"`

## Command Handlers (`main.py`)

### `cmd_wear(args)`
1. Find item in inventory — check **both** `items_db` and `artifacts_db`
2. Check for a `slot` field — reject items without one ("You can't wear that.")
3. Check slot not occupied — tell player to REMOVE first if occupied
4. Call `char.wear_item(item_id, slot)`
5. Success message

### `cmd_remove(args)`
1. Try target as slot name (`REMOVE torso`)
2. Then match item name against worn items (checking both `items_db` and `artifacts_db` for name lookup)
3. Call `char.remove_worn(slot)` — item goes back to inventory
4. Success message

### Register in handler dict (line ~344)
```python
"wear": self.cmd_wear,
"remove": self.cmd_remove,
```

### `_examine_target`: Add "self"/"me"/"myself"
Insert at top of method (before NPC check, line 400):
```python
if target in ("self", "me", "myself"):
    display.display_self(char, self.items_db, self.artifacts_db)
    return
```

### `_examine_target`: Search worn items
After searching inventory items (line ~463), add a block to search worn items. Build a list of worn item IDs, check against both `items_db` and `artifacts_db`:
```python
worn_ids = [wid for wid in char.worn.values() if wid is not None]
art_id, art = self._find_entity(worn_ids, target, self.artifacts_db)
if art:
    # show artifact details (description, aspects, stat_bonuses, mote value)
    return
item_id, item = self._find_entity(worn_ids, target, self.items_db)
if item:
    # show item details
    return
```

## Display (`engine/display.py`)

### New `display_self(character, items_db, artifacts_db=None)`
```
═══ Sevarik ═══
  Fae-Lands Warrior Stranded in the Void

  Wearing:
    Head     (nothing)
    Torso    Scout Jacket
    Legs     Field Trousers
    Feet     Void Boots
    Hands    (nothing)

  Aspects:
    Fae-Lands Warrior Stranded in the Void
    Honor-Bound to Protect Everyone
    Battle-Scarred Veteran
    Reluctant Leader
```

Looks up item names from both `items_db` and `artifacts_db`. Uses `item_name()` for worn items, `aspect_text()` for aspects. Empty slots show dim `(nothing)`.

### Help text
Add to universal commands in `display_help`:
```python
("WEAR <item>", "Put on a piece of clothing or artifact"),
("REMOVE <item>", "Take off something you're wearing"),
("EXAMINE SELF", "See your appearance, worn items, and aspects"),
```

### `display_inventory` — worn section
After inventory listing, show worn items:
```python
worn = {s: i for s, i in character.worn.items() if i} if hasattr(character, 'worn') else {}
if worn:
    print(f"  {BOLD}Wearing:{RESET}")
    for slot, item_id in worn.items():
        name = _lookup_name(item_id, items_db, artifacts_db)
        print(f"    {slot.capitalize()}: {item_name(name)}")
```

Where `_lookup_name` is a small helper that checks items_db then artifacts_db then falls back to title-case formatting. Used in both `display_self` and `display_inventory` — single source of truth.

## Save Migration (`engine/save.py`)

Add to `_migrate_state`:
```python
for char_key in ("explorer", "steward"):
    if char_key in state:
        state[char_key].setdefault("worn", {})
```

## KEEP Interaction

KEEP stays as-is for artifacts. A player who KEEPs a slotted artifact gets it in inventory — they can then WEAR it from inventory to equip it on the body slot. KEEP → inventory, WEAR → body slot. Both are valid. This means during the tutorial, after the player TAKEs the artifact, they have three choices:
- KEEP (stays in inventory, passive)
- WEAR (equips to body slot, visible on EXAMINE SELF)
- OFFER TO <seed> (fed for motes)

No code changes to cmd_keep needed for this.

## Tutorial Updates (`engine/tutorial.py`)

The `"wear": "use"` alias is removed, so WEAR is now its own command. The tutorial's `artifact_use` step needs to accept both USE and WEAR as valid actions after TAKE.

**Line 15 comment**: Change to `# TAKE then USE or WEAR the artifact`

**`after_command` for `artifact_use` step** (line 194):
- Change `if cmd == "use"` to `if cmd in ("use", "wear")`
- Both commands are valid ways to interact with the artifact after picking it up

**Prompt text** (line 191):
- Change `_tutorial_prompt(f"Type USE {art_name.upper()}")` to `_tutorial_prompt(f"Type WEAR {art_name.upper()}")`
- WEAR is more natural for equipping things to your body; USE is for activating consumables/effects

**Tuft's line** (line 190):
- Change `"Good. Now try it on."` — keep this, it works for both

**`get_current_hint`** (line 372):
- Change `"Try it on. USE the {art_name}."` to `"Try it on. WEAR the {art_name}."`
- Change `_tutorial_prompt(f"Type USE {art_name.upper()}")` to `_tutorial_prompt(f"Type WEAR {art_name.upper()}")`

## Files Summary

| File | Changes |
|------|---------|
| `models/character.py` | `BODY_SLOTS` constant, `worn` dict, wear/remove methods, `to_dict` |
| `models/item.py` | Add `slot` field |
| `data/items.json` | 4 clothing items |
| `data/artifacts.json` | Add `slot` to silver_slippers + red_clown_nose |
| `data/characters.json` | `worn` field for both characters |
| `engine/parser.py` | Remove `wear→use` alias, add WEAR + REMOVE commands, aliases |
| `main.py` | `cmd_wear`, `cmd_remove`, handler dict, `_examine_target` self + worn search |
| `engine/display.py` | `display_self()`, `_lookup_name()` helper, help text, inventory worn section |
| `engine/save.py` | `worn` migration |
| `engine/tutorial.py` | Accept WEAR in artifact_use step, update prompts/hints |

## Verification

1. New game → both characters wearing starting clothes
2. EXAMINE SELF / EXAMINE ME → shows description, worn items by slot, aspects
3. WEAR <item> → equips to correct slot (works for clothing AND artifacts)
4. WEAR when slot occupied → "REMOVE it first"
5. WEAR non-slotted item → "You can't wear that"
6. REMOVE <item name> → unequips, returns to inventory
7. REMOVE <slot name> → same by slot
8. INVENTORY → shows carried items AND worn section
9. LOOK <worn item> → examines it (description, aspects, stat info)
10. Old saves load without crash (worn defaults to empty)
11. Tutorial artifact flow unchanged (USE still works for special effects)
12. Silver Slippers wearable on feet, Red Clown Nose wearable on head
