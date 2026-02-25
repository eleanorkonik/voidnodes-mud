# Voidnodes MUD — Architecture & Build Plan

## Context

Eleanor wants a text-based MUD game set in her Voidnodes fiction universe (specifically the Skerry story). It's a turn-based, solo-playable game with asymmetric Explorer/Homekeeper roles, FATE RPG mechanics, and a baby world seed (Tuft) as both progression system and game interface. Built in Python with standard library only. Designed for family play at tabletop frequency.

## Core Design Decisions (already settled)

- **Python, stdlib only** — no pip packages
- **FATE mechanics** — 4dF dice, 10 custom skills, aspects, stress/consequences, fate points
- **Turn-based alternating phases** — Explorer phase → Homekeeper phase → new day
- **Solo mode** — one person plays both roles sequentially
- **Async 2-player** — save file tracks current phase
- **Lusternia-style commands** — LOOK, GO NORTH, ATTACK, CRAFT, ASSIGN, etc.
- **Visible mote economy** — no hidden numbers
- **Pre-generated characters** — Sevarik (Explorer), Miria (Homekeeper)
- **3 void zones** with 2 NPCs each + skerry home base
- **Eliok House** — discoverable artifact, not starting content
- **Pokemon-style failure** — Tuft emergency extraction costs motes; total depletion = game over
- **Skerry expands** — NPCs get houses, village grows, water source appears

## File Structure

```
projects/voidnodes-mud/
├── main.py                 # Entry point, game loop
├── engine/
│   ├── __init__.py
│   ├── parser.py           # Command parser (Lusternia-style)
│   ├── display.py          # ANSI-colored text output
│   ├── dice.py             # 4dF dice, skill rolls, opposed rolls
│   └── save.py             # JSON save/load
├── models/
│   ├── __init__.py
│   ├── character.py        # Character (skills, aspects, stress, consequences, fate points)
│   ├── room.py             # Room (exits, items, aspects, NPCs present)
│   ├── npc.py              # NPC (character + loyalty, assignment, house, mood)
│   ├── tuft.py             # Tuft (mote pool, growth stage, aspects, communication)
│   ├── item.py             # Item/Artifact (aspects, mote value, stat bonuses)
│   └── skerry.py           # Skerry state (rooms, expansion queue, village status)
├── systems/
│   ├── __init__.py
│   ├── combat.py           # FATE conflict (exchanges, attack/defend, stress, concede)
│   ├── exploration.py      # Zone traversal, scavenging, discoveries
│   ├── crafting.py          # Recipe-based crafting from scavenged materials
│   ├── npc_manager.py      # NPC recruitment, assignment, mood, events
│   ├── skerry_builder.py   # Skerry expansion logic, room unlocking
│   └── events.py           # Random events, compels, crises for both phases
├── data/
│   ├── characters.json     # Sevarik + Miria starting stats
│   ├── npcs.json           # 6 NPCs (Emmy, Dax, Chris, Tilly, Callum, Angya) + Varis
│   ├── zones.json          # 3 void zones with rooms, enemies, loot tables
│   ├── skerry.json         # Starting skerry layout (4 rooms)
│   ├── recipes.json        # Crafting recipes
│   ├── artifacts.json      # Discoverable artifacts (including Eliok House)
│   ├── events.json         # Random event pools for both phases
│   └── tuft.json           # Tuft growth stages, aspect progressions
└── saves/                  # Save files go here
```

## Data Models

### Character (shared by PCs and NPCs)
```python
{
    "name": "Sevarik",
    "aspects": {
        "high_concept": "Fae-Lands Warrior Stranded in the Void",
        "trouble": "Honor-Bound to Protect Everyone",
        "other": ["Battle-Scarred Veteran", "Reluctant Leader"]
    },
    "skills": {  # Pyramid: +4, +3x2, +2x3, +1x4
        "Fight": 4, "Navigate": 3, "Endure": 3,
        "Notice": 2, "Scavenge": 2, "Will": 2,
        "Craft": 1, "Rapport": 1, "Commune": 1, "Organize": 1
    },
    "stress": [false, false, false],  # 3 boxes
    "consequences": {"mild": null, "moderate": null, "severe": null},
    "fate_points": 3,
    "refresh": 3,
    "inventory": []
}
```

