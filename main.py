#!/usr/bin/env python3
"""Voidnodes MUD — The Skerry Chronicle.

A text-based adventure set in the space between worlds.
"""

import sys
import json
import random

from engine import parser, display, save, dice, tutorial, map_renderer
from models.character import Character, BODY_SLOTS
from models.room import Room
from models.world_seed import WorldSeed
from models.skerry import Skerry
from models.item import Item


class Game:
    """Main game controller."""

    def __init__(self):
        self.state = None
        self.explorer = None
        self.steward = None
        self.seed = None
        self.skerry = None
        self.rooms = {}       # all rooms by ID
        self.items_db = {}    # item templates
        self.enemies_db = {}  # enemy templates
        self.npcs_db = {}     # NPC data
        self.agents_db = {}   # inactive player agents
        self.artifacts_db = {}
        self.recipes_db = {}
        self.events_db = {}
        self.running = False
        self.in_combat = False
        self.combat_target = None
        self.defending = False

    @property
    def seed_name(self):
        """The player-chosen name for the world seed."""
        return self.state.get("world_seed_name", "Tuft") if self.state else "Tuft"

    def sub(self, text):
        """Substitute {seed_name} (and future placeholders) in data file text."""
        return text.format(seed_name=self.seed_name)

    @property
    def explorer_name(self):
        return self.state.get("explorer_name", "Sevarik") if self.state else "Sevarik"

    @property
    def steward_name(self):
        return self.state.get("steward_name", "Miria") if self.state else "Miria"

    def start(self):
        """Main entry point."""
        display.title_screen()
        saves = save.list_saves()

        if saves:
            display.header("Save Files")
            for i, (name, meta) in enumerate(saves):
                seed = meta.get("seed_name", "Tuft")
                print(f"  {i + 1}. {seed} — Day {meta['day']}, {meta['phase']} phase")
            print(f"  {len(saves) + 1}. New Game")
            print()

            while True:
                try:
                    choice = input(f"{display.BOLD}Choose (1-{len(saves) + 1}): {display.RESET}").strip()
                    if not choice:
                        continue
                    idx = int(choice) - 1
                    if idx == len(saves):
                        self.new_game()
                        break
                    elif 0 <= idx < len(saves):
                        self.load(saves[idx][0])
                        break
                except (ValueError, IndexError):
                    print("Invalid choice.")
                except EOFError:
                    return
        else:
            print("  No save files found. Starting a new game.\n")
            self.new_game()

        self.run()

    def new_game(self):
        """Initialize a new game from data files."""
        self.state = save.new_game_state()
        self._hydrate()

        # Tutorial prologue — atmospheric intro with world seed as guide
        tutorial.show_prologue_intro()

    def load(self, slot_name):
        """Load a saved game."""
        self.state = save.load_game(slot_name)
        if not self.state:
            display.error(f"Could not load save '{slot_name}'.")
            sys.exit(1)
        self._hydrate()
        display.success(f"\nLoaded save: {slot_name}")
        phase = self.state["current_phase"]
        if phase == "prologue":
            display.narrate("Resuming tutorial...\n")
        else:
            display.narrate(f"Day {self.state['day']}, {phase} phase.\n")

    def _hydrate(self):
        """Populate live objects from state dict."""
        self.explorer = Character(self.state["explorer"])
        self.steward = Character(self.state["steward"])
        self.seed = WorldSeed(self.state["seed"])
        self.skerry = Skerry(self.state["skerry"])
        self.items_db = self.state.get("items_db", {})
        self.artifacts_db = self.state.get("artifacts", {})
        self.recipes_db = self.state.get("recipes", {})
        self.events_db = self.state.get("events", {})
        self.npcs_db = self.state.get("npcs", {})
        self.agents_db = self.state.get("agents", {})

        # Build rooms dict
        self.rooms = {}
        for zone_id, zone in self.state.get("zones", {}).items():
            for room_data in zone.get("rooms", []):
                self.rooms[room_data["id"]] = Room(room_data)
            for enemy in zone.get("enemies_data", []):
                self.enemies_db[enemy["id"]] = enemy
        for room_data in self.state.get("skerry", {}).get("rooms", []):
            self.rooms[room_data["id"]] = Room(room_data)

    def _dehydrate(self):
        """Write live objects back to state dict for saving."""
        self.state["explorer"] = self.explorer.to_dict()
        self.state["steward"] = self.steward.to_dict()
        self.state["seed"] = self.seed.to_dict()
        self.state["skerry"] = self.skerry.to_dict()
        self.state["agents"] = self.agents_db

        # Update rooms in zones
        for zone_id, zone in self.state.get("zones", {}).items():
            for i, room_data in enumerate(zone.get("rooms", [])):
                if room_data["id"] in self.rooms:
                    zone["rooms"][i] = self.rooms[room_data["id"]].to_dict()

        # Update skerry rooms
        skerry_rooms = []
        for room_data in self.state.get("skerry", {}).get("rooms", []):
            if room_data["id"] in self.rooms:
                skerry_rooms.append(self.rooms[room_data["id"]].to_dict())
        self.state["skerry"]["rooms"] = skerry_rooms

    def save_game(self, silent=False):
        """Save current game state."""
        self._dehydrate()
        path = save.save_game(self.state)
        if not silent:
            display.success(f"Game saved.")

    def run(self):
        """Main game loop."""
        self.running = True
        phase = self.state["current_phase"]
        day = self.state["day"]

        if phase == "prologue":
            # Place Sevarik at the shelter during prologue
            shelter = self.rooms.get("skerry_shelter")
            if shelter and "sevarik" not in shelter.npcs:
                shelter.add_npc("sevarik")
            if "sevarik" not in self.npcs_db:
                self.npcs_db["sevarik"] = {
                    "name": self.explorer_name,
                    "location": "skerry_shelter",
                    "recruited": True,
                    "aspects": {
                        "high_concept": "Fae-Lands Warrior Stranded in the Void",
                        "trouble": "Honor-Bound to Protect Everyone",
                        "other": ["Battle-Scarred Veteran", "Reluctant Leader"],
                    },
                    "skills": {},
                    "stress": [False, False, False],
                    "consequences": {"mild": None, "moderate": None},
                    "loyalty": 10,
                    "assignment": "explorer",
                    "mood": "content",
                    "house_level": 0,
                    "dialogue": {
                        "greeting": "A scarred man stands at the edge, staring into the void. He glances your way. 'You're the one the seed chose. Ready when you are.'",
                        "idle": f"'Whenever {self.seed_name} shifts focus to me, I'll head out.'",
                        "happy": "'The skerry. It's not much, but it's worth fighting for.'",
                    },
                    "recruit_dc": None,
                    "recruit_condition": None,
                }

            step = self.state.get("tutorial_step", "awakening")
            current_room = self.rooms.get(self.state.get("prologue_location", "skerry_central"))

            if step == "awakening":
                # Player is in the void — don't discover or show the room yet.
                # The bond is what gives perception and reveals the skerry.
                pass
            else:
                # Resuming mid-tutorial: discover room, show it, show hint
                if current_room:
                    current_room.discover()
                    display.display_room(current_room, self.game_context())
                print()
                # If resuming at exploring step while already at Sevarik's room,
                # trigger the encounter immediately
                if step == "exploring" and current_room and "sevarik" in current_room.npcs:
                    tutorial._show_sevarik_encounter(self)
                else:
                    tutorial.get_current_hint(step, self.state)
        else:
            # Ensure inactive agent is placed on the skerry
            inactive_role = "steward" if phase == "explorer" else "explorer"
            inactive_id = self.steward_name.lower() if inactive_role == "steward" else self.explorer_name.lower()
            if inactive_id not in self.agents_db:
                self._deactivate_agent(inactive_role)

            display.phase_banner(phase, day, self.explorer_name, self.steward_name)

            # Show starting location
            current_char = self.explorer if phase == "explorer" else self.steward
            loc_key = f"{phase}_location"
            current_room = self.rooms.get(self.state[loc_key])
            if current_room:
                current_room.discover()
                display.display_room(current_room, self.game_context())
            display.display_status(current_char, phase)
            display.display_seed(self.seed.to_dict(), name=self.seed_name)
            print()

        while self.running:
            try:
                phase = self.state["current_phase"]
                raw = input(display.prompt(phase))

                # Naming the world seed — capture raw input instead of parsing
                if self.state.get("awaiting_world_seed_name"):
                    name = raw.strip()
                    if not name:
                        display.seed_speak("Go on. Anything you like.")
                        continue
                    # Title-case the name
                    name = name.strip().title()
                    # Enforce unique seed names across saves
                    if save.seed_name_taken(name):
                        display.error(f"A world seed named '{name}' already exists in another save.")
                        display.seed_speak("That name is already taken. Try another?")
                        continue
                    self.state["world_seed_name"] = name
                    self.state["awaiting_world_seed_name"] = False
                    self.state["tutorial_step"] = "first_look"
                    print()
                    display.seed_speak(f"{name}.")
                    print()
                    display.seed_speak("I like that.")
                    tutorial.get_current_hint("first_look", self.state)
                    continue

                cmd, args = parser.parse(raw)

                if cmd is None:
                    continue

                if cmd == "unknown":
                    display.error(f"Unknown command: {args[0]}. Type HELP for commands.")
                    continue

                if not parser.is_valid_for_phase(cmd, phase):
                    display.error(f"'{cmd.upper()}' is not available during the {phase} phase.")
                    continue

                # Stash location so tutorial can detect failed moves
                if phase == "prologue":
                    self.state["_pre_cmd_location"] = self.state.get("prologue_location")

                self.handle_command(cmd, args)

                # Tutorial after-command hook
                if phase == "prologue" and not self.state.get("tutorial_complete"):
                    complete = tutorial.after_command(cmd, args, self)
                    if complete:
                        self._transition_to_day1()
                    self.state.pop("_pre_cmd_location", None)

            except EOFError:
                print()
                self.save_game()
                display.narrate("Farewell, wanderer.")
                break
            except KeyboardInterrupt:
                print()
                self.save_game()
                display.narrate("Farewell, wanderer.")
                break

    def handle_command(self, cmd, args):
        """Route a parsed command to its handler."""
        phase = self.state["current_phase"]

        handlers = {
            "look": self.cmd_look,
            "ih": self.cmd_ih,
            "go": self.cmd_go,
            "inventory": self.cmd_inventory,
            "status": self.cmd_status,
            "check": self.cmd_check,
            "help": self.cmd_help,
            "save": self.cmd_save,
            "done": self.cmd_done,
            "quit": self.cmd_quit,
            "talk": self.cmd_talk,
            "use": self.cmd_use,
            "wear": self.cmd_wear,
            "remove": self.cmd_remove,
            "map": self.cmd_map,
            "skip": self.cmd_skip,
            "bond": self.cmd_bond,
            "give": self.cmd_give,
            "switch": self.cmd_switch,
            "attack": self.cmd_attack,
            "defend": self.cmd_defend,
            "invoke": self.cmd_invoke,
            "concede": self.cmd_concede,
            "scavenge": self.cmd_scavenge,
            "probe": self.cmd_probe,
            "feed": self.cmd_feed,
            "keep": self.cmd_keep,
            "offer": self.cmd_offer,
            "take": self.cmd_take,
            "recruit": self.cmd_recruit,
            "retreat": self.cmd_retreat,
            "craft": self.cmd_craft,
            "recipes": self.cmd_recipes,
            "build": self.cmd_build,
            "assign": self.cmd_assign,
            "organize": self.cmd_organize,
            "trade": self.cmd_trade,
        }

        handler = handlers.get(cmd)
        if handler:
            handler(args)
        else:
            display.error(f"Command '{cmd}' not yet implemented.")

    # ── Current character / room helpers ──────────────────────────

    def current_character(self):
        phase = self.state["current_phase"]
        if phase == "prologue":
            return self.steward
        return self.explorer if phase == "explorer" else self.steward

    def current_room(self):
        phase = self.state["current_phase"]
        if phase == "prologue":
            loc_key = "prologue_location"
        else:
            loc_key = f"{phase}_location"
        return self.rooms.get(self.state.get(loc_key))

    def game_context(self):
        return {
            "items_db": self.items_db,
            "artifacts_db": self.artifacts_db,
            "npcs_db": self.npcs_db,
            "enemies_db": self.enemies_db,
            "agents_db": self.agents_db,
            "bonded_with_seed": self.state.get("bonded_with_seed", False),
        }

    # ── Universal Commands ────────────────────────────────────────

    def cmd_look(self, args):
        room = self.current_room()
        if not room:
            display.error("You're nowhere. That's concerning.")
            return

        if not args:
            display.display_room(room, self.game_context())
            return

        self._examine_target(" ".join(args))

    def _examine_target(self, target):
        """Shared logic for examining a specific thing — used by LOOK <thing> and IH <thing>."""
        room = self.current_room()
        if not room:
            display.error("You're nowhere. That's concerning.")
            return

        # Examine self
        if target in ("self", "me", "myself"):
            char = self.current_character()
            display.display_self(char, self.items_db, self.artifacts_db)
            return

        # Look at NPC
        npc_id, npc = self._find_entity(room.npcs, target, self.npcs_db)
        if npc:
            display.header(npc["name"])
            hc = npc.get("aspects", {}).get("high_concept", "")
            display.narrate(f"  {hc}")
            if npc.get("recruited"):
                display.info(f"  Loyalty: {npc.get('loyalty', 0)}/10  Mood: {npc.get('mood', 'unknown')}")
                assignment = npc.get("assignment", "idle")
                display.info(f"  Assignment: {assignment}")
            return

        # Look at inactive agent
        agent_id, agent = self._find_agent_in_room(target, room.id)
        if agent:
            display.header(agent["name"])
            display.narrate(f"  {agent['name']} — the {agent['role']}. {self.seed_name}'s tendril")
            display.narrate(f"  around them is dim but present, waiting.")
            return

        # Look at enemy
        enemy_id, enemy = self._find_entity(room.enemies, target, self.enemies_db)
        if enemy:
            display.header(enemy["name"])
            display.narrate(f"  {enemy.get('description', '')}")
            aspects = ", ".join(display.aspect_text(a) for a in enemy.get("aspects", []))
            if aspects:
                print(f"  Aspects: {aspects}")
            return

        # Look at artifact in room
        art_id, art = self._find_entity(room.items, target, self.artifacts_db)
        if art:
            display.header(art["name"])
            display.narrate(f"  {art.get('description', '')}")
            if art.get("aspects"):
                aspects = ", ".join(display.aspect_text(a) for a in art["aspects"])
                print(f"  Aspects: {aspects}")
            return

        # Look at item in room
        item_id, item = self._find_entity(room.items, target, self.items_db)
        if item:
            display.header(item["name"])
            display.narrate(f"  {item.get('description', '')}")
            return

        # Look at artifact in inventory
        char = self.current_character()
        art_id, art = self._find_entity(char.inventory, target, self.artifacts_db)
        if art:
            display.header(art["name"])
            display.narrate(f"  {art.get('description', '')}")
            if art.get("aspects"):
                aspects = ", ".join(display.aspect_text(a) for a in art["aspects"])
                print(f"  Aspects: {aspects}")
            if art.get("stat_bonuses"):
                bonuses = ", ".join(f"+{v} {k}" for k, v in art["stat_bonuses"].items())
                display.info(f"  Bonuses (if kept): {bonuses}")
            display.info(f"  Mote value (if fed): {art.get('mote_value', 1)}")
            return

        # Look at item in inventory
        item_id, item = self._find_entity(char.inventory, target, self.items_db)
        if item:
            display.header(item["name"])
            display.narrate(f"  {item.get('description', '')}")
            if item.get("stat_bonuses"):
                bonuses = ", ".join(f"+{v} {k}" for k, v in item["stat_bonuses"].items())
                display.info(f"  Bonuses (if kept): {bonuses}")
            display.info(f"  Mote value (if fed): {item.get('mote_value', 1)}")
            return

        # Look at worn items
        worn_ids = [wid for wid in char.worn.values() if wid is not None]
        art_id, art = self._find_entity(worn_ids, target, self.artifacts_db)
        if art:
            display.header(art["name"])
            display.narrate(f"  {art.get('description', '')}")
            if art.get("aspects"):
                aspects = ", ".join(display.aspect_text(a) for a in art["aspects"])
                print(f"  Aspects: {aspects}")
            if art.get("stat_bonuses"):
                bonuses = ", ".join(f"+{v} {k}" for k, v in art["stat_bonuses"].items())
                display.info(f"  Bonuses: {bonuses}")
            display.info(f"  Mote value (if fed): {art.get('mote_value', 1)}")
            return
        item_id, item = self._find_entity(worn_ids, target, self.items_db)
        if item:
            display.header(item["name"])
            display.narrate(f"  {item.get('description', '')}")
            return

        # Look at aspect
        for aspect in room.aspects:
            if target in aspect.lower():
                print(f"  {display.aspect_text(aspect)} — a room aspect that can be invoked in rolls.")
                return

        display.narrate(f"You don't see '{target}' here.")

    def cmd_ih(self, args):
        """IH — focused list of interactable room contents, or examine a target."""
        room = self.current_room()
        if not room:
            display.error("You're nowhere. That's concerning.")
            return

        if args:
            self._examine_target(" ".join(args))
            return

        # No args — show focused list of interactable things (no room desc, no exits)
        has_contents = False

        # Items (check both items_db and artifacts_db for names)
        if room.items:
            for item_id in room.items:
                if item_id in self.items_db:
                    print(f"  {display.item_name(self.items_db[item_id]['name'])}")
                elif item_id in self.artifacts_db:
                    print(f"  {display.item_name(self.artifacts_db[item_id]['name'])}")
                else:
                    print(f"  {display.item_name(item_id.replace('_', ' ').title())}")
                has_contents = True

        # NPCs
        for npc_id in room.npcs:
            npc = self.npcs_db.get(npc_id, {})
            name = npc.get("name", npc_id.replace("_", " ").title())
            print(f"  {display.npc_name(name)} is here.")
            has_contents = True

        # Inactive agents
        for agent_id, agent_data in self.agents_db.items():
            if agent_data.get("location") == room.id:
                print(f"  {display.npc_name(agent_data['name'])} is here.")
                has_contents = True

        if not has_contents:
            display.narrate("Nothing of interest here.")

    def cmd_go(self, args):
        if not args:
            display.error("Go where? Specify a direction (NORTH, SOUTH, EAST, WEST, UP, DOWN).")
            return

        if self.in_combat:
            display.error("You're in combat! RETREAT, CONCEDE, or finish the fight.")
            return

        direction = args[0].lower()
        room = self.current_room()
        if not room:
            return

        if direction not in room.exits:
            available = ", ".join(d.upper() for d in room.get_exit_directions())
            display.error(f"You can't go {direction}. Exits: {available}")
            return

        target_id = room.exits[direction]
        target_room = self.rooms.get(target_id)
        if not target_room:
            display.error("That path leads nowhere. (This shouldn't happen.)")
            return

        # Move
        phase = self.state["current_phase"]
        if phase == "prologue":
            self.state["prologue_location"] = target_id
        else:
            self.state[f"{phase}_location"] = target_id
        target_room.discover()

        display.display_room(target_room, self.game_context())

        # World seed flavor message occasionally
        if random.random() < 0.3:
            print()
            display.seed_speak(self.seed.communicate(self.seed_name))

    def cmd_inventory(self, args):
        display.display_inventory(self.current_character(), self.items_db, self.artifacts_db)

    def cmd_status(self, args):
        char = self.current_character()
        display.display_character_sheet(char)
        print()
        display.display_seed(self.seed.to_dict(), name=self.seed_name)

    def cmd_check(self, args):
        if not args:
            display.error(f"Check what? Try CHECK SEED, CHECK <npc name>, or CHECK SKERRY.")
            return

        target = " ".join(args).lower()

        if target in ("seed", "tuft", self.seed_name.lower()):
            display.header(f"{self.seed_name} — The World Seed")
            display.display_seed(self.seed.to_dict(), name=self.seed_name)
            print(f"  Aspects: {', '.join(display.aspect_text(a) for a in self.seed.aspects)}")
            stress_str = "".join("[X]" if s else "[ ]" for s in self.seed.stress)
            print(f"  Stress: {stress_str}")
            print(f"  Alive: {'Yes' if self.seed.alive else 'NO — GAME OVER'}")
            print()
            display.seed_speak(self.seed.communicate(self.seed_name))
            return

        if target == "skerry":
            display.header("Skerry Status")
            for room in self.skerry.get_all_rooms():
                structures = ", ".join(room.structures) if room.structures else "none"
                print(f"  {display.npc_name(room.name)}: structures={structures}")
            if self.skerry.expandable:
                print(f"\n  {display.BOLD}Buildable:{display.RESET}")
                for tmpl in self.skerry.expandable:
                    reqs = tmpl.get("requires", {})
                    mats = ", ".join(f"{v}x {k.replace('_', ' ')}" for k, v in reqs.get("materials", {}).items())
                    print(f"    {tmpl['name']} — needs: {mats}")
            return

        # Check NPC
        npc_id, npc = self._find_in_db(target, self.npcs_db)
        if npc:
            display.header(npc["name"])
            display.narrate(f"  {npc['aspects']['high_concept']}")
            if npc.get("recruited"):
                display.info(f"  Loyalty: {npc.get('loyalty', 0)}/10")
                display.info(f"  Mood: {npc.get('mood', 'unknown')}")
                display.info(f"  Assignment: {npc.get('assignment', 'idle')}")
                house_level = npc.get("house_level", 0)
                house_names = {0: "none", 1: "tent", 2: "proper house"}
                display.info(f"  Housing: {house_names.get(house_level, 'unknown')}")
            else:
                display.info(f"  Location: {npc.get('location', 'unknown')}")
                display.info(f"  Not yet recruited")
            return

        # Check inactive agent
        room = self.current_room()
        agent_id, agent = self._find_agent_in_room(target, room.id if room else "")
        if agent:
            role = agent.get("role", "")
            char = self.explorer if role == "explorer" else self.steward
            display.display_character_sheet(char)
            return

        display.narrate(f"You don't know anything about '{target}'.")

    def cmd_help(self, args):
        display.display_help(self.state["current_phase"], seed_name=self.seed_name)

    def cmd_map(self, args):
        current = self.current_room()
        current_id = current.id if current else None

        if args and args[0].lower() == "all":
            lines = map_renderer.render_all_zones_overview(
                self.state.get("zones", {}), self.rooms, current_id)
            for line in lines:
                print(line)
            return

        if args:
            zone_id = map_renderer.resolve_zone_name(args[0])
            if not zone_id:
                display.error(f"Unknown zone: '{args[0]}'. Try: skerry, debris, coral, wreck")
                return
            # Check if at least one room discovered there
            layout = map_renderer.ZONE_LAYOUTS.get(zone_id, {})
            discovered = any(
                self.rooms.get(rid) and self.rooms[rid].discovered
                for _, _, rid in layout.get("grid", [])
            )
            if not discovered:
                display.error(f"You haven't discovered anything in that zone yet.")
                return
            lines = map_renderer.render_zone_map(zone_id, self.rooms, current_id)
            for line in lines:
                print(line)
            return

        # Default: show current zone
        if current_id:
            zone_id = map_renderer.get_zone_for_room(current_id)
            if zone_id:
                lines = map_renderer.render_zone_map(zone_id, self.rooms, current_id)
                for line in lines:
                    print(line)
                return

        display.error("Can't determine your current zone. Try MAP ALL.")

    def cmd_skip(self, args):
        if self.state["current_phase"] != "prologue":
            display.error("Nothing to skip.")
            return
        tutorial.show_skip_message()
        self.state["tutorial_step"] = "complete"
        self.state["tutorial_complete"] = True
        self.state["bonded_with_seed"] = True
        self._transition_to_day1()

    def cmd_bond(self, args):
        if self.state.get("bonded_with_seed"):
            display.narrate("The tendril hums. Warm. Alive.")
            display.seed_speak("We're already connected. I'm right here.")
            return

        # Must be near the world seed (hollow or at least on the skerry)
        room = self.current_room()
        if not room or not room.id.startswith("skerry_"):
            display.seed_speak("You're too far away. Come back to the skerry.")
            return

        self.state["bonded_with_seed"] = True

        if self.state["current_phase"] == "prologue":
            # During the tutorial — tendril comes from the void,
            # pulls you toward the skerry, you see it from outside first
            print()
            display.narrate("You reach out — and the thread of light reaches back.")
            print()
            display.narrate("It winds gently around you like a second pulse.")
            display.narrate("Warm. Alive. Pulsing.")
            print()
            display.narrate("And then it pulls.")
            print()
            display.narrate("The void blurs past you — wreckage, dust, the husks of")
            display.narrate("dead ships — until something appears ahead. Small against")
            display.narrate("the emptiness. A jagged chunk of earth and stone, floating")
            display.narrate("in nothing, wrapped in a faint green shimmer like a bubble")
            display.narrate("about to burst. Roots dangle from its underside. A few")
            display.narrate("stubborn plants cling to the top.")
            print()
            display.narrate("It's tiny. Fragile. The shimmer pulses in time with")
            display.narrate("the tendril around you.")
            print()
            display.narrate("The tendril draws you through the membrane — a moment")
            display.narrate("of warmth, of resistance — and then your feet find")
            display.narrate("solid ground.")
            # Tutorial after_command handles room display and naming
        else:
            # Non-tutorial bond (defensive — shouldn't normally happen)
            print()
            display.narrate("You reach out — and something reaches back.")
            print()
            display.narrate("A tendril of green light rises from the soil, thin as")
            display.narrate("thread, bright as new growth. It stretches toward you,")
            display.narrate("hesitates — then winds gently around your head.")
            print()
            display.narrate("It wraps around you like a second pulse. Warm. Alive.")
            display.narrate("You can feel it pulse in time with the ground beneath you,")
            display.narrate("and suddenly the world has depth it didn't have before.")
            print()
            display.display_room(room, self.game_context())
            print()
            if room.aspects:
                aspect_list = ". ".join(room.aspects)
                display.seed_speak(f"See those? {aspect_list}.")
            else:
                display.seed_speak("See that?")
            display.seed_speak("Those are aspects — the deeper nature of things,")
            display.seed_speak("the way I understand the world. Now you can see it too.")
            print()
            display.seed_speak("When you're in trouble, you can invoke an aspect for")
            display.seed_speak("strength. But that costs a fate point. Use them wisely.")

    def cmd_give(self, args):
        if not args:
            display.error("Give what to whom?")
            return
        display.error("You can't give that.")

    def _transition_to_day1(self):
        """Transition from prologue to Day 1 Explorer Phase."""
        self.state["current_phase"] = "explorer"
        day = self.state["day"]

        # Remove Sevarik-as-NPC (he's now the active explorer character)
        for room in self.rooms.values():
            if "sevarik" in room.npcs:
                room.remove_npc("sevarik")
        if "sevarik" in self.npcs_db:
            del self.npcs_db["sevarik"]

        # Miria becomes an inactive agent on the skerry
        self._deactivate_agent("steward")

        print()
        display.phase_banner("explorer", day, self.explorer_name, self.steward_name)

        # Show explorer starting location
        room = self.rooms.get(self.state["explorer_location"])
        if room:
            room.discover()
            display.display_room(room, self.game_context())

        print()
        display.display_status(self.explorer, "explorer")
        display.display_seed(self.seed.to_dict(), name=self.seed_name)

        # World seed gives Sevarik direction
        print()
        display.seed_speak("Good. We have a steward. I'm stronger now.")
        display.seed_speak("I can send you beyond the skerry to look for supplies.")
        print()
        display.seed_speak("I sense something to the south. It has the feel of")
        display.seed_speak("a faint harmonic hum. Doesn't feel big.")
        display.seed_speak("Are you interested in investigating it?")
        print()
        display.seed_speak("Head south when you're ready.")
        print()

        self.save_game(silent=True)

    def cmd_save(self, args):
        self.save_game()

    def cmd_done(self, args):
        phase = self.state["current_phase"]
        if phase == "prologue":
            if self.state.get("tutorial_step") == "handoff":
                display.seed_speak(f"Tell me to shift focus to {self.explorer_name}.")
                display.info(f"  Type SWITCH FOCUS TO {self.explorer_name.upper()}.")
            else:
                display.seed_speak("Not yet. There's more to see here first.")
        elif phase == "explorer":
            display.seed_speak(f"Ready to shift? Tell me to focus on {self.steward_name}.")
            display.info(f"  Type SWITCH FOCUS TO {self.steward_name.upper()}.")
        else:
            display.seed_speak(f"Ready to shift? Tell me to focus on {self.explorer_name}.")
            display.info(f"  Type SWITCH FOCUS TO {self.explorer_name.upper()}.")

    def cmd_switch(self, args):
        if not args:
            display.error("Switch focus to whom?")
            return

        # Strip filler words
        words = [w for w in args if w not in ("focus", "to")]
        if not words:
            display.error("Switch focus to whom?")
            return

        target = " ".join(words).lower()
        explorer_id = self.explorer_name.lower()
        steward_id = self.steward_name.lower()
        phase = self.state["current_phase"]

        # Match by name or role alias
        if target in (explorer_id, "explorer"):
            target_role = "explorer"
        elif target in (steward_id, "steward"):
            target_role = "steward"
        else:
            display.error(f"You can't switch focus to '{target}'.")
            return

        # Prologue handling
        if phase == "prologue":
            if target_role == "explorer" and self.state.get("tutorial_step") == "handoff":
                self._switch_focus_narration("explorer")
                return  # tutorial.after_command handles completion
            else:
                display.seed_speak("Not yet. Get to know this place first.")
                return

        # Validate: not switching to current
        if (phase == "explorer" and target_role == "explorer") or \
           (phase == "steward" and target_role == "steward"):
            target_name = self.explorer_name if target_role == "explorer" else self.steward_name
            display.seed_speak(f"I'm already focused on {target_name}.")
            return

        self._switch_focus(target_role)

    def _switch_focus_narration(self, target_role):
        """Narration for the tutorial handoff — no phase transition."""
        explorer_name = self.explorer_name
        print()
        display.narrate(f"{self.seed_name}'s tendril around you dims — not gone, but")
        display.narrate("quieter, like a heartbeat fading into the background.")
        print()
        display.narrate("You feel the other tendril brighten — the one reaching")
        display.narrate(f"toward {explorer_name}. His eyes sharpen. The void sharpens")
        display.narrate("into focus around him.")
        print()

    def _switch_focus(self, target_role):
        """Switch active agent between explorer and steward."""
        self.save_game(silent=True)

        if target_role == "steward":
            # Explorer → Steward
            self.state["current_phase"] = "steward"
            print()
            display.narrate(f"{self.explorer_name} returns to the skerry, weary but alive.")
            display.narrate(f"{self.seed_name}'s tendril around him dims — not gone, but")
            display.narrate("quieter, like a heartbeat fading into the background.")
            print()
            display.narrate(f"The other tendril brightens — the one reaching toward")
            display.narrate(f"{self.steward_name}. {self.seed_name}'s presence floods back in.")
            self.explorer.clear_stress()
            self.in_combat = False
            self.combat_target = None

            # Deactivate explorer, activate steward
            self._deactivate_agent("explorer")
            self._activate_agent("steward")

            print()
            display.phase_banner("steward", self.state["day"], self.explorer_name, self.steward_name)

            room = self.rooms.get(self.state["steward_location"])
            if room:
                display.display_room(room, self.game_context())
            display.display_status(self.steward, "steward")
            display.display_seed(self.seed.to_dict(), name=self.seed_name)

        else:
            # Steward → Explorer (day increment)
            self.state["day"] += 1
            self.state["current_phase"] = "explorer"
            self.steward.clear_stress()
            day = self.state["day"]

            print()
            display.narrate("The day ends. Night falls on the skerry — or what")
            display.narrate("passes for night in the void.")

            self._day_transition()

            print()
            display.narrate(f"Morning. {self.seed_name}'s tendril around {self.steward_name} dims.")
            display.narrate(f"The other tendril brightens — reaching toward {self.explorer_name}.")
            display.narrate("His eyes sharpen. The void sharpens into focus.")

            # Deactivate steward, activate explorer
            self._deactivate_agent("steward")
            self._activate_agent("explorer")

            print()
            display.phase_banner("explorer", day, self.explorer_name, self.steward_name)

            room = self.rooms.get(self.state["explorer_location"])
            if room:
                display.display_room(room, self.game_context())
            display.display_status(self.explorer, "explorer")
            display.display_seed(self.seed.to_dict(), name=self.seed_name)

        self.save_game(silent=True)
        print()

    def cmd_quit(self, args):
        self.save_game()
        display.narrate("Farewell, wanderer. The void remembers.")
        self.running = False

    def cmd_talk(self, args):
        if not args:
            display.error("Talk to whom?")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        npc_id, npc = self._find_entity(room.npcs, target, self.npcs_db)
        if npc:
            dialogue = npc.get("dialogue", {})
            if npc.get("recruited"):
                mood = npc.get("mood", "content")
                if mood == "content" or mood == "happy":
                    msg = dialogue.get("happy", dialogue.get("idle", "..."))
                else:
                    msg = dialogue.get("idle", "...")
                display.npc_speak(npc["name"], self._sub_dialogue(msg))
                # Talking to recruited NPCs boosts loyalty slightly
                if npc.get("loyalty", 0) < 10:
                    npc["loyalty"] = min(10, npc.get("loyalty", 0) + 1)
                    display.success(f"  {npc['name']}'s loyalty increases to {npc['loyalty']}.")
            else:
                msg = dialogue.get("greeting", "They look at you warily.")
                display.npc_speak(npc["name"], self._sub_dialogue(msg))
            return

        # Talk to inactive agent
        agent_id, agent = self._find_agent_in_room(target, room.id)
        if agent:
            dialogue = agent.get("dialogue", {})
            msg = dialogue.get("idle", f"{agent['name']} nods quietly.")
            display.npc_speak(agent["name"], self._sub_dialogue(msg))
            return

        display.narrate(f"There's nobody called '{target}' here to talk to.")

    def cmd_use(self, args):
        if not args:
            display.error("Use what?")
            return

        target = " ".join(args).lower()
        char = self.current_character()

        # Check artifacts in inventory
        art_id, art = self._find_entity(char.inventory, target, self.artifacts_db)
        if art:
            if art_id == "silver_slippers":
                display.narrate("You slip them on and click the heels together.")
                display.narrate("Once. Twice. Three times.")
                print()
                display.seed_speak("You feel a tug — toward the skerry. Lost in the")
                display.seed_speak("void, click your heels and these will pull you home.")
            elif art_id == "red_clown_nose":
                display.narrate("You put on the nose. It's squishy. Ridiculous.")
                display.narrate("But something shifts — the air around you softens.")
                print()
                display.seed_speak("Less sharp. Less threatening. Less worth envying.")
                display.seed_speak("That could save your life out there.")
            else:
                display.narrate(f"You hold the {art['name']}. It hums faintly.")
            return

        item_id, item = self._find_entity(char.inventory, target, self.items_db)
        if item:
            if item.get("special") == "restore_stress":
                char.clear_stress()
                char.remove_from_inventory(item_id)
                display.success(f"You eat the {item['name']}. All stress cleared.")
            elif item.get("type") == "crafted" and item.get("stat_bonuses"):
                display.narrate(f"The {item['name']} is already providing its bonus passively.")
            else:
                display.narrate(f"You can't use {item.get('name', target)} right now.")
            return

        display.narrate(f"You don't have '{target}'.")

    def cmd_wear(self, args):
        if not args:
            display.error("Wear what?")
            return

        target = " ".join(args).lower()
        char = self.current_character()

        # Find item in inventory — check both items_db and artifacts_db
        art_id, art = self._find_entity(char.inventory, target, self.artifacts_db)
        if art:
            slot = art.get("slot")
            if not slot:
                display.narrate("You can't wear that.")
                return
            if char.worn.get(slot):
                current_name = display._lookup_name(char.worn[slot], self.items_db, self.artifacts_db)
                display.narrate(f"You're already wearing {current_name} on your {slot}. REMOVE it first.")
                return
            char.wear_item(art_id, slot)
            display.success(f"You put on the {art['name']}.")
            return

        item_id, item = self._find_entity(char.inventory, target, self.items_db)
        if item:
            slot = item.get("slot")
            if not slot:
                display.narrate("You can't wear that.")
                return
            if char.worn.get(slot):
                current_name = display._lookup_name(char.worn[slot], self.items_db, self.artifacts_db)
                display.narrate(f"You're already wearing {current_name} on your {slot}. REMOVE it first.")
                return
            char.wear_item(item_id, slot)
            display.success(f"You put on the {item['name']}.")
            return

        display.narrate(f"You don't have '{target}'.")

    def cmd_remove(self, args):
        if not args:
            display.error("Remove what?")
            return

        target = " ".join(args).lower()
        char = self.current_character()

        # Try target as a slot name
        if target in BODY_SLOTS:
            item_id = char.remove_worn(target)
            if item_id:
                name = display._lookup_name(item_id, self.items_db, self.artifacts_db)
                display.success(f"You take off the {name}.")
            else:
                display.narrate(f"You're not wearing anything on your {target}.")
            return

        # Match item name against worn items
        worn_ids = [wid for wid in char.worn.values() if wid is not None]
        art_id, art = self._find_entity(worn_ids, target, self.artifacts_db)
        if art:
            slot = char.find_worn_by_item(art_id)
            if slot:
                char.remove_worn(slot)
                display.success(f"You take off the {art['name']}.")
                return

        item_id, item = self._find_entity(worn_ids, target, self.items_db)
        if item:
            slot = char.find_worn_by_item(item_id)
            if slot:
                char.remove_worn(slot)
                display.success(f"You take off the {item['name']}.")
                return

        display.narrate(f"You're not wearing anything called '{target}'.")

    # ── Explorer Commands ─────────────────────────────────────────

    def cmd_attack(self, args):
        if not args:
            display.error("Attack what?")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        enemy_id, enemy_data = self._find_entity(room.enemies, target, self.enemies_db)
        if not enemy_data:
            display.error(f"There's nothing called '{target}' to attack here.")
            return

        self.in_combat = True
        self.combat_target = enemy_id
        self.defending = False

        # Get skills
        atk_skill_val = self.explorer.get_skill("Fight")
        def_skill_val = enemy_data["skills"].get("Fight", 1)

        # Roll opposed
        atk_total, def_total, shifts, atk_dice, def_dice = dice.opposed_roll(atk_skill_val, def_skill_val)

        display.header(f"Combat: {self.explorer.name} vs {enemy_data['name']}")
        print(f"  {self.explorer.name}: {dice.roll_description(atk_dice, atk_skill_val, 'Fight')}")
        print(f"  {enemy_data['name']}: {dice.roll_description(def_dice, def_skill_val, 'Fight')}")

        if shifts > 0:
            # Player hits enemy
            display.success(f"  You hit for {shifts} shifts!")
            if self._apply_enemy_damage(enemy_data, enemy_id, shifts, room):
                return

        elif shifts < 0:
            # Enemy hits player
            hit_amount = abs(shifts)
            display.warning(f"  {enemy_data['name']} hits you for {hit_amount} shifts!")
            taken_out = self.explorer.apply_damage(hit_amount)

            if taken_out:
                display.warning(f"\n  {self.explorer.name} is taken out!")
                self._seed_extraction()
                return

            stress_str = "".join("[X]" if s else "[ ]" for s in self.explorer.stress)
            display.info(f"  Stress: {stress_str}")

        else:
            display.narrate("  The exchange is a draw. Neither side gains ground.")

        print()
        display.narrate("Combat continues. ATTACK again, DEFEND, INVOKE an aspect, CONCEDE, or RETREAT.")

    def cmd_defend(self, args):
        if not self.in_combat:
            display.error("You're not in combat.")
            return

        self.defending = True
        display.narrate("You take a defensive stance. (+2 to your next defense roll)")

        # Enemy attacks
        enemy_data = self.enemies_db.get(self.combat_target, {})
        if not enemy_data:
            return

        def_skill_val = self.explorer.get_skill("Fight") + 2  # defensive bonus
        atk_skill_val = enemy_data["skills"].get("Fight", 1)

        atk_total, def_total, shifts, atk_dice, def_dice = dice.opposed_roll(atk_skill_val, def_skill_val)

        print(f"  {enemy_data['name']} attacks: {dice.roll_description(atk_dice, atk_skill_val, 'Fight')}")
        print(f"  Your defense: {dice.roll_description(def_dice, def_skill_val, 'Fight (defending)')}")

        if shifts > 0:
            display.warning(f"  Despite your defense, you take {shifts} shifts!")
            taken_out = self.explorer.apply_damage(shifts)
            if taken_out:
                display.warning(f"\n  {self.explorer.name} is taken out!")
                self._seed_extraction()
                return
        else:
            display.success("  You successfully defend against the attack.")

        self.defending = False

    def cmd_invoke(self, args):
        if not args:
            display.error("Invoke which aspect? Type INVOKE followed by an aspect name.")
            return

        if not self.in_combat:
            display.error("You can only invoke aspects during combat.")
            return

        aspect_name = " ".join(args)
        char = self.current_character()

        # Check if aspect exists on character, room, or enemy
        all_aspects = char.get_all_aspects()
        room = self.current_room()
        if room:
            all_aspects.extend(room.aspects)
        if self.combat_target:
            enemy = self.enemies_db.get(self.combat_target, {})
            all_aspects.extend(enemy.get("aspects", []))

        found = None
        for a in all_aspects:
            if aspect_name.lower() in a.lower():
                found = a
                break

        if not found:
            display.error(f"No matching aspect found for '{aspect_name}'.")
            display.info(f"Available aspects:")
            for a in all_aspects:
                print(f"  {display.aspect_text(a)}")
            return

        if not char.spend_fate_point():
            display.error("No fate points to spend!")
            return

        display.success(f"You invoke {display.aspect_text(found)} for +2 on your next roll!")
        display.info(f"  (Fate Points remaining: {char.fate_points})")

        # Auto-attack with the bonus
        enemy_data = self.enemies_db.get(self.combat_target, {})
        if not enemy_data:
            return

        atk_skill_val = self.explorer.get_skill("Fight") + 2  # invoke bonus
        def_skill_val = enemy_data["skills"].get("Fight", 1)

        atk_total, def_total, shifts, atk_dice, def_dice = dice.opposed_roll(atk_skill_val, def_skill_val)

        print(f"  {self.explorer.name} (invoked): {dice.roll_description(atk_dice, atk_skill_val, 'Fight+2')}")
        print(f"  {enemy_data['name']}: {dice.roll_description(def_dice, def_skill_val, 'Fight')}")

        if shifts > 0:
            display.success(f"  Empowered strike for {shifts} shifts!")
            if self._apply_enemy_damage(enemy_data, self.combat_target, shifts, room):
                self.combat_target = None
                return
        elif shifts < 0:
            display.warning(f"  Even with the invoke, {enemy_data['name']} counters for {abs(shifts)} shifts!")
            self.explorer.apply_damage(abs(shifts))
        else:
            display.narrate("  A draw despite the invocation.")

    def cmd_concede(self, args):
        if not self.in_combat:
            display.error("You're not in combat.")
            return

        self.in_combat = False
        enemy = self.enemies_db.get(self.combat_target, {})
        self.combat_target = None
        self.explorer.gain_fate_point()

        display.narrate(f"You concede the fight against {enemy.get('name', 'the enemy')}.")
        display.narrate("You back away carefully, ceding ground.")
        display.success("+1 Fate Point for conceding.")
        display.narrate("The enemy lets you go — for now.")

    def cmd_scavenge(self, args):
        room = self.current_room()
        if room.has_enemies():
            display.error("You can't scavenge while enemies are present!")
            return

        total, shifts, dice_result = dice.skill_check(self.explorer.get_skill("Scavenge"), 1)
        print(f"  Scavenge: {dice.roll_description(dice_result, self.explorer.get_skill('Scavenge'), 'Scavenge')}")

        if shifts >= 0:
            # Find something
            zone_id = room.zone
            zone = self.state["zones"].get(zone_id, {})
            possible_loot = []
            for enemy_data in zone.get("enemies_data", []):
                possible_loot.extend(enemy_data.get("loot", []))
            if not possible_loot:
                possible_loot = ["metal_scraps", "torn_fabric", "wire"]

            found = random.choice(possible_loot)
            self.explorer.add_to_inventory(found)
            item_info = self.items_db.get(found, {})
            display.success(f"  Found: {item_info.get('name', found)}!")

            if shifts >= 3:  # Succeed with style
                bonus = random.choice(possible_loot)
                self.explorer.add_to_inventory(bonus)
                bonus_info = self.items_db.get(bonus, {})
                display.success(f"  Excellent work! Also found: {bonus_info.get('name', bonus)}!")
        else:
            display.narrate("  You search carefully but find nothing useful this time.")

    def cmd_probe(self, args):
        if not args:
            display.error("Probe what? Specify an item or object to examine.")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        # Check artifacts in room
        art_id, art = self._find_in_db(target, self.artifacts_db)
        if art and art.get("room") == room.id:
            if art_id not in self.state.get("artifacts_status", {}):
                display.header(art["name"])
                display.narrate(self.sub(art.get("discovery_text", art["description"])))
                self.state.setdefault("artifacts_status", {})[art_id] = "discovered"
                display.info(f"  Feed to {self.seed_name}: {art['mote_value']} motes")
                if art.get("stat_bonuses"):
                    bonuses = ", ".join(f"+{v} {k}" for k, v in art["stat_bonuses"].items())
                    display.info(f"  Keep for: {bonuses}")
                if art.get("keep_effect"):
                    display.info(f"  Special: {self.sub(art['keep_effect'][:80])}...")
            else:
                display.header(art["name"])
                display.narrate(self.sub(art["description"]))
            return

        # Check items in room
        item_id, item = self._find_entity(room.items, target, self.items_db)
        if item:
            display.header(item["name"])
            display.narrate(self.sub(item["description"]))
            display.info(f"  Mote value: {item.get('mote_value', 1)}")
            return

        display.narrate(f"Nothing called '{target}' to probe here.")

    def cmd_feed(self, args):
        if not args:
            display.error(f"Feed what to {self.seed_name}?")
            return

        target = " ".join(args).lower()
        char = self.current_character()

        # Check artifacts first
        art_id, art = self._find_in_db(target, self.artifacts_db)
        if art and (art_id in char.inventory or self.state.get("artifacts_status", {}).get(art_id) == "discovered"):
            motes = art["mote_value"]
            new_total, stage_changed = self.seed.feed(motes)
            char.remove_from_inventory(art_id)
            self.state.setdefault("artifacts_status", {})[art_id] = "fed"

            if art.get("feed_effect"):
                display.narrate(self.sub(art["feed_effect"]))
            else:
                display.success(f"You feed the {art['name']} to {self.seed_name}. +{motes} motes!")

            if stage_changed:
                display.success(f"\n  ✧ {self.seed_name.upper()} GROWS STRONGER! ✧")
                display.seed_speak(self.seed.communicate(self.seed_name))

            display.display_seed(self.seed.to_dict(), name=self.seed_name)
            return

        # Check regular items
        item_id, item = self._find_entity(list(char.inventory), target, self.items_db)
        if item:
            motes = item.get("mote_value", 1)
            new_total, stage_changed = self.seed.feed(motes)
            char.remove_from_inventory(item_id)

            display.success(f"You feed {item.get('name', item_id)} to {self.seed_name}. +{motes} motes!")
            if stage_changed:
                display.success(f"\n  ✧ {self.seed_name.upper()} GROWS STRONGER! ✧")
                display.seed_speak(self.seed.communicate(self.seed_name))

            display.display_seed(self.seed.to_dict(), name=self.seed_name)
            return

        display.narrate(f"You don't have '{target}' to feed.")

    def cmd_keep(self, args):
        if not args:
            display.error("Keep which artifact?")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        art_id, art = self._find_in_db(target, self.artifacts_db)
        if art:
            char = self.current_character()
            already_held = art_id in char.inventory
            status = self.state.get("artifacts_status", {}).get(art_id)
            if already_held or status == "discovered" or art.get("room") == room.id:
                if not already_held:
                    char.add_to_inventory(art_id)
                self.state.setdefault("artifacts_status", {})[art_id] = "kept"

                display.success(f"You keep the {art['name']}.")
                if art.get("stat_bonuses"):
                    for skill, bonus in art["stat_bonuses"].items():
                        display.success(f"  +{bonus} {skill} while carried!")
                if art.get("keep_effect"):
                    display.narrate(self.sub(art["keep_effect"]))
                return

        display.narrate(f"No artifact called '{target}' to keep here.")

    def cmd_offer(self, args):
        """OFFER <item> TO <target> — give an item to someone (feed to seed, or gift to NPC)."""
        if not args:
            display.error("Offer what to whom? Usage: OFFER <item> TO <target>")
            return

        # Split on "to" to get item and target
        raw = " ".join(args)
        parts = raw.split(" to ", 1)
        if len(parts) < 2:
            display.error("Offer what to whom? Usage: OFFER <item> TO <target>")
            return

        item_name_str = parts[0].strip().lower()
        target_name = parts[1].strip().lower()

        # Check if target is the world seed
        seed_name = self.seed_name.lower()
        if target_name in (seed_name, "seed", "tuft"):
            # Same logic as feeding — check artifacts first, then items
            char = self.current_character()

            art_id, art = self._find_in_db(item_name_str, self.artifacts_db)
            if art and (art_id in char.inventory or char.find_worn_by_item(art_id)):
                # If worn, unequip first (moves to inventory)
                worn_slot = char.find_worn_by_item(art_id)
                if worn_slot:
                    char.remove_worn(worn_slot)
                motes = art["mote_value"]
                new_total, stage_changed = self.seed.feed(motes)
                char.remove_from_inventory(art_id)
                self.state.setdefault("artifacts_status", {})[art_id] = "fed"

                if art.get("feed_effect"):
                    display.narrate(self.sub(art["feed_effect"]))
                else:
                    display.success(f"You offer the {art['name']} to {self.seed_name}. +{motes} motes!")

                if stage_changed:
                    display.success(f"\n  ✧ {self.seed_name.upper()} GROWS STRONGER! ✧")
                    display.seed_speak(self.seed.communicate(self.seed_name))

                display.display_seed(self.seed.to_dict(), name=self.seed_name)
                return

            # Check inventory and worn items
            worn_ids = [wid for wid in char.worn.values() if wid]
            search_ids = list(char.inventory) + worn_ids
            item_id, item = self._find_entity(search_ids, item_name_str, self.items_db)
            if item:
                # If worn, unequip first (moves to inventory)
                worn_slot = char.find_worn_by_item(item_id)
                if worn_slot:
                    char.remove_worn(worn_slot)
                motes = item.get("mote_value", 1)
                new_total, stage_changed = self.seed.feed(motes)
                char.remove_from_inventory(item_id)

                display.success(f"You offer {item.get('name', item_id)} to {self.seed_name}. +{motes} motes!")
                if stage_changed:
                    display.success(f"\n  ✧ {self.seed_name.upper()} GROWS STRONGER! ✧")
                    display.seed_speak(self.seed.communicate(self.seed_name))

                display.display_seed(self.seed.to_dict(), name=self.seed_name)
                return

            display.narrate(f"You don't have '{item_name_str}' to offer.")
            return

        # Target is an NPC — future functionality
        display.narrate("They don't seem interested.")

    def cmd_take(self, args):
        if not args:
            display.error("Take what?")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        # Check artifacts in room
        art_id, art = self._find_entity(list(room.items), target, self.artifacts_db)
        if art:
            room.remove_item(art_id)
            self.current_character().add_to_inventory(art_id)
            display.success(f"You pick up the {art.get('name', art_id)}.")
            return

        item_id, item = self._find_entity(list(room.items), target, self.items_db)
        if item:
            room.remove_item(item_id)
            self.current_character().add_to_inventory(item_id)
            display.success(f"You pick up {item.get('name', item_id)}.")
            return

        display.narrate(f"There's nothing called '{target}' here to take.")

    def cmd_recruit(self, args):
        if not args:
            display.error("Recruit whom?")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        npc_id, npc = self._find_entity(room.npcs, target, self.npcs_db)
        if not npc:
            display.narrate(f"There's nobody called '{target}' here to recruit.")
            return

        if npc.get("recruited"):
            display.narrate(f"{npc['name']} is already with you.")
            return

        dc = npc.get("recruit_dc", 2)
        if dc is None:
            display.narrate(f"{npc['name']} can't be recruited.")
            return

        # Special conditions
        condition = npc.get("recruit_condition")
        if condition == "combat_demo":
            display.narrate(self._sub_dialogue(npc["dialogue"].get("recruit_fail", "They want proof of your strength.")))
            display.info("  (Defeat an enemy in this room first, then try again.)")
            if room.has_enemies():
                return
            dc = 0

        total, shifts, dice_result = dice.skill_check(self.explorer.get_skill("Rapport"), dc)
        print(f"  Rapport check: {dice.roll_description(dice_result, self.explorer.get_skill('Rapport'), 'Rapport')}")
        print(f"  DC: +{dc}")

        if shifts >= 0:
            npc["recruited"] = True
            npc["loyalty"] = 3
            npc["location"] = "skerry_central"
            self.state.setdefault("recruited_npcs", []).append(npc_id)

            room.remove_npc(npc_id)
            skerry_central = self.rooms.get("skerry_central")
            if skerry_central:
                skerry_central.add_npc(npc_id)

            display.success(self._sub_dialogue(npc["dialogue"].get("recruit_success", f"{npc['name']} joins you!")))
            display.info(f"  {npc['name']} will head to the skerry.")
        else:
            display.narrate(self._sub_dialogue(npc["dialogue"].get("recruit_fail", f"{npc['name']} isn't convinced yet.")))

    def cmd_retreat(self, args):
        if self.in_combat:
            display.warning(f"Emergency retreat! {self.seed_name} pulls you back to safety.")
            self._seed_extraction()
        else:
            # Just go back to skerry
            self.state["explorer_location"] = "skerry_landing"
            display.narrate("You make your way back to the skerry.")
            room = self.rooms.get("skerry_landing")
            if room:
                display.display_room(room, self.game_context())

    # ── Steward Commands ─────────────────────────────────────────

    def cmd_craft(self, args):
        if not args:
            display.error("Craft what? Type RECIPES to see available recipes.")
            return

        target = " ".join(args).lower()
        _, recipe = self._find_in_db(target, self.recipes_db)
        if not recipe:
            display.error(f"Unknown recipe: '{target}'. Type RECIPES to see options.")
            return

        if recipe["id"] not in self.state.get("discovered_recipes", []):
            display.error(f"You haven't learned the {recipe['name']} recipe yet.")
            return

        # Check materials
        char = self.steward
        inv_counts = self._inventory_counts(char)

        missing = []
        for mat, needed in recipe["materials"].items():
            if inv_counts.get(mat, 0) < needed:
                mat_name = self.items_db.get(mat, {}).get("name", mat)
                missing.append(f"{needed}x {mat_name} (have {inv_counts.get(mat, 0)})")

        if missing:
            display.error(f"Missing materials: {', '.join(missing)}")
            return

        # Skill check
        skill_name = recipe.get("skill", "Craft")
        dc = recipe["difficulty"]
        total, shifts, dice_result = dice.skill_check(char.get_skill(skill_name), dc)
        print(f"  {skill_name}: {dice.roll_description(dice_result, char.get_skill(skill_name), skill_name)}")
        print(f"  DC: +{dc}")

        if shifts >= 0:
            # Consume materials
            for mat, needed in recipe["materials"].items():
                for _ in range(needed):
                    char.remove_from_inventory(mat)

            # Create result
            result_id = recipe["result"]
            char.add_to_inventory(result_id)
            result_info = self.items_db.get(result_id, {})
            display.success(f"Crafted: {result_info.get('name', result_id)}!")

            if shifts >= 3:
                display.success("Masterwork! You crafted it with exceptional quality.")
                # Bonus: extra item or better version
                char.add_to_inventory(result_id)
                display.success(f"  Bonus: crafted a second {result_info.get('name', result_id)}!")
        else:
            # Fail — lose some materials
            lost_mat = list(recipe["materials"].keys())[0]
            char.remove_from_inventory(lost_mat)
            lost_name = self.items_db.get(lost_mat, {}).get("name", lost_mat)
            display.warning(f"Crafting failed! Lost 1x {lost_name} in the attempt.")

    def cmd_recipes(self, args):
        display.header("Known Recipes")
        discovered = self.state.get("discovered_recipes", [])
        if not discovered:
            print("  No recipes known yet.")
            return

        for rid in discovered:
            recipe = self.recipes_db.get(rid, {})
            mats = ", ".join(f"{v}x {self.items_db.get(k, {}).get('name', k)}"
                           for k, v in recipe.get("materials", {}).items())
            result_name = self.items_db.get(recipe.get("result", ""), {}).get("name", recipe.get("result", "?"))
            print(f"  {display.BOLD}{recipe.get('name', rid)}{display.RESET}: {mats} → {result_name} (DC +{recipe.get('difficulty', 0)})")

    def cmd_build(self, args):
        if not args:
            display.error("Build what? Type CHECK SKERRY to see buildable structures.")
            return

        target = " ".join(args).lower()

        # Check for NPC house building
        if target.startswith("house "):
            npc_target = target[6:].strip()
            npc_id, npc = self._find_in_db(npc_target, self.npcs_db)
            if not npc or not npc.get("recruited"):
                display.error(f"No recruited NPC named '{npc_target}' to build a house for.")
                return

            current = self.skerry.get_house_level(npc_id)
            if current >= 2:
                display.narrate(f"{npc['name']} already has a proper house.")
                return

            # Cost: tent = 2 fabric + 1 rope; house = 3 metal + 2 fabric
            if current == 0:
                needed = {"torn_fabric": 2, "rope": 1}
                label = "tent"
            else:
                needed = {"metal_scraps": 3, "torn_fabric": 2}
                label = "proper house"

            inv_counts = self._inventory_counts(self.steward)

            missing = []
            for mat, count in needed.items():
                if inv_counts.get(mat, 0) < count:
                    missing.append(f"{count}x {self.items_db.get(mat, {}).get('name', mat)}")

            if missing:
                display.error(f"Need: {', '.join(missing)} to build a {label}.")
                return

            for mat, count in needed.items():
                for _ in range(count):
                    self.steward.remove_from_inventory(mat)

            self.skerry.build_npc_house(npc_id)
            npc["house_level"] = self.skerry.get_house_level(npc_id)
            display.success(f"Built a {label} for {npc['name']}!")
            if npc.get("mood") == "restless":
                npc["mood"] = "content"
                display.success(f"  {npc['name']}'s mood improves to content.")
            return

        # Check expandable skerry rooms
        for tmpl in list(self.skerry.expandable):
            if target in tmpl["name"].lower():
                inv_counts = self._inventory_counts(self.steward)

                npc_count = len(self.state.get("recruited_npcs", []))
                can, reason = self.skerry.can_build(tmpl, inv_counts, npc_count, self.seed.growth_stage)

                if not can:
                    display.error(f"Can't build {tmpl['name']}: {reason}")
                    return

                # Consume materials
                for mat, count in tmpl.get("requires", {}).get("materials", {}).items():
                    for _ in range(count):
                        self.steward.remove_from_inventory(mat)

                room = self.skerry.build_room(tmpl)
                self.rooms[room.id] = room

                display.success(f"Built: {room.name}!")
                display.narrate(f"  {room.description}")

                # Update skerry state
                self.state["skerry"] = self.skerry.to_dict()
                return

        display.error(f"Nothing called '{target}' to build. Type CHECK SKERRY for options.")

    def cmd_assign(self, args):
        if len(args) < 2:
            display.error("Usage: ASSIGN <npc> <task>  (tasks: scavenging, building, gardening, guarding, crafting)")
            return

        npc_target = args[0].lower()
        task = args[1].lower()
        valid_tasks = ["scavenging", "building", "gardening", "guarding", "crafting", "idle"]

        if task not in valid_tasks:
            display.error(f"Unknown task: '{task}'. Valid tasks: {', '.join(valid_tasks)}")
            return

        npc_id, npc = self._find_in_db(npc_target, self.npcs_db)
        if not npc or not npc.get("recruited"):
            display.error(f"No recruited NPC named '{npc_target}'.")
            return

        total, shifts, dice_result = dice.skill_check(self.steward.get_skill("Organize"), 1)
        print(f"  Organize: {dice.roll_description(dice_result, self.steward.get_skill('Organize'), 'Organize')}")

        if shifts >= 0:
            npc["assignment"] = task
            display.success(f"Assigned {npc['name']} to {task}.")
        else:
            display.narrate(f"You try to assign {npc['name']}, but the instructions get muddled. Try again.")

    def cmd_organize(self, args):
        display.header("NPC Assignments")
        has_npcs = False
        for npc_id, npc in self.npcs_db.items():
            if npc.get("recruited"):
                has_npcs = True
                mood_colors = {"content": display.GREEN, "happy": display.BRIGHT_GREEN,
                              "restless": display.YELLOW, "unhappy": display.RED, "crisis": display.BRIGHT_RED}
                mood = npc.get("mood", "content")
                mc = mood_colors.get(mood, display.WHITE)
                print(f"  {display.npc_name(npc['name'])}: {npc.get('assignment', 'idle')} — "
                      f"Loyalty: {npc.get('loyalty', 0)}/10 — {mc}{mood}{display.RESET}")
        if not has_npcs:
            print("  No NPCs recruited yet.")

    def cmd_trade(self, args):
        display.narrate("Trading isn't fully set up yet — NPCs share resources with the community for now.")

    # ── Helper Methods ────────────────────────────────────────────

    def _sub_dialogue(self, text):
        """Substitute template variables in NPC dialogue strings."""
        return text.replace("{seed_name}", self.seed_name)

    def _find_entity(self, entity_ids, target, db):
        """Find an entity by name or id from a list. Returns (id, data) or (None, None)."""
        for eid in entity_ids:
            edata = db.get(eid, {})
            if target in edata.get("name", "").lower() or target == eid:
                return eid, edata
        return None, None

    def _find_in_db(self, target, db):
        """Find an entity by name or id across the whole db. Returns (id, data) or (None, None)."""
        for eid, edata in db.items():
            if target in edata.get("name", "").lower() or target == eid:
                return eid, edata
        return None, None

    def _deactivate_agent(self, role):
        """Mark an agent as inactive — add to agents_db so they appear on the skerry."""
        if role == "explorer":
            agent_id = self.explorer_name.lower()
            location = "skerry_landing"
            agent_data = {
                "name": self.explorer_name,
                "role": "explorer",
                "location": location,
                "dialogue": {
                    "greeting": f"{self.explorer_name} nods. 'Back from the void. What do you need?'",
                    "idle": f"'{self.seed_name} is focused on you right now. I'll wait.'",
                    "happy": "'The skerry. It's not much, but it's worth fighting for.'",
                },
            }
        else:
            agent_id = self.steward_name.lower()
            location = self.state.get("steward_location", "skerry_central")
            agent_data = {
                "name": self.steward_name,
                "role": "steward",
                "location": location,
                "dialogue": {
                    "greeting": f"{self.steward_name} looks up from her work. 'Everything's holding together.'",
                    "idle": f"'{self.seed_name} is focused on you right now. I'll keep busy.'",
                    "happy": "'The skerry feels stronger today. We're getting somewhere.'",
                },
            }
        self.agents_db[agent_id] = agent_data

    def _activate_agent(self, role):
        """Mark an agent as active — remove from agents_db (player controls them directly)."""
        if role == "explorer":
            agent_id = self.explorer_name.lower()
        else:
            agent_id = self.steward_name.lower()
        self.agents_db.pop(agent_id, None)

    def _find_agent_in_room(self, target, room_id):
        """Find an inactive agent in the given room. Returns (agent_id, agent_data) or (None, None)."""
        for agent_id, agent_data in self.agents_db.items():
            if agent_data.get("location") == room_id:
                name = agent_data.get("name", "").lower()
                role = agent_data.get("role", "")
                if target in name or target == agent_id or target == role:
                    return agent_id, agent_data
        return None, None

    def _inventory_counts(self, char):
        """Count items in a character's inventory. Returns {item_id: count}."""
        counts = {}
        for item_id in char.inventory:
            counts[item_id] = counts.get(item_id, 0) + 1
        return counts

    def _apply_enemy_damage(self, enemy_data, enemy_id, shifts, room):
        """Apply damage to an enemy. Returns True if enemy was defeated."""
        enemy_stress = enemy_data.get("stress", [False, False])
        enemy_cons = enemy_data.get("consequences", {"mild": None})

        absorbed = False
        for i in range(len(enemy_stress)):
            if not enemy_stress[i] and (i + 1) >= shifts:
                enemy_stress[i] = True
                absorbed = True
                display.narrate(f"  {enemy_data['name']} absorbs the hit.")
                break

        if not absorbed:
            con_values = {"mild": 2, "moderate": 4, "severe": 6}
            for sev in ["mild", "moderate", "severe"]:
                if sev in enemy_cons and enemy_cons[sev] is None and con_values.get(sev, 0) >= shifts:
                    enemy_cons[sev] = "Wounded"
                    absorbed = True
                    display.warning(f"  {enemy_data['name']} takes a {sev} consequence!")
                    break

        if not absorbed:
            # Enemy defeated!
            display.success(f"\n  {enemy_data['name']} is defeated!")
            room.remove_enemy(enemy_id)
            self.in_combat = False
            self.combat_target = None
            loot = enemy_data.get("loot", [])
            if loot:
                dropped = random.choice(loot)
                room.add_item(dropped)
                item_info = self.items_db.get(dropped, {})
                display.success(f"  It drops: {item_info.get('name', dropped)}")
            self.explorer.gain_fate_point()
            display.info(f"  (+1 Fate Point for victory)")
            return True

        enemy_data["stress"] = enemy_stress
        enemy_data["consequences"] = enemy_cons
        return False

    def _seed_extraction(self):
        """Handle world seed emergency extraction."""
        cost = self.seed.extraction_cost(self.state["extractions"])

        if self.seed.spend_motes(cost):
            self.state["extractions"] += 1
            self.in_combat = False
            self.combat_target = None
            self.explorer.clear_stress()
            # Reset consequences to None only if pending
            for sev in list(self.explorer.consequences.keys()):
                if self.explorer.consequences[sev] == "Pending":
                    self.explorer.consequences[sev] = None

            self.state["explorer_location"] = "skerry_landing"

            display.warning(f"\n  {self.seed_name} spends {cost} motes to yank you back to the skerry!")
            display.display_seed(self.seed.to_dict(), name=self.seed_name)

            if not self.seed.alive:
                display.error(f"\n  ═══ {self.seed_name.upper()}'S MOTES ARE DEPLETED ═══")
                display.error("  The world seed flickers and goes dark.")
                display.error(f"  Without {self.seed_name}, the skerry crumbles into the void.")
                display.error("  ═══ GAME OVER ═══\n")
                self.running = False
            else:
                display.narrate(f"You collapse on the landing pad, gasping. {self.seed_name} saved you — but at a cost.")
                display.seed_speak(self.seed.communicate(self.seed_name))
        else:
            display.error(f"  {self.seed_name} doesn't have enough motes ({cost} needed, {self.seed.motes} available)!")
            display.error(f"\n  ═══ {self.seed_name.upper()} CANNOT SAVE YOU ═══")
            display.error("  ═══ GAME OVER ═══\n")
            self.running = False

    def _day_transition(self):
        """Handle end-of-day events."""
        day = self.state["day"]

        # World seed growth check
        display.seed_speak(self.seed.communicate(self.seed_name))

        # NPC mood updates
        for npc_id, npc in self.npcs_db.items():
            if npc.get("recruited"):
                house = npc.get("house_level", 0)
                if house == 0 and npc.get("mood") != "unhappy":
                    if random.random() < 0.3:
                        npc["mood"] = "restless"
                        display.info(f"  {npc['name']} is getting restless without proper shelter.")

        # NPC task yields
        for npc_id, npc in self.npcs_db.items():
            if not npc.get("recruited"):
                continue
            task = npc.get("assignment", "idle")
            if task == "scavenging":
                if random.random() < 0.6:
                    loot = random.choice(["metal_scraps", "wire", "torn_fabric", "coral_fragments"])
                    self.steward.add_to_inventory(loot)
                    loot_name = self.items_db.get(loot, {}).get("name", loot)
                    display.success(f"  {npc['name']} (scavenging) found: {loot_name}")
            elif task == "gardening":
                if random.random() < 0.4:
                    self.steward.add_to_inventory("seeds")
                    display.success(f"  {npc['name']} (gardening) harvested: Seeds")
            elif task == "guarding":
                display.info(f"  {npc['name']} keeps watch over the skerry.")

        # Random event
        if random.random() < 0.4:
            events = self.events_db.get("steward_events", [])
            if events:
                # Filter by requirements
                eligible = []
                npc_count = len(self.state.get("recruited_npcs", []))
                for evt in events:
                    reqs = evt.get("requires", {})
                    if npc_count >= reqs.get("min_npcs", 0):
                        eligible.append(evt)

                if eligible:
                    weights = [e.get("weight", 1) for e in eligible]
                    event = random.choices(eligible, weights=weights, k=1)[0]
                    display.header(f"Event: {self.sub(event['name'])}")
                    display.narrate(f"  {self.sub(event['description'])}")

                    if event.get("skill_check"):
                        sc = event["skill_check"]
                        total, shifts, dice_result = dice.skill_check(
                            self.steward.get_skill(sc["skill"]), sc["difficulty"])
                        print(f"  {dice.roll_description(dice_result, self.steward.get_skill(sc['skill']), sc['skill'])}")

                        if shifts >= 0:
                            display.success(f"  {self.sub(event['success'])}")
                            effect = event.get("success_effect", {})
                            if effect.get("mote_bonus"):
                                self.seed.feed(effect["mote_bonus"])
                            if effect.get("random_item"):
                                item = random.choice(["metal_scraps", "wire", "torn_fabric"])
                                self.steward.add_to_inventory(item)
                            if effect.get("loyalty_bonus"):
                                for nid, n in self.npcs_db.items():
                                    if n.get("recruited"):
                                        n["loyalty"] = min(10, n.get("loyalty", 0) + 1)
                        else:
                            display.warning(f"  {self.sub(event['failure'])}")
                            effect = event.get("failure_effect", {})
                            if effect.get("stress"):
                                self.steward.apply_damage(effect["stress"])
                            if effect.get("mood_penalty"):
                                for nid, n in self.npcs_db.items():
                                    if n.get("recruited") and n.get("mood") == "content":
                                        n["mood"] = "restless"
                    else:
                        display.success(f"  {self.sub(event['success'])}")
                        effect = event.get("success_effect", {})
                        if effect.get("mote_bonus"):
                            self.seed.feed(effect["mote_bonus"])
                        if effect.get("mood_bonus"):
                            for nid, n in self.npcs_db.items():
                                if n.get("recruited"):
                                    n["mood"] = "content"

        self.state["event_log"].append(f"Day {day}: The skerry endures.")
        display.display_seed(self.seed.to_dict(), name=self.seed_name)


if __name__ == "__main__":
    game = Game()
    game.start()
