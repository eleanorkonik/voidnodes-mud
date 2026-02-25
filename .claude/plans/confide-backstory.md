# Feature: Loyalty/Rapport System (CONFIDE Command)

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

## Shape: CONFIDE Command + Hidden Aspect Layers

New `CONFIDE <npc>` command. TALK/GREET builds loyalty; CONFIDE spends it.

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

## Design Details

- **Loyalty threshold: 6** — base recruit starts at 3, needs ~3 interactions to qualify
- **Rapport DC: 2 (Fair)** per hidden aspect, can escalate (per-aspect `dc` field)
- **Miria (Rapport 3)** succeeds ~79% vs DC 2. **Sevarik (Rapport 1)** succeeds ~38%.
- Attempt (not just success) consumes the daily limit — no save-scumming
- Both characters can CONFIDE (Sevarik is just bad at it)
- **Flawless recruit also reveals first backstory aspect** (implemented) — same `npc.backstory.aspects[]` data, appends to `npc.aspects.other[]`, tracked via `npc.revealed_backstory[]`. CONFIDE should check `revealed_backstory` to skip already-revealed aspects.

## Implementation Status

`cmd_confide` exists in `commands/npcs.py`. Backstory reveal via flawless recruit implemented. Need to verify: hidden_aspects data in npcs.json, daily limit tracking, mood modifiers.
