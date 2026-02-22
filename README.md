# Voidnodes MUD

Voidnodes is a text-based adventure game where you control two characters who each do different things. Sevarik is the explorer — you type commands like SEEK to launch into the void and discover new floating islands full of enemies, survivors, and magical artifacts. You decide how to handle what you find: fight or sneak past threats, recruit people you meet, and choose whether to keep artifacts for their power or offer them to your home base. Miria stays home on the skerry, where she manages the growing settlement — assigning NPCs to jobs, expanding into new areas, and taking care of the people Sevarik brings back.

The game plays like a choose-your-own-adventure book where you type your choices instead of picking from a list, and when things get risky — combat, crafting, healing wounds, resolving conflicts, managing gardens, dealing with threats like void-storms — it rolls dice behind the scenes like a tabletop RPG. There's no single right path through the story. You can explore zones in any order, and switching between the two characters with the SWITCH command lets you bounce between Sevarik's dangerous expeditions and Miria's base-building whenever you want, so the adventure keeps moving on two fronts at once.

## How to Run

```bash
python3 main.py
```

No external dependencies. Pure Python 3 stdlib.

## Core Concept

Two playable characters in alternating phases:
- **Sevarik** (Explorer phase) — combat, exploration, scavenging, recruitment
- **Miria** (Steward phase) — crafting, building, NPC management

A living **World Seed** grows as you feed it motes (energy from materials/artifacts). It anchors the skerry, communicates telepathically, and unlocks abilities across 5 growth stages (0→300 motes).

## Project Structure

```
main.py              # Game controller. Core loop, init, dispatch.
commands/            # cmd_* handlers split into mixin classes
  combat.py          # ATTACK, DEFEND, INVOKE, EXPLOIT, CONCEDE, RETREAT
  movement.py        # GO, SEEK, ENTER, MAP
  items.py           # TAKE, DROP, GIVE, USE, WEAR, REMOVE, FEED, INVENTORY
  npcs.py            # RECRUIT, TALK, ASSIGN, TRADE
  artifacts.py       # PROBE, KEEP, OFFER
  examine.py         # LOOK, STATUS, CHECK, IH, HELP
  building.py        # BUILD, CRAFT, RECIPES
  skerry_mgmt.py     # ORGANIZE, skerry management
  farming.py         # HARVEST, farming/garden systems
  story.py           # SCAVENGE, SWITCH, DONE, story progression
models/
  character.py       # Character/NPC stats, skills, inventory, aspects
  room.py            # Room locations, exits, contents
  item.py            # Items and artifacts
  skerry.py          # Home base rooms and expansion
  world_seed.py      # Seed growth stages, mote tracking, communication
engine/
  parser.py          # Command parsing and alias resolution
  display.py         # ANSI colored terminal output
  dice.py            # FATE dice (4dF) system
  tutorial.py        # 3-act tutorial (30+ steps, state machine)
  save.py            # JSON save/load
  map_renderer.py    # ASCII map generation
  quest.py           # Quest state management
  recruit.py         # Grid-based persuasion minigame
data/
  characters.json    # Sevarik & Miria starting stats
  items.json         # Materials, crafted items, clothing
  artifacts.json     # 6 unique artifacts with special powers
  npcs.json          # Recruitable NPCs (~31KB)
  recipes.json       # Crafting recipes
  zones.json         # 3 void zones with rooms (~26KB)
  skerry.json        # Home base structure
  events.json        # Random steward-phase events
  tuft.json          # Starting world seed config
saves/               # Player save files (JSON)
systems/             # Unused (commands live in mixin files)
proselytize.jsx      # React prototype for recruit minigame UI
```

## Game Systems

### FATE Dice
Roll 4 Fudge dice (each -1/0/+1) + skill bonus vs difficulty. Aspects can be invoked (spend Fate Point) for +2. Opposed rolls for combat.

### Combat (Explorer phase)
`ATTACK` / `DEFEND` / `INVOKE` aspect / `EXPLOIT` aspect / `CONCEDE` / `RETREAT`

