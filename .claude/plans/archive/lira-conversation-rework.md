# Lira Conversation Flow Rework

## Context

The current Lira dialogue dumps greeting + quest_intro + quest_options all in one shot when the player first TALKs to her. Eleanor wants:
1. A hint to TALK to Lira when entering her room (she got no cue to initialize this)
2. Lira asks "Do you have tools?" and the player can **SAY YES/NO** to respond
3. Lira's response varies based on the answer (tools path vs burn path with recruit condition)
4. World seed chimes in about sensing a survivor + RECRUIT hint
5. A new SAY command (also `"` prefix shortcut, MUD-standard)

## New Command: SAY

**parser.py:**
- Add `"say"` to COMMANDS: all phases, args required
- Handle `"` / `'` prefix before verb parsing: `"yes` → `say yes`

```python
# Early in parse(), before split:
if raw[0] in ('"', "'"):
    rest = raw[1:].strip()
    if rest:
        return "say", rest.lower().split()
    return "say", []
```

**main.py: `cmd_say()`:**
- Check `state["pending_npc_question"]`
- If active + player in correct room → dispatch to conversation handler
- If active but wrong room → generic speech (pending question still exists for when they return)
- If no pending question → generic `[CharName] says: "..."`

## Conversation State

New state field: `state["pending_npc_question"]`

```python
{
    "npc_id": "lira",
    "key": "tools_question",
    "room_id": "vw_greenhouse"
}
```

- **Set** when Lira asks "Do you have tools?" via `get_quest_talk()`
- **Cleared** when player SAYs a valid response
- **Cleared** on successful room exit (`cmd_go`)
- **Re-set** if player leaves and TALKs to Lira again (quest still not started)

## Updated Lira Dialogue Flow

### Room Entry Hint (new) — Survivor + TALK

In `cmd_go()`, after room display (line ~1002), seed senses a survivor and hints TALK:

```python
# After _quest_room_hints and before _on_room_enter:
if not self.state.get("_npc_talk_hint_shown"):
    for npc_id in target_room.npcs:
        npc = self.npcs_db.get(npc_id)
        if npc and not npc.get("recruited"):
            self.state["_npc_talk_hint_shown"] = True
            print()
            display.seed_speak("I sense a survivor here. Someone who knows this place.")
            display.seed_speak("TALK to them — they might know something useful.")
            break
```

Fires once total (first non-recruited NPC encountered). Survivor detection + TALK hint together on room entry.

### TALK → Question (modified `get_quest_talk`)

**Quest not started, first talk:**
- Lines: greeting + quest_intro (ends with "Do you have tools?")
- Sets `pending_npc_question` + `lira_tools_asked = True`
- Does NOT start quest yet
- Hint printed: `(SAY YES or SAY NO to answer her)`

**Quest not started, re-talk (walked away and came back):**
- Lines: just quest_intro again (shorter, no greeting repeat)
- Re-sets `pending_npc_question`

**Quest active, tools answered:**
- Existing behavior (quest_options for in-progress, quest_complete, etc.)

### SAY Response Handlers

**SAY YES / Y / YEAH** → focuses on Growth Controller path:
```
Lira: "You do? Good. The Growth Control room is west of the root wall.
USE your tools ON the CONSOLE — if the logic board is intact, the roots
should retract on their own."
```
- Quest activates, control room exit revealed, seed RECRUIT hint

**SAY NO / N / NOPE** → explains both options with burn caveat:
```
Lira: "Well, if you have any way to CRAFT some, the Growth Controller
is west of the root wall — that's the clean option. Otherwise... coat
the roots with resin and burn through. It would work. But these roots
are the only thing keeping the biodome alive. I won't let you torch
them unless you take me somewhere safe first."
```
- Quest activates, control room exit revealed, seed RECRUIT hint

**SAY anything else:**
- Hint: `(SAY YES or SAY NO to answer her)`

### World Seed RECRUIT Hint (END of conversation, after SAY response)

After Lira's response + quest activation + exit reveal, the seed gives the RECRUIT cue:

```python
cap = self.skerry.population_cap()
current = 2 + len(self.state.get("recruited_npcs", []))
remaining = cap - current
print()
display.seed_speak(f"We have space for {remaining} more at the skerry.")
display.seed_speak(f"RECRUIT her, and I can bring her safely home with you.")
```

Note: the "I sense a survivor" line already fired on room entry — NOT repeated here. This is just the capacity + RECRUIT hint.

## Dialogue Data Changes (npcs.json)

Add two new keys to Lira's dialogue:
- `"quest_reply_yes"`: Tools-path response
- `"quest_reply_no"`: Both-paths response with burn caveat + "take me somewhere safe"

Keep existing `quest_options` for the quest-active reminder (when TALKing again after quest started).

## Files to Modify

| File | Changes |
|------|---------|
| `engine/parser.py` | Add `say` command (all phases), `"` prefix handling |
| `engine/quest.py` | Split `get_quest_talk` for Lira into question→answer flow, add `handle_lira_say()` |
| `main.py` | Add `cmd_say()`, NPC-TALK room entry hint, clear pending on `cmd_go`, seed RECRUIT hint |
| `data/npcs.json` | Add `quest_reply_yes` and `quest_reply_no` to Lira dialogue |
| `engine/save.py` | No changes needed (pending_npc_question is transient, not saved) |

## Implementation Order

1. Add SAY command to parser (+ quote prefix)
2. Add `quest_reply_yes` / `quest_reply_no` to npcs.json
3. Modify `get_quest_talk()` in quest.py — split into question flow
4. Add `cmd_say()` in main.py with Lira tools_question handler
5. Add NPC-TALK room entry hint in `cmd_go()`
6. Add seed RECRUIT hint after SAY response
7. Clear pending_npc_question on room exit

## Verification

1. New game → explore to verdant wreck → enter vw_greenhouse
   - Seed says "I sense a survivor here. Someone who knows this place."
   - Seed says "TALK to them — they might know something useful."
2. TALK LIRA → greeting + quest intro ("Do you have tools?")
   - Hint: "(SAY YES or SAY NO to answer her)"
3. SAY YES → Lira explains Growth Controller → quest starts → exit revealed
   - Seed says "We have space for N more at the skerry."
   - Seed says "RECRUIT her, and I can bring her safely home with you."
4. (Alt) SAY NO → Lira explains both options + "take me somewhere safe" → quest starts → exit revealed → seed RECRUIT hint
5. Walk away before SAYing → come back → TALK LIRA → repeats question (no greeting)
6. After quest active: TALK LIRA → existing quest_options reminder
7. `"yes` works same as `SAY YES`
8. RECRUIT without TALKing first still works (not hard-blocked)
