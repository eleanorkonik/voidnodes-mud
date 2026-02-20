#!/usr/bin/env python3
"""Voidnodes MUD — The Skerry Chronicle.

A text-based adventure set in the space between worlds.
"""

import sys
import json
import random

from engine import parser, display, save, dice, tutorial, map_renderer, recruit, aspects
from models.character import Character, BODY_SLOTS
from models.room import Room
from models.world_seed import WorldSeed
from models.skerry import Skerry
from models.item import Item


SKIP_WORDS = {"a", "an", "the", "of", "in", "is", "it", "that", "and", "but", "with", "for", "from", "to", "by"}


def _aspect_hint_words(aspect, count=2):
    """Pick the first few meaningful words from an aspect for a SEEK hint."""
    words = [w for w in aspect.split() if w.lower() not in SKIP_WORDS]
    return " ".join(words[:count]).upper() if words else aspect.split()[0].upper()


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
        self.exploit_advantages = {}  # {aspect_name: count} — free +2 from EXPLOIT
        self.combat_boost = 0  # one-use +2 from ties
        self.combat_consequences_taken = 0  # for CONCEDE FP calculation
        self.invoked_aspects = set()  # aspects invoked this combat (once each)
        self.enemy_compel_boost = 0  # +2 from compel accept (enemy_boost effect)
        self.in_compel = False
        self.compel_data = None
        self.compel_triggered = False  # at most one compel per combat
        self.in_recruit = False
        self.recruit_state = None
        self.pending_invoke_bonus = 0  # floating +2 from invoke, consumed by next roll
        self.pending_invoke_aspect = None

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
                if current_room.id == "skerry_landing":
                    self._show_landing_pad_destinations(current_room)
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

                # Compel prompt — intercept before recruit/parser
                if self.in_compel:
                    self._handle_compel_input(raw.strip())
                    continue

                # Recruit minigame — intercept raw input before parser
                if self.in_recruit:
                    self._handle_recruit_input(raw.strip())
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
                if not self.state.get("tutorial_complete"):
                    loc_key = {"prologue": "prologue_location", "explorer": "explorer_location", "steward": "steward_location"}.get(phase)
                    if loc_key:
                        self.state["_pre_cmd_location"] = self.state.get(loc_key)

                self.handle_command(cmd, args)

                # Tutorial after-command hook — runs for ALL phases while active
                if not self.state.get("tutorial_complete"):
                    tutorial.after_command(cmd, args, self)
                    self.state.pop("_pre_cmd_location", None)

            except EOFError:
                print()
                self.save_game()
                display.seed_speak(f"Placing you in stasis, {self.current_character().name}. I'll watch over you.")
                break
            except KeyboardInterrupt:
                print()
                self.save_game()
                display.seed_speak(f"Placing you in stasis, {self.current_character().name}. I'll watch over you.")
                break

    def handle_command(self, cmd, args):
        """Route a parsed command to its handler."""
        handler = getattr(self, f"cmd_{cmd}", None)
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

    def _get_zone_aspect(self, room):
        """Get the zone-level aspect for the room's zone, if any."""
        if room.zone == "skerry":
            return self.state.get("skerry", {}).get("aspect")
        return self.state.get("zones", {}).get(room.zone, {}).get("aspect")

    def game_context(self):
        return {
            "items_db": self.items_db,
            "artifacts_db": self.artifacts_db,
            "npcs_db": self.npcs_db,
            "enemies_db": self.enemies_db,
            "agents_db": self.agents_db,
            "bonded_with_seed": self.state.get("bonded_with_seed", False),
            "artifacts_status": self.state.get("artifacts_status", {}),
            "skerry": self.state.get("skerry", {}),
            "zones": self.state.get("zones", {}),
            "quests": self.state.get("quests", {}),
        }

    # ── Universal Commands ────────────────────────────────────────

    def cmd_look(self, args):
        room = self.current_room()
        if not room:
            display.error("You're nowhere. That's concerning.")
            return

        if not args:
            display.display_room(room, self.game_context())
            if room.id == "skerry_landing":
                self._show_landing_pad_destinations(room)
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

        # Look at artifact at this location
        for art_id, art in self._artifacts_in_room(room.id):
            if target in art.get("name", "").lower() or target == art_id:
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

        # Look at room feature (interactable objects — roots, consoles, etc.)
        for feature in room.features:
            if target in feature.get("keywords", []) or target in feature.get("name", "").lower():
                display.header(feature["name"])
                display.narrate(f"  {feature['description']}")
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

        # Look at aspect (zone + room)
        zone_aspect = self._get_zone_aspect(room)
        if zone_aspect and target in zone_aspect.lower():
            print(f"  {display.aspect_text(zone_aspect)} — a zone aspect that can be invoked in rolls.")
            return
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

        # Items
        if room.items:
            for item_id in room.items:
                if item_id in self.items_db:
                    print(f"  {display.item_name(self.items_db[item_id]['name'])}")
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

        # Room features (interactable objects)
        for feature in room.features:
            print(f"  {display.aspect_text(feature['name'])}")
            has_contents = True

        if not has_contents:
            display.narrate("Nothing of interest here.")

    def _narrate_void_crossing(self, from_room, to_room):
        """Narrate the tendril FWOOM between skerry and a node."""
        seed = self.seed_name
        print()
        if to_room.zone != "skerry":
            # Leaving the skerry → outbound
            display.narrate(f"{seed}'s tendril coils around you — warm, insistent — and launches you out.")
            print()
            display.success("  FWOOM.")
            print()
            display.narrate("Void-dark. Rushing emptiness. Your stomach drops.")
            display.narrate("Then ground under your feet, and the tendril loosens.")
        else:
            # Returning to the skerry → homebound
            display.narrate(f"{seed}'s tendril tugs — homeward. You let go.")
            print()
            display.success("  FWOOM.")
            print()
            display.narrate("The skerry rises under your feet. The tendril loosens, satisfied.")
        print()

    # Zone-to-artifact mapping (each void node has one artifact)
    _ZONE_ARTIFACTS = {
        "debris_field": "stabilization_engine",
        "coral_thicket": "growth_lattice",
        "frozen_wreck": "eliok_house",
        "verdant_wreck": "bloom_catalyst",
    }

    def _get_void_crossings(self, room):
        """Find exits from this room that cross into a different zone."""
        crossings = {}
        for direction, target_id in room.exits.items():
            target = self.rooms.get(target_id)
            if target and target.zone != room.zone:
                crossings[direction] = target
        return crossings

    def _get_zone_aspect_for_zone(self, zone_id):
        """Get the aspect string for a zone by its ID."""
        if zone_id == "skerry":
            return self.state.get("skerry", {}).get("aspect", "")
        return self.state.get("zones", {}).get(zone_id, {}).get("aspect", "")

    def _is_zone_depleted(self, zone_id):
        """Check if a zone's artifact has been resolved (kept/fed/given/stored/spent)."""
        art_id = self._ZONE_ARTIFACTS.get(zone_id)
        if not art_id:
            return False
        status = self.state.get("artifacts_status", {}).get(art_id)
        return status in ("kept", "fed", "given", "stored", "spent")

    def _on_artifact_resolved(self, art_id):
        """Called when any artifact is resolved. Increments zones_cleared for zone artifacts."""
        # Only zone artifacts count as zone clears
        if art_id in self._ZONE_ARTIFACTS.values():
            self.state["zones_cleared"] = self.state.get("zones_cleared", 0) + 1
            cleared = aspects.check_mild_auto_heal(self)
            for char_key, consequence_text in cleared:
                char_name = self.state.get(f"{char_key}_name", char_key.title())
                display.success(f"  {char_name}'s mild injury ({consequence_text}) has healed with time.")

    def _record_consequence(self, char_key, severity, consequence_text):
        """Track consequence metadata for the healing system."""
        meta = self.state.setdefault("consequence_meta", {})
        meta_key = f"{char_key}_{severity}"
        meta[meta_key] = {
            "taken_at": self.state.get("zones_cleared", 0),
            "cure": aspects.get_cure_for_consequence(consequence_text),
        }

    def _consume_invoke_bonus(self):
        """Consume any pending invoke bonus. Returns the bonus value (0 if none)."""
        bonus = self.pending_invoke_bonus
        if bonus > 0:
            display.info(f"  (Invoking {display.aspect_text(self.pending_invoke_aspect)} — +{bonus})")
            self.pending_invoke_bonus = 0
            self.pending_invoke_aspect = None
        return bonus

    def _show_landing_pad_destinations(self, room):
        """Show available void destinations from the landing pad."""
        crossings = self._get_void_crossings(room)
        if not crossings:
            return
        # Deduplicate by zone
        seen_zones = set()
        destinations = []  # (zone_id, aspect, depleted)
        for direction, target in crossings.items():
            if target.zone in seen_zones or target.zone == "skerry":
                continue
            seen_zones.add(target.zone)
            aspect = self._get_zone_aspect_for_zone(target.zone)
            depleted = self._is_zone_depleted(target.zone)
            destinations.append((target.zone, aspect, depleted))
        if not destinations:
            return
        print()
        display.seed_speak("I sense nodes in the void...")
        for zone_id, aspect, depleted in destinations:
            if depleted:
                print(f"    {display.DIM}{aspect} (depleted){display.RESET}")
            else:
                hint = _aspect_hint_words(aspect)
                print(f"    {display.aspect_text(aspect)}  {display.DIM}— SEEK {hint}{display.RESET}")
        mote_cost = 1
        print(f"  {display.DIM}(Travel costs {mote_cost} mote. {self.seed_name} has {self.seed.motes}.){display.RESET}")

    def _show_sensed_nodes(self, room):
        """Have the seed announce what void nodes it senses from this room."""
        crossings = self._get_void_crossings(room)
        if not crossings:
            return
        # Deduplicate — multiple exits can lead to the same zone
        seen_zones = set()
        aspects = []
        for direction, target in crossings.items():
            if target.zone in seen_zones:
                continue
            seen_zones.add(target.zone)
            aspect = self._get_zone_aspect_for_zone(target.zone)
            if aspect:
                aspects.append(aspect)
            else:
                aspects.append(target.zone.replace("_", " ").title())
        print()
        display.seed_speak("I sense nodes in the void...")
        for aspect in aspects:
            print(f"    {display.aspect_text(aspect)}")
        print()
        display.seed_speak("SEEK an aspect to follow it.")

    def _match_zone_by_aspect(self, keywords, room):
        """Match player keywords against zone aspects of reachable crossings.

        Returns (direction, target_room) or (None, None).
        """
        crossings = self._get_void_crossings(room)
        query = " ".join(keywords).lower()

        # Strip trailing "in void" or "in the void" from query
        for suffix in (" in the void", " in void"):
            if query.endswith(suffix):
                query = query[:-len(suffix)].strip()

        if not query:
            return None, None

        # "home" and "skerry" are shortcuts for the skerry zone
        if query in ("home", "skerry", "back"):
            for direction, target in crossings.items():
                if target.zone == "skerry":
                    return direction, target
            display.error("There's no path home from here.")
            return None, None

        # Try each crossing — check if all query words appear in the zone aspect
        query_words = query.split()
        matches = []
        for direction, target in crossings.items():
            aspect = self._get_zone_aspect_for_zone(target.zone).lower()
            if not aspect:
                continue
            if all(w in aspect for w in query_words):
                matches.append((direction, target))

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # Ambiguous — show what matched
            display.error("That matches more than one node. Be more specific:")
            for d, t in matches:
                aspect = self._get_zone_aspect_for_zone(t.zone)
                print(f"    {display.aspect_text(aspect)}")
            return None, None

        return None, None

    def cmd_seek(self, args):
        """Handle SEEK <aspect keywords> [IN VOID] — cross to a void node by its aspect."""
        if not args:
            # No args — show destinations if at landing pad, else generic error
            room = self.current_room()
            if room and self._get_void_crossings(room):
                self._show_landing_pad_destinations(room)
            else:
                display.error("Seek what? SEEK <aspect> to follow a node's resonance.")
            return

        if self.in_combat:
            display.error("You're in combat! RETREAT, CONCEDE, or finish the fight.")
            return

        room = self.current_room()
        if not room:
            return

        crossings = self._get_void_crossings(room)
        if not crossings:
            display.error("There are no void crossings from here.")
            return

        direction, target_room = self._match_zone_by_aspect(args, room)
        if not direction:
            # No match found
            display.error("No node resonates with that.")
            self._show_landing_pad_destinations(room)
            return

        # Block travel to depleted zones
        if target_room.zone != "skerry" and self._is_zone_depleted(target_room.zone):
            aspect = self._get_zone_aspect_for_zone(target_room.zone)
            display.seed_speak(f"That node is spent. Nothing left to find there.")
            display.info(f"  {display.DIM}{aspect} (depleted){display.RESET}")
            return

        # Travel costs 1 mote (returning home is free)
        if target_room.zone != "skerry":
            mote_cost = 1
            if self.seed.motes < mote_cost:
                display.seed_speak(f"I don't have the strength. I need at least {mote_cost} mote to launch you.")
                return
            self.seed.spend_motes(mote_cost)
            # Explain cost on first crossing
            if not self.state.get("_seek_cost_explained"):
                self.state["_seek_cost_explained"] = True
                display.seed_speak(f"Crossing costs me a mote each time. I have {self.seed.motes} left.")

        # Move and FWOOM
        target_id = room.exits[direction]
        phase = self.state["current_phase"]
        self.state[f"{phase}_location"] = target_id
        target_room.discover()

        if phase == "explorer":
            self._move_followers(target_id)

        self._narrate_void_crossing(room, target_room)
        display.display_room(target_room, self.game_context())

        # Show destinations if we just arrived at the landing pad
        if target_room.id == "skerry_landing":
            self._show_landing_pad_destinations(target_room)

        # Check for aggressive enemies
        if self.state["current_phase"] == "explorer":
            self._on_room_enter(target_room)

    def cmd_enter(self, args):
        """Handle ENTER VOID — legacy command, redirects to SEEK."""
        if not args or args[0].lower() != "void":
            display.error("Enter what?")
            return

        room = self.current_room()
        if not room:
            return

        crossings = self._get_void_crossings(room)
        if not crossings:
            display.error("There's no void to cross here.")
            return

        # If only one crossing, allow it (convenience for returning home)
        if len(crossings) == 1:
            if self.in_combat:
                display.error("You're in combat! RETREAT, CONCEDE, or finish the fight.")
                return
            direction = list(crossings.keys())[0]
            target_room = crossings[direction]
            # Depleted check
            if target_room.zone != "skerry" and self._is_zone_depleted(target_room.zone):
                display.seed_speak("That node is spent. Nothing left to find there.")
                return
            # Mote cost (returning home is free)
            if target_room.zone != "skerry":
                if self.seed.motes < 1:
                    display.seed_speak("I don't have the strength. I need at least 1 mote to launch you.")
                    return
                self.seed.spend_motes(1)
                if not self.state.get("_seek_cost_explained"):
                    self.state["_seek_cost_explained"] = True
                    display.seed_speak(f"Crossing costs me a mote each time. I have {self.seed.motes} left.")
            target_id = room.exits[direction]
            phase = self.state["current_phase"]
            self.state[f"{phase}_location"] = target_id
            target_room.discover()
            if phase == "explorer":
                self._move_followers(target_id)
            self._narrate_void_crossing(room, target_room)
            display.display_room(target_room, self.game_context())
            if self.state["current_phase"] == "explorer":
                self._on_room_enter(target_room)
            return

        # Multiple crossings — show what the seed senses and prompt SEEK
        self._show_sensed_nodes(room)


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
            # Check locked exits — visible but blocked
            from engine.quest import check_lock_condition
            lock = room.locked_exits.get(direction) if hasattr(room, 'locked_exits') else None
            if lock:
                if not check_lock_condition(lock["condition"], self.state):
                    display.narrate(lock["locked_desc"])
                    return
                else:
                    # Condition met — treat locked exit as a real exit
                    target_id = lock.get("target")
                    if target_id:
                        room.exits[direction] = target_id
                    else:
                        display.error("That path leads nowhere.")
                        return
            else:
                available = ", ".join(d.upper() for d in room.get_exit_directions())
                display.error(f"You can't go {direction}. Exits: {available}")
                return

        target_id = room.exits[direction]
        target_room = self.rooms.get(target_id)
        if not target_room:
            display.error("That path leads nowhere. (This shouldn't happen.)")
            return

        # Cross-zone movement — requires SEEK
        if room.zone != target_room.zone:
            display.narrate("The void stretches before you.")
            if target_room.zone == "skerry":
                display.seed_speak("Are you ready to come home?")
                display.info("  SEEK HOME to return.")
            elif self._is_zone_depleted(target_room.zone):
                display.seed_speak("That node is spent. Nothing left to find there.")
            else:
                aspect = self._get_zone_aspect_for_zone(target_room.zone)
                if aspect:
                    display.seed_speak(f"I sense it — {display.aspect_text(aspect)}")
                    hint_words = _aspect_hint_words(aspect)
                    display.info(f"  SEEK {hint_words} to follow it.")
                else:
                    display.info("  Use SEEK to cross.")
            return

        # Move
        phase = self.state["current_phase"]
        if phase == "prologue":
            self.state["prologue_location"] = target_id
        else:
            self.state[f"{phase}_location"] = target_id
        target_room.discover()

        # Followers move with the explorer
        if phase == "explorer":
            self._move_followers(target_id)

        display.display_room(target_room, self.game_context())

        # Show destinations if we just arrived at the landing pad
        if target_id == "skerry_landing":
            self._show_landing_pad_destinations(target_room)

        # Contextual quest hints on room entry
        self._quest_room_hints(target_room)

        # Check for aggressive enemies
        if self.state["current_phase"] == "explorer":
            self._on_room_enter(target_room)

        # World seed flavor message occasionally
        if not self.in_combat and random.random() < 0.3:
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
                inv_counts = self._inventory_counts(self.steward)
                room = self.current_room()
                if room:
                    for item_id in room.items:
                        inv_counts[item_id] = inv_counts.get(item_id, 0) + 1
                npc_count = len(self.state.get("recruited_npcs", []))
                print(f"\n  {display.BOLD}Buildable:{display.RESET}")
                for tmpl in self.skerry.expandable:
                    reqs = tmpl.get("requires", {})
                    mats = ", ".join(f"{v}x {k.replace('_', ' ')}" for k, v in reqs.get("materials", {}).items())
                    can, _ = self.skerry.can_build(tmpl, inv_counts, npc_count, self.seed.growth_stage)
                    if can:
                        print(f"    {display.BRIGHT_WHITE}{tmpl['name']}{display.RESET} — needs: {mats}")
                    else:
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
                display.error(f"Unknown zone: '{args[0]}'. Try: skerry, debris, coral, wreck, verdant")
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

    def cmd_quests(self, args):
        from engine.quest import get_quest_display
        quests = self.state.get("quests", {})
        if not quests:
            display.info("  You haven't learned of any quests yet.")
            return

        shown = False
        for quest_id, quest_state in quests.items():
            info = get_quest_display(quest_id, quest_state)
            if not info:
                continue
            shown = True
            status = info["status"]
            if status == "complete":
                marker = f"{display.GREEN}complete{display.RESET}"
            else:
                marker = f"{display.BRIGHT_YELLOW}active{display.RESET}"
            print()
            print(f"  {display.BOLD}{info['name']}{display.RESET}  [{marker}]")
            print(f"  {display.DIM}From {info['giver']} — {info['zone']}{display.RESET}")
            print(f"  {info['summary']}")
            if info.get("hint") and status == "active":
                print()
                print(f"  {display.CYAN}{info['hint']}{display.RESET}")

        if not shown:
            display.info("  You haven't learned of any quests yet.")
        print()

    def cmd_fix(self, args):
        display.info("  To interact with objects, USE an item from your inventory on them.")
        display.info(f"  Example: {display.BOLD}USE BASIC_TOOLS{display.RESET}")

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
            all_aspects = []
            zone_aspect = self._get_zone_aspect(room)
            if zone_aspect:
                all_aspects.append(zone_aspect)
            all_aspects.extend(room.aspects)
            if all_aspects:
                aspect_list = ". ".join(display.aspect_text(a) for a in all_aspects)
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
            display.error("Give what to whom? Usage: GIVE <item> TO <name>")
            return

        raw = " ".join(args)
        parts = raw.split(" to ", 1)
        if len(parts) < 2:
            display.error("Give what to whom? Usage: GIVE <item> TO <name>")
            return

        item_part = parts[0].strip().lower()
        target_name = parts[1].strip().lower()
        room = self.current_room()
        char = self.current_character()

        if not item_part:
            display.error("Give what? Usage: GIVE <item> TO <name>")
            return

        # Find target agent in room
        agent_id, agent_data = self._find_agent_in_room(target_name, room.id)
        if not agent_data:
            # Also check NPCs
            npc_id, npc_data = self._find_entity(room.npcs, target_name, self.npcs_db)
            if not npc_data:
                display.error(f"There's nobody called '{target_name}' here to give things to.")
                return
            # For NPCs, just accept artifacts for tutorial purposes
            art_id, art = self._find_entity(char.inventory, item_part, self.artifacts_db)
            if art:
                char.remove_from_inventory(art_id)
                self.state.setdefault("artifacts_status", {})[art_id] = "given"
                self._on_artifact_resolved(art_id)
                if not self.state.get("tutorial_complete"):
                    self.state["tutorial_artifact_resolved"] = True
                display.success(f"You give the {art['name']} to {npc_data['name']}.")
                return
            display.error(f"You don't have anything called '{item_part}'.")
            return

        # Determine target character object
        target_role = agent_data.get("role")
        target_char = self.steward if target_role == "steward" else self.explorer

        # Check artifacts first, then items
        art_id, art = self._find_entity(char.inventory, item_part, self.artifacts_db)
        if art:
            char.remove_from_inventory(art_id)
            target_char.add_to_inventory(art_id)
            self.state.setdefault("artifacts_status", {})[art_id] = "given"
            self._on_artifact_resolved(art_id)
            if not self.state.get("tutorial_complete"):
                self.state["tutorial_artifact_resolved"] = True
            display.success(f"You give the {art['name']} to {agent_data['name']}.")
            return

        item_id, item = self._find_entity(char.inventory, item_part, self.items_db)
        if not item:
            display.error(f"You don't have anything called '{item_part}'.")
            return

        char.remove_from_inventory(item_id)
        target_char.add_to_inventory(item_id)
        display.success(f"You give {item['name']} to {agent_data['name']}.")

    def cmd_drop(self, args):
        if not args:
            display.error("Drop what? DROP <item> or DROP ALL.")
            return

        target = " ".join(args).lower()
        char = self.current_character()
        room = self.current_room()

        if target in ("all", "materials"):
            dropped = []
            for item_id in list(char.inventory):
                if self.items_db.get(item_id, {}).get("type") == "material":
                    char.remove_from_inventory(item_id)
                    room.add_item(item_id)
                    dropped.append(item_id)
            if dropped:
                counts = {}
                for mid in dropped:
                    name = self.items_db.get(mid, {}).get("name", mid)
                    counts[name] = counts.get(name, 0) + 1
                display.narrate("You pile your salvage on the ground.")
                for name, count in counts.items():
                    if count > 1:
                        display.info(f"  {display.item_name(name)} x{count}")
                    else:
                        display.info(f"  {display.item_name(name)}")
            else:
                display.narrate("You don't have any materials to drop.")
            return

        # Drop specific item
        item_id, item = self._find_entity(char.inventory, target, self.items_db)
        if item:
            char.remove_from_inventory(item_id)
            room.add_item(item_id)
            display.success(f"You set down the {item['name']}.")
            return

        # Check artifacts too
        art_id, art = self._find_entity(char.inventory, target, self.artifacts_db)
        if art:
            char.remove_from_inventory(art_id)
            room.add_item(art_id)
            self.state.setdefault("artifacts_status", {})[art_id] = "stored"
            self._on_artifact_resolved(art_id)
            display.success(f"You set down the {art['name']}.")
            if room.zone == "skerry":
                display.narrate("It'll be safe here until you decide what to do with it.")
            if not self.state.get("tutorial_complete"):
                self.state["tutorial_artifact_resolved"] = True
            return

        display.error(f"You don't have anything called '{target}'.")

    def _transition_to_day1(self):
        """Transition from prologue to Day 1 Explorer Phase."""
        self.state["current_phase"] = "explorer"
        day = self.state["day"]

        # Sevarik starts where Miria found him (the prologue location)
        self.state["explorer_location"] = self.state.get("prologue_location", "skerry_central")

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
        display.seed_speak("I can send you beyond the skerry — my tendril will carry you.")
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

        # Tutorial gates — can only switch at handoff steps
        if not self.state.get("tutorial_complete"):
            step = self.state.get("tutorial_step", "")
            if phase == "prologue":
                if target_role == "explorer" and step == "handoff":
                    self._switch_focus_narration("explorer")
                    return  # tutorial.after_command handles phase transition
                else:
                    display.seed_speak("Not yet. Get to know this place first.")
                    return
            elif phase == "explorer" and step != "explorer_handoff":
                steward_name = self.steward_name
                display.narrate(f"{self.seed_name} refuses to turn its attention away. There's more")
                display.narrate(f"you need to learn before it's comfortable focusing on {steward_name} again.")
                print()
                tutorial.get_current_hint(step, self.state)
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

            # Followers arrive at the skerry with the explorer
            self._followers_to_skerry()

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

            # Followers rejoin the explorer
            self._followers_rejoin_explorer()

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
        display.seed_speak(f"Placing you in stasis, {self.current_character().name}. I'll watch over you.")
        self.running = False

    def cmd_talk(self, args):
        if not args:
            display.error("Talk to whom?")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        npc_id, npc = self._find_entity(room.npcs, target, self.npcs_db)
        # Also check followers at this location
        if not npc:
            npc_id, npc = self._find_follower(target, room.id)
        if npc:
            # Check for quest-specific dialogue first
            from engine.quest import get_quest_talk, apply_quest_talk_effects
            quest_result = get_quest_talk(npc_id, npc, self.state)
            if quest_result:
                for line in quest_result["lines"]:
                    display.npc_speak(npc["name"], self._sub_dialogue(line))
                if quest_result.get("quest_started"):
                    display.info("  [Quest started: The Verdant Heart]")
                apply_quest_talk_effects(quest_result, self.state, self.rooms, self.current_character())
                return

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
            display.error("Use what? (USE <item> or USE <item> ON <target>)")
            return

        raw = " ".join(args).lower()
        char = self.current_character()
        room = self.current_room()

        # Parse USE <item> ON <target>
        item_part, use_target = raw, None
        if " on " in raw:
            parts = raw.split(" on ", 1)
            item_part, use_target = parts[0].strip(), parts[1].strip()

        # Targeted use — quest interactions (USE RESIN ON ROOTS, etc.)
        from engine.quest import handle_quest_use
        if use_target and room:
            item_id_q, item_q = self._find_entity(char.inventory, item_part, self.items_db)
            if item_id_q:
                # Lira stops you from burning her biodome if she's still living here
                if self._lira_blocks_torch(item_id_q, room):
                    return
                biodome_was_burning = self.state.get("quests", {}).get("verdant_bloom", {}).get("biodome_burning")
                handled, consumed = handle_quest_use(item_id_q, use_target, room.id, self.state, char, self.rooms)
                if handled:
                    if consumed:
                        char.remove_from_inventory(item_id_q)
                    # Lira reacts to watching her biodome burn
                    if not biodome_was_burning and self.state.get("quests", {}).get("verdant_bloom", {}).get("biodome_burning"):
                        self._lira_fire_reaction()
                    return
            if not item_id_q:
                display.error(f"You don't have '{item_part}'.")
            else:
                display.narrate(f"Using {item_q['name']} on that doesn't do anything.")
            return

        # No target — untargeted item use (artifacts, food, etc.)
        target = item_part

        # Check artifacts in inventory
        art_id, art = self._find_entity(char.inventory, target, self.artifacts_db)
        if art:
            if art_id == "bloom_catalyst":
                uses = art.get("uses_remaining", 0)
                if uses <= 0:
                    display.narrate("The crystal is spent. It crumbles to dust in your hands.")
                    char.remove_from_inventory(art_id)
                    self.state.get("artifacts_status", {})[art_id] = "spent"
                    self._on_artifact_resolved(art_id)
                    return
                art["uses_remaining"] = uses - 1
                char.add_to_inventory("preserved_food")
                char.add_to_inventory("seeds")
                remaining = uses - 1
                display.success("The Bloom Catalyst pulses. Nearby vegetation erupts into")
                display.success("flower and fruit. You gather what you can.")
                display.info(f"  Gained: preserved food, seeds. ({remaining} bloom{'s' if remaining != 1 else ''} remaining)")
                if remaining > 0:
                    words = ["Zero", "One", "Two", "Three", "Four", "Five"]
                    art["aspects"] = ["Instant Harvest", f"{words[remaining]} Bloom{'s' if remaining != 1 else ''} Remain{'s' if remaining == 1 else ''}"]
                else:
                    display.narrate("The crystal dims and crumbles to dust. Its blooms are spent.")
                    char.remove_from_inventory(art_id)
                    self.state.get("artifacts_status", {})[art_id] = "spent"
                    self._on_artifact_resolved(art_id)
                return
            elif art_id == "silver_slippers":
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
        if not args and not self.in_combat:
            display.error("Attack what?")
            return

        room = self.current_room()

        if not self.in_combat:
            target = " ".join(args).lower()
            enemy_id, enemy_data = self._find_entity(room.enemies, target, self.enemies_db)
            if not enemy_data:
                # Check if attacking Lira after she warned you
                quest = self.state.get("quests", {}).get("verdant_bloom", {})
                if target == "lira" and quest.get("lira_warned") and not quest.get("lira_defeated"):
                    lira = self.npcs_db.get("lira")
                    if lira and not lira.get("recruited"):
                        self._lira_attacks(room)
                        return  # combat started — player acts next turn
                display.error(f"There's nothing called '{target}' to attack here.")
                return
            self._start_combat(enemy_id)
        elif args:
            # Already in combat — check if re-targeting
            target = " ".join(args).lower()
            enemy_id, enemy_data = self._find_entity(room.enemies, target, self.enemies_db)
            if enemy_data:
                self.combat_target = enemy_id

        enemy_data = self.enemies_db.get(self.combat_target)
        if not enemy_data:
            return

        # Calculate bonus from pending invoke, exploit advantages, and boost
        bonus = self._consume_invoke_bonus()
        used_aspect = None
        if self.exploit_advantages:
            # Auto-consume one exploit advantage
            aspect_name = next(iter(self.exploit_advantages))
            self.exploit_advantages[aspect_name] -= 1
            if self.exploit_advantages[aspect_name] <= 0:
                del self.exploit_advantages[aspect_name]
            bonus += 2
            used_aspect = aspect_name

        if self.combat_boost > 0:
            bonus += self.combat_boost
            self.combat_boost = 0

        atk_skill_val = self.explorer.get_skill("Fight") + bonus
        def_skill_val = enemy_data["skills"].get("Fight", 1)

        atk_total, def_total, shifts, atk_dice, def_dice = dice.opposed_roll(atk_skill_val, def_skill_val)

        display.header(f"Combat: {self.explorer.name} vs {enemy_data['name']}")
        if used_aspect:
            print(f"  {display.DIM}(Exploit advantage: {display.aspect_text(used_aspect)}){display.RESET}")
        skill_label = f"Fight+{bonus}" if bonus else "Fight"
        base_fight = self.explorer.get_skill("Fight")
        print(f"  {self.explorer.name}: {dice.roll_description(atk_dice, base_fight + bonus, skill_label)}")
        print(f"  {enemy_data['name']}: {dice.roll_description(def_dice, def_skill_val, 'Fight')}")

        if shifts > 0:
            display.success(f"  You hit for {shifts} shifts!")
            if self._apply_enemy_damage(enemy_data, self.combat_target, shifts, room):
                return
        elif shifts == 0:
            display.narrate("  A draw — you gain a momentary edge.")
            self.combat_boost += 2
            display.info(f"  (Boost: +2 on your next action)")
        else:
            display.narrate(f"  You miss. {enemy_data['name']} deflects your strike.")

        # Enemy turn
        self._enemy_turn()

    def cmd_defend(self, args):
        if not self.in_combat:
            display.error("You're not in combat.")
            return

        self.defending = True
        display.narrate("You brace yourself, watching for openings. (+2 defense this exchange)")

        # Enemy turn (with the +2 defense active)
        self._enemy_turn()
        self.defending = False

    def cmd_exploit(self, args):
        """EXPLOIT <aspect> — Create an Advantage by exploiting an aspect.

        Roll Notice vs difficulty to set up a tactical advantage on the aspect.
        Success: 1 advantage. Success with style (3+): 2 advantages.
        Tie: boost (+2 one-use). Fail: wasted turn, enemy still attacks.
        """
        if not args:
            display.error("Exploit what? EXPLOIT <aspect> to create a tactical advantage.")
            return

        if not self.in_combat:
            display.error("You can only exploit aspects during combat.")
            return

        aspect_name = " ".join(args)
        enemy_data = self.enemies_db.get(self.combat_target, {})

        # Gather all available aspects
        all_aspects = []
        room = self.current_room()
        if room:
            all_aspects.extend(room.aspects)
            zone_aspect = self._get_zone_aspect(room)
            if zone_aspect:
                all_aspects.append(zone_aspect)
        all_aspects.extend(enemy_data.get("aspects", []))
        char = self.current_character()
        all_aspects.extend(char.get_all_aspects())

        # Fuzzy match
        found = None
        for a in all_aspects:
            if aspect_name.lower() in a.lower():
                found = a
                break

        if not found:
            display.error(f"No matching aspect found for '{aspect_name}'.")
            display.info("Available aspects:")
            for a in all_aspects:
                print(f"  {display.aspect_text(a)}")
            return

        # Determine difficulty: enemy aspects use enemy Notice, room aspects use flat 1
        is_enemy_aspect = found in enemy_data.get("aspects", [])
        if is_enemy_aspect:
            difficulty = enemy_data["skills"].get("Notice", 1)
        else:
            difficulty = 1

        notice_val = self.explorer.get_skill("Notice")
        total, shifts, dice_result = dice.skill_check(notice_val, difficulty)

        display.header(f"Exploit: {found}")
        diff_label = f"vs {enemy_data['name']} Notice" if is_enemy_aspect else "vs difficulty 1"
        print(f"  {self.explorer.name}: {dice.roll_description(dice_result, notice_val, 'Notice')} ({diff_label})")

        if shifts >= 3:
            # Success with style — 2 advantages
            self.exploit_advantages[found] = self.exploit_advantages.get(found, 0) + 2
            display.success(f"  Brilliant! You spot exactly how to use {display.aspect_text(found)}.")
            display.info(f"  (2 exploit advantages on {found} — free +2 each on your next attacks)")
            if not self.state.get("tutorial_complete"):
                self.state["tutorial_exploit_done"] = True
        elif shifts >= 0:
            # Success — 1 advantage
            self.exploit_advantages[found] = self.exploit_advantages.get(found, 0) + 1
            display.success(f"  You find a way to use {display.aspect_text(found)} to your advantage.")
            display.info(f"  (Exploit advantage on {found} — free +2 on your next attack)")
            if not self.state.get("tutorial_complete"):
                self.state["tutorial_exploit_done"] = True
        elif shifts == -1:
            # Tie — boost
            self.combat_boost += 2
            display.narrate(f"  Not quite — but you gain a momentary edge.")
            display.info(f"  (Boost: +2 on your next action)")
        else:
            # Fail
            display.narrate(f"  You try to exploit {display.aspect_text(found)} but can't find an opening.")

        # Enemy turn
        self._enemy_turn()

    def cmd_invoke(self, args):
        """INVOKE [aspect] [ATTACK|DEFEND|SETUP] — Spend a fate point to invoke an aspect."""
        # In combat — full combat invoke with effects
        if self.in_combat:
            self._combat_invoke(args)
            return

        # Outside combat/recruitment — floating invoke for next skill check
        self._general_invoke(args)

    def _general_invoke(self, args):
        """Invoke an aspect outside combat/recruitment. Stores a floating +2 for the next roll."""
        char = self.current_character()
        all_aspects = aspects.collect_invokable_aspects(self, context="combat")

        if not args:
            # Show available aspects
            print(f"\n{display.BOLD}{display.BRIGHT_CYAN}═══ Invoke an Aspect ═══{display.RESET}  (1 FP — you have {char.fate_points})")
            print()
            print("  Available:")
            for a, source in all_aspects:
                print(f"    {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            print()
            display.info("  INVOKE <aspect> to gain +2 on your next skill check.")
            if self.pending_invoke_bonus > 0:
                display.info(f"  (Already invoking: {display.aspect_text(self.pending_invoke_aspect)})")
            return

        raw = " ".join(args)
        found = None
        for a, source in all_aspects:
            if raw.lower() in a.lower():
                found = a
                break

        if not found:
            display.error(f"No matching aspect for '{raw}'.")
            display.info("Available aspects:")
            for a, source in all_aspects:
                print(f"  {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            return

        if not char.spend_fate_point():
            display.error("No fate points to spend!")
            return

        self.pending_invoke_bonus = 2
        self.pending_invoke_aspect = found
        if not self.state.get("tutorial_complete"):
            self.state["tutorial_invoke_done"] = True

        display.success(f"You invoke {display.aspect_text(found)} — +2 on your next action.")
        display.info(f"  (Fate Points remaining: {char.fate_points})")

    def _combat_invoke(self, args):
        """Handle INVOKE during combat — choose-your-effect system."""
        char = self.current_character()
        all_aspects = aspects.collect_invokable_aspects(self, context="combat")

        # No args — show the invoke menu
        if not args:
            self._display_invoke_menu(char, all_aspects, "combat")
            return

        # Parse args: last word might be an effect keyword
        raw = " ".join(args)
        effect = None
        for keyword in aspects.COMBAT_EFFECTS:
            if raw.upper().endswith(" " + keyword):
                effect = keyword
                raw = raw[:-(len(keyword) + 1)].strip()
                break

        # Fuzzy-match the aspect
        aspect_name = raw
        found = None
        for a, source in all_aspects:
            if aspect_name.lower() in a.lower():
                found = a
                break

        if not found:
            display.error(f"No matching aspect found for '{aspect_name}'.")
            display.info("Available aspects:")
            for a, source in all_aspects:
                if a not in self.invoked_aspects:
                    print(f"  {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            return

        # Check if already invoked this fight
        if found in self.invoked_aspects:
            display.error(f"You've already invoked {display.aspect_text(found)} this fight.")
            remaining = [(a, s) for a, s in all_aspects if a not in self.invoked_aspects]
            if remaining:
                display.info("  Still available:")
                for a, source in remaining:
                    print(f"    {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            return

        # Default effect
        if effect is None:
            effect = "ATTACK"

        # Spend fate point
        if not char.spend_fate_point():
            display.error("No fate points to spend!")
            return

        self.invoked_aspects.add(found)
        if not self.state.get("tutorial_complete"):
            self.state["tutorial_invoke_done"] = True

        display.success(f"You invoke {display.aspect_text(found)} — {aspects.COMBAT_EFFECTS[effect]['desc']}!")
        display.info(f"  (Fate Points remaining: {char.fate_points})")

        # Branch on effect
        if effect == "ATTACK":
            self._invoke_attack(found)
        elif effect == "DEFEND":
            self._invoke_defend(found)
        elif effect == "SETUP":
            self._invoke_setup(found)

    def _display_invoke_menu(self, char, all_aspects, context):
        """Show available aspects and effects for invocation."""
        effects = aspects.COMBAT_EFFECTS if context == "combat" else aspects.RECRUIT_EFFECTS

        print(f"\n{display.BOLD}{display.BRIGHT_CYAN}═══ Invoke an Aspect ═══{display.RESET}  (1 FP each — you have {char.fate_points})")
        print()

        invoked = self.invoked_aspects if context == "combat" else self.recruit_state.get("invoked_aspects", set())

        available = [(a, s) for a, s in all_aspects if a not in invoked]
        spent = [(a, s) for a, s in all_aspects if a in invoked]

        if available:
            print("  Available:")
            for a, source in available:
                print(f"    {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
        else:
            print(f"  {display.DIM}No aspects remaining to invoke.{display.RESET}")

        if spent:
            print()
            print("  Already invoked:")
            for a, source in spent:
                print(f"    {display.DIM}\u2717 {a} ({source}){display.RESET}")

        print()
        effect_parts = []
        for keyword, info in effects.items():
            effect_parts.append(f"{display.BOLD}{keyword}{display.RESET} ({info['desc']})")
        print(f"  Effects:  {'  \u00b7  '.join(effect_parts)}")
        print()
        if context == "combat":
            print(f"  {display.DIM}INVOKE <aspect> [ATTACK|DEFEND|SETUP]{display.RESET}")
        else:
            print(f"  {display.DIM}INVOKE <aspect> [PUSH|COUNTER|RESTORE]{display.RESET}")
        print()

    def _invoke_attack(self, invoked_aspect):
        """INVOKE for +2 attack — roll attack with bonus."""
        enemy_data = self.enemies_db.get(self.combat_target, {})
        if not enemy_data:
            return
        room = self.current_room()

        bonus = 2  # invoke bonus
        used_free = None
        if self.exploit_advantages:
            free_aspect = next(iter(self.exploit_advantages))
            self.exploit_advantages[free_aspect] -= 1
            if self.exploit_advantages[free_aspect] <= 0:
                del self.exploit_advantages[free_aspect]
            bonus += 2
            used_free = free_aspect

        if self.combat_boost > 0:
            bonus += self.combat_boost
            self.combat_boost = 0

        atk_skill_val = self.explorer.get_skill("Fight") + bonus
        def_skill_val = enemy_data["skills"].get("Fight", 1)

        atk_total, def_total, shifts, atk_dice, def_dice = dice.opposed_roll(atk_skill_val, def_skill_val)

        base_fight = self.explorer.get_skill("Fight")
        skill_label = f"Fight+{bonus}"
        if used_free:
            print(f"  {display.DIM}(Also using exploit advantage: {display.aspect_text(used_free)}){display.RESET}")
        print(f"  {self.explorer.name}: {dice.roll_description(atk_dice, base_fight + bonus, skill_label)}")
        print(f"  {enemy_data['name']}: {dice.roll_description(def_dice, def_skill_val, 'Fight')}")

        if shifts > 0:
            display.success(f"  Empowered strike for {shifts} shifts!")
            if self._apply_enemy_damage(enemy_data, self.combat_target, shifts, room):
                return
        elif shifts == 0:
            display.narrate("  A draw despite the invocation — you gain a momentary edge.")
            self.combat_boost += 2
            display.info(f"  (Boost: +2 on your next action)")
        else:
            display.narrate(f"  Even with the invoke, {enemy_data['name']} deflects your strike.")

        # Enemy turn
        self._enemy_turn()

    def _invoke_defend(self, invoked_aspect):
        """INVOKE for +2 defense — set defending and pass to enemy turn."""
        self.defending = True
        display.narrate(f"  You brace yourself, drawing on {display.aspect_text(invoked_aspect)}.")
        display.info(f"  (+2 defense until your next action)")
        self._enemy_turn()

    def _invoke_setup(self, invoked_aspect):
        """INVOKE SETUP — gain an exploit advantage on a random enemy aspect."""
        enemy_data = self.enemies_db.get(self.combat_target, {})
        enemy_aspects = enemy_data.get("aspects", [])
        if enemy_aspects:
            target_aspect = random.choice(enemy_aspects)
            self.exploit_advantages[target_aspect] = self.exploit_advantages.get(target_aspect, 0) + 1
            display.narrate(f"  You spot an opening in {display.aspect_text(target_aspect)}.")
            display.info(f"  (Exploit advantage gained — free +2 on your next attack)")
        else:
            # No enemy aspects — grant a generic boost instead
            self.combat_boost += 2
            display.narrate(f"  You study your opponent and find an opening.")
            display.info(f"  (Boost: +2 on your next action)")
        self._enemy_turn()

    def cmd_concede(self, args):
        """CONCEDE — Surrender combat. Gain 1 FP + 1 per consequence taken this fight."""
        if not self.in_combat:
            display.error("You're not in combat.")
            return

        enemy = self.enemies_db.get(self.combat_target, {})
        cons_taken = self.combat_consequences_taken
        fp_gain = 1 + cons_taken
        self._end_combat()

        for _ in range(fp_gain):
            self.explorer.gain_fate_point()

        display.narrate(f"You concede the fight against {enemy.get('name', 'the enemy')}.")
        display.narrate("You back away carefully, ceding ground.")
        display.success(f"+{fp_gain} Fate Point{'s' if fp_gain > 1 else ''} for conceding.")
        if cons_taken > 0:
            display.info(f"  (1 base + {cons_taken} for consequences taken)")
        display.narrate("The enemy lets you go — for now.")

    def cmd_scavenge(self, args):
        room = self.current_room()
        if room.has_enemies():
            enemy_id = room.enemies[0]
            enemy_name = self.enemies_db.get(enemy_id, {}).get("name", "something")
            display.narrate(f"You start rummaging through the debris — and the {enemy_name}")
            display.narrate("takes the opening.")
            print()
            self._start_combat(enemy_id)
            self._enemy_turn()
            return

        # Scaling difficulty: each scavenge in a room raises the DC by 1
        scavenge_counts = self.state.setdefault("scavenge_counts", {})
        times_searched = scavenge_counts.get(room.id, 0)
        difficulty = 1 + times_searched

        invoke_bonus = self._consume_invoke_bonus()
        skill_val = self.explorer.get_skill("Scavenge") + invoke_bonus
        total, shifts, dice_result = dice.skill_check(skill_val, difficulty)

        label = f"Scavenge+{invoke_bonus}" if invoke_bonus else "Scavenge"
        if times_searched > 0:
            display.info(f"  You've searched here {times_searched} time{'s' if times_searched != 1 else ''} before. (DC {difficulty})")
        print(f"  Scavenge: {dice.roll_description(dice_result, skill_val, label)} vs DC {difficulty}")

        scavenge_counts[room.id] = times_searched + 1

        if shifts >= 0:
            # Find something from the zone's scavenge pool
            zone_id = room.zone
            zone = self.state["zones"].get(zone_id, {})
            possible_loot = zone.get("scavenge_pool", ["metal_scraps", "torn_fabric", "wire"])

            found = random.choice(possible_loot)
            self.explorer.add_to_inventory(found)
            item_info = self.items_db.get(found, {})
            display.success(f"  Found: {item_info.get('name', found)}!")

            if shifts >= 3:  # Succeed with style
                bonus = random.choice(possible_loot)
                self.explorer.add_to_inventory(bonus)
                bonus_info = self.items_db.get(bonus, {})
                display.success(f"  Excellent work! Also found: {bonus_info.get('name', bonus)}!")

            if not self.state.get("tutorial_complete"):
                self.state["tutorial_scavenge_done"] = True
        else:
            display.narrate("  You search carefully but find nothing useful this time.")

    def cmd_probe(self, args):
        if not args:
            display.error("Probe what? Specify an item or object to examine.")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        # Check artifacts at this location
        for art_id, art in self._artifacts_in_room(room.id):
            if target in art.get("name", "").lower() or target == art_id:
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

        # Check inventory items
        char = self.current_character()
        inv_item_id, inv_item = self._find_entity(list(char.inventory), target, self.items_db)
        if inv_item:
            display.header(inv_item["name"])
            display.narrate(self.sub(inv_item["description"]))
            if inv_item.get("aspects"):
                for a in inv_item["aspects"]:
                    print(f"    {display.aspect_text(a)}")
            if inv_item.get("type"):
                display.info(f"  Type: {inv_item['type']}")
            if inv_item.get("mote_value"):
                display.info(f"  Mote value: {inv_item['mote_value']}")
            if inv_item.get("stat_bonuses"):
                bonuses = ", ".join(f"+{v} {k}" for k, v in inv_item["stat_bonuses"].items())
                display.info(f"  Bonuses: {bonuses}")
            return

        # Check inventory artifacts
        for art_id in char.inventory:
            art = self.artifacts_db.get(art_id)
            if art and (target in art.get("name", "").lower() or target == art_id):
                display.header(art["name"])
                display.narrate(self.sub(art["description"]))
                if art.get("aspects"):
                    for a in art["aspects"]:
                        print(f"    {display.aspect_text(a)}")
                if art.get("stat_bonuses"):
                    bonuses = ", ".join(f"+{v} {k}" for k, v in art["stat_bonuses"].items())
                    display.info(f"  Keep bonuses: {bonuses}")
                display.info(f"  Mote value: {art['mote_value']}")
                return

        # Check enemies in room
        enemy_id, enemy = self._find_entity(room.enemies, target, self.enemies_db)
        if enemy:
            display.header(enemy["name"])
            display.narrate(self.sub(enemy.get("description", "A hostile creature.")))
            if enemy.get("aspects"):
                for a in enemy["aspects"]:
                    print(f"    {display.aspect_text(a)}")
            if enemy.get("skills"):
                skills_str = ", ".join(f"{k} {v}" for k, v in enemy["skills"].items())
                display.info(f"  Skills: {skills_str}")
            return

        # Check NPCs in room + followers
        npc_pool = list(room.npcs)
        for npc_id, npc in self.npcs_db.items():
            if npc.get("following") and npc_id not in npc_pool:
                npc_pool.append(npc_id)
        npc_id, npc = self._find_entity(npc_pool, target, self.npcs_db)
        if npc:
            display.header(npc["name"])
            display.narrate(self.sub(npc.get("description", "You see nothing unusual.")))
            if npc.get("aspects"):
                for a in npc["aspects"]:
                    print(f"    {display.aspect_text(a)}")
            if npc.get("skills"):
                skills_str = ", ".join(f"{k} {v}" for k, v in npc["skills"].items())
                display.info(f"  Skills: {skills_str}")
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
            self._on_artifact_resolved(art_id)
            self._move_artifact(art_id, None, None)

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

        # Skerry-only restriction for artifacts
        if room and room.zone != "skerry":
            display.error("You need to be back at the skerry to decide what to do with artifacts.")
            return

        art_id, art = self._find_in_db(target, self.artifacts_db)
        if art:
            char = self.current_character()
            already_held = art_id in char.inventory
            status = self.state.get("artifacts_status", {}).get(art_id)
            if already_held or status == "discovered":
                if not already_held:
                    phase = self.state.get("current_phase", "explorer")
                    char_role = "explorer" if phase == "explorer" else "steward"
                    char.add_to_inventory(art_id)
                    self._move_artifact(art_id, "inventory", char_role)
                self.state.setdefault("artifacts_status", {})[art_id] = "kept"
                self._on_artifact_resolved(art_id)
                if not self.state.get("tutorial_complete"):
                    self.state["tutorial_artifact_resolved"] = True

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
            # Skerry-only restriction
            room = self.current_room()
            if room and room.zone != "skerry":
                display.error(f"You need to be near {self.seed_name} on the skerry to offer artifacts.")
                return

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
                self._on_artifact_resolved(art_id)
                self._move_artifact(art_id, None, None)
                if not self.state.get("tutorial_complete"):
                    self.state["tutorial_artifact_resolved"] = True

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

    def cmd_request(self, args):
        """REQUEST TREATMENT [FROM <name>] — treat a consequence with Lore + cure item."""
        if not args:
            display.error("Request what? Usage: REQUEST TREATMENT [FROM <name>]")
            return

        raw = " ".join(args).lower()

        # Must start with "treatment"
        if not raw.startswith("treatment"):
            display.error("Request what? Usage: REQUEST TREATMENT [FROM <name>]")
            return

        char = self.current_character()
        phase = self.state.get("current_phase", "explorer")
        char_key = "explorer" if phase == "explorer" else "steward"

        # Figure out the treater
        treater_name = None
        treater_lore = None
        remainder = raw[len("treatment"):].strip()
        if remainder.startswith("from "):
            treater_name = remainder[5:].strip()

        if treater_name:
            # Check if it's the other player character
            other_key = "steward" if char_key == "explorer" else "explorer"
            other_name = self.state.get(f"{other_key}_name", "").lower()
            if treater_name == other_name:
                other_char_data = self.state.get(other_key, {})
                treater_lore = other_char_data.get("skills", {}).get("Lore", 0)
                treater_name = self.state.get(f"{other_key}_name")
            else:
                # Check NPCs at this location
                room = self.current_room()
                npc_pool = list(room.npcs or [])
                # Also check followers
                for npc_id, npc in self.npcs_db.items():
                    if npc.get("following") and npc.get("location") == room.id and npc_id not in npc_pool:
                        npc_pool.append(npc_id)
                npc_id, npc_data = self._find_entity(npc_pool, treater_name, self.npcs_db)
                if npc_data:
                    treater_lore = npc_data.get("skills", {}).get("Lore", 0)
                    treater_name = npc_data.get("name", npc_id)
                else:
                    display.error(f"There's nobody called '{treater_name}' here to treat you.")
                    return
        else:
            # Self-treatment — use own Lore
            treater_lore = char.get_skill("Lore")
            treater_name = char.name

        # Check what consequences need treatment
        consequences = []
        for sev in ["severe", "moderate", "mild"]:
            con = char.consequences.get(sev)
            if con:
                consequences.append((sev, con))

        if not consequences:
            display.narrate(f"{char.name} has no injuries to treat.")
            return

        # Show status and find treatable consequences
        display.header("Injuries")
        treatable = []
        for sev, con in consequences:
            eligible, reason = aspects.can_treat_consequence(self, char_key, sev)
            cure = aspects.get_cure_for_consequence(con)
            cure_name = self.items_db.get(cure, {}).get("name", cure) if cure else "unknown"

            if sev == "mild":
                zones_cleared = self.state.get("zones_cleared", 0)
                meta = self.state.get("consequence_meta", {})
                taken_at = meta.get(f"{char_key}_mild", {}).get("taken_at", 0)
                remaining = max(0, aspects.ZONE_CLEARS_REQUIRED["mild"] - (zones_cleared - taken_at))
                print(f"  {display.BOLD}Mild:{display.RESET} {con}")
                display.info(f"    Heals on its own. {remaining} zone clear{'s' if remaining != 1 else ''} remaining.")
            elif eligible:
                has_cure = cure in char.inventory
                difficulty = aspects.TREATMENT_DIFFICULTY[sev]
                ladder = {0: "Mediocre", 1: "Average", 2: "Fair", 3: "Good", 4: "Great"}
                diff_label = ladder.get(difficulty, f"+{difficulty}")
                print(f"  {display.BOLD}{sev.capitalize()}:{display.RESET} {con}")
                if has_cure:
                    print(f"    Needs: {display.item_name(cure_name)} {display.BRIGHT_GREEN}(have){display.RESET} + Lore check ({diff_label})")
                    if sev == "severe":
                        display.info(f"    Treatment will downgrade to moderate, not fully heal.")
                    treatable.append((sev, con, cure, difficulty))
                else:
                    print(f"    Needs: {display.item_name(cure_name)} {display.BRIGHT_RED}(missing){display.RESET} + Lore check ({diff_label})")
            else:
                print(f"  {display.BOLD}{sev.capitalize()}:{display.RESET} {con}")
                display.info(f"    {reason}")

        if not treatable:
            if any(sev != "mild" for sev, _ in consequences):
                display.narrate("No consequences are ready for treatment right now.")
            return

        # Treat the most severe treatable consequence
        sev, con, cure, difficulty = treatable[0]

        # Consume cure item
        char.remove_from_inventory(cure)
        cure_name = self.items_db.get(cure, {}).get("name", cure)

        # Roll Lore check
        print()
        invoke_bonus = self._consume_invoke_bonus()
        effective_lore = treater_lore + invoke_bonus
        label = f"Lore+{invoke_bonus}" if invoke_bonus else "Lore"
        display.narrate(f"{treater_name} prepares the {cure_name} and gets to work...")
        atk_dice = dice.roll_4df()
        total = sum(atk_dice) + effective_lore

        print(f"  {treater_name}: {dice.roll_description(atk_dice, effective_lore, label)}")
        print(f"  Difficulty: {difficulty} ({['Mediocre', 'Average', 'Fair', 'Good', 'Great'][difficulty]})")

        shifts = total - difficulty

        if shifts >= 0:
            # Success
            if sev == "severe":
                # Downgrade to moderate
                char.consequences["severe"] = None
                char.consequences["moderate"] = con
                # Update metadata — moderate now tracks from current zone clears
                meta = self.state.setdefault("consequence_meta", {})
                meta.pop(f"{char_key}_severe", None)
                meta[f"{char_key}_moderate"] = {
                    "taken_at": self.state.get("zones_cleared", 0),
                    "cure": cure,
                }
                print()
                display.success(f"The treatment takes hold. The injury stabilizes.")
                display.narrate(f"  {con} downgraded from severe to moderate.")
                display.info(f"  Will need another round of treatment to fully heal.")
            else:
                # Full heal for moderate
                char.consequences[sev] = None
                meta = self.state.setdefault("consequence_meta", {})
                meta.pop(f"{char_key}_{sev}", None)
                print()
                display.success(f"The treatment works. {con} has healed.")
        else:
            # Failure — cure item is still consumed
            print()
            display.warning(f"The treatment doesn't take. The {cure_name} is used up, but the injury persists.")
            display.info(f"  (Failed by {abs(shifts)} — try again with better aspects or a more skilled healer.)")

    def cmd_take(self, args):
        if not args:
            display.error("Take what?")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        # GET ALL / TAKE ALL — grab all loose items (not artifacts)
        if target == "all":
            if not room.items:
                display.narrate("There's nothing here to pick up.")
                return
            picked = []
            for item_id in list(room.items):
                if item_id in self.items_db and self.items_db[item_id].get("type") != "fixture":
                    room.remove_item(item_id)
                    self.current_character().add_to_inventory(item_id)
                    picked.append(item_id)
            if not picked:
                display.narrate("There's nothing here to pick up.")
                return
            counts = {}
            for mid in picked:
                name = self.items_db.get(mid, {}).get("name", mid)
                counts[name] = counts.get(name, 0) + 1
            for name, count in counts.items():
                if count > 1:
                    display.success(f"  {display.item_name(name)} x{count}")
                else:
                    display.success(f"  {display.item_name(name)}")
            return

        # Check artifacts at this location
        for art_id, art in self._artifacts_in_room(room.id):
            if target in art.get("name", "").lower() or target == art_id:
                phase = self.state.get("current_phase", "explorer")
                char_role = "explorer" if phase == "explorer" else "steward"
                self.current_character().add_to_inventory(art_id)
                self._move_artifact(art_id, "inventory", char_role)
                display.success(f"You pick up the {art.get('name', art_id)}.")
                if not self.state.get("tutorial_complete"):
                    self.state["tutorial_artifact_found"] = True
                # Mark quest complete when bloom_catalyst is found
                if art_id == "bloom_catalyst":
                    self.state["tutorial_quest_done"] = True
                    quest = self.state.get("quests", {}).get("verdant_bloom", {})
                    if quest.get("status") == "active":
                        quest["status"] = "complete"
                return

        item_id, item = self._find_entity(list(room.items), target, self.items_db)
        if item:
            if item.get("type") == "fixture":
                display.narrate(f"The {item.get('name', item_id)} is built into the room. Try PROBE to examine it, or USE an item on it.")
                return
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

        # Check fate point cost for retries
        attempts = npc.get("recruit_attempts", 0)
        if attempts > 0:
            if not self.explorer.spend_fate_point():
                display.error(f"You need 1 fate point to try recruiting {npc['name']} again. (You have {self.explorer.fate_points} FP.)")
                return
            display.info(f"  Spent 1 fate point to retry. (Fate Points remaining: {self.explorer.fate_points})")

        # FATE roll — sets puzzle difficulty
        invoke_bonus = self._consume_invoke_bonus()
        rapport_val = self.explorer.get_skill("Rapport") + invoke_bonus
        rapport_label = f"Rapport+{invoke_bonus}" if invoke_bonus else "Rapport"
        total, shifts, dice_result = dice.skill_check(rapport_val, dc)
        print(f"  Rapport check: {dice.roll_description(dice_result, rapport_val, rapport_label)}")
        print(f"  DC: +{dc}")
        print(f"  Shifts: {shifts:+d}")

        # Look up puzzle parameters
        grid_size, num_colors, base_threshold = recruit.RECRUIT_DIFFICULTIES.get(dc, (6, 3, 20))
        threshold = recruit.calculate_threshold(base_threshold, shifts, grid_size)

        if shifts >= 0:
            display.success(f"  Your pitch is strong. Threshold: {threshold} steps.")
        elif shifts >= -2:
            display.narrate(f"  A lukewarm start. Threshold: {threshold} steps.")
        else:
            display.warning(f"  Tough crowd. Threshold: {threshold} steps.")
        print()

        # Show NPC greeting for context
        greeting = npc.get("dialogue", {}).get("greeting", "")
        if greeting:
            display.npc_speak(npc["name"], self._sub_dialogue(greeting))
            print()

        # Generate board and start minigame
        origin_zone = room.zone if room else None
        state = recruit.create_recruit_state(npc_id, npc, grid_size, num_colors, threshold)
        state["origin_zone"] = origin_zone
        self.recruit_state = state
        self.in_recruit = True

        seed_hex = f"{state['seed']:06X}"
        display.info(f"  Conversation variant: {seed_hex}")
        print()

        # Show initial board
        recruit.display_board(state, npc["name"])
        flavor = recruit.get_npc_flavor(state, state["score"] / threshold)
        if flavor:
            display.narrate(f"  {flavor}")

        # Tutorial hint: INVOKE works in recruitment too
        if not self.state.get("tutorial_complete") and not self.state.get("_recruit_invoke_hint"):
            self.state["_recruit_invoke_hint"] = True
            print()
            display.seed_speak("Your aspects have power here too.")
            display.seed_speak("INVOKE <aspect> to tip the conversation — PUSH lowers")
            display.seed_speak("the threshold, COUNTER resets a fading topic, RESTORE")
            display.seed_speak("reopens closed lines of argument.")
            display.seed_speak("Type INVOKE with no arguments to see your options.")

        print()

    def _handle_recruit_input(self, raw):
        """Handle player input during the recruit minigame."""
        state = self.recruit_state
        npc_name = state["npc_name"]
        npc = state["npc_data"]

        # Empty input — redisplay
        if not raw:
            recruit.display_board(state, npc_name)
            flavor = recruit.get_npc_flavor(state, state["score"] / state["threshold"])
            if flavor:
                display.narrate(f"  {flavor}")
            return

        cmd = raw.lower().strip()

        # Help
        if cmd in ("help", "?"):
            recruit.display_help_text()
            return

        # Quit/abandon
        if cmd in ("quit", "abandon"):
            self._resolve_recruit(won=False)
            return

        # Invoke aspect
        if cmd.startswith("invoke "):
            self._recruit_invoke(cmd[7:].strip(), state, npc_name)
            return
        if cmd == "invoke":
            char = self.current_character()
            all_aspects = aspects.collect_invokable_aspects(self, context="recruit")
            self._display_invoke_menu(char, all_aspects, "recruit")
            return

        # Parse direction
        direction_map = {
            "w": "WHEEDLE", "wheedle": "WHEEDLE",
            "a": "APPEAL", "appeal": "APPEAL",
            "s": "SUGGEST", "suggest": "SUGGEST",
            "d": "DESCRIBE", "describe": "DESCRIBE",
        }
        direction = direction_map.get(cmd)
        if not direction:
            display.error("Type a tactic (W/A/S/D), INVOKE <aspect>, QUIT, or HELP.")
            return

        # Apply move
        success, messages = recruit.apply_move(state, direction)
        if not success:
            for msg in messages:
                display.error(msg)
            return

        # Show messages (flavor, warnings, eliminations)
        for msg in messages:
            display.narrate(f"  {msg}")

        # Threshold crossed — notify once, but keep going
        if state["score"] >= state["threshold"] and not state.get("threshold_reached"):
            state["threshold_reached"] = True
            print()
            display.success(f"  {npc_name} is convinced! But the conversation is flowing — keep going for bonuses.")

        # Check game over (no valid moves)
        if not recruit.has_valid_moves(state):
            print()
            won = state["score"] >= state["threshold"]
            if won:
                over = state["score"] - state["threshold"]
                display.success(f"  Conversation complete. {state['score']}/{state['threshold']} steps (+{over} over par).")
            else:
                display.warning(f"  No more moves. You reached {state['score']}/{state['threshold']} steps.")
            self._resolve_recruit(won=won)
            return

        # Redisplay board
        recruit.display_board(state, npc_name)
        flavor = recruit.get_npc_flavor(state, state["score"] / state["threshold"])
        if flavor:
            display.narrate(f"  {flavor}")

    def _recruit_invoke(self, raw_query, state, npc_name):
        """INVOKE an aspect during recruitment — choose effect (PUSH/COUNTER/RESTORE)."""
        char = self.current_character()

        # Initialize per-aspect tracking if not present
        if "invoked_aspects" not in state:
            state["invoked_aspects"] = set()

        all_aspects = aspects.collect_invokable_aspects(self, context="recruit")

        # Parse effect keyword from end of args
        effect = None
        query = raw_query
        for keyword in aspects.RECRUIT_EFFECTS:
            if query.upper().endswith(" " + keyword):
                effect = keyword
                query = query[:-(len(keyword) + 1)].strip()
                break

        # Fuzzy-match the aspect
        found = None
        found_source = None
        for a, source in all_aspects:
            if query.lower() in a.lower():
                found = a
                found_source = source
                break

        if not found:
            display.error(f"No matching aspect for '{query}'.")
            display.info("  Available aspects:")
            for a, source in all_aspects:
                if a not in state["invoked_aspects"]:
                    print(f"    {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            return

        # Check if already invoked this attempt
        if found in state["invoked_aspects"]:
            display.error(f"You've already invoked {display.aspect_text(found)} this conversation.")
            remaining = [(a, s) for a, s in all_aspects if a not in state["invoked_aspects"]]
            if remaining:
                display.info("  Still available:")
                for a, source in remaining:
                    print(f"    {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
            return

        # Default effect
        if effect is None:
            effect = "PUSH"

        # Spend fate point
        if not char.spend_fate_point():
            display.error(f"No fate points to spend! (You have {char.fate_points} FP.)")
            return

        state["invoked_aspects"].add(found)
        if not self.state.get("tutorial_complete"):
            self.state["tutorial_invoke_done"] = True

        source_type = "seed" if found_source == self.seed_name else None
        flavor = aspects.get_recruit_invoke_flavor(found, found_source, npc_name, source_type=source_type)
        display.narrate(f"  {flavor}")
        display.info(f"  (Fate Points remaining: {char.fate_points})")

        # Branch on effect
        if effect == "PUSH":
            old_threshold = state["threshold"]
            total_tiles = state["grid_size"] ** 2
            floor = int(total_tiles * 0.4)
            state["threshold"] = max(floor, old_threshold - 4)
            display.info(f"  Threshold: {old_threshold} → {state['threshold']}")
        elif effect == "COUNTER":
            recruit.reset_lowest_counter(state)
        elif effect == "RESTORE":
            recruit.restore_tiles(state, count=3)

        # Check if threshold now crossed
        if state["score"] >= state["threshold"] and not state.get("threshold_reached"):
            state["threshold_reached"] = True
            print()
            display.success(f"  {npc_name} is convinced! But the conversation is flowing — keep going for bonuses.")

        recruit.display_board(state, npc_name)

    def _resolve_recruit(self, won):
        """Handle the end of a recruit minigame."""
        state = self.recruit_state
        npc_id = state["npc_id"]
        npc = state["npc_data"]
        npc_name = state["npc_name"]
        seed_hex = f"{state['seed']:06X}"

        print()
        if won:
            npc["recruited"] = True
            npc["following"] = True
            npc["location"] = self.state.get("explorer_location", "skerry_central")
            self.state.setdefault("recruited_npcs", []).append(npc_id)

            room = self.current_room()
            if room:
                room.remove_npc(npc_id)

            display.success(self._sub_dialogue(npc["dialogue"].get("recruit_success", f"{npc_name} joins you!")))
            display.info(f"  {npc_name} falls into step behind you.")

            # Bonus tiers for going over par
            over = max(0, state["score"] - state["threshold"])
            bonus_tiers = over // 5
            base_loyalty = 3
            # Zone the NPC knows about (from where they were when recruited)
            npc_zone = state.get("origin_zone")

            if bonus_tiers >= 1:
                # Tier 1: extra loyalty
                base_loyalty += 2
                display.success(f"  Bonus: {npc_name} is impressed. (+2 loyalty)")

            if bonus_tiers >= 2:
                # Tier 2: artifact hint from what they've seen in their zone
                hint = self._get_artifact_hint(npc_zone)
                if hint:
                    print()
                    display.npc_speak(npc_name, hint)
                else:
                    # Already found the artifact — extra loyalty instead
                    base_loyalty += 2
                    display.success(f"  Bonus: {npc_name} shares everything they know. (+2 loyalty)")

            # Future: tier 2+ could also grant quests (e.g. NPC asks you to
            # retrieve something from their zone, escort them somewhere, or
            # investigate a mystery they noticed). Hook point for quest system.

            if bonus_tiers >= 3:
                # Tier 3: exceptional rapport — happy mood + high loyalty
                base_loyalty = max(base_loyalty, 7)
                npc["mood"] = "happy"
                display.success(f"  Bonus: A perfect conversation. {npc_name} is genuinely fired up.")

            npc["loyalty"] = base_loyalty
            display.info(f"  Score: {state['score']}/{state['threshold']} (+{over} over par, variant: {seed_hex})")

            self.state["event_log"].append(
                f"Day {self.state['day']}: Recruited {npc_name} (+{over} over par, variant: {seed_hex.lower()})"
            )

            if not self.state.get("tutorial_complete"):
                self.state["tutorial_recruit_done"] = True
        else:
            npc["recruit_attempts"] = npc.get("recruit_attempts", 0) + 1
            display.narrate(self._sub_dialogue(npc["dialogue"].get("recruit_fail", f"{npc_name} isn't convinced yet.")))
            display.info(f"  Score: {state['score']}/{state['threshold']} (variant: {seed_hex})")
            display.info(f"  You can try again (costs 1 fate point).")

        self.in_recruit = False
        self.recruit_state = None

    def _locate_artifact(self, art_id):
        """Resolve an artifact's location to (loc_type, zone, room_or_holder).

        Returns (None, None, None) if the artifact has no location (consumed).
        """
        art = self.artifacts_db.get(art_id)
        if not art:
            return None, None, None
        loc = art.get("location")
        if not loc:
            return None, None, None

        loc_type = loc.get("type")
        loc_id = loc.get("id")

        if loc_type == "room":
            room = self.rooms.get(loc_id)
            if room:
                return "room", room.zone, room
            return "room", None, None
        elif loc_type == "inventory":
            # loc_id is "explorer" or "steward"
            char_loc = self.state.get(f"{loc_id}_location")
            room = self.rooms.get(char_loc) if char_loc else None
            zone = room.zone if room else "skerry"
            return "inventory", zone, loc_id
        elif loc_type == "npc":
            npc = self.npcs_db.get(loc_id)
            npc_loc = npc.get("location") if npc else None
            room = self.rooms.get(npc_loc) if npc_loc else None
            zone = room.zone if room else None
            return "npc", zone, loc_id
        return None, None, None

    def _move_artifact(self, art_id, loc_type, loc_id):
        """Move an artifact to a new location. Single point of control for all artifact movement.

        loc_type: "room", "inventory", "npc", or None (consumed/removed)
        loc_id: room id, "explorer"/"steward", npc id, or None
        """
        art = self.artifacts_db.get(art_id)
        if not art:
            return
        if loc_type is None:
            art["location"] = None
        else:
            art["location"] = {"type": loc_type, "id": loc_id}

    def _artifacts_in_room(self, room_id):
        """Find all unresolved artifacts whose location is a specific room."""
        results = []
        for art_id, art in self.artifacts_db.items():
            loc = art.get("location")
            if not loc:
                continue
            if loc.get("type") == "room" and loc.get("id") == room_id:
                status = self.state.get("artifacts_status", {}).get(art_id)
                if status not in ("kept", "fed", "given"):
                    results.append((art_id, art))
        return results

    def _get_artifact_hint(self, zone):
        """Compose a dynamic hint about an unresolved artifact in this zone.

        Resolves artifact location at runtime and combines room/holder context
        with the artifact's hint_sensory field.
        """
        if not zone:
            return None
        for art_id, art in self.artifacts_db.items():
            status = self.state.get("artifacts_status", {}).get(art_id)
            if status in ("kept", "fed", "given"):
                continue
            loc_type, art_zone, context = self._locate_artifact(art_id)
            if art_zone != zone:
                continue
            sensory = art.get("hint_sensory")
            if not sensory:
                continue
            # Compose hint based on where the artifact actually is
            if loc_type == "room" and context:
                room_name = context.name if hasattr(context, 'name') else str(context)
                prefix = "" if room_name.lower().startswith("the ") else "the "
                return f"In {prefix}{room_name} — I noticed {sensory}."
            elif loc_type == "npc":
                npc = self.npcs_db.get(context, {})
                npc_name = npc.get("name", context)
                return f"Someone called {npc_name} has {sensory}."
            elif loc_type == "inventory":
                return f"I saw {sensory} — but someone already took it."
        return None

    def _move_followers(self, target_room_id):
        """Move all following NPCs to the explorer's new location."""
        for npc_id, npc in self.npcs_db.items():
            if npc.get("following"):
                npc["location"] = target_room_id

    def _followers_to_skerry(self):
        """Move all followers to the skerry when the explorer comes home."""
        for npc_id, npc in self.npcs_db.items():
            if npc.get("following"):
                npc["following"] = False
                npc["location"] = "skerry_central"
                skerry_central = self.rooms.get("skerry_central")
                if skerry_central and npc_id not in skerry_central.npcs:
                    skerry_central.add_npc(npc_id)

    def _followers_rejoin_explorer(self):
        """Followers leave the skerry and rejoin the explorer."""
        explorer_loc = self.state.get("explorer_location", "skerry_central")
        for npc_id, npc in self.npcs_db.items():
            if npc.get("recruited") and npc_id != "sevarik":
                npc["following"] = True
                npc["location"] = explorer_loc
                # Remove from skerry room
                skerry_central = self.rooms.get("skerry_central")
                if skerry_central and npc_id in skerry_central.npcs:
                    skerry_central.remove_npc(npc_id)

    def cmd_retreat(self, args):
        if self.in_combat:
            display.warning(f"Emergency retreat! {self.seed_name} pulls you back to safety.")
            self._seed_extraction()
        else:
            # FWOOM back to skerry
            from_room = self.current_room()
            to_room = self.rooms.get("skerry_landing")
            self.state["explorer_location"] = "skerry_landing"
            self._move_followers("skerry_landing")
            if from_room and to_room and from_room.zone != "skerry":
                self._narrate_void_crossing(from_room, to_room)
            display.display_room(to_room, self.game_context())

    def cmd_settle(self, args):
        """SETTLE <npc> — settle a following NPC on the skerry."""
        if not args:
            display.error("Settle who? SETTLE <name>.")
            return
        target = " ".join(args).lower()
        room = self.current_room()
        if not room or room.zone != "skerry":
            display.error("You can only settle people on the skerry.")
            return

        npc_id, npc = self._find_in_db(target, self.npcs_db)
        if not npc or not npc.get("recruited"):
            display.error(f"No recruited companion named '{target}'.")
            return
        if not npc.get("following"):
            display.narrate(f"{npc['name']} is already settled here.")
            return

        npc["following"] = False
        npc["location"] = "skerry_central"
        skerry_central = self.rooms.get("skerry_central")
        if skerry_central and npc_id not in skerry_central.npcs:
            skerry_central.add_npc(npc_id)
        display.success(f"{npc['name']} settles in on the skerry.")
        display.narrate(f"{npc['name']} looks around, taking it in. For now, the clearing will do.")
        self.state["tutorial_settle_done"] = True

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

        # Check materials — inventory + room items
        char = self.current_character()
        room = self.current_room()
        inv_counts = self._inventory_counts(char)
        # Also count materials in the room
        if room:
            for item_id in room.items:
                inv_counts[item_id] = inv_counts.get(item_id, 0) + 1

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
        invoke_bonus = self._consume_invoke_bonus()
        skill_val = char.get_skill(skill_name) + invoke_bonus
        label = f"{skill_name}+{invoke_bonus}" if invoke_bonus else skill_name
        total, shifts, dice_result = dice.skill_check(skill_val, dc)
        print(f"  {label}: {dice.roll_description(dice_result, skill_val, label)}")
        print(f"  DC: {dc:+d}")

        if shifts >= 0:
            # Consume materials — take from room first, then inventory
            for mat, needed in recipe["materials"].items():
                for _ in range(needed):
                    if room and mat in room.items:
                        room.remove_item(mat)
                    else:
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

        # Count available materials (inventory + room)
        char = self.current_character()
        room = self.current_room()
        available = self._inventory_counts(char)
        if room:
            for item_id in room.items:
                available[item_id] = available.get(item_id, 0) + 1

        for rid in discovered:
            recipe = self.recipes_db.get(rid, {})
            mats = ", ".join(f"{v}x {self.items_db.get(k, {}).get('name', k)}"
                           for k, v in recipe.get("materials", {}).items())
            result_name = self.items_db.get(recipe.get("result", ""), {}).get("name", recipe.get("result", "?"))
            can_craft = all(available.get(mat, 0) >= needed
                          for mat, needed in recipe.get("materials", {}).items())
            if can_craft:
                print(f"  {display.BRIGHT_WHITE}{display.BOLD}{recipe.get('name', rid)}{display.RESET}: {mats} → {result_name} (DC +{recipe.get('difficulty', 0)})")
            else:
                print(f"  {display.DIM}{recipe.get('name', rid)}: {mats} → {result_name} (DC +{recipe.get('difficulty', 0)}){display.RESET}")

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
            room = self.current_room()
            if room:
                for item_id in room.items:
                    inv_counts[item_id] = inv_counts.get(item_id, 0) + 1

            missing = []
            for mat, count in needed.items():
                if inv_counts.get(mat, 0) < count:
                    missing.append(f"{count}x {self.items_db.get(mat, {}).get('name', mat)}")

            if missing:
                display.error(f"Need: {', '.join(missing)} to build a {label}.")
                return

            for mat, count in needed.items():
                for _ in range(count):
                    if room and mat in room.items:
                        room.remove_item(mat)
                    else:
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
                room = self.current_room()
                if room:
                    for item_id in room.items:
                        inv_counts[item_id] = inv_counts.get(item_id, 0) + 1

                npc_count = len(self.state.get("recruited_npcs", []))
                can, reason = self.skerry.can_build(tmpl, inv_counts, npc_count, self.seed.growth_stage)

                if not can:
                    display.error(f"Can't build {tmpl['name']}: {reason}")
                    return

                # Consume materials — take from room first, then inventory
                for mat, count in tmpl.get("requires", {}).get("materials", {}).items():
                    for _ in range(count):
                        if room and mat in room.items:
                            room.remove_item(mat)
                        else:
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
            display.error("Usage: ASSIGN <npc> <task>  (tasks: salvage, building, gardening, guarding, crafting)")
            return

        npc_target = args[0].lower()
        task = args[1].lower()
        valid_tasks = ["salvage", "building", "gardening", "guarding", "crafting", "idle"]

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
                              "restless": display.YELLOW, "grim": display.YELLOW,
                              "unhappy": display.RED, "angry": display.BRIGHT_RED,
                              "crisis": display.BRIGHT_RED}
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

    def _find_follower(self, target, room_id):
        """Find a following NPC at the given location by name. Returns (id, data) or (None, None)."""
        for npc_id, npc in self.npcs_db.items():
            if npc.get("following") and npc.get("location") == room_id:
                if target in npc.get("name", "").lower() or target == npc_id:
                    return npc_id, npc
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

    def _start_combat(self, enemy_id):
        """Initialize combat state for a new encounter."""
        self.in_combat = True
        self.combat_target = enemy_id
        self.defending = False
        self.exploit_advantages = {}
        self.combat_boost = 0
        self.combat_consequences_taken = 0
        self.invoked_aspects = set()
        self.enemy_compel_boost = 0
        self.compel_triggered = False
        self.in_compel = False
        self.compel_data = None

    def _end_combat(self):
        """Clean up after combat ends (victory, concede, or extraction)."""
        self.in_combat = False
        self.combat_target = None
        self.defending = False
        self.exploit_advantages = {}
        self.combat_boost = 0
        self.combat_consequences_taken = 0
        self.invoked_aspects = set()
        self.enemy_compel_boost = 0
        self.compel_triggered = False
        self.in_compel = False
        self.compel_data = None
        self.explorer.clear_stress()

    def _enemy_turn(self):
        """Enemy takes an independent attack action."""
        if not self.in_combat or not self.combat_target:
            return

        enemy_data = self.enemies_db.get(self.combat_target)
        if not enemy_data:
            return

        # Enemy attacks with Fight vs player Fight (+2 if defending)
        enemy_fight = enemy_data["skills"].get("Fight", 1)
        # Apply compel boost if enemy earned one
        if self.enemy_compel_boost > 0:
            enemy_fight += self.enemy_compel_boost
            self.enemy_compel_boost = 0
        player_fight = self.explorer.get_skill("Fight")
        defend_bonus = 2 if self.defending else 0
        player_defense = player_fight + defend_bonus

        atk_total, def_total, shifts, atk_dice, def_dice = dice.opposed_roll(enemy_fight, player_defense)

        print()
        defense_label = f"Fight+2" if self.defending else "Fight"
        print(f"  {display.DIM}{enemy_data['name']} strikes back!{display.RESET}")
        print(f"  {enemy_data['name']}: {dice.roll_description(atk_dice, enemy_fight, 'Fight')}")
        print(f"  {self.explorer.name}: {dice.roll_description(def_dice, player_defense, defense_label)}")

        if shifts > 0:
            display.warning(f"  {enemy_data['name']} hits you for {shifts} shifts!")
            taken_out = self.explorer.apply_damage(shifts)
            if taken_out:
                display.error(f"\n  ═══ {self.explorer.name.upper()} IS TAKEN OUT! ═══")
                display.narrate(f"  {self.seed_name} reaches across the void...")
                self._seed_extraction()
                return
            # Track consequences for concede calculation
            for sev in ["mild", "moderate", "severe"]:
                if self.explorer.consequences.get(sev) == "Pending":
                    self.combat_consequences_taken += 1
                    # Name the consequence based on enemy
                    con_text = f"Wounded by {enemy_data['name']}"
                    self.explorer.consequences[sev] = con_text
                    self._record_consequence("explorer", sev, con_text)
            # Show current stress
            stress_str = "".join("[X]" if s else "[ ]" for s in self.explorer.stress)
            display.info(f"  Stress: {stress_str}")
        elif shifts == 0:
            display.narrate(f"  {enemy_data['name']} lunges but you deflect it perfectly.")
        else:
            display.narrate(f"  {enemy_data['name']} swings wide. You sidestep easily.")

        # Reset defending after enemy attack resolves
        self.defending = False

        # Check for compel after enemy turn
        self._check_compel()

    def _check_compel(self):
        """Maybe trigger a compel after an enemy turn. At most once per combat."""
        if self.compel_triggered or not self.in_combat:
            return
        if random.random() >= 0.25:
            return
        compel = aspects.check_compel(self)
        if not compel:
            return
        self.compel_triggered = True
        self._present_compel(compel)

    def _present_compel(self, compel, environmental=False):
        """Display a compel prompt to the player."""
        char = self.current_character()
        self.in_compel = True
        self.compel_data = compel
        self.compel_data["_environmental"] = environmental
        print()
        if environmental:
            print(f"{display.BOLD}{display.BRIGHT_RED}═══ Hazard ═══{display.RESET}")
            print(f"  {display.aspect_text(compel['aspect'])} —")
        else:
            print(f"{display.BOLD}{display.BRIGHT_YELLOW}═══ Compel ═══{display.RESET}")
            print(f"  Your {display.aspect_text(compel['aspect'])} —")
        print(f"  {compel['text']}")
        print()
        if environmental:
            print(f"  {display.BRIGHT_GREEN}ACCEPT{display.RESET}: Push through. Take {compel.get('stress', 1)} stress.")
            if char.fate_points > 0:
                print(f"  {display.BRIGHT_RED}REFUSE{display.RESET}: Spend 1 FP to find a safer path. (You have {char.fate_points} FP)")
            else:
                print(f"  {display.DIM}REFUSE: Not available — no fate points.{display.RESET}")
        else:
            print(f"  {display.BRIGHT_GREEN}ACCEPT{display.RESET}: Suffer the effect. Gain 1 FP.")
            if char.fate_points > 0:
                print(f"  {display.BRIGHT_RED}REFUSE{display.RESET}: Spend 1 FP to resist. (You have {char.fate_points} FP)")
            else:
                print(f"  {display.DIM}REFUSE: Not available — no fate points to resist.{display.RESET}")
        print()

    def _handle_compel_input(self, raw):
        """Handle ACCEPT/REFUSE input during a compel."""
        cmd = raw.lower().strip()
        char = self.current_character()
        environmental = self.compel_data.get("_environmental", False)

        if cmd in ("accept", "a", "yes"):
            self.in_compel = False
            compel = self.compel_data
            self.compel_data = None

            if environmental:
                # Environmental: take stress, no FP gain
                display.narrate(compel["accept_text"])
                stress_amount = compel.get("stress", 1)
                taken_out = char.apply_damage(stress_amount)
                stress_str = "".join("[X]" if s else "[ ]" for s in char.stress)
                display.info(f"  ({stress_amount} stress — {stress_str})")
                if taken_out:
                    display.error(f"\n  ═══ {self.explorer.name.upper()} IS TAKEN OUT! ═══")
                    display.narrate(f"  {self.seed_name} reaches across the void...")
                    self._seed_extraction()
                    return
            else:
                # Character compel: suffer effect, gain FP
                effect = compel["accept_effect"]
                messages = aspects.resolve_compel_accept(self, compel)
                for msg in messages:
                    if msg == "TAKEN_OUT":
                        display.error(f"\n  ═══ {self.explorer.name.upper()} IS TAKEN OUT! ═══")
                        display.narrate(f"  {self.seed_name} reaches across the void...")
                        self._seed_extraction()
                        return
                    else:
                        display.narrate(msg)
                # Lose turn — enemy gets a free attack
                if effect == "lose_turn":
                    self._enemy_turn()

        elif cmd in ("refuse", "r", "no"):
            if char.fate_points <= 0:
                display.error("You can't refuse — no fate points.")
                display.info("  Type ACCEPT.")
                return

            self.in_compel = False
            compel = self.compel_data
            self.compel_data = None

            if environmental:
                # Environmental: spend FP, find a safer path
                char.spend_fate_point()
                display.narrate("You spot a safer route and duck through, avoiding the worst of it.")
                display.info(f"  (-1 Fate Point — you now have {char.fate_points})")
            else:
                messages = aspects.resolve_compel_refuse(self, compel)
                for msg in messages:
                    display.narrate(msg)

        else:
            display.error("Type ACCEPT or REFUSE.")

    def _quest_room_hints(self, room):
        """Lira gives contextual advice at quest locations if she's following."""
        lira = self.npcs_db.get("lira")
        if not lira or not lira.get("following"):
            return
        quest = self.state.get("quests", {}).get("verdant_bloom", {})
        if quest.get("status") != "active":
            return

        inv = self.explorer.inventory

        if room.id == "vw_root_wall" and not quest.get("roots_cleared"):
            print()
            if not quest.get("roots_weakened"):
                if "resin" in inv:
                    print(f"  {display.npc_name('Lira')}: \"Those roots are too damp to burn. But resin's")
                    print(f"  flammable — coat them and a torch would catch. USE RESIN ON ROOTS.\"")
                elif "basic_tools" in inv:
                    print(f"  {display.npc_name('Lira')}: \"There's a Growth Controller west of here.")
                    print(f"  Go WEST and USE BASIC TOOLS ON CONSOLE.\"")
                else:
                    print(f"  {display.npc_name('Lira')}: \"We need to get past these roots. The Growth")
                    print(f"  Controller is west of here — GO WEST and USE BASIC TOOLS ON CONSOLE.")
                    print(f"  Or coat these roots with resin — USE RESIN ON ROOTS — and burn through.\"")
            else:
                # Roots weakened, need fire
                if "torch" in inv:
                    print(f"  {display.npc_name('Lira')}: \"The roots are coated — they'll burn now.")
                    print(f"  USE TORCH ON ROOTS to burn through.\" She hesitates.")
                    print(f"  {display.npc_name('Lira')}: \"Be ready to move fast.\"")
                else:
                    print(f"  {display.npc_name('Lira')}: \"The resin's on — they'll catch now, but we need fire.")
                    print(f"  We need a torch. CRAFT TORCH if you have luminous moss and wire.\"")

        elif room.id == "vw_control" and not quest.get("roots_cleared"):
            if "basic_tools" in inv:
                print()
                print(f"  {display.npc_name('Lira')}: \"This is the Growth Controller. USE BASIC TOOLS ON CONSOLE")
                print(f"  — the logic board might still work.\"")

    def _lira_blocks_torch(self, item_id, room):
        """Lira stops you from torching her biodome if she hasn't been recruited.

        First time: warning. Second time: she attacks.
        """
        if item_id != "torch" or room.id != "vw_root_wall":
            return False
        quest = self.state.get("quests", {}).get("verdant_bloom", {})
        if not quest.get("roots_weakened") or quest.get("roots_cleared"):
            return False
        lira = self.npcs_db.get("lira")
        if not lira or lira.get("recruited"):
            return False
        if quest.get("lira_defeated"):
            return False

        if not quest.get("lira_warned"):
            # First attempt — she confronts you
            quest["lira_warned"] = True
            print()
            display.narrate("You raise the torch toward the resin-coated roots —")
            print()
            display.narrate("A hand grabs your wrist. Hard.")
            print()
            print(f"  {display.npc_name('Lira')}: \"What are you DOING?\"")
            print()
            print(f"  {display.npc_name('Lira')}: \"I live here. This is my home. You set that fire")
            print(f"  {display.npc_name('Lira')}: and everything in this biodome burns — including me.\"")
            print()
            display.narrate("She stands between you and the roots.")
            print()
            print(f"  {display.npc_name('Lira')}: \"Use the Growth Controller. Or take me with you first.\"")
            return True
        else:
            # Second attempt — she attacks
            self._lira_attacks(room)
            return True

    def _lira_attacks(self, room):
        """Lira attacks you to defend her biodome."""
        print()
        display.narrate("You raise the torch again. Lira's eyes go wide.")
        print()
        print(f"  {display.npc_name('Lira')}: \"No!\"")
        print()
        display.narrate("She rips a thorny vine from the wall and swings at you.")
        print()
        # Set up Lira as a temporary enemy
        lira_enemy = {
            "id": "lira_hostile",
            "name": "Lira",
            "aspects": ["Botanist Without a Ship", "Knows Every Root by Name"],
            "skills": {"Fight": 1, "Notice": 2},
            "stress": [False, False],
            "consequences": {"mild": None},
            "aggressive": False,
            "loot": [],
            "_is_npc": True,
        }
        self.enemies_db["lira_hostile"] = lira_enemy
        room.enemies.append("lira_hostile")
        self._start_combat("lira_hostile")
        display.warning(f"  Lira attacks!")

    def _handle_lira_defeat(self):
        """Handle Lira being defeated in combat — she can no longer be recruited."""
        quest = self.state.get("quests", {}).get("verdant_bloom", {})
        quest["lira_defeated"] = True
        lira = self.npcs_db.get("lira")
        if lira:
            # Remove her from her room
            greenhouse = self.rooms.get("vw_greenhouse")
            if greenhouse and "lira" in greenhouse.npcs:
                greenhouse.npcs.remove("lira")
        print()
        display.narrate("Lira slumps against the wall, clutching her side.")
        print()
        print(f"  {display.npc_name('Lira')}: \"You... you'd really...\"")
        print()
        display.narrate("She pulls herself up and stumbles south, into the smoke.")
        display.narrate("You hear the airlock cycle. She's gone.")
        print()
        display.warning("  Lira can no longer be recruited.")

    def _lira_fire_reaction(self):
        """Lira reacts to the biodome being set on fire, if she's following."""
        lira = self.npcs_db.get("lira")
        if not lira or not lira.get("following"):
            return
        explorer_loc = self.state.get("explorer_location")
        if lira.get("location") != explorer_loc:
            return
        print()
        display.narrate("Lira watches the fire climb. Her jaw tightens.")
        print()
        print(f"  {display.npc_name('Lira')}: \"I knew it would spread. I told you it would.\"")
        print()
        display.narrate("She's not looking at you. She's watching the canopy catch,")
        display.narrate("weeks of growth curling black in seconds.")
        print()
        print(f"  {display.npc_name('Lira')}: \"Get the bloom. Before we lose that too.\"")
        print()
        # Mood and mechanical impact — she suggested it, but watching still hurts
        lira["mood"] = "grim"
        lira["loyalty"] = max(0, lira.get("loyalty", 0) - 1)
        quest = self.state.get("quests", {}).get("verdant_bloom", {})
        quest["lira_witnessed_fire"] = True

    def _on_room_enter(self, room):
        """Check for hazards and aggressive enemies when entering a room."""
        # Environmental compels (burning biodome, etc.)
        from engine.quest import check_fire_compel
        fire_compel = check_fire_compel(self)
        if fire_compel:
            self._present_compel(fire_compel, environmental=True)
            return  # don't also trigger enemy ambush in a burning room

        if not room.enemies:
            return

        for enemy_id in room.enemies:
            enemy_data = self.enemies_db.get(enemy_id)
            if not enemy_data or not enemy_data.get("aggressive"):
                continue

            # Aggressive enemy — initiative roll: enemy Notice vs player Notice
            enemy_notice = enemy_data["skills"].get("Notice", 0)
            invoke_bonus = self._consume_invoke_bonus()
            player_notice = self.explorer.get_skill("Notice") + invoke_bonus
            atk_total, def_total, shifts, _, _ = dice.opposed_roll(enemy_notice, player_notice)

            if shifts >= 0:
                # Enemy wins initiative — gets a free strike
                print()
                display.warning(f"  {enemy_data['name']} lunges at you!")
                self._start_combat(enemy_id)

                enemy_fight = enemy_data["skills"].get("Fight", 1)
                player_fight = self.explorer.get_skill("Fight")
                atk_total, def_total, hit_shifts, atk_dice, def_dice = dice.opposed_roll(enemy_fight, player_fight)

                print(f"  {enemy_data['name']}: {dice.roll_description(atk_dice, enemy_fight, 'Fight')}")
                print(f"  {self.explorer.name}: {dice.roll_description(def_dice, player_fight, 'Fight')}")

                if hit_shifts > 0:
                    display.warning(f"  Ambush! {enemy_data['name']} hits for {hit_shifts} shifts!")
                    taken_out = self.explorer.apply_damage(hit_shifts)
                    if taken_out:
                        display.error(f"\n  ═══ {self.explorer.name.upper()} IS TAKEN OUT! ═══")
                        display.narrate(f"  {self.seed_name} reaches across the void...")
                        self._seed_extraction()
                        return
                    for sev in ["mild", "moderate", "severe"]:
                        if self.explorer.consequences.get(sev) == "Pending":
                            self.combat_consequences_taken += 1
                            con_text = f"Ambushed by {enemy_data['name']}"
                            self.explorer.consequences[sev] = con_text
                            self._record_consequence("explorer", sev, con_text)
                    stress_str = "".join("[X]" if s else "[ ]" for s in self.explorer.stress)
                    display.info(f"  Stress: {stress_str}")
                else:
                    display.narrate(f"  You dodge the ambush! {enemy_data['name']} snarls.")

                display.info(f"  You're locked in combat with {enemy_data['name']}!")
                return
            else:
                # Player wins initiative — they noticed it first
                display.warning(f"  {enemy_data['name']} tenses, ready to spring!")
                display.info("  You have the initiative. ATTACK or EXPLOIT to act first.")
                return

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
            room.remove_enemy(enemy_id)
            self._end_combat()

            # Special handling for NPC combatants
            if enemy_data.get("_is_npc"):
                if enemy_id == "lira_hostile":
                    self._handle_lira_defeat()
                return True

            display.success(f"\n  {enemy_data['name']} is defeated!")
            loot = enemy_data.get("loot", [])
            if loot:
                dropped = random.choice(loot)
                room.add_item(dropped)
                item_info = self.items_db.get(dropped, {})
                display.success(f"  It drops: {item_info.get('name', dropped)}")
            self.explorer.gain_fate_point()
            display.info(f"  (+1 Fate Point for victory)")
            if not self.state.get("tutorial_complete"):
                self.state["tutorial_combat_done"] = True
            return True

        enemy_data["stress"] = enemy_stress
        enemy_data["consequences"] = enemy_cons
        return False

    def _seed_extraction(self):
        """Handle world seed emergency extraction."""
        cost = self.seed.extraction_cost(self.state["extractions"])

        if self.seed.spend_motes(cost):
            self.state["extractions"] += 1
            self._end_combat()
            # Reset consequences to None only if pending
            for sev in list(self.explorer.consequences.keys()):
                if self.explorer.consequences[sev] == "Pending":
                    self.explorer.consequences[sev] = None

            self.state["explorer_location"] = "skerry_landing"
            self._move_followers("skerry_landing")

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
            if task == "salvage":
                if random.random() < 0.6:
                    loot = random.choice(["metal_scraps", "wire", "torn_fabric", "coral_fragments"])
                    # Deposit in junkyard room, not steward inventory
                    junkyard = self.rooms.get("skerry_junkyard")
                    if junkyard:
                        junkyard.add_item(loot)
                    else:
                        self.steward.add_to_inventory(loot)
                    loot_name = self.items_db.get(loot, {}).get("name", loot)
                    display.success(f"  {npc['name']} (salvage) processed: {loot_name}")
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