### 10 Skills
| Skill | Explorer Use | Homekeeper Use |
|-------|-------------|----------------|
| Fight | Combat offense/defense | Defend skerry from threats |
| Navigate | Move through void zones | — |
| Scavenge | Find materials & artifacts | — |
| Notice | Spot dangers & hidden things | Detect NPC moods, problems |
| Endure | Survive hazards | Endure crises |
| Craft | Field repairs | Build structures, make tools |
| Rapport | Recruit NPCs, negotiate | Manage NPC relationships |
| Commune | Communicate with Tuft | Communicate with Tuft |
| Organize | — | Assign tasks, manage resources |
| Will | Resist mental attacks | Resist compels, stay focused |

### Tuft
```python
{
    "motes": 15,           # Starting pool
    "growth_stage": 0,     # 0-4: Mote, Tendril, Aura, Canopy, Beacon
    "stage_thresholds": [0, 30, 75, 150, 300],
    "total_motes_fed": 0,  # Lifetime counter for stage progression
    "aspects": ["Baby Seed With Perfect Memory", "Hungry for Motes"],
    "stress": [false, false],
    "alive": true
}
```

Growth stages unlock skerry features:
- **Mote (0)**: Basic shelter, Tuft communicates in colors/feelings
- **Tendril (30)**: Tuft can anchor debris, +1 skerry room capacity
- **Aura (75)**: Faint protective bubble, NPC mood bonuses, Tuft speaks in images
- **Canopy (150)**: Full environmental control, weather, farming possible
- **Beacon (300)**: Tuft attracts travelers, endgame content

### Room
```python
{
    "id": "void_zone_1_room_3",
    "name": "Shattered Hull Fragment",
    "description": "A twisted piece of metal hull...",
    "zone": "debris_field",
    "exits": {"north": "room_id", "south": "room_id"},
    "aspects": ["Unstable Footing", "Sharp Metal Edges"],
    "items": ["rusty_bracket", "torn_fabric"],
    "npcs": ["emmy"],
    "enemies": [],
    "discovered": false
}
```

### Skerry Room (expandable)
```python
{
    "id": "skerry_central",
    "name": "Central Clearing",
    "description": "The heart of the skerry...",
    "exits": {"north": "skerry_garden", "east": "skerry_workshop"},
    "aspects": ["Safe Haven", "Tuft's Presence"],
    "structures": ["basic_shelter"],
    "assigned_npcs": [],
    "resources": {}
}
```

## Game Loop

```
main.py
  ├── New Game → create save from data/*.json
  └── Load Game → read save, check current_phase
       │
       ├── EXPLORER PHASE
       │   ├── Display: location, Tuft tactical info, inventory
       │   ├── Commands: LOOK, GO, ATTACK, SCAVENGE, PROBE, FEED, USE, RECRUIT, RETREAT
       │   ├── On RETREAT or incapacitation → Tuft extraction (costs motes)
       │   └── On DONE → save, switch to HOMEKEEPER
       │
       ├── HOMEKEEPER PHASE
       │   ├── Display: skerry overview, NPC statuses, Tuft environmental info
       │   ├── Commands: LOOK, GO, CRAFT, ASSIGN, BUILD, TALK, TRADE, ORGANIZE, CHECK
       │   ├── Random event roll (NPC conflict, resource shortage, visitor, etc.)
       │   └── On DONE → save, advance day counter, switch to EXPLORER
       │
       └── Day Transition
           ├── Tuft growth check (has threshold been crossed?)
           ├── NPC mood updates
           ├── Resource consumption
           ├── Skerry expansion check (enough NPCs + materials?)
           └── New day begins
```

## Combat System (FATE Conflicts)

