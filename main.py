#!/usr/bin/env python3
"""Voidnodes MUD — The Skerry Chronicle.

A text-based adventure set in the space between worlds.
"""

import sys
import json
import random

from engine import parser, display, save, dice, tutorial, map_renderer, recruit, aspects, farming, subtasks
from models.character import Character, BODY_SLOTS
from models.room import Room
from models.world_seed import WorldSeed
from models.skerry import Skerry
from models.item import Item

from commands.combat import CombatMixin
from commands.movement import MovementMixin
from commands.items import ItemsMixin
from commands.npcs import NpcsMixin
from commands.artifacts import ArtifactsMixin
from commands.examine import ExamineMixin
from commands.building import BuildingMixin
from commands.skerry_mgmt import SkerryMgmtMixin
from commands.farming import FarmingMixin
from commands.story import StoryMixin


SKIP_WORDS = {"a", "an", "the", "of", "in", "is", "it", "that", "and", "but", "with", "for", "from", "to", "by"}


import re

_REPEAT_RE = re.compile(r'^x(\d+)\s+', re.IGNORECASE)
_REPEAT_RE_SUFFIX = re.compile(r'^(\d+)x\s+', re.IGNORECASE)


def _parse_repeat_prefix(raw):
    """Strip xN or Nx prefix from input. Returns (count, remaining_input).

    Max repeat is 20 to prevent accidents. Returns (1, raw) if no prefix.
    """
    stripped = raw.strip()
    m = _REPEAT_RE.match(stripped) or _REPEAT_RE_SUFFIX.match(stripped)
    if m:
        count = min(int(m.group(1)), 20)
        return max(count, 1), stripped[m.end():]
    return 1, raw


def _aspect_hint_words(aspect, count=2):
    """Pick the first few meaningful words from an aspect for a SEEK hint."""
    words = [w for w in aspect.split() if w.lower() not in SKIP_WORDS]
    return " ".join(words[:count]).upper() if words else aspect.split()[0].upper()


