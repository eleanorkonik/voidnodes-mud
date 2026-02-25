# Food Stores & Plant Breeding System

## Context

Eleanor wants a farming/food mechanic for Miria's steward phase, inspired by `plant-breeding-design.md`. The colony needs aggregate food tracking (not per-person Rimworld style) with a "are people starving" baseline from a food storage building. Plants are bred over generations with real tradeoffs. Food recipes extend CRAFT for buff meals. NPCs handle day-to-day garden work; Miria makes strategic decisions and can boost with artifacts.

**Key decisions (from Eleanor):**
- All 5 tradeoff axes present from day one, but revealed/taught through gameplay events
- Food recipes extend existing CRAFT (no new COOK command)
- NPCs assigned to garden handle planting/harvesting automatically; Miria does breeding + artifact boosts

---

## Specimens: The Foundation of Everything

Per the design doc, scavengers bring back **specimens** — not just "seeds." Each is a package of unknown genetics from an alien environment. The specimen type determines what you can do with it.

### Specimen Types

| Type | What It Is | Propagation | Available Breeding Actions |
|------|-----------|-------------|---------------------------|
| **Seeds** | Dried seeds, seed pods | Sexual reproduction — plant, grow, cross-pollinate | CROSS-POLLINATE, SELECT, BANK |
| **Cuttings** | Stem/branch segments | Vegetative cloning — produces genetic copies | CLONE (instant), GRAFT onto rootstock |
| **Tubers** | Root/bulb specimens | Plant directly, regrows from root | SELECT, BANK, BACKCROSS with wild stock |
| **Spore Samples** | Fungal/alien spores | Scatter on substrate, unpredictable growth | SELECT (only — too alien for targeted breeding) |
| **Transplants** | Live whole plants | Plant at full size, immediate yield | GRAFT, CLONE cuttings from it, harvest immediately |

### Specimen Data Model — `data/specimens.json` (NEW file)

Each specimen is a named plant variety with full properties:

