# Voidnodes Queue

Single source of truth for what's planned, in progress, and done.
Updated every session that touches voidnodes.

Plan files: `.claude/plans/voidnodes-queue/`

## Status key

- [ ] Not started
- [~] In progress
- [x] Done (move plan to `archive/`)

---

## Unshaped

Raw ideas, not yet shaped into plans.

- Mountain brine spring zone — `mountain-brine-spring.md` (fiction seed, no plan yet)

## Bug Fixes

(none)

## Independent Features

No dependency on the feature sequence. Can be done anytime.

- [ ] **CONFIDE Command** — `confide-backstory.md`. Loyalty threshold + rapport check → hidden aspect reveals.
- [ ] **Loyalty Rapport Unlock** — `loyalty-rapport-unlock.md`. Related to CONFIDE — once-per-day rapport check at loyalty threshold.
- [x] **Steward Rapport Checks** — CHECK <NPC> and CHECK SKERRY both show mood tiers.
- [ ] **Bandage Wounds** — `bandage-wounds.md`. Wounds should be greyable so enemies can't invoke them. Healing exists, greying doesn't.
- [ ] **Wound/Stress/Rescue** — `wound-stress-rescue.md`. Multiple consequences per slot, severe wounds trigger rescue mechanic.
- [ ] **Three Artifacts Per Zone** — `three-artifacts-per-zone.md`. Currently 1 per zone; need 2 more each + randomized spawning.

## Infrastructure

- [ ] **Comic Pipeline** — `voidnodes-comic-pipeline-20260222.md`. Structured event logging + NPC descriptions for automated comic generation.

## Feature Sequence

Original roadmap. Order matters — later features build on earlier ones.

1. [x] Inventory Slots
2. [x] Social Encounters (GREET)
3. [ ] **Aspect Affinities** — `aspect-affinities.md`. Aspects declare skill alignments, matching invoke = +3.
4. [ ] **Just-in-Time Hints** — `just-in-time-hints.md`. Kill tutorial state machine, move hints to command handlers.
5. [ ] **Three New Zones** — `three-new-zones.md`. Silk Hollows, Driftpost Station, Dragon's Maw. Sub-plans: `zone-vegetarian-spiders.md`, `zone-ranchers-daughter.md`, `zone-dragon-boss.md`
6. [ ] **Beacons for Miria** — `beacons.md`, `beacons-miria-seek.md`. Craftable beacons in cleared zones, Miria can SEEK to them.

## Big Systems

Major multi-phase work. Not building unless Eleanor says go.

- [ ] **Food & Farming** — `food-stores-plant-breeding-20260220.md`. Phase 1: food stores + gardens. Phase 2: plant breeding. Phase 3: companion planting.
- [ ] **Plant Breeding Design** — `plant-breeding-design.md`. Deep design doc for farming Phase 2-3. Reference, not a task.
- [ ] **Mote Growth Expansion** — `mote-growth.md`. Passive generation, growth events, mote spending. Brainstorm only.

## Done

- [x] **Inventory Slots** — `archive/inventory-slots.md`
- [x] **Social Encounters (GREET)** — `archive/peaceful-greeting-forest.md`
- [x] **Festering Compels on Room Entry** — `archive/festering-compel-sneak-attack.md`
- [x] **NPC Spawn Randomness** — zones roll random NPC subsets each new game
- [x] **DROP SPECIMENS** — was already working (DROP ALL, DROP SPECIMENS, DROP <name>)
- [x] **HEAL Syntax** — HEAL / HEAL <name> already implemented alongside REQUEST TREATMENT
- [x] **Early Game Mote Drain** — festering aspects drain 1 mote/day + population-based food consumption
