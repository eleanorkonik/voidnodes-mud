# Plan: Flexible Invoke + Automated Compels

## Context

INVOKE is flat "+2 no matter what" without a human GM. Eleanor wants two things:
1. **Flexible invoke** — any aspect can fuel any effect (like tabletop Fate), but the choice of WHICH aspect to burn matters because each aspect is one-use per scene
2. **Automated compels** — trouble aspects create complications that earn FP, making aspects double-edged

## Phase 1: Choose-Your-Effect Invoke

### How it works

Any visible aspect can be invoked for any effect. But each aspect can only be invoked **once per combat encounter** (or once per recruitment attempt). The tactical choice: which of your ~8 available aspects do you burn on which effect?

### Command syntax

- `INVOKE` → shows all available aspects (which are spent, which remain) + effect list
- `INVOKE <aspect>` → prompts for effect choice
- `INVOKE <aspect> ATTACK` → +2 attack (combat)
- `INVOKE <aspect> DEFEND` → +2 defense (combat)
- `INVOKE <aspect> SETUP` → free invocation (combat)
- `INVOKE <aspect> PUSH` → threshold -4 (recruitment)
- `INVOKE <aspect> COUNTER` → reset counter (recruitment)
- `INVOKE <aspect> RESTORE` → un-eliminate tiles (recruitment)

Default shortcut: `INVOKE <aspect>` with no effect keyword → ATTACK in combat, PUSH in recruitment (preserves backward compatibility).

### Combat effects (1 FP each, each aspect once per encounter)

| Keyword | Label | Effect |
|---------|-------|--------|
| ATTACK | +2 Attack | Auto-attack with +2 bonus (current behavior) |
| DEFEND | +2 Defense | Set defending, enemy attacks into +2 def |
| SETUP | Free Invoke | Gain free invocation on random enemy aspect, pass turn |

### Recruitment effects (1 FP each, each aspect once per attempt)

| Keyword | Label | Effect |
|---------|-------|--------|
| PUSH | Threshold -4 | Straight threshold reduction |
| COUNTER | Counter Reset | Reset lowest counter to MAX_COUNTER |
| RESTORE | Restore 3 Tiles | Un-eliminate 3 random tiles |

### No-args display (combat example)

```
═══ Invoke an Aspect ═══  (1 FP each — you have 3)

  Available:
    "Battle-Scarred Veteran"
    "Honor-Bound to Protect Everyone"
    "Eyeless and Hunting by Sound" (enemy)
    "One Wrong Move Draws Blood" (room)

  Already invoked this fight:
    ✗ "Fae-Lands Warrior Stranded in the Void"

  Effects:  ATTACK (+2 attack)  ·  DEFEND (+2 defense)  ·  SETUP (free invoke)

  INVOKE <aspect> [ATTACK|DEFEND|SETUP]
```

### Aspect sources (same as current, plus followers)

- Character aspects via `char.get_all_aspects()` (includes consequences)
- Room aspects
- Enemy aspects (combat only)
- NPC target aspects (recruitment only) — flattened from `{high_concept, trouble, other}` dict
- Following NPC aspects (combat) — recruited NPCs at same location
- World seed aspects
- Item aspects from inventory
- Artifact aspects if kept

Zone aspects remain **not invokable** (always present, too broad).

### Tracking

- `self.invoked_aspects = set()` — aspect strings invoked this combat. Cleared in `_end_combat()`.
- Recruitment: `state["invoked_aspects"] = set()` — per recruitment attempt. No limit on count (unlike current once-per-attempt), but each aspect is one-use.

### Implementation

**New file: `engine/aspects.py`**
- `collect_invokable_aspects(game, context)` — gathers all visible aspects with source labels. Returns list of `(aspect_text, source_label)`. Filters out zone aspects. Handles NPC aspect flattening (fixes existing bug where `npc.get("aspects", [])` returns the dict).
- `_flatten_npc_aspects(npc_data)` — flattens `{high_concept, trouble, other}` to list
- Constants for effect keywords and descriptions