Damage flows: stress boxes (1/2/3) → consequences (mild/-2, moderate/-4, severe/-6) → Taken Out.

### Exploration
- `GO` direction within zones, `SEEK` aspect at Landing Pad to travel between zones
- `SCAVENGE` defeated rooms for materials, `PROBE` artifacts to reveal aspects
- `ENTER` artifact to find its location, `FEED` material to seed for motes

### Recruitment
Grid-based persuasion minigame. Navigate colored tiles (N/S/E/W), each color = conversational topic. Colors decay if unvisited; reach score threshold to recruit. Difficulty 0-3 scales grid size and color count.

### Base Building (Steward phase)
`CRAFT` from recipes (skill checks), `BUILD` expandable rooms (require materials + NPCs + seed stage), `ASSIGN` NPCs to tasks (gathering/crafting/guarding).

### World Seed Growth
5 stages: Baby(0) → Tendril(30) → Aura(75) → Voyager(150) → Sun(300 motes). Unlocks new aspects, stress boxes, communication depth.

## Commands

### Universal (all phases)
`LOOK` / `GO` / `INVENTORY` / `STATUS` / `CHECK` seed / `HELP` / `SAVE` / `DONE` / `QUIT` / `TALK` / `USE` / `WEAR` / `REMOVE` / `MAP` / `GIVE` / `SWITCH` / `OFFER` / `DROP` / `IH`

### Explorer-only
`ATTACK` / `DEFEND` / `INVOKE` / `EXPLOIT` / `CONCEDE` / `SCAVENGE` / `PROBE` / `FEED` / `KEEP` / `RECRUIT` / `RETREAT` / `ENTER` / `SEEK` / `TAKE`

### Steward-only
`CRAFT` / `RECIPES` / `BUILD` / `ASSIGN` / `ORGANIZE` / `TRADE`

### Aliases
Movement: `n/s/e/w/u/d`. Look: `l/x`. Inventory: `i/inv`. Take: `get/grab/pick`. Equip: `equip→wear`. Flee: `flee/run→retreat`. Examine: `examine→probe`.

## World Map

**Home — The Skerry:** Central Clearing, Shelter, Hollow (seed), Junkyard, Landing Pad + 4 expandable rooms (Workshop, Garden, Water Collection, Lookout Post)

**Void Zones:**
1. **Debris Field** (easy) — dead ship, 5 rooms. Enemies: rats, hounds, automatons. Artifact: Stabilization Engine.
2. **Coral Thicket** (medium) — bioluminescent ecosystem. Artifact: Growth Lattice.
3. **Frozen Wreck** (hard) — ancient ship in void-ice. Artifact: Eliok House (major feed-vs-keep choice).

## Architecture Notes

**Game loop:** `start() → _hydrate() → run() → parse → cmd_*() → tutorial.after_command()`. Save via `_dehydrate()`.

**Mixin pattern:** `Game` class in `main.py` inherits from 10 mixin classes in `commands/`. Each mixin defines `cmd_*` handlers for a command group. All `self.*` state lives in `Game.__init__` — mixins don't define `__init__`. Command dispatch via `getattr(self, f"cmd_{cmd}")` resolves handlers across all mixins.

**Phase system:** `prologue` (tutorial) → `explorer` / `steward` alternating. `DONE` advances day and switches.

**Data-driven:** All content (NPCs, zones, items, recipes, events) defined in JSON. Code handles mechanics; JSON handles content.

**Each command is its own handler** — `cmd_attack()`, `cmd_offer()`, etc. Do NOT alias new commands to existing ones; Eleanor wants them to diverge independently.

## Design Decisions

- **OFFER is not FEED** — separate verbs, separate handlers, even if similar
- **Each verb gets its own command** — no combining or aliasing new functionality onto existing commands
- **FATE system faithful** — aspects, invokes, exploit advantages, consequences all work per FATE Core rules
- **Recruit minigame uses compass directions** (N/S/E/W), not WASD
- **Tutorial is thorough** — 3 acts, teaches seed bonding → exploration → steward phase
