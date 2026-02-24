---
shaping: true
---

# Voidnodes MUD — Six New Features (Shaping)

## Source

Eleanor's Telegram messages (2026-02-21/22):

> "When loyalty gets to a certain point, you can do a rapport check once per day in order to try to unlock a new aspect for the backstory and trouble for NPCs."

> "Aspects should be programmed with potential ways they can be called, so you can invoke it for different skills, not just generally"

> "There should be slots that can be filled in the inventory for the explorer, can only bring home a certain amount of things from each zone, which can of course be extended and expanded. To start with let's say one large item, two medium items, and 20 small items."

> "And then we can add artifacts that do things like make it free to carry all tools, or increase your carrying capacity of large items... We could maybe even do strength checks or whatever those are in order to see whether you can add something extra."

> "Maybe the slots are free and then you can add extra if you have enough either strength for the large or dexterity for the small. With rapidly increasing difficulty checks."

> "I don't want to think of the introduction as a tutorial anymore, I just want to jump right into the game and then have just in time hints."

> "The next zone should be the vegetarian spider stuff, the short story I have is a good starting point for the backstory of the character who could be the priest who got lost there, we can have the acacia trees the specimen brought back from that zone"

> "Rancher's daughter in the post office is another good zone"

> "Zone: boss fight with a non flying old school dragon"

> "Need a way for miria to be able to go to a cleared zone... Maybe when tuft reaches a certain stage it can create BEACONS that let Miria SEEK"

---

# Feature 1: Inventory Slots System — ACTIVE BUILD TARGET

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | Explorer can only carry limited items from zones: 1 large, 2 medium, 20 small | Core goal |
| R1 | Items have a size classification (small/medium/large) | Must-have |
| R2 | Base slots are free — no check needed to fill them | Must-have |
| R3 | Overflow slots available via skill checks with escalating difficulty | Must-have |
| R4 | Endure maps to "strength" (large overflow), Navigate/Scavenge maps to "dexterity" (small overflow) | Leaning yes |
| R5 | Artifacts can modify capacity (free tool carrying, increased large slots) | Nice-to-have |
| R6 | Worn items don't count against inventory slots | Must-have |
| R7 | Stackable items: 1 stack = 1 slot, stacks cap at 5 | **Decided** |
| R8 | Zone limits (1L/2M/20S) for expeditions. Skerry has generous storage (e.g. 5L/10M/100S), upgradable via BUILD | **Decided** |
| R9 | Miria has her own zone capacity when visiting via beacons | Must-have |

## Shape A: Size-Tagged Items with Overflow Skill Checks

### Parts

| Part | Mechanism | Files |
|------|-----------|-------|
| **A1** | Add `"size": "small"|"medium"|"large"` field to every item in `items.json`. Default untagged = "small". | `data/items.json` |
| **A2** | `Character.slot_capacity` dict: `{"large": 1, "medium": 2, "small": 20}`. Tracked in character state. | `engine/models.py` |
| **A3** | `_check_capacity(item)` helper in items.py. Counts current inventory by size. If at cap, triggers overflow check. If overflow fails, TAKE is denied with message. | `commands/items.py` |
| **A4** | Overflow skill checks: Endure for large items (DC starts at 2, +2 per extra), Navigate for small items (DC starts at 2, +2 per extra). Medium uses the higher of Endure/Navigate. Each overflow costs 1 FP. | `commands/items.py` |
| **A5** | INVENTORY display shows slot usage: `[Large: 1/1] [Medium: 0/2] [Small: 8/20]` | `commands/examine.py` |
| **A6** | Artifact capacity bonuses: add `"capacity_bonus"` field to artifacts. E.g., Stabilization Engine KEEP: `{"small": +5}`. Applied in `_on_artifact_kept()`. | `data/artifacts.json`, `commands/artifacts.py` |
| **A7** | Save migration: `setdefault` for `slot_capacity` on characters, `size` on items. | `main.py` `_migrate_state()` |

### Fit Check: All R0-R9 ✅

---

