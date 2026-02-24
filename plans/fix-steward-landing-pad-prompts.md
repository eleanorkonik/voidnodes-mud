# Fix: Steward/prologue sees explorer-only landing pad prompts

## Context

When a steward walks to `skerry_landing`, they see "I sense nodes in the void...", SEEK hints, and mote cost info — all explorer-specific. Then if they try SEEK, they get "'SEEK' is not available during the prologue phase." The steward shouldn't see those prompts at all.

Three issues found:

## Fix 1 — Gate `_show_landing_pad_destinations()` to explorer-only

**File:** `projects/voidnodes-mud/commands/movement.py:73`

Add an early return if phase != `"explorer"`:

```python
def _show_landing_pad_destinations(self, room):
    """Show available void destinations from the landing pad."""
    if self.state["current_phase"] != "explorer":
        return
```

This fixes all four call sites at once:
- `cmd_go` line 231 (arriving at landing pad)
- `cmd_seek` line 155 (bare SEEK with no args)
- `cmd_seek` line 177 (no match found)
- `cmd_look` in examine.py line 20

## Fix 2 — Gate cross-zone SEEK hints in `cmd_go`

**File:** `projects/voidnodes-mud/commands/movement.py:338-354`

The cross-zone rejection block in `cmd_go` shows SEEK hints ("SEEK HOME", "SEEK DEAD SHIP to follow it") regardless of phase. Add a phase check:

```python
# Cross-zone movement — requires SEEK
if room.zone != target_room.zone:
    if self.state["current_phase"] != "explorer":
        display.narrate("You can't go that way.")
        return
    display.narrate("The void stretches before you.")
    ...
```

## Fix 3 — Rename `_show_sensed_nodes` → `_show_landing_pad_destinations` in tutorial

**File:** `projects/voidnodes-mud/engine/tutorial.py`

Two references to a method that was renamed and no longer exists:
- Line 217: `game._show_sensed_nodes(game.current_room())`
- Line 707: `game._show_sensed_nodes(game.current_room())`

Replace both with `game._show_landing_pad_destinations(game.current_room())`.

(These are tutorial-only paths that run during the explorer tutorial, so the phase gate from Fix 1 won't block them.)

## Verification

1. Start a new game, get to steward phase
2. Walk to `skerry_landing` — should NOT see "I sense nodes" or SEEK prompts
3. Try `GO S` from landing pad (cross-zone) — should see "You can't go that way." not SEEK hints
4. Switch to explorer, walk to landing pad — SHOULD see the full destination list and SEEK prompts
5. Load a save at `explorer_void_cross` tutorial step — should not crash (Fix 3)
