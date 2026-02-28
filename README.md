# Voidnodes MUD

A text-based adventure game you play by typing commands in your terminal. No graphics, no mouse — just you, a blinking cursor, and a world of floating islands in an endless void.

You control two characters. **Sevarik** explores dangerous zones full of enemies, survivors, and magical artifacts. **Miria** stays home on a floating island called the skerry, where she builds, crafts, and manages the people Sevarik brings back. You switch between them whenever you want.

The game uses dice rolls behind the scenes (like a tabletop RPG), so the same fight or conversation can play out differently each time. There's no single right path — explore zones in any order, recruit who you want, and decide whether to keep powerful artifacts or sacrifice them to grow your living World Seed.

## Getting Started

**Requirements:** Python 3 (no other dependencies needed)

```bash
# Clone the repo
git clone https://github.com/eleanorkonik/voidnodes-mud.git
cd voidnodes-mud

# Play!
python3 main.py
```

The game starts with a tutorial that teaches you the basics: how to move, fight, talk to your World Seed, and explore. Type commands and hit Enter. If you get stuck, type `HELP`.

## Basic Commands

Moving around:
- `GO NORTH` (or just `n`, `s`, `e`, `w`, `u`, `d`)
- `LOOK` to see where you are (or just `l`)
- `MAP` to see a map of the area

Interacting with things:
- `TAKE` something, `DROP` it, `USE` it
- `INVENTORY` to see what you're carrying (or just `i`)
- `TALK` to NPCs you meet

Exploring (as Sevarik):
- `SEEK` to launch into the void and find new zones
- `ATTACK` / `DEFEND` in combat
- `RECRUIT` to try convincing NPCs to join you
- `SCAVENGE` to search defeated areas for materials
- `PROBE` artifacts to learn what they do

Building (as Miria):
- `CRAFT` items from materials
- `BUILD` new rooms for the skerry
- `ASSIGN` NPCs to jobs
- `RECIPES` to see what you can make

Other:
- `STATUS` to check your character's condition
- `SWITCH` to swap between Sevarik and Miria
- `SAVE` / `QUIT` (the game also auto-saves)
- `DONE` to end your turn and advance the day

## What's the World Seed?

The World Seed is a living magical entity that anchors your home island. You grow it by feeding it materials (called motes). As it grows through 5 stages, it unlocks new abilities and communicates more. Taking care of the seed is the closest thing the game has to a main quest.

## The Zones

1. **Debris Field** (easy) — A wrecked ship floating in the void. Watch out for rats and automatons.
2. **Coral Thicket** (medium) — A bioluminescent ecosystem. Stranger creatures here.
3. **Frozen Wreck** (hard) — An ancient ship locked in void-ice. The biggest challenges and choices.

## For Parents

This game is played entirely in the terminal. Kids will practice:
- **Typing commands** and reading text output
- **Problem-solving** — combat uses a dice system where they need to manage resources (fate points, stress boxes, consequences)
- **Reading comprehension** — the game communicates entirely through text descriptions
- **Decision-making** — keep a powerful artifact vs. sacrifice it for the greater good, fight vs. sneak, who to recruit

There's no inappropriate content. Combat is abstract (stress boxes and consequences, not gore). The tone is adventure/fantasy — floating islands, magical seeds, void exploration.

The game saves automatically. Kids can quit anytime with `QUIT` and pick up where they left off.

## How Combat Works

The game uses FATE dice — four dice that each show -1, 0, or +1. Your roll plus your skill bonus vs. the difficulty determines success. Characters have aspects (like personality traits) that can be invoked for a +2 bonus by spending Fate Points. Damage fills stress boxes, then escalates to consequences. It's the same system used in tabletop RPGs like Fate Core, simplified for solo play.

## Project Structure

```
main.py          # Game loop and core logic
commands/        # Command handlers (combat, movement, items, NPCs, etc.)
engine/          # Game systems (dice, display, saving, tutorial, maps)
models/          # Data models (characters, rooms, items, world seed)
data/            # All game content as JSON (zones, NPCs, items, recipes)
saves/           # Your save files (gitignored)
```

The game is pure Python 3 stdlib with no external dependencies. All content (NPCs, zones, items, recipes) is data-driven via JSON files, so it's easy to mod.

## License

MIT — do whatever you want with it. See [LICENSE](LICENSE) for details.