# Feature 2: Loyalty/Rapport System (CONFIDE Command)

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | Loyalty threshold gates access to rapport checks | Core goal |
| R1 | Rapport skill check is the mechanic | Must-have |
| R2 | Limited to once per day per NPC | Must-have |
| R3 | Success unlocks a new aspect on the NPC | Must-have |
| R4 | Unlockable aspects include backstory content | Must-have |
| R5 | Unlockable aspects include trouble-type content | Must-have |
| R6 | Player-initiated (not automatic) | Must-have |

## Shape A: CONFIDE Command + Hidden Aspect Layers

New `CONFIDE <npc>` command. Not TALK (different verb per hard rule #1). TALK already builds loyalty; CONFIDE spends it.

### Parts

| Part | Mechanism | Files |
|------|-----------|-------|
| **A1** | `cmd_confide()` handler: find NPC → check recruited → check loyalty >= 6 → check daily limit → roll Rapport vs DC → reveal or fail | `commands/npcs.py` |
| **A2** | `hidden_aspects` array in NPC JSON. Each entry: `{aspect, type (backstory/trouble), dc, confide_text, fail_text}`. 2-3 per NPC, pre-written. Unlocked sequentially. | `data/npcs.json` |
| **A3** | `revealed_aspects` list + `rapport_last_day` int on each NPC (runtime state) | `data/npcs.json` (runtime) |
| **A4** | Revealed aspects append to `npc.aspects.other[]` — automatically invokable, automatically visible in PROBE | `commands/npcs.py` |
| **A5** | Mood modifier: happy = -1 DC, distressed = +1 DC, grim blocks CONFIDE | `commands/npcs.py` |
| **A6** | INVOKE works before CONFIDE for +2 on Rapport roll (existing `_consume_invoke_bonus` pattern) | `commands/npcs.py` |
| **A7** | Register `confide` in parser for both phases | `engine/parser.py` |
| **A8** | Save migration for `rapport_last_day`, `revealed_aspects` on NPCs | `main.py` |

### Design Details
- **Loyalty threshold: 6** — base recruit starts at 3, needs ~3 TALKs to qualify
- **Rapport DC: 2 (Fair)** per hidden aspect, can escalate (per-aspect `dc` field)
- **Miria (Rapport 3)** succeeds ~79% vs DC 2. **Sevarik (Rapport 1)** succeeds ~38%. Miria is the natural social character.
- Attempt (not just success) consumes the daily limit — no save-scumming

### Decided
- Both characters can CONFIDE (Sevarik is just bad at it — Rapport 1 vs Miria's 3)
- Threshold 6, no FP cost (daily limit is sufficient gate)

---

# Feature 3: Programmable Aspects (Skill Affinities)

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | Aspects declare which skills they naturally align with | Core goal |
| R1 | Invocation is context-aware (knows if aspect matches the skill being rolled) | Must-have |
| R2 | Generic INVOKE still works for any aspect + any skill (FATE flexibility preserved) | Must-have |
| R3 | Mechanical differentiation: matching invoke is better than non-matching | Must-have |
| R4 | Data-driven: skill associations in JSON, not hardcoded | Must-have |
| R5 | Backward compatible: untagged aspects work exactly as today (+2) | Must-have |

## Shape A: Affinity Tags with Tiered Bonuses

New file `data/aspect_affinities.json` maps aspect strings to skill lists. Central lookup — one source of truth. Avoids migrating the 6+ different JSON structures that store aspects as strings.

**Bonus tiers:** +3 for affinity match, +2 for non-match or untagged. The +1 difference is significant in FATE math (turns ties into successes) without making non-matching invocations useless.

### Parts

| Part | Mechanism | Files |
|------|-----------|-------|
| **A1** | New `data/aspect_affinities.json`: maps ~40-50 aspect strings to skill lists | New file |
| **A2** | Load affinities in `Game.__init__`, store as `self.aspect_affinities` | `main.py` |
| **A3** | `pending_invoke_affinities` field alongside existing `pending_invoke_bonus` | `main.py` |
| **A4** | `_consume_invoke_bonus(skill_name)` gains a parameter. Returns +3 if match, +2 otherwise. | `main.py` + 6 call sites across `combat.py`, `npcs.py`, `building.py`, `examine.py`, `movement.py` |
| **A5** | INVOKE menu shows skill affinities inline next to aspect names | `commands/combat.py` |
| **A6** | Narration flavor: "your training surges" (match) vs "not your strongest angle" (stretch) | `commands/combat.py` |
| **A7** | Save migration: `setdefault` for `pending_invoke_affinities` | `main.py` |

### Decided
- **+3/+2** (reward good play, don't punish creative stretches)
- Trouble affinities and EXPLOIT affinities deferred to future iteration

---

# Feature 4: Just-in-Time Hints (Replace Tutorial)

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | No formal tutorial phase — game feels like "real play" from keystroke one | Core goal |
| R1 | Hints triggered by context, not sequence | Must-have |
| R2 | Player never blocked (existing hard rule, extended) | Must-have |
| R3 | Hints feel like the world seed speaking naturally | Must-have |
| R4 | First-time players still learn all core mechanics | Must-have |
| R5 | Prologue narrative (awakening, bonding, meeting Sevarik) preserved as story, not tutorial | Must-have |

## Shape B: Dissolve Tutorial into Command Handlers ← Selected

Delete `engine/tutorial.py`. Each command handler (`cmd_attack`, `cmd_go`, etc.) checks a one-time flag and shows a seed hint on first relevant encounter. Several handlers already do this (recruit INVOKE hint, garden walkthrough). Shape B standardizes the existing pattern.

### Parts

| Part | Mechanism | Files |
|------|-----------|-------|
| **B1** | Delete `engine/tutorial.py` and all imports/references | `engine/tutorial.py`, `main.py` |
| **B2** | First-use hints in combat: ATTACK → combat hint, EXPLOIT → advantage hint, INVOKE → contrast with EXPLOIT | `commands/combat.py` |
| **B3** | First-use hints in movement: first enemy room → danger hint, first NPC room → "survivor here", first artifact room → "something powerful" | `commands/movement.py` |
| **B4** | First-use hints in social: RECRUIT → puzzle hint, SCAVENGE → crafting hint, SWITCH → dual-character rhythm | `commands/npcs.py`, `commands/story.py`, `main.py` |
| **B5** | Central `HINT_TEXT` dict for all hint copy (editable in one place) | New `engine/hints.py` or inline |
| **B6** | Remove prologue phase from parser. Game starts in explorer phase, Day 1. BOND/naming/Sevarik-meeting as scripted opening events. | `main.py`, `engine/parser.py` |
| **B7** | Remove SWITCH blocking and all tutorial gate logic | `main.py` |
| **B8** | Rewrite all hint text from imperative ("Try ATTACK") to seed-voice ("Those creatures look dangerous") | All hint text |
| **B9** | Save migration: convert old `tutorial_step` to `hints_shown` flags | `main.py` |

### Open Questions
1. **Does "no tutorial" mean removing the prologue phase entirely?** Proposed: yes, fold the narrative (BOND, naming, Sevarik meeting) into Day 1 explorer phase as scripted events, not a separate game mode.

---

# Feature 5: Three New Zones

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | Each zone follows established data-driven JSON pattern | Must-have |
| R1 | 5-10 rooms per zone, NPCs and enemies never share rooms | Must-have |
| R2 | At least 1 recruitable NPC per zone | Must-have |
| R3 | 1 artifact per zone with keep/offer choice | Must-have |
| R4 | 2-4 enemy types per zone, FATE-statted | Must-have |
| R5 | Unique scavengeable materials | Must-have |
| R6 | Quest hook or puzzle per zone | Must-have |
| R7 | Lore grounded in Eleanor's existing fiction | Must-have |
| R8 | Difficulty calibrated against existing zones | Must-have |

## Shape A: Three Zones

### A1: Silk Hollows (Vegetarian Spiders) — Medium Difficulty

**Theme:** Alien acacia forest fragment in the void. Giant jumping spiders feed on acacia protein nodules (Beltian bodies), not meat. Mutualistic ecology: spiders protect trees, trees feed spiders.

**Lore grounding:** Eleanor's "Spidersilk" article, Bagheera kiplingi reference note, Eheuian priest culture from Townsfolk.md.

| Element | Details |
|---------|---------|
| **NPC** | Brother Mahiai — Eheuian priest-navigator, lost from trade fleet, lived among spiders for months. Commune 3, Navigate 2, Lore 2. Recruit DC 2. |
| **Artifact** | Spindle of Living Silk — KEEP: +1 Craft, silk recipes. OFFER: 15 motes, passive silk on skerry. |
| **Rooms (7)** | Canopy Edge → Lower Boughs → Feeding Grove (Mahiai) → Nursery Web → Silk Bridge → Hollow Trunk → Queen's Chamber (artifact + matriarch) |
| **Enemies** | Scout Spider (Fight 2), Brood Guardian (Fight 3), Web Spinner (Fight 2, Craft 3), Spider Matriarch (Fight 4, mini-boss) |
| **Quest** | "The Silk Road" — silk barrier blocks Queen's Chamber. Peaceful path: lure matriarch with beltian bodies. Forceful: burn with torch (enrages colony). |
| **Materials** | raw_silk, beltian_body, acacia_bark, acacia_sapling, silk_strand |

### A2: Driftpost Station (Rancher's Daughter) — Easy Difficulty

**Theme:** A USPS post office ripped into the void. Parallels Miria's arrival scene from the comic scripts. Social/puzzle zone, minimal combat.

**Lore grounding:** `!duo-arrival.fountain.md` (Morgan/Miria at a post office), Townsfolk.md (rancher's granddaughter backstory).

| Element | Details |
|---------|---------|
| **NPC** | Josie Calloway — Wyoming rancher's daughter, arrived to pick up a package. Practical, competent. Notice 3, Craft 2, Rapport 2, Organize 2. Recruit DC 1. |
| **Artifact** | Undelivered Parcel — address label shifts to show void coordinates. KEEP: +1 Navigate, pre-reveal room aspects. OFFER: 10 motes, better SEEK hints. |
| **Rooms (6)** | Parking Lot → Post Office Lobby (Josie) → Mailroom → Loading Dock → Break Room → Sorting Room (locked, artifact) |
| **Enemies** | Postal Automaton (Fight 2, thematic), Void Rat Pack (Fight 1, minimal) |
| **Quest** | "Return to Sender" — 4-digit code puzzle. Clues scattered across rooms. Alt: force door with Craft check DC 3. |
| **Materials** | cardboard, packing_tape, bubble_wrap, packaged_snacks, office_supplies |

### A3: The Dragon's Maw (Boss Fight) — Hard+ Difficulty

**Theme:** Ancient cavern inside a void-torn mountain. Wingless dragon (Smaug/Glaurung style) sleeping on artifact hoard. First true boss fight. The dragon fell out of a normal world — it is NOT void-native. Never call anything "void X".

**Lore grounding:** Voidnodes cosmology — creature from a harvested world, fed on a dying world seed.

| Element | Details |
|---------|---------|
| **NPC** | Korvath — trapped knight from medieval world. Failed dragonslayer. Fight 3, Endure 3, Will 2. Recruit DC 1 (condition: dragon defeated). |
| **Artifact** | Wyrm's Heart Stone — crystallized dragon organ. KEEP: +1 Fight, +1 Endure, warmth immunity. OFFER: 20 motes, fire resist on skerry. |
| **Rooms (8)** | Cavern Mouth → Winding Passage → Bone Gallery → Hidden Crevice (Korvath) → Thermal Vent → Dragon's Approach → Dragon's Lair (boss) → The Hoard (locked, artifact) |
| **Enemies** | Cave Wyrm (Fight 3), Bone Crawler (Fight 2), Magma Mite Swarm (Fight 2), **The Old Wyrm** (Fight 5, 5 stress, 3 consequences, 4 aspects — BOSS, 2-phase) |
| **Boss mechanics** | 2-phase fight: (1) Normal Fight 5, (2) After moderate consequence → enraged Fight 6 but loses defense aspect. Can be killed (taken out) or player can CONCEDE. |
| **Quest** | "Dragon's Blind Side" — no puzzle gate, just raw boss fight. Korvath gives tactical intel ("One Eye Scarred Shut" weakness). Cross-zone items help (torch = free exploit, frozen_water = 1 stress). |
| **Materials** | cave_mushroom, fire_stone, dragon_scale, ancient_alloys, crystal_shards |

### Decided
- **Boss:** 2-phase (normal → enraged). Dragon is killable.
- **Naming rule:** NEVER call anything "void X". These creatures/places fell out of normal worlds — they aren't void-native.
- **Defaults accepted:** Eheuian priest, +3/+2 aspect bonuses, both chars CONFIDE, stage 2 beacons.

### Remaining Questions
1. **Acacia sapling** — planting mechanic for steward phase, or just a material for now?

---

# Feature 6: Beacon/Seek Mechanic for Miria

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

## Shape B: Player-Placed Beacons ← Selected

Craftable beacon item. Sevarik places in entry rooms. Limited slots = tuft stage count. Strategic choice of which zones to beacon. More zones are coming, so beacon scarcity is real, not artificial.

### Parts

| Part | Mechanism | Files |
|------|-----------|-------|
| **B1** | New craftable item `beacon` in `data/items.json` + recipe in `data/recipes.json` (crystal_shards + luminous_moss + wire) | `data/items.json`, `data/recipes.json` |
| **B2** | `state["beacons"]` dict: `{zone_id: entry_room_id}` | `engine/save.py` |
| **B3** | New `cmd_place()` handler: PLACE BEACON in entry room of cleared zone. Checks max capacity (= tuft growth_stage). | `commands/items.py` or new mixin |
| **B4** | New `cmd_reclaim()` handler: RECLAIM BEACON returns beacon to inventory from a zone. | Same |
| **B5** | `max_beacons()` on WorldSeed returns `growth_stage` (0 at Baby, 1 at Tendril, 2 at Aura, etc.) | `models/world_seed.py` |
| **B6** | Steward SEEK: `_show_landing_pad_destinations()` shows beaconed zones for steward. `cmd_seek()` allows depleted zones if in beacons. | `commands/movement.py` |
| **B7** | Zone partial-reload: load entry room + 1-2 salvage rooms with post-clear descriptions for beaconed zones | `commands/artifacts.py` or `main.py` |
| **B8** | SCAVENGE unlocked for steward phase (use `current_character()` not `self.explorer`) | `engine/parser.py`, `commands/story.py` |
| **B9** | Steward return via SEEK HOME — does NOT advance day | `commands/movement.py` |
| **B10** | CHECK BEACONS shows active beacons and capacity | `commands/examine.py` |
| **B11** | Register `place`, `reclaim` in parser for explorer+steward phases | `engine/parser.py` |
| **B12** | Save migration for `beacons` dict | `main.py` |

### Design Details
- **Beacons only activatable in fully cleared zones** (prevents Miria entering active combat zones)
- **Max beacons = growth_stage** (0 Baby, 1 Tendril, 2 Aura, 3 Voyager, 4 Sun)
- **Beacon travel costs 1 mote** (same as explorer SEEK)
- **What Miria does:** SCAVENGE (zone pool, higher DC), TALK unrecruited NPCs, PROBE
- **Beacon items transferable** via junkyard (shared storage on skerry)

### Fit Check

| Req | B |
|-----|---|
| R0 | ✅ |
| R1 | ✅ (stage gates max beacons) |
| R2 | ✅ (craft + place) |
| R3 | ✅ (SEEK to beaconed zones) |
| R4 | ✅ (SCAVENGE, TALK, PROBE) |
| R5 | ✅ (mild coupling: Sevarik places, but beacon items craftable by either character) |
| R6 | ✅ (explicit SEEK required) |

---

# Implementation Order

```
Feature 3 (Aspects) ──→ Feature 2 (CONFIDE reveals invokable aspects)
Feature 4 (Hints)   ──→ independent, but should happen before new zones
Feature 1 (Inventory) → independent
Feature 5 (Zones)   ──→ Feature 6 (Beacons need cleared zones to visit)
Feature 6 (Beacons) ──→ needs at least 1 clearable zone
```

**Proposed order:**
1. **Inventory Slots** (self-contained, touches items.py + models.py) ← BUILD NOW
2. **Programmable Aspects** (data file + invoke handler changes)
3. **Loyalty/CONFIDE** (builds on aspect system)
4. **Just-in-Time Hints** (tutorial refactor, independent)
5. **Three New Zones** (content-heavy, benefits from inventory + aspects being in place)
6. **Beacons** (needs zones to exist and be clearable)
