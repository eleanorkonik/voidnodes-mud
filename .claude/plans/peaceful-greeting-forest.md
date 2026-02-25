# Plan: Social Encounter System (GREET)

## Context

The steward (Miria) phase lacks mechanically interesting social gameplay. TALK is a vending machine: press button, get +1 loyalty, hear a canned line. Eleanor wants Miria's daily rounds to produce **social encounters** — structured multi-step interactions using FATE challenges and contests, as mechanically engaging as combat is for Sevarik. Backstory reveals, NPC skill boosts, recipes, and mood bonuses are the steward's "loot system."

This also replaces the planned CONFIDE command — backstory reveals emerge organically from social encounters instead of a dedicated verb.

## Key Decisions

- **GREET** is the primary social verb. TALK and HI alias to it.
- Social encounters are a **mix** of FATE challenges (multi-skill) and contests (back-and-forth).
- Encounters are **data-driven** in `data/encounters.json`, not hardcoded.
- Both characters can GREET, but Miria (Empathy 4, Rapport 3) is vastly better than Sevarik (Empathy 1, Rapport 1).
- Build the mechanic with placeholder content; Eleanor fills in NPC-specific text later.

---

## Data Structures

### Encounter definitions (`data/encounters.json`)

Three encounter types:

**Simple** — single skill check, resolves inline (no intercept needed):
```json
{
    "homesick_talk": {
        "type": "simple",
        "name": "Homesick",
        "min_loyalty": 4,
        "once": true,
        "description": "{npc_name} is staring at the void with a faraway look.",
        "skill": "Empathy",
        "dc": 2,
        "success_text": "You sit with {npc_name} and listen...",
        "failure_text": "You try, but the words come out wrong...",
        "success_reward": {"loyalty_bonus": 2, "backstory_reveal": true},
        "failure_penalty": {"mood_penalty": 1}
    }
}
```

**Challenge** — multiple independent overcome actions, different skills:
```json
{
    "tool_dispute": {
        "type": "challenge",
        "name": "The Tool Dispute",
        "min_loyalty": 3,
        "min_npcs": 2,
        "description": "Two settlers are arguing over the last good wrench.",
        "steps": [
            {"skill": "Empathy", "dc": 2, "prompt": "Read the room. What's really going on?",
             "success_text": "...", "failure_text": "...",
             "success_reward": {"mood_bonus": 1}},
            {"skill": "Rapport", "dc": 2, "prompt": "Talk them down.",
             "success_text": "...", "failure_text": "...",
             "success_reward": {"loyalty_bonus": 1}},
            {"skill": "Crafts", "dc": 1, "prompt": "Maybe you can make a second tool.",
             "success_text": "...", "failure_text": "...",
             "success_reward": {"item": "basic_tools"}}
        ],
        "resolution": {
            "full_success": "Both settlers thank you.",
            "partial_success": "Not perfect, but the argument is over.",
            "failure": "The dispute festers."
        }
    }
}
```

**Contest** — back-and-forth rounds, first to N victories:
```json
{
    "skeptic_debate": {
        "type": "contest",
        "name": "Prove Your Worth",
        "npc_specific": ["dax"],
        "min_loyalty": 2,
        "once": true,
        "description": "Dax wants proof the skerry plan isn't doomed.",
        "npc_skill": "Will",
        "npc_skill_value": 2,
        "victories_needed": 3,
        "tactics": [
            {"id": "evidence", "name": "Appeal to Evidence", "skill": "Rapport",
             "flavor": "You lay out the facts..."},
            {"id": "emotion", "name": "Appeal to Emotion", "skill": "Empathy",
             "flavor": "You speak to what she's really afraid of..."},
            {"id": "demonstrate", "name": "Show, Don't Tell", "skill": "Crafts",
             "flavor": "You pick up the nearest broken thing and fix it."}
        ],
        "win_text": "Dax nods once. 'Fine. You might not be an idiot.'",
        "lose_text": "Dax turns away. 'Come back when you have better answers.'",
        "win_reward": {"loyalty_bonus": 2, "backstory_reveal": true},
        "lose_penalty": {"mood_penalty": 1}
    }
}
```

### NPC additions (`data/npcs.json`)

Each NPC gets:
```json
"encounter_pool": ["tool_dispute", "homesick_talk"],
"greet_lines": {
    "low_loyalty": ["..."],
    "high_loyalty": ["..."],
    "mood_restless": ["..."]
}
```

Empty stubs initially — falls back to existing `dialogue.idle` / `dialogue.happy`.

### Game state additions

```python
# main.py __init__:
self.in_social_encounter = False
self.social_encounter_state = None

# Persisted in self.state (via setdefault in _load_state):
state.setdefault("encounter_cooldown", {})   # {encounter_id: day_last_triggered}

# Per NPC (via setdefault on access):
npc.setdefault("encounter_history", [])      # completed once-only encounter IDs
npc.setdefault("last_encounter_day", 0)      # day of last encounter trigger for this NPC
```

