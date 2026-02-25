# Feature: Three New Zones

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

## Zone 1: Silk Hollows (Vegetarian Spiders) — Medium Difficulty

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

## Zone 2: Driftpost Station (Rancher's Daughter) — Easy Difficulty

**Theme:** A USPS post office ripped into the void. Social/puzzle zone, minimal combat.

**Lore grounding:** `!duo-arrival.fountain.md` (Morgan/Miria at a post office), Townsfolk.md (rancher's granddaughter backstory).

| Element | Details |
|---------|---------|
| **NPC** | Josie Calloway — Wyoming rancher's daughter, arrived to pick up a package. Practical, competent. Notice 3, Craft 2, Rapport 2, Organize 2. Recruit DC 1. |
| **Artifact** | Undelivered Parcel — KEEP: +1 Navigate, pre-reveal room aspects. OFFER: 10 motes, better SEEK hints. |
| **Rooms (6)** | Parking Lot → Post Office Lobby (Josie) → Mailroom → Loading Dock → Break Room → Sorting Room (locked, artifact) |
| **Enemies** | Postal Automaton (Fight 2, thematic), Void Rat Pack (Fight 1, minimal) |
| **Quest** | "Return to Sender" — 4-digit code puzzle. Clues scattered across rooms. Alt: force door with Craft check DC 3. |
| **Materials** | cardboard, packing_tape, bubble_wrap, packaged_snacks, office_supplies |

## Zone 3: The Dragon's Maw (Boss Fight) — Hard+ Difficulty

**Theme:** Ancient cavern inside a void-torn mountain. Wingless dragon sleeping on artifact hoard. First true boss fight. The dragon fell out of a normal world — NOT void-native. Never call anything "void X".

**Lore grounding:** Voidnodes cosmology — creature from a harvested world, fed on a dying world seed.

| Element | Details |
|---------|---------|
| **NPC** | Korvath — trapped knight from medieval world. Failed dragonslayer. Fight 3, Endure 3, Will 2. Recruit DC 1 (condition: dragon defeated). |
| **Artifact** | Wyrm's Heart Stone — KEEP: +1 Fight, +1 Endure, warmth immunity. OFFER: 20 motes, fire resist on skerry. |
| **Rooms (8)** | Cavern Mouth → Winding Passage → Bone Gallery → Hidden Crevice (Korvath) → Thermal Vent → Dragon's Approach → Dragon's Lair (boss) → The Hoard (locked, artifact) |
| **Enemies** | Cave Wyrm (Fight 3), Bone Crawler (Fight 2), Magma Mite Swarm (Fight 2), **The Old Wyrm** (Fight 5, 5 stress, 3 consequences, 4 aspects — BOSS, 2-phase) |
| **Boss mechanics** | 2-phase fight: (1) Normal Fight 5, (2) After moderate consequence → enraged Fight 6 but loses defense aspect. Can be killed or player can CONCEDE. |
| **Quest** | "Dragon's Blind Side" — no puzzle gate, just boss fight. Korvath gives tactical intel ("One Eye Scarred Shut" weakness). Cross-zone items help (torch = free exploit, frozen_water = 1 stress). |
| **Materials** | cave_mushroom, fire_stone, dragon_scale, ancient_alloys, crystal_shards |

## Design Decisions

- **Boss:** 2-phase (normal → enraged). Dragon is killable.
- **Naming rule:** NEVER call anything "void X". These creatures/places fell out of normal worlds.
- **Acacia sapling** — planting mechanic for steward phase? Or just a material? (open question)

## Implementation Status

No new zones created yet. Existing zones: debris_field, coral_thicket, frozen_wreck, verdant_wreck.