```json
{
    "reef_grain": {
        "id": "reef_grain",
        "name": "Reef Grain",
        "specimen_type": "seeds",
        "family": "grain",
        "origin": "coral_thicket",
        "domestication": "feral",
        "compatibility_group": "grain-A",
        "description": "Salt-crusted seed heads from a grass that colonized the coral shelves. Tough and wind-resistant, but the kernels are small and bitter.",
        "traits": {
            "yield": 3, "defense": 7,
            "speed": 4, "nutrition": 6,
            "specialist": 7, "generalist": 3,
            "uniformity": 3, "diversity": 7,
            "edible": 7, "utility": 3
        },
        "hidden_traits": {
            "salt_tolerance": true,
            "allelopathic": false,
            "recessive_blight_susceptibility": false
        },
        "produces": {
            "food_id": "reef_grain_harvest",
            "utility_id": null
        },
        "growth_time": 8,
        "base_yield": 2,
        "probe_text": "Wiry stalks with dense, compact seed heads. The salt-adapted root system runs deep. Low yield, but this thing could grow in a hurricane."
    },
    "feral_tuber": {
        "id": "feral_tuber",
        "name": "Feral Tuber",
        "specimen_type": "tuber",
        "family": "rootcrop",
        "origin": "verdant_wreck",
        "domestication": "feral",
        "compatibility_group": "rootcrop-B",
        "description": "A soil-crusted tuber the size of your fist, covered in coarse reddish skin with deep-set eyes. Sharp, acrid smell from the thick skin.",
        "traits": {
            "yield": 2, "defense": 8,
            "speed": 4, "nutrition": 6,
            "specialist": 3, "generalist": 7,
            "uniformity": 2, "diversity": 8,
            "edible": 5, "utility": 5
        },
        "hidden_traits": {
            "salt_tolerance": false,
            "allelopathic": false,
            "pest_repellent_skin": true
        },
        "produces": {
            "food_id": "feral_tuber_harvest",
            "utility_id": "tuber_skin_compound"
        },
        "growth_time": 10,
        "base_yield": 1,
        "probe_text": "Thick defensive skin, deep-set eyes. High genetic variability — kernel sizes and skin colors vary from rust to amber. The acrid skin compounds may have pest-repellent applications."
    },
    "tangle_vine_cutting": {
        "id": "tangle_vine_cutting",
        "name": "Tangle Vine Cutting",
        "specimen_type": "cutting",
        "family": "vine",
        "origin": "coral_thicket",
        "domestication": "wild",
        "compatibility_group": "vine-C",
        "description": "A thick, ropy segment of vine with aerial roots already groping for purchase. Grows fast. Produces strong fiber but barely edible fruit.",
        "traits": {
            "yield": 4, "defense": 6,
            "speed": 8, "nutrition": 2,
            "specialist": 5, "generalist": 5,
            "uniformity": 8, "diversity": 2,
            "edible": 2, "utility": 8
        },
        "hidden_traits": {
            "allelopathic": true,
            "aggressive_growth": true
        },
        "produces": {
            "food_id": "vine_fruit",
            "utility_id": "plant_fiber"
        },
        "growth_time": 4,
        "base_yield": 2,
        "probe_text": "Aggressive grower — aerial roots seek any surface. Primarily a fiber source; the small, sour fruit is an afterthought. WARNING: may suppress neighboring plants."
    },
    "biodome_wheat": {
        "id": "biodome_wheat",
        "name": "Biodome Wheat",
        "specimen_type": "seeds",
        "family": "grain",
        "origin": "verdant_wreck",
        "domestication": "feral",
        "compatibility_group": "grain-A",
        "description": "Tall stalks gone wild in the wreck's broken greenhouse. Three generations feral — still carries domesticated yield genes but defense is creeping back.",
        "traits": {
            "yield": 6, "defense": 4,
            "speed": 5, "nutrition": 5,
            "specialist": 4, "generalist": 6,
            "uniformity": 4, "diversity": 6,
            "edible": 8, "utility": 2
        },
        "hidden_traits": {
            "rust_susceptibility": true
        },
        "produces": {
            "food_id": "biodome_wheat_harvest",
            "utility_id": null
        },
        "growth_time": 6,
        "base_yield": 3,
        "probe_text": "Recognizably wheat — someone bred this, once. Gone feral but the yield genes are still there. The rust-colored spots on some leaves suggest a latent disease susceptibility."
    },
    "cryo_pod_specimen": {
        "id": "cryo_pod_specimen",
        "name": "Cryo-Preserved Specimen",
        "specimen_type": "transplant",
        "family": "unknown",
        "origin": "frozen_wreck",
        "domestication": "engineered",
        "compatibility_group": "exotic-X",
        "description": "A sealed cryo-tube containing a pale rootlet suspended in nutrient gel. The manifest fragment reads 'Iteration 14.' Crystalline structures stud the rootlet.",
        "traits": {
            "yield": 5, "defense": 5,
            "speed": 7, "nutrition": 3,
            "specialist": 8, "generalist": 2,
            "uniformity": 9, "diversity": 1,
            "edible": 3, "utility": 7
        },
        "hidden_traits": {
            "engineered_sterility": true,
            "crystal_compound_production": true,
            "allelopathic": "unknown"
        },
        "produces": {
            "food_id": "pod_fruit",
            "utility_id": "crystal_compound"
        },
        "growth_time": 3,
        "base_yield": 4,
        "probe_text": "Lab-engineered. Fast growth, crystalline structures, designed for something specific you don't understand yet. Extreme monoculture risk — clonal stock, zero genetic diversity."
    },
    "luminous_spore": {
        "id": "luminous_spore",
        "name": "Luminous Spore Culture",
        "specimen_type": "spore",
        "family": "fungal",
        "origin": "coral_thicket",
        "domestication": "wild",
        "compatibility_group": "fungal-F",
        "description": "A sealed vial of glowing spores scraped from deep coral formations. Not a plant at all — but it grows on organic substrate and produces edible fruiting bodies.",
        "traits": {
            "yield": 5, "defense": 5,
            "speed": 6, "nutrition": 4,
            "specialist": 6, "generalist": 4,
            "uniformity": 3, "diversity": 7,
            "edible": 6, "utility": 4
        },
        "hidden_traits": {
            "shade_dependent": true,
            "medicinal_compound": true
        },
        "produces": {
            "food_id": "glowcap_mushroom",
            "utility_id": "luminous_extract"
        },
        "growth_time": 3,
        "base_yield": 3,
        "probe_text": "Not a plant — fungal. Grows in darkness on organic waste. The glowing fruiting bodies are edible and may have medicinal properties. Unpredictable — spore cultures resist selective breeding."
    },
    "moss_leaf": {
        "id": "moss_leaf",
        "name": "Moss Leaf Spores",
        "specimen_type": "spore",
        "family": "leafy",
        "origin": "verdant_wreck",
        "domestication": "feral",
        "compatibility_group": "moss-M",
        "description": "Fine green powder from the wreck's walls. Grows anywhere damp. Fast, nutritious, utterly flavorless.",
        "traits": {
            "yield": 5, "defense": 5,
            "speed": 9, "nutrition": 1,
            "specialist": 2, "generalist": 8,
            "uniformity": 2, "diversity": 8,
            "edible": 9, "utility": 1
        },
        "hidden_traits": {},
        "produces": {
            "food_id": "moss_leaf_harvest",
            "utility_id": null
        },
        "growth_time": 2,
        "base_yield": 4,
        "probe_text": "Grows on anything wet. Extremely fast. High volume, zero flavor, low nutrition per unit. Emergency calories — nobody wants to eat this long-term but it keeps you alive."
    }
}
```