Exchange-based, not real-time:
1. **ATTACK [target]** → attacker rolls skill + 4dF vs defender rolls skill + 4dF
2. **Difference = shifts** — applied as stress or absorbed by consequences
3. **Invoke aspect** — spend 1 fate point, +2 to roll (must tag a relevant aspect)
4. **Stress boxes** — absorb exactly that many shifts (box 1 = 1 shift, box 2 = 2, box 3 = 3)
5. **Consequences** — mild (-2), moderate (-4), severe (-6) absorb remaining shifts
6. **Taken out** — all stress full + no consequences left = defeated
7. **Concede** — surrender before taken out, get 1 fate point, narrator chooses outcome
8. **Tuft extraction** — if Explorer is taken out, Tuft spends motes to yank them back (5 motes base + 2 per extraction this game)

Enemy stat blocks in zones.json, pre-authored for each zone.

## Command Parser

Lusternia-style: `VERB [TARGET] [MODIFIER]`

```
LOOK                    → describe current room
LOOK [thing/npc]        → detailed description
GO [direction]          → move (NORTH, SOUTH, EAST, WEST, UP, DOWN)
ATTACK [target]         → start/continue combat
DEFEND                  → defensive stance in combat (+2 defend, no attack)
INVOKE [aspect]         → spend fate point for +2 in current contest
CONCEDE                 → surrender current combat
SCAVENGE                → search room for materials (Notice/Scavenge roll)
PROBE [thing]           → examine item/artifact details
FEED [item]             → feed item/artifact to Tuft (gain motes)
KEEP [item]             → keep artifact for stat bonuses
USE [item]              → use consumable or artifact ability
RECRUIT [npc]           → attempt to recruit NPC (Rapport roll)
TALK [npc]              → conversation with NPC
CRAFT [recipe]          → craft item from materials (Craft roll)
RECIPES                 → list known recipes
BUILD [structure]       → build skerry structure (Craft + materials)
ASSIGN [npc] [task]     → assign NPC to task (Organize roll)
CHECK [npc/tuft/skerry] → status check
INVENTORY / INV         → show inventory
STATUS                  → show character sheet
DONE                    → end current phase
HELP                    → list commands
SAVE                    → manual save (auto-saves on DONE)
QUIT                    → save and exit
```

## Content: 3 Void Zones

### Zone 1: Debris Field (nearest to skerry)
- 4-5 rooms of broken ship hull, floating cargo
- **Emmy** — enthusiastic scavenger, easy to recruit (Rapport DC +1)
- **Dax** — cautious mechanic, needs convincing (Rapport DC +3)
- Enemies: void-vermin (small, pack tactics), corroded automaton
- Loot: metal scraps, wire, fabric, basic tools
- Artifact: Stabilization Engine (keep: +1 Craft; feed: 8 motes)

### Zone 2: Coral Thicket (medium difficulty)
- 4-5 rooms of crystallized organic growth, bioluminescent
- **Chris** — teenager, scared, will follow anyone who's kind (Rapport DC +0)
- **Tilly** — practical farmer type, wants proof the skerry is safe (Rapport DC +2, needs skerry visit)
- Enemies: thorn-crawlers (ambush predators), spore clouds (environmental hazard)
- Loot: luminous moss, resin, seeds, coral fragments
- Artifact: Growth Lattice (keep: +1 Commune; feed: 12 motes)

### Zone 3: Frozen Wreck (hardest)
- 5-6 rooms of ancient petrified ship, ice-encrusted
- **Callum** — scholar, obsessed with the wreck's origins (Rapport DC +2, wants to study first)
- **Angya** — warrior, will only respect strength (Rapport DC requires combat demonstration)
- Enemies: frost-shade (strong single enemy), swarm-mites (many weak)
- Loot: ancient alloys, frozen water, preserved food, crystal shards
- Artifact: **Eliok House** (keep: transforms into NPC housing + dryad companion; feed: 25 motes — the biggest decision in the game)

### Skerry (home base, starts with 4 rooms)
- Central Clearing, Basic Shelter, Tuft's Hollow, Landing Pad
- **Varis** — starts here, initial tension/quest-giver NPC
- Expands as NPCs arrive and materials gathered:
  - Workshop (unlocked with metal + tools)
  - Garden (unlocked with seeds + resin)
  - NPC Houses (one per recruited NPC, built with materials)
  - Water Collection (unlocked at Tuft Tendril stage + crystal shards)
  - Lookout Post (unlocked with ancient alloys)