class Game(CombatMixin, MovementMixin, ItemsMixin, NpcsMixin, ArtifactsMixin,
           ExamineMixin, BuildingMixin, SkerryMgmtMixin, FarmingMixin, StoryMixin):
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
        self.scene_invoked_aspects = set()  # aspects invoked this scene (reset on day change)
        self.enemy_compel_boost = 0  # +2 from compel accept (enemy_boost effect)
        self.in_compel = False
        self.compel_data = None
        self.compel_triggered = False  # at most one compel per combat
        self.in_recruit = False
        self.recruit_state = None
        self.in_social_encounter = False
        self.social_encounter_state = None
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

    def _wrong_phase_narrate(self, intended_role, context=None):
        """Narrative rejection when a command is used by the wrong character."""
        phase = self.state["current_phase"]
        other = self.steward_name if phase == "explorer" else self.explorer_name
        if intended_role == "steward" and phase == "explorer":
            msgs = {
                "farming": f"That's {other}'s domain. Your hands are better suited to a blade.",
                "building": f"{other} handles the building. You handle the void.",
                "management": f"The people answer to {other} here. Focus on what's out there.",
                "stores": f"{other} manages the stores.",
            }
            display.seed_speak(msgs.get(context, f"Leave that to {other}."))
        elif intended_role == "explorer" and phase == "steward":
            if context == "combat":
                display.narrate("There's nothing to fight here. The skerry is safe.")
            elif context == "scavenge":
                display.seed_speak(f"The skerry's been picked clean. {other} can find materials out there.")
            elif context == "void":
                display.seed_speak(f"The void is {other}'s domain. I need you here.")
            else:
                display.seed_speak(f"That's {other}'s kind of work.")

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
        self.specimens_db = farming.load_specimens()
        self.scene_invoked_aspects = set(self.state.get("scene_invoked_aspects", []))

        # Build rooms dict — skip zones that were previously unloaded
        # (but keep entry rooms so the landing pad still shows them)
        self.rooms = {}
        unloaded = set(self.state.get("unloaded_zones", []))
        for zone_id, zone in self.state.get("zones", {}).items():
            if zone_id in unloaded:
                # Only load the entry room for depleted zones
                entry_id = zone.get("entry_room")
                for room_data in zone.get("rooms", []):
                    if room_data["id"] == entry_id:
                        self.rooms[room_data["id"]] = Room(room_data)
                        break
                continue
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
        self.state["scene_invoked_aspects"] = list(self.scene_invoked_aspects)

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
                    "desc": "Tall and lean-muscled, with short dark hair and a faint scar across one cheek. Clean-shaven, with a square jaw and steady grey eyes. His hands are rough and oversized for his frame, the hands of someone used to holding a weapon.",
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
            self._destinations_shown_this_turn = False

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
            char_key = "explorer" if phase == "explorer" else "steward"
            display.display_status(current_char, phase, char_key=char_key,
                                   consequence_meta=self.state.get("consequence_meta", {}))
            display.display_seed(self.seed.to_dict(), name=self.seed_name)
            print()

        while self.running:
            try:
                phase = self.state["current_phase"]
                raw = input(display.prompt(phase))

                # Naming the world seed — capture raw input instead of parsing
                if self.state.get("awaiting_world_seed_name"):
                    name = raw.strip()
                    if name.lower() == "skip":
                        self.state["awaiting_world_seed_name"] = False
                        self.cmd_skip([])
                        continue
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

                # Social encounter — intercept raw input before parser
                if self.in_social_encounter:
                    self._handle_social_encounter_input(raw.strip())
                    continue

                # Repeat prefix: "x5 scavenge" or "5x scavenge"
                repeat, cmd_raw = _parse_repeat_prefix(raw)

                cmd, args = parser.parse(cmd_raw)

                if cmd is None:
                    continue

                if cmd == "unknown":
                    display.error(f"Unknown command: {args[0]}. Type HELP for commands.")
                    continue

                if not parser.is_valid_for_phase(cmd, phase):
                    display.error(f"'{cmd.upper()}' is not available right now.")
                    continue

                for i in range(repeat):
                    if not self.running:
                        break
                    # Only break repeat chains, not the first execution
                    if i > 0 and (self.in_combat or self.in_recruit or self.in_compel or self.in_social_encounter):
                        break

                    if repeat > 1 and i > 0:
                        print()
                        display.info(f"({i + 1}/{repeat})")

                    # Stash location so tutorial can detect failed moves
                    if not self.state.get("tutorial_complete"):
                        loc_key = {"prologue": "prologue_location", "explorer": "explorer_location", "steward": "steward_location"}.get(phase)
                        if loc_key:
                            self.state["_pre_cmd_location"] = self.state.get(loc_key)

                    self._destinations_shown_this_turn = False
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
        # Clear overflow confirmation if doing anything other than picking up the same item
        if cmd != "take":
            self._overflow_confirmed = None

        # Handle hyphenated commands that can't be method names
        if cmd == "cross-pollinate":
            self._handle_cross_pollinate(args)
            return
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
            "recruited_npcs": self.state.get("recruited_npcs", []),
            "bonded_with_seed": self.state.get("bonded_with_seed", False),
            "artifacts_status": self.state.get("artifacts_status", {}),
            "skerry": self.state.get("skerry", {}),
            "zones": self.state.get("zones", {}),
            "quests": self.state.get("quests", {}),
        }

    # ── Event logging ──────────────────────────────────────────────

    def _log_event(self, event_type, comic_weight=1, **kwargs):
        """Log a structured event to the event_log.

        Auto-includes day, phase, current actor, and location.
        comic_weight (1-5) indicates narrative importance for the comic pipeline.
        """
        room = self.current_room()
        entry = {
            "day": self.state.get("day", 1),
            "phase": self.state.get("current_phase", "unknown"),
            "type": event_type,
            "actor": self.current_character().name.lower() if self.current_character() else "unknown",
            "location": room.id if room else "unknown",
            "comic_weight": comic_weight,
        }
        entry.update(kwargs)
        self.state.setdefault("event_log", []).append(entry)

    # ── Shared helpers ─────────────────────────────────────────────

    def _record_consequence(self, char_key, severity, consequence_text):
        """Track consequence metadata for the healing system."""
        meta = self.state.setdefault("consequence_meta", {})
        meta_key = f"{char_key}_{severity}"
        meta[meta_key] = {
            "taken_at": self.state.get("zones_cleared", 0),
            "cure": aspects.get_cure_for_consequence(consequence_text),
            "recovery": 0,
        }

    def _consume_invoke_bonus(self):
        """Consume any pending invoke bonus. Returns the bonus value (0 if none)."""
        bonus = self.pending_invoke_bonus
        if bonus > 0:
            display.info(f"  (Invoking {display.aspect_text(self.pending_invoke_aspect)} — +{bonus})")
            self.pending_invoke_bonus = 0
            self.pending_invoke_aspect = None
        return bonus

    def _sub_dialogue(self, text):
        """Substitute template variables in NPC dialogue strings."""
        return text.replace("{seed_name}", self.seed_name)

    def _find_entity(self, entity_ids, target, db):
        """Find an entity by name or id from a list. Returns (id, data) or (None, None).

        Handles masterwork prefix: "masterwork:rope" looks up "rope" in db,
        and "masterwork rope" as a target matches masterwork items.
        """
        from engine.masterwork import is_masterwork, base_id
        # Normalize "masterwork rope" → match against masterwork items
        mw_target = None
        if target.startswith("masterwork "):
            mw_target = target[len("masterwork "):]

        for eid in entity_ids:
            bid = base_id(eid)
            edata = db.get(bid) or db.get(eid, {})
            ename = edata.get("name", "").lower()

            if is_masterwork(eid):
                # Match "masterwork rope", "rope", or the full id
                if mw_target and (mw_target in ename or mw_target == bid):
                    return eid, edata
                if target in ename or target == eid or target == bid:
                    return eid, edata
            else:
                # Normal item — skip if player specifically asked for masterwork
                if mw_target:
                    continue
                if target in ename or target == eid:
                    return eid, edata
        return None, None

    def _find_follower(self, target, room_id):
        """Find a following NPC at the given location by name. Returns (id, data) or (None, None).

        Only scans recruited NPCs — unrecruited zone NPCs can't be followers.
        """
        for npc_id in self.state.get("recruited_npcs", []):
            npc = self.npcs_db.get(npc_id, {})
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

    def _inventory_counts(self, char):
        """Count items in a character's inventory. Returns {item_id: count}."""
        counts = {}
        for item_id in char.inventory:
            counts[item_id] = counts.get(item_id, 0) + 1
        return counts

    # ── Core Commands ──────────────────────────────────────────────

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
            elif phase == "explorer" and step == "explorer_handoff":
                # Don't let explorer hand off until junkyard has enough to build something
                junkyard = self.rooms.get("skerry_junkyard")
                if junkyard and self.skerry.expandable:
                    junk_counts = {}
                    for item_id in junkyard.items:
                        junk_counts[item_id] = junk_counts.get(item_id, 0) + 1
                    # Also count steward inventory (materials may already be picked up)
                    for item_id in self.steward.inventory:
                        junk_counts[item_id] = junk_counts.get(item_id, 0) + 1
                    npc_count = len(self.state.get("recruited_npcs", []))
                    can_build_any = any(
                        self.skerry.can_build(tmpl, junk_counts, npc_count, self.seed.growth_stage)[0]
                        for tmpl in self.skerry.expandable
                    )
                    if not can_build_any:
                        steward_name = self.steward_name
                        display.seed_speak(f"{steward_name} won't have enough to work with.")
                        display.seed_speak("Gather more salvage before heading back.")
                        display.info("  SEEK to cross into the void and find more materials.")
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
        from_role = self.state["current_phase"]
        self._log_event("character_switched", comic_weight=1,
                        from_role=from_role, to_role=target_role)
        self.save_game(silent=True)

        if target_role == "steward":
            # Explorer → Steward (focus shift only — no day increment)
            self.state["current_phase"] = "steward"
            self.explorer.clear_stress()
            self.in_combat = False
            self.combat_target = None

            print()
            display.narrate(f"Day {self.state['day']}.")
            print()
            display.narrate(f"{self.seed_name}'s tendril around him dims — not gone, but")
            display.narrate("quieter, like a heartbeat fading into the background.")
            print()
            display.narrate(f"The other tendril brightens — the one reaching toward")
            display.narrate(f"{self.steward_name}. {self.seed_name}'s presence floods back in.")

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
            display.display_status(self.steward, "steward", char_key="steward",
                                   consequence_meta=self.state.get("consequence_meta", {}))
            display.display_seed(self.seed.to_dict(), name=self.seed_name)

        else:
            # Steward → Explorer (same day — day ticks when explorer returns)
            self.state["current_phase"] = "explorer"
            self.steward.clear_stress()
            day = self.state["day"]

            print()
            display.narrate(f"{self.seed_name}'s tendril around {self.steward_name} dims.")
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
            display.display_status(self.explorer, "explorer", char_key="explorer",
                                   consequence_meta=self.state.get("consequence_meta", {}))
            display.display_seed(self.seed.to_dict(), name=self.seed_name)

        self.save_game(silent=True)
        print()

    def cmd_quit(self, args):
        self.save_game()
        display.seed_speak(f"Placing you in stasis, {self.current_character().name}. I'll watch over you.")
        self.running = False


if __name__ == "__main__":
    game = Game()
    game.start()