---

## GREET Command Flow

### 1. Parser (`engine/parser.py`)

- Add `"greet"` to COMMANDS dict (all phases, args required)
- Change aliases: `"talk": "greet"`, `"hi": "greet"`
- Remove old `"talk"` from COMMANDS (it's now an alias)

### 2. cmd_greet (`commands/npcs.py`)

```
GREET <npc>
  1. Find NPC (room NPCs, followers, agents)
  2. If not recruited → show dialogue.greeting, return
  3. Check for eligible encounter (see selection logic below)
  4a. If encounter found → start it
  4b. If no encounter → show contextual greeting (no loyalty — loyalty comes from encounters only)
```

**No daily limit on GREETing.** You can say hi as many times as you want. NPCs respond with contextual flavor (mood-aware, assignment-aware). Encounters only trigger when eligible (per-NPC daily check + cooldown + once-only tracking). No free +1 loyalty from just greeting — loyalty is earned through encounter rewards, gifts, and other meaningful interactions.

### 3. Encounter selection logic (`engine/social.py`)

```
Pick eligible encounters for this NPC:
  - Skip if npc.last_encounter_day == current day (max 1 encounter per NPC per day)
  - NPC's encounter_pool + generic encounters (no npc_specific field)
  - Filter: min_loyalty met, min_npcs met, not in cooldown, not in encounter_history (if once)
  - 30% base chance to trigger (+ 5% per loyalty above 5, + 10% in steward phase)
  - If triggered: pick random from eligible pool, set npc.last_encounter_day = current day
  - If not triggered: contextual flavor greeting (no loyalty gain)
```

### 4. Simple encounters resolve inline in cmd_greet

Single skill check → reward/penalty → done. No intercept needed.

### 5. Challenge/contest encounters use the intercept pattern

Set `self.in_social_encounter = True`, route input to `_handle_social_encounter_input()`.

---

## Challenge Encounter (terminal flow)

```
═══ The Tool Dispute ═══

  Two settlers are arguing over the last good wrench.

  Step 1 of 3: Read the room. What's really going on?
  Skill: Empathy (DC +2)

  > ATTEMPT    Roll Empathy vs DC 2
  > INVOKE     Spend FP for +2, then roll
  > CONCEDE    Walk away (minor mood penalty)
```

Player types ATTEMPT:

```
  Miria: Empathy (+4) [+ 0 + -] → +5
  DC: +2 | Shifts: +3

  [success text]

  Step 2 of 3: Talk them down.
  Skill: Rapport (DC +2)
  ...
```

After all steps, show resolution based on success count (all/partial/none).

---

## Contest Encounter (terminal flow)

```
═══ Prove Your Worth ═══

  Dax wants proof the skerry plan isn't doomed.

  Round 1 — You: 0  Dax: 0  (first to 3)

  1. Appeal to Evidence    (Rapport +3)
  2. Appeal to Emotion     (Empathy +4)
  3. Show, Don't Tell      (Crafts +2)

  > 1/2/3, INVOKE <aspect>, or CONCEDE
```

Player types `2`:

```
  Miria: Empathy (+4) [+ + 0 -] → +5
  Dax:   Will (+2) [0 + - 0] → +2
  Shifts: +3 — You win this exchange.

  [flavor text]

  Round 2 — You: 1  Dax: 0
  ...
```

**Stale argument rule**: reusing the same tactic applies cumulative -1 per reuse. Forces variety.

---

## Reward System (`engine/social.py`)

Single `apply_reward(game, npc, reward_dict)` function handles all reward types:

| Key | Effect |
|-----|--------|
| `loyalty_bonus` | `min(10, loyalty + N)` |
| `mood_bonus` | Upgrade mood by N tiers |
| `backstory_reveal` | Reveal next unrevealed `npc.backstory.aspects[]` entry, append to `npc.aspects.other[]` |
| `npc_skill_bonus` | `{"skill": "Crafts", "amount": 1}` — permanent NPC skill increase |
| `item` | Add item to current character's inventory |
| `recipe` | Add to `state.discovered_recipes` |
| `skerry_mood_bonus` | +1 mood for all recruited NPCs |

Symmetric `apply_penalty()` for `mood_penalty`, `loyalty_penalty`, and a new key:

| Key | Effect |
|-----|--------|
| `mood_penalty` | Downgrade mood by N tiers |
| `loyalty_penalty` | Lose N loyalty |
| `miria_stress` | Deal N stress to Miria (uses existing stress/consequence system) |
| `festering_aspect` | Add named aspect to `skerry.dynamic_aspects` + deal 1 stress to seed + start 1 mote/day drain + apply -1 to subtask checks |

Backstory reveal reuses the existing `npc.revealed_backstory[]` tracking from the flawless recruit mechanic — same code path, single source of truth.

### Festering: Dynamic Aspects + Seed/Miria Stress

Failed or conceded community encounters create **festering aspects** on `skerry.dynamic_aspects`. These mirror how combat injuries work for Sevarik, but for the social/community domain.

**Three effects stack per festering aspect (all three apply):**

1. **Seed stress** — each festering aspect deals 1 stress to the seed (`self.seed.stress`). The seed has 2-3 stress boxes depending on growth stage. Overflow = seed consequence (new mechanic, parallel to character consequences — e.g., "Roots Withdrawing").
2. **Mote drain** — each festering aspect costs 1 mote per day at day transition. The player watches resources bleed until they fix the problem.
3. **Growth penalty** — each festering aspect applies -1 to NPC subtask skill checks (the seed is distracted, the community is tense). Reuses the existing subtask bonus slot in `engine/subtasks.py`.

**Miria takes emotional stress from failed encounters** — uses her existing stress boxes and consequence slots (same system as combat). Social consequences are psychic/emotional: "Compassion Fatigue", "Everyone's Disappointed", "Burned Out". These are compellable aspects that persist until healed (same healing mechanic as combat consequences — time + successful social encounters instead of zones cleared).

**Resolution:** Follow-up encounters can specify `resolves_aspect: "Unresolved Dispute"`. Success removes the aspect, restores the seed stress box, and stops the mote drain.

**The feedback loop:**
```
Ignore social problems → festering aspects accumulate
  → seed loses motes/day (resources bleed)
  → seed takes stress (fewer stress boxes for void threats)
  → NPC subtasks get -1 (skerry production drops)
  → Miria takes stress (consequences compound)
  → more social problems emerge → loop tightens
```

Encounter data supports this:
```json
"failure_penalty": {
    "miria_stress": 1,
    "festering_aspect": "Unresolved Dispute"
},
"resolves_aspect": "Unresolved Dispute"
```

### Social Compels (Miria's FP Economy)

Festering aspects trigger **compels on room entry** — when Miria enters a skerry room while festering aspects are active. This mirrors combat compels from trouble aspects but for the social domain.

**How it works:**
1. Miria enters a skerry room (via GO or after REST)
2. System checks `skerry.dynamic_aspects` for social/festering aspects
3. If found, compel triggers (max 1 per room entry, pick the oldest uncompelled):

```
  The "Unresolved Dispute" weighs on you as you step inside.
  Everyone's tense. It's your problem now.

  Accept (Y) — Take 1 stress, gain 1 FP
  Resist (N) — Spend 1 FP to push through
```

4. Uses existing compel intercept pattern (`self.in_compel = True`, Y/N input)
5. Accept: `char.apply_damage(1)` + `char.gain_fate_point()` — same as combat compels
6. Resist: `char.spend_fate_point()` — aspect still present, but no stress this time

**Compel cooldown:** Each festering aspect only compels once per day (tracked via `state["social_compels_today"]`, reset at day transition). Otherwise Miria would get compelled every time she walks through a room.

**This gives Miria a real FP economy:**
- **Earn FP:** Accept social compels (emotional weight of unresolved problems)
- **Spend FP:** INVOKE during encounters (+2 on Empathy/Rapport rolls)
- **Refresh:** Day transition (back to 3, same as Sevarik)
- No FP from resolving encounters — resolution is its own reward (FATE-correct)

**Implementation:** Extend `check_compel` in `engine/aspects.py` (or add a parallel `check_social_compel`) that checks `skerry.dynamic_aspects` instead of trouble aspects. Wire into room entry in `commands/movement.py` (the `cmd_go` handler already has post-move hooks for tutorials, zone entry, etc.).

Day transition in `_day_transition()` adds:
```python
# Festering aspect mote drain
social_aspects = [a for a in skerry.dynamic_aspects if a in SOCIAL_ASPECTS]
if social_aspects:
    drain = len(social_aspects)
    self.seed.spend_motes(drain)
    display.warning(f"  {self.seed_name} strains under unresolved tensions. (-{drain} motes)")
```

---

## Day Cycle Integration

- Once-only encounters tracked in `npc.encounter_history`, never repeat
- Repeatable encounters have 3-day cooldown via `state.encounter_cooldown`
- Per-NPC encounter gating via `npc.last_encounter_day` (max 1 encounter trigger per NPC per day)
- No day-transition reset needed — the day number comparison handles it naturally

---

## Starter Encounter Templates (6)

| ID | Type | NPC? | min_loyalty | Festering aspect | Summary |
|----|------|------|-------------|-----------------|---------|
| `tool_dispute` | challenge | generic (2+ NPCs) | 3 | "Unresolved Dispute" | Two NPCs fighting over resources |
| `homesick_talk` | simple | generic | 4 | — | NPC misses home |
| `skeptic_debate` | contest | Dax | 2 | "Doubts About Leadership" | Prove the plan isn't doomed |
| `lonely_night` | simple | Chris | 1 | — | Can't sleep, needs reassurance |
| `scholar_puzzle` | challenge | Callum | 3 | — | Found inscription, needs help |
| `garden_crisis` | challenge | generic (needs garden) | 3 | "Neglected Garden" | Plants dying — investigate and fix |

Not every encounter festers on failure — simple personal conversations (homesick, lonely) just have mood/loyalty penalties. Community-level problems (disputes, crises, challenges to authority) create lingering aspects.

All with placeholder text. Eleanor fills in real content.

---

## Files Changed

| File | Change |
|------|--------|
| `engine/social.py` | **NEW** — encounter engine: state factory, selection logic, step/round resolution, reward/penalty helpers |
| `data/encounters.json` | **NEW** — 6 encounter definitions |
| `engine/parser.py` | Flip aliases: `talk → greet`, `hi → greet`. Add `greet` to COMMANDS, remove `talk` |
| `commands/npcs.py` | Add `cmd_greet()`, `_handle_social_encounter_input()`, `_start_encounter()`, `_resolve_encounter()`. Remove `cmd_talk()` (absorbed into greet) |
| `main.py` | Add `in_social_encounter` / `social_encounter_state` flags + game loop intercept |
| `commands/story.py` | Add festering mote drain to `_day_transition()` |
| `engine/subtasks.py` | Check for festering aspects → -1 per aspect to subtask skill checks |
| `models/world_seed.py` | Add seed consequence support (overflow from stress boxes) |
| `engine/aspects.py` | Add `check_social_compel()` for festering aspect compels |
| `commands/movement.py` | Hook social compel check into room entry on skerry |
| `data/npcs.json` | Add `encounter_pool` and `greet_lines` stubs to each NPC |
| `engine/display.py` | Add encounter display helpers (header, step prompt, contest round, resolution) |

## Implementation Order

1. `engine/parser.py` — register command, flip aliases
2. `engine/social.py` — encounter engine (state factory, resolution, rewards/penalties, selection)
3. `data/encounters.json` — 6 placeholder encounters
4. `commands/npcs.py` — `cmd_greet` + encounter handlers, remove `cmd_talk`
5. `main.py` — intercept flags + game loop
6. `engine/aspects.py` — `check_social_compel()` for festering aspects
7. `commands/movement.py` — hook social compels into skerry room entry
8. `commands/story.py` — festering mote drain + `social_compels_today` reset in `_day_transition()`
9. `engine/subtasks.py` — festering penalty on subtask checks
10. `models/world_seed.py` — seed consequence support
11. `data/npcs.json` — NPC stubs (encounter_pool, greet_lines)
12. `engine/display.py` — encounter display helpers

## Verification

1. **Simple greeting**: GREET an NPC with no eligible encounters → contextual flavor, no loyalty
2. **Repeat greeting**: GREET same NPC again → different flavor line, still no encounter (daily cap)
3. **Simple encounter**: GREET triggers a simple encounter → skill check → reward/penalty
4. **Challenge encounter**: Trigger a challenge → ATTEMPT/INVOKE/CONCEDE through each step → resolution
5. **Contest encounter**: Trigger a contest → pick tactics through rounds → win/lose
6. **Stale argument**: Reuse same tactic in contest → see -1 penalty applied
7. **Festering creates aspect**: Fail a community encounter → dynamic aspect on skerry, visible in SURVEY
8. **Festering drains motes**: REST with festering aspects → seed loses 1 mote per aspect
9. **Festering stresses seed**: Festering aspect creation → seed takes 1 stress
10. **Festering penalizes subtasks**: NPC subtask check with active festering → -1 per aspect
11. **Miria takes stress**: Fail encounter with `miria_stress` → Miria's stress boxes fill, overflow → consequence
12. **Resolve festering**: Succeed at follow-up encounter → aspect removed, seed stress healed, drain stops
13. **Social compel on entry**: Enter skerry room with festering aspect → compel prompt (Y/N)
14. **Accept compel**: Accept → take 1 stress, gain 1 FP
15. **Resist compel**: Resist → spend 1 FP, no stress
16. **Compel cooldown**: Same festering aspect doesn't re-compel same day
17. **Backstory reveal**: Win encounter with `backstory_reveal: true` → aspect appears in PROBE
18. **INVOKE integration**: INVOKE before ATTEMPT in challenge → +2 applied (Miria spends FP earned from compels)
19. **Both characters**: Sevarik GREETs → same flow but worse odds
20. **TALK alias**: `TALK EMMY` and `GREET EMMY` do the same thing