## NPC System

NPCs have:
- **Character stats** (simplified — 3-4 skills, 2 aspects, 2 stress boxes)
- **Loyalty** (0-10, affects willingness, mood, task quality)
- **Assignment** (idle, scavenging, building, gardening, guarding, crafting)
- **Mood** (content, restless, unhappy, crisis) — affected by housing, food, events
- **House** (none → tent → proper house) — affects mood

Homekeeper manages NPCs by:
- ASSIGN [npc] [task] — put them to work
- TALK [npc] — raise loyalty, learn about their needs
- BUILD HOUSE [npc] — improve their living situation
- Resolving events (NPC arguments, shortages, visitors)

## Crafting System

Recipes require materials + Craft skill roll:
- **Rope** — fabric + resin (DC +1)
- **Basic Tools** — metal scraps + wire (DC +2)
- **Torch** — luminous moss + wire (DC +0)
- **Shelter Patch** — fabric + coral fragments (DC +1)
- **Water Filter** — crystal shards + resin + metal scraps (DC +3)
- **Signal Beacon** — ancient alloys + luminous moss + wire (DC +4)

Failed craft rolls waste some materials. Succeed with style (+3 over DC) = bonus item or higher quality.

## Save Format (JSON)

```python
{
    "version": 1,
    "day": 1,
    "current_phase": "explorer",  # or "homekeeper"
    "explorer": { ... character data ... },
    "homekeeper": { ... character data ... },
    "tuft": { ... tuft data ... },
    "skerry": { rooms: [...], structures: [...] },
    "npcs": { "emmy": {...}, "dax": {...}, ... },
    "zones": { "debris_field": {rooms: [...]}, ... },  # tracks discovered/looted state
    "artifacts": { ... discovered/kept/fed status ... },
    "event_log": ["Day 1: Arrived at the skerry...", ...],
    "extractions": 0  # count for escalating mote cost
}
```

## Interface

Terminal-based. Run `python3 main.py`, type commands, get colored text output. Classic MUD experience.

## Display

ANSI colors via escape codes (no curses):
- **White** — narration
- **Cyan** — room names, NPC names
- **Yellow** — items, materials
- **Red** — enemies, damage, warnings
- **Green** — Tuft communication, positive outcomes
- **Magenta** — aspects (when invokable)
- **Bold** — headers, important info

Status bars rendered as text:
```
[Sevarik] Stress: [X][ ][ ]  Fate Points: 2
[Tuft] Motes: 23/30  Stage: Tendril
```

## Build Order (10 sprints)

1. **Dice + Character model** — `dice.py`, `character.py`, skill rolls, 4dF
2. **Room model + Parser** — `room.py`, `parser.py`, LOOK/GO/HELP
3. **Display + Game loop** — `display.py`, `main.py`, phase switching, DONE
4. **Save/Load** — `save.py`, JSON serialization, new game from data files
5. **Combat** — `combat.py`, ATTACK/DEFEND/INVOKE/CONCEDE, stress/consequences
6. **Exploration + Scavenging** — `exploration.py`, SCAVENGE/PROBE/FEED/KEEP
7. **NPCs + Recruitment** — `npc.py`, `npc_manager.py`, RECRUIT/TALK, loyalty
8. **Crafting + Building** — `crafting.py`, `skerry_builder.py`, CRAFT/BUILD/ASSIGN
9. **Events + Tuft** — `events.py`, `tuft.py`, random events, Tuft growth, communication
10. **Content + Polish** — populate all data files, balance numbers, Eliok House, endgame

## Verification

After each sprint, test by playing:
- Sprint 1-2: Walk around rooms, look at things
- Sprint 3-4: Complete a full Explorer→Homekeeper→Explorer cycle, save/load
- Sprint 5-6: Fight an enemy, get taken out, test Tuft extraction. Scavenge, keep vs feed an artifact.
- Sprint 7-8: Recruit an NPC, bring them to skerry, assign tasks, craft items, build structures
- Sprint 9-10: Play through multiple days, watch Tuft grow, trigger events, discover Eliok House

Final test: Play a full game from new save through Tuft reaching Aura stage (75 motes).
