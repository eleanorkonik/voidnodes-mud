## Open Bugs

### BUG: beds not filled properly

Skerry Status
  Population: 3/8

  Central Clearing
    Residents: — (0/1 beds)
    Working:   —
  Basic Shelter
    Residents: — (0/2 beds)
    Working:   —
  The Hollow
    Residents: — (0/1 beds)
    Working:   —
  The Junkyard
    Residents: — (0/1 beds)
    Working:   Emmy
  Landing Pad
    4 nodes within sensing distance
  Workshop
    Residents: — (0/2 beds)
    Working:   —

Emmy should be 1/1 beds for the junkyard, and sevarik and miria are 2/2 beds for the shelter.

## Design Questions (deferred)

### PROBLEM: Workshop purpose / material distribution unclear

It's not entirely clear how to utilize the workshop, or how it synergizes with the JUNKYARD. Are we supposed to move components there? Does it let you make better tools? what commands allow usage?

SUBISSUE: Should there be a way to move BUILDING MATERIALS to the WORKSHOP after they've been PROCESSED into raw materials? Should the NPC be doing that as part of "salvaging" -- moving things to the right rooms if they're useful in certain places (like bandages to the apothecary...)

### FEATURE REQUEST: Buildable apothecary

We should have a dedicated room for healing.

### QUESTION: Do masterworks matter?

Crafted: Rope!
Masterwork! You crafted it with exceptional quality.

### QUESTION: What happens if empathy skill fails when assigning ppl?

> assign lira workshop
  Organize: Organize (+4) [0 - - 0] = -2 → Total: +2
Assigned Lira to crafting.

Assume she failed. What would happen? Would the NPC lose a loyalty point? is there a Difficulty Check based on aptitude (NPC skill level for the tasks)

---

## Archive (fixed)

### FIXED: "Junkyard hasn't been built yet" when standing in junkyard

`has_structure()` only checked `structures_built` list, missing starting rooms. Fixed to also check room structures.

### FIXED: Assigning NPC doesn't move them to new location

`cmd_assign` updated assignment but never updated `npc["location"]`. Added `_move_npc_to_task_room()`.

### FIXED: Specimens not droppable

`cmd_drop` only searched `items_db` and `artifacts_db`. Added `specimens_db` lookup.

### FIXED: Fate points don't reset on day change

`_day_transition()` never called `refresh_fate_points()`. Added for both characters.

### FIXED: Junkyard doesn't stack items (23 individual items listed)

Room display now uses `Counter` to group duplicates and show "x5" counts.

### FIXED: Consequences show "(open)" instead of "(none)"

Changed in `display_character_sheet()`.

### FIXED: Artifacts in room desc not highlighted

Artifacts now display as bold white with "(artifact)" tag in room display.

### FIXED: ASCII banner misalignment

Fixed via `unicodedata.east_asian_width()` per LEARNINGS.md.

### FIXED: Skerry-wide aspect not showing

Code already shows zone aspects in room display — was working correctly.

### FIXED: Sort Salvage ignores remnants, produces random scrap

`_handler_sort_salvage` now processes remnants first (using their `process_yields` and `process_dc` with NPC Crafts skill check), only falls back to random scrap when no remnants are in the room.

### FIXED: Verdant Wreck map shows NE/SW where E/W should be

`vw_canopy` was at grid position (1,2) instead of (2,2) — one row too high, causing the renderer to draw a diagonal instead of a horizontal connection from the greenhouse.