**Modify: `main.py` — `cmd_invoke()` (line 1711)**
1. Gather aspects via `collect_invokable_aspects()`
2. If no args → show menu (available/spent aspects + effects)
3. If args → fuzzy-match aspect, parse optional effect keyword
4. Check if aspect already invoked this scene → reject
5. Spend FP
6. Branch on effect: ATTACK (extract existing auto-attack to `_invoke_attack(bonus)`), DEFEND (set `self.defending`, call `_enemy_turn()`), SETUP (add to `self.free_invocations`, call `_enemy_turn()`)
7. Add aspect to `invoked_aspects` set
8. Set `tutorial_invoke_done` regardless of effect

**Modify: `main.py` — `_recruit_invoke()` (line ~2299)**
- Remove old one-per-attempt gate (`state["invoked"]`)
- Add `state["invoked_aspects"] = set()` tracking
- Parse effect keyword (PUSH/COUNTER/RESTORE, default PUSH)
- Branch on effect

**Modify: `main.py` — `_handle_recruit_input()` (line ~2232)**
- `invoke` with no args shows the grouped menu for recruitment context
- `invoke <aspect>` prompts for effect
- `invoke <aspect> push/counter/restore` applies directly

**Modify: `main.py` — `_end_combat()` + `_start_combat()`**
- Clear `self.invoked_aspects`

**Modify: `engine/recruit.py`**
- Add `reset_lowest_counter(state)` and `restore_tiles(state, count=3)` helpers
- Update `display_help_text()` with new invoke effects

---

## Phase 2: Automated Compels

### How it works

After certain enemy turns in combat, the game checks if the active character's **trouble aspect** could create a complication. If so, it presents a choice:

```
═══ Compel ═══
  Your "Honor-Bound to Protect Everyone" —
  Emmy is in the crossfire. You feel compelled to shield her.

  ACCEPT: Take 1 stress. Gain 1 FP.
  REFUSE: Spend 1 FP to resist. (You have 2 FP)
```

Player types ACCEPT or REFUSE. If 0 FP, must accept.

### Trigger

- After `_enemy_turn()` completes (if player survived)
- ~25% chance per round (`random.random() < 0.25`)
- Only if not already compelled this combat (`self.compel_triggered` flag)
- At most once per combat encounter (keeps it from being annoying)

### Compel data

Pre-written for each trouble aspect (~10 total). Stored in `engine/aspects.py`:

```python
COMPELS = {
    # Sevarik
    "Honor-Bound to Protect Everyone": {
        "condition": "follower_present",
        "text": "{follower} is in the crossfire. You feel compelled to shield them.",
        "accept_effect": "take_stress",
        "accept_text": "You throw yourself between {follower} and danger.",
        "stress": 1,
    },
    "Reluctant Leader": {  # also Sevarik — used if no follower present
        "condition": "always",
        "text": "The weight of command hits you. Do you really have the right to risk this?",
        "accept_effect": "lose_turn",
        "accept_text": "You hesitate, second-guessing yourself.",
    },
    # NPCs (only matter if they become active character, which they don't currently)
    # But listing them for completeness / future use
    "Secrets That Could Help or Harm": {
        "condition": "always",
        "text": "You know something that could help — but revealing it would expose your secrets.",
        "accept_effect": "enemy_boost",
        "accept_text": "You hold back, and the enemy presses the advantage.",
    },
    "Too Trusting for the Void": {
        "condition": "always",
        "text": "You lower your guard for just a moment — old habits.",
        "accept_effect": "take_stress",
        "accept_text": "The opening costs you.",
        "stress": 1,
    },
    "Jumps at Every Shadow": {
        "condition": "always",
        "text": "A flicker of movement in the corner of your eye. Your nerve wavers.",
        "accept_effect": "lose_turn",
        "accept_text": "You flinch, losing your composure.",
    },
    "Trust Issues (Well-Founded)": {
        "condition": "follower_present",
        "text": "You glance at {follower}. Can you really count on them?",
        "accept_effect": "lose_turn",
        "accept_text": "Doubt clouds your judgment.",
    },
    "Won't Move Without Proof": {
        "condition": "always",
        "text": "You're not sure this fight is worth it. Where's the evidence you should be here?",
        "accept_effect": "enemy_boost",
        "accept_text": "Your hesitation gives the enemy an opening.",
    },
    "Knowledge Above Self-Preservation": {
        "condition": "always",
        "text": "You notice something fascinating about the enemy's anatomy. Mid-fight.",
        "accept_effect": "take_stress",
        "accept_text": "Your curiosity costs you a hit, but you learn something.",
        "stress": 1,
    },
    "Respects Only Strength": {
        "condition": "always",
        "text": "This enemy is weak. Beneath you. You lower your guard in contempt.",
        "accept_effect": "enemy_boost",
        "accept_text": "Your arrogance gives them an opening.",
    },
    "Patient Observer": {
        "condition": "always",
        "text": "You pause to study your opponent's pattern. Fascinating, but...",
        "accept_effect": "lose_turn",
        "accept_text": "You watch instead of act.",
    },
}
```