### Zone Scavenge Pool Updates — `data/zones.json`

Replace generic `"seeds"` with specific specimen IDs:

| Zone | Current Pool | Updated Pool |
|------|-------------|--------------|
| **coral_thicket** | `coral_fragments, luminous_moss, seeds, resin` | `coral_fragments, luminous_moss, reef_grain, tangle_vine_cutting, luminous_spore, resin` |
| **verdant_wreck** | `resin, seeds, luminous_moss, torn_fabric` | `resin, biodome_wheat, feral_tuber, moss_leaf, torn_fabric` |
| **frozen_wreck** | `crystal_shards, frozen_water, ancient_alloys, preserved_food` | `crystal_shards, frozen_water, ancient_alloys, preserved_food, cryo_pod_specimen` |
| **debris_field** | `metal_scraps, wire, torn_fabric` | No change — industrial debris, no biology |

### How Specimen Traits Flow to Food

The data pipeline from scavenging to food stores:

```
SCAVENGE (explorer) → find specimen
    ↓
BRING TO SKERRY → specimen in inventory
    ↓
PLANT in garden plot (or NPC auto-plants)
    ↓
GROW over days (growth_time modified by speed trait + NPC tending)
    ↓
HARVEST → produces food item(s) + maybe utility item(s)
    ↓
STORE in food stores (or keep in inventory)
```

**Trait → Food property mapping:**
- specimen `yield` trait × `base_yield` → **quantity** of food items per harvest
- specimen `nutrition` trait → food item's **calories** (nutrition × 10 + 10 = 20-110 cal range)
- specimen `speed` trait → **growth_time** reduction (speed 10 = halved growth time)
- specimen `edible` trait → food item's **pleasure** (edible × 1 = 1-10 pleasure)
- specimen `family` → food item's **variety_category** (grain, root, leaf, fruit, fungal, preserved)
- specimen `diversity` trait → **shelf_life** modifier (diverse = variable shelf life, uniform = consistent)
- specimen `utility` trait → whether utility byproducts are also produced (fiber, medicine, fuel)

Food items are **generated dynamically** from specimen traits at harvest time, not pre-defined in items.json. A `reef_grain` with yield 3 and nutrition 6 produces different food than a `reef_grain` that's been selectively bred to yield 7 and nutrition 3. The food item inherits the specimen's name + a suffix:

```
reef_grain harvest → "Reef Grain (Cal: 70, Shelf: 12d, Pleasure: 7)"
bred_reef_grain harvest → "Reef Grain cv.2 (Cal: 40, Shelf: 8d, Pleasure: 3)"
```

### Garden Build Requirement Update

The garden currently requires `"seeds": 2`. Change to accept ANY specimen item:
- Check if any 2 items in inventory have `type: "specimen"` (loaded from specimens.json)
- Or keep generic `seeds` as a material item AND have specific specimens alongside

**Recommended:** Change garden build to require 1 specimen + 1 basic_tools (narratively: you need something to plant and tools to break/till the ground). basic_tools is already craftable (2 metal_scraps + 1 wire, DC 2). This chains nicely: scavenge metal → craft tools → find specimen → build garden.

---

## Phase 1: Food Stores Foundation

### 1a. Food Properties

Food items produced by harvesting have these properties (derived from specimen traits, see mapping above):

- **calories** — energy per unit. Colony needs `population × 50` cal/day.
- **shelf_life** — days before spoilage. -1 = preserved indefinitely.
- **satiation** — fullness per unit (derived from nutrition trait). Higher = fewer units needed.
- **variety_category** — from specimen family: `grain`, `root`, `leaf`, `fruit`, `fungal`, `preserved`. Variety score = distinct categories in stores.
- **pleasure** — enjoyment (derived from edible trait). Affects morale.

Existing `preserved_food` gets these fields added (high shelf_life, low pleasure, category "preserved").

### 1b. Food Stores Tracking — `models/skerry.py`

New `food_stores` list on Skerry, unlocked by building storehouse:

```python
food_stores = [
    {"item_id": "colony_grain", "quantity": 12, "day_stored": 5},
    {"item_id": "preserved_food", "quantity": 3, "day_stored": 1},
]
```

New commands:
- **STORE <item>** — move food from Miria's inventory to stores (steward phase, requires storehouse built)
- **CHECK STORES** — aggregate food status display

Display:
```
── FOOD STORES ──────────────────────────────────────
  Colony Grain ×12       60 cal each    14 days left
  Preserved Food ×3      40 cal each    stable
  Wild Berries ×5        20 cal each    3 days left

  Total: 920 calories │ ~3.8 days at current pop (5)
  Variety: 3/6 categories (grain, preserved, fruit)
  Avg Pleasure: 3.2 — "Edible, but nobody's excited."

  ⚠ Low variety — people are getting bored of grain.
─────────────────────────────────────────────────────
```

### 1c. Day Transition: Consumption + Starvation — `main.py`

During `_day_transition()`:
1. Calculate daily need: `(2 + len(recruited_npcs)) × 50` calories
2. Consume from stores oldest-first (shortest shelf_life items first)
3. Remove spoiled food (age > shelf_life)
4. Evaluate starvation tier → set/remove skerry aspects

**Starvation tiers** (FATE aspects, fits existing compel system):

| Days of Food | Aspect | Effect |
|---|---|---|
| >5 days | None | Normal |
| 2-5 days | "Rations Are Getting Thin" | Compellable. NPC mood -1 step. |
| 1-2 days | "Hunger Gnaws at Everyone" | NPC loyalty -1/day. Both characters gain 1 stress. |
| 0 days | "People Are Starving" | NPCs with loyalty <3 leave. Both characters take 1 stress/day. |

**Variety/Pleasure modifiers:**
- Variety < 3 categories → aspect "Monotonous Diet" (compellable for morale events)
- Avg pleasure > 6 → aspect "Well-Fed Colony" (free invoke once per steward phase)

### 1d. Food Recipes — extend `data/recipes.json`

New recipes with `"recipe_type": "food"`:

```json
"hearty_stew": {
    "id": "hearty_stew", "name": "Hearty Stew",
    "materials": {"colony_grain": 2, "wild_berries": 1},
    "result": "hearty_stew_meal",
    "difficulty": 1, "skill": "Craft",
    "recipe_type": "food",
    "description": "A filling stew that lifts spirits."
}
```

Results are consumable meals with buffs:
```json
"hearty_stew_meal": {
    "type": "consumable", "special": "restore_stress",
    "buff": {"mood_bonus": 1, "duration": 2},
    "calories": 120, "pleasure": 6,
    "description": "A bowl of thick, warming stew."
}
```

Food recipes can pull materials from stores (not just inventory). The existing `cmd_craft` is modified to also check `skerry.food_stores` when crafting food recipes.

Buff types: stress restoration, temporary skill bonuses (+1 to a skill for N days), NPC mood boost (all NPCs +1 mood for N days), free invocations on food-related aspects.

---

## Phase 2: Garden + Growing (NPC-Driven)

### 2a. Garden Plots — `data/skerry.json` + `models/skerry.py`

Garden room (already buildable) enhanced with plot tracking:

```python
garden = {
    "plots": [
        {"id": 1, "plant": {"seed_id": "colony_grain_seed", "planted_day": 3,
                             "growth": 4, "growth_needed": 6, "traits": {...}},
         "soil": {"n": 8, "p": 7, "k": 9}},
        {"id": 2, "plant": None, "soil": {"n": 10, "p": 10, "k": 10}},
        {"id": 3, "plant": None, "soil": {"n": 10, "p": 10, "k": 10}},
        {"id": 4, "plant": None, "soil": {"n": 10, "p": 10, "k": 10}},
    ],
    "max_plots": 4,
}
```

Starts with 4 plots. Expandable later (BUILD more plots in garden).

### 2b. NPC Auto-Farming

NPCs assigned to `"gardening"` handle routine work during day transition:
1. **Auto-plant** — if empty plots and seeds available in stores/inventory, plant them
2. **Auto-harvest** — when growth reaches growth_needed, harvest and add to food stores
3. **Growth bonus** — each NPC on gardening duty adds +1 growth tick/day to all plots

Miria's manual garden commands (strategic decisions):
- **SURVEY** — see all plots, growth progress, plant health, trait readouts
- **PLANT <seed> [plot]** — manually plant a specific seed in a specific plot (overrides NPC auto-planting)
- **UPROOT <plot>** — remove a plant before harvest (to make room or abandon a bad specimen)

### 2c. Miria Artifact Boosts

Miria can USE artifacts ON garden plots or plants for special effects:
- USE <artifact> ON <plot> — artifact mote energy accelerates growth, improves yield, or reveals hidden traits
- Fits existing `handle_quest_use()` pattern (USE <item> ON <target> with room-context resolution)
- Specific artifacts could have garden-specific effects (e.g., a crystal artifact reveals all hidden recessive traits on a plant)

---

## Phase 3: Plant Breeding

### 3a. Trait Axes (already on specimens from Phase 1)

Every specimen carries 5 axes as paired integers summing to 10 (defined in `specimens.json`). These are visible from the moment Sevarik picks them up — no gating. The game teaches their *significance* through narrative events:

1. **Yield/Defense** — first blight event. High-yield plants die, wild specimens survive.
2. **Speed/Nutrition** — first harvest comparison. Fast crop = many low-cal units vs slow crop = fewer high-cal.
3. **Specialist/Generalist** — first environmental shift. Specialists fail, generalists survive.
4. **Uniformity/Diversity** — first disease sweep. Monoculture wiped out, landrace loses 20%.
5. **Edible/Utility** — first time colony needs fiber/medicine and food crops can't provide it.

Each lesson is a one-time narrative moment (not a tutorial gate).

### 3b. Breeding Commands (Gated by Specimen Type)

Not every specimen supports every action:

| Command | Requires | Effect |
|---------|----------|--------|
| **CROSS-POLLINATE <plot> WITH <plot>** | Both plants must be `seeds` type, same `compatibility_group` | Sacrifices harvest from both. Produces 1-3 new seeds with blended traits ± mutation (each axis ±1-2 random). |
| **SELECT <plot> FOR <trait>** | Any specimen type except `transplant` | Slow: next harvest shifts named trait +1, opposite -1. Preserves diversity. |
| **CLONE <plot>** | `cutting` or `transplant` type | Instant: produces identical specimen. High uniformity risk — clones share all vulnerabilities. |
| **GRAFT <plot> ONTO <plot>** | One `cutting`/`transplant` as scion, one rooted plant as rootstock | Combines rootstock environmental traits + scion output traits. Doesn't breed true — seeds from grafts are unpredictable. Labor-intensive. |
| **BACKCROSS <plot> WITH <specimen>** | Domesticated plant + wild specimen, same `compatibility_group` | Reintroduces wild defense genetics. Loses yield for 2-3 generations. Essential for disease recovery. |
| **BANK <specimen>** | Any specimen | Store in seed vault (storehouse feature). Protected indefinitely. Retrievable with WITHDRAW. |

Spore samples only support SELECT — too alien for targeted breeding. This makes fungal crops reliable emergency food but hard to optimize.

### 3c. Compatibility Groups

Cross-pollination and backcrossing require compatible specimens:
- **Same group** (e.g., grain-A × grain-A): reliable, predictable offspring
- **Adjacent group** (e.g., grain-A × grain-B): possible but produces reduced fertility — next gen may be sterile
- **Distant groups**: incompatible for sexual reproduction — only grafting works

Groups defined in `specimens.json` on each specimen. New specimens from breeding inherit parent's group.

### 3d. PROBE Plant Display

```
── PLOT 3: Biodome Wheat (Gen 2, seeds) ──────────────
  Growth: ████████░░ 8/10 — harvest in 2 days
  Planted: Day 5 │ NPC Varis tending
  Compat: grain-A │ Domestication: feral

    YIELD   ■■■■■■░░░░ DEFENSE    Good yield, moderate defense.
    SPEED   ■■■■■░░░░░ NUTRIENT   Fast but starchy.
   EDIBLE   ■■■■■■■■░░ UTILITY    Food crop, weak fiber.
  UNIFORM   ■■■■░░░░░░ DIVERSE    Some variety — moderate
                                   disease resistance.
  SPECIAL   ■■■■░░░░░░ GENERAL    Adapted to current conditions.

  Breed: CROSS-POLLINATE, SELECT, BANK
  Hidden: ⚠ Rust susceptibility (revealed Gen 1)
  Health: Good │ No interactions detected
───────────────────────────────────────────────────────
```

```
── PLOT 1: Tangle Vine (cutting) ─────────────────────
  Growth: ██████████ READY — harvest available
  Planted: Day 2 │ Clone of original

    YIELD   ■■■■░░░░░░ DEFENSE    Moderate yield, tough.
    SPEED   ■■■■■■■■░░ NUTRIENT   Very fast, low nutrition.
   EDIBLE   ■■░░░░░░░░ UTILITY    Fiber plant, barely edible.
  UNIFORM   ■■■■■■■■░░ DIVERSE    Clone stock — monoculture.
  SPECIAL   ■■■■■░░░░░ GENERAL    Moderate adaptability.

  Breed: CLONE, GRAFT, SELECT
  Hidden: ⚠ Allelopathic (discovered Day 8 — suppresses
          adjacent plots)
  Health: Vigorous │ Aggressive growth
───────────────────────────────────────────────────────
```

---

## Phase 4: Environmental Events (future)

- Blight events targeting genetic lineages
- Companion planting adjacency bonuses
- Allelopathy (hidden, discovered through play)
- Soil depletion per plot (N/P/K nutrients)
- Crop rotation mechanics
- Pest invasions from scavenging runs
- Colony crises (population surges requiring emergency food)
- CLONE, GRAFT, BACKCROSS breeding commands