### Compel effects

| Effect | Mechanic |
|--------|----------|
| `take_stress` | Apply N stress to player (default 1) |
| `lose_turn` | Skip player's next action (enemy gets a free attack) |
| `enemy_boost` | Enemy gains +2 boost on next attack |

### Compel conditions

| Condition | Check |
|-----------|-------|
| `follower_present` | Any recruited NPC following at current room |
| `always` | Always valid |

If condition fails, compel doesn't trigger (try another trouble aspect or skip).

### Input handling

- `self.in_compel = True` set when compel is presented
- `self.compel_data = {...}` stores current compel details
- Main game loop: if `self.in_compel`, route input to `_handle_compel_input()`
- ACCEPT → gain 1 FP, apply effect, resume combat
- REFUSE → spend 1 FP, resume combat
- 0 FP → "You can't refuse — no fate points to resist." Must accept.

### Implementation

**Modify: `engine/aspects.py`**
- Add `COMPELS` dict (trouble aspect → compel data)
- Add `check_compel(game)` → returns compel data dict or None
- Add `resolve_compel_accept(game, compel)` and `resolve_compel_refuse(game, compel)`

**Modify: `main.py`**
- Add `self.in_compel = False`, `self.compel_data = None` to `__init__`
- After `_enemy_turn()` calls: `self._check_compel()` which may set `in_compel`
- Add `_handle_compel_input()` for ACCEPT/REFUSE
- Add `_present_compel()` for display
- Main loop: check `self.in_compel` before `self.in_recruit`
- `_end_combat()`: clear compel state, set `self.compel_triggered = False`

---

## Files

| File | Change |
|------|--------|
| `engine/aspects.py` | **NEW** — `collect_invokable_aspects()`, `_flatten_npc_aspects()`, effect constants, `COMPELS` dict, `check_compel()`, compel resolution |
| `main.py` | Rewrite `cmd_invoke` (choose-your-effect + once-per-scene tracking), rewrite `_recruit_invoke`, add `_display_invoke_menu`, extract `_invoke_attack` helper, add compel state + input handler + trigger after `_enemy_turn()` |
| `engine/recruit.py` | Add `reset_lowest_counter()`, `restore_tiles()`. Update help text. |

## Verification

### Phase 1 (Invoke)
1. Combat: `INVOKE` with no args → shows available aspects + effects
2. Combat: `INVOKE veteran ATTACK` → +2 attack fires
3. Combat: `INVOKE veteran` again → "Already invoked this fight"
4. Combat: `INVOKE honor DEFEND` → +2 defense, enemy attacks
5. Combat: `INVOKE eyeless SETUP` → free invocation gained
6. Combat: end combat → invoked_aspects cleared
7. Recruitment: `INVOKE` shows recruitment effects (PUSH/COUNTER/RESTORE)
8. Recruitment: `INVOKE botanist PUSH` → threshold -4
9. Recruitment: `INVOKE observer COUNTER` → lowest counter resets
10. Recruitment: `INVOKE botanist` again → "Already invoked"
11. Recruitment: `INVOKE roots RESTORE` → 3 tiles un-eliminated
12. Tutorial: any invoke sets `tutorial_invoke_done`

### Phase 2 (Compels)
13. Combat with follower: ~25% chance after enemy turn → compel presented
14. ACCEPT → gain 1 FP, suffer effect (stress/lose turn/enemy boost)
15. REFUSE → spend 1 FP, no effect
16. 0 FP → forced to accept
17. At most one compel per combat encounter
18. Compel text uses correct follower name when condition is `follower_present`