---

## Files to Modify

| File | Changes |
|------|---------|
| **`data/specimens.json`** (NEW) | All specimen definitions: named varieties with types, traits, hidden traits, compatibility groups, origin zones, produces mappings. ~7 starting specimens. |
| **`data/items.json`** | Add meal result items (consumable buffs). Add nutrition fields to existing preserved_food. Add utility byproduct items (plant_fiber, tuber_skin_compound, etc.). Remove or repurpose generic `seeds` item. |
| **`data/recipes.json`** | Add food recipes with `recipe_type: "food"` that consume harvested food items. |
| **`data/zones.json`** | Replace generic `"seeds"` in scavenge pools with specific specimen IDs per zone. |
| **`data/skerry.json`** | Add garden plot data to garden room template. Garden build requirement: 1 specimen + 1 basic_tools. Add seed vault to storehouse room. |
| **`models/skerry.py`** | Add `food_stores` list, `garden` plot tracking, `seed_vault` list, consumption/spoilage methods. |
| **`engine/parser.py`** | Add commands: PLANT, HARVEST, SURVEY, STORE, UPROOT, CROSS-POLLINATE (or CROSS), SELECT, CLONE, GRAFT, BACKCROSS, BANK, WITHDRAW. |
| **`main.py`** | Add all new command handlers. Modify cmd_craft for food recipe sourcing from stores. Modify _day_transition for food consumption + NPC auto-farming + plant growth. Modify cmd_check for STORES subcommand. Modify cmd_probe for specimen/plant display. |
| **`engine/display.py`** | Food store display, plant survey formatting, trait bar rendering (the `■░` bars from design doc). |
| **`engine/farming.py`** (NEW) | Specimen loading, plant breeding logic (trait inheritance, mutation, compatibility checks), growth calculations, harvest-to-food conversion, environmental event handling. Single source of truth for all farming mechanics — keeps main.py from bloating. |

## Existing Code to Reuse

- **`Skerry` model** (`models/skerry.py`) — extend with food_stores + garden (same serialization pattern)
- **`cmd_craft()` flow** (`main.py:2843`) — food recipes reuse same materials + skill check pattern
- **`_day_transition()`** (`main.py`) — hook food consumption + NPC auto-farming here
- **`_inventory_counts()`** (`main.py`) — for material checking (extended to check stores too)
- **FATE aspect system** — starvation/variety/pleasure aspects fit existing compel mechanics
- **NPC mood/loyalty** — starvation consequences slot into existing `npc["mood"]` and `npc["loyalty"]`
- **`handle_quest_use()` pattern** (`engine/quest.py`) — USE artifact ON plot follows same room-context design
- **`display.py` formatting** — existing bar/header patterns for trait displays

## Verification

1. Build storehouse → CHECK STORES shows empty stores
2. Build garden → ASSIGN NPC to gardening → NPC auto-plants available seeds
3. Day transition: plants grow, NPC harvests mature plants → food goes to stores
4. CHECK STORES shows calories, days-of-food, variety, pleasure
5. Day transition: colony consumes food, spoiled food removed
6. Let food run low → starvation aspects appear → NPC mood drops → loyalty drops
7. Let food run out → "People Are Starving" aspect → low-loyalty NPCs leave
8. CRAFT hearty stew (food recipe pulls from stores) → produces buff meal
9. USE meal → stress restored / skill buffed
10. PLANT specific seed manually → SURVEY shows growth progress + trait axes
11. CROSS-POLLINATE two plots → sacrifice harvests → new seeds with blended traits
12. SELECT plot FOR yield → next harvest shifts yield +1 / defense -1
13. BANK seeds → stored in vault → WITHDRAW later → plant banked seeds
14. USE artifact ON plot → growth boost / trait revelation
15. Variety < 3 → "Monotonous Diet" aspect appears
16. Avg pleasure > 6 → "Well-Fed Colony" aspect with free invoke
