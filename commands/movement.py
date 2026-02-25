"""Movement domain — go, seek, enter, void crossings, room entry."""

import random

from engine import display, dice


# Module-level constant used by _aspect_hint_words
SKIP_WORDS = {"a", "an", "the", "of", "in", "is", "it", "that", "and", "but", "with", "for", "from", "to", "by"}


def _aspect_hint_words(aspect, count=2):
    """Pick the first few meaningful words from an aspect for a SEEK hint."""
    words = [w for w in aspect.split() if w.lower() not in SKIP_WORDS]
    return " ".join(words[:count]).upper() if words else aspect.split()[0].upper()


class MovementMixin:
    """Mixin providing movement commands and helpers for the Game class."""

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

    def _show_landing_pad_destinations(self, room):
        """Show available void destinations from the landing pad."""
        if self.state["current_phase"] != "explorer":
            return
        # Guard against showing twice in the same turn
        if getattr(self, "_destinations_shown_this_turn", False):
            return
        self._destinations_shown_this_turn = True
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
                print(f"    {display.aspect_text(aspect)}")
        print()
        display.seed_speak("SEEK an aspect to follow it.")
        mote_cost = 1
        print(f"  {display.DIM}(Travel costs {mote_cost} mote. {self.seed_name} has {self.seed.motes}.){display.RESET}")


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
        if self.state["current_phase"] == "steward":
            self._wrong_phase_narrate("explorer", "void")
            return
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
        first_visit = not target_room.discovered
        target_room.discover()

        if phase == "explorer":
            self._move_followers(target_id)

        # Log zone entry
        zone_name = self.state.get("zones", {}).get(target_room.zone, {}).get("name", target_room.zone)
        self._log_event("zone_entered", comic_weight=4 if first_visit else 2,
                        zone=target_room.zone, zone_name=zone_name,
                        from_zone=room.zone, first_visit=first_visit,
                        motes_spent=1 if target_room.zone != "skerry" else 0)

        # Returning to the skerry from the void — a day passes
        if room.zone != "skerry" and target_room.zone == "skerry":
            self.state["day"] += 1
            self._narrate_void_crossing(room, target_room)
            print()
            display.narrate(f"The void crossing takes its toll. By the time you reach")
            display.narrate(f"the skerry, it is morning. Day {self.state['day']}.")
            self._day_transition()
        else:
            self._narrate_void_crossing(room, target_room)

        display.display_room(target_room, self.game_context())

        # Show destinations if we just arrived at the landing pad
        if target_room.id == "skerry_landing":
            self._show_landing_pad_destinations(target_room)

        # Check for aggressive enemies (explorer only) + passive artifact discovery
        if self.state["current_phase"] == "explorer":
            self._on_room_enter(target_room)
        else:
            self._check_passive_artifact_discovery(target_room)

    def cmd_enter(self, args):
        """Handle ENTER VOID — legacy command, redirects to SEEK."""
        if self.state["current_phase"] == "steward":
            self._wrong_phase_narrate("explorer", "void")
            return
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
            # Returning to the skerry from the void — a day passes
            if room.zone != "skerry" and target_room.zone == "skerry":
                self.state["day"] += 1
                self._narrate_void_crossing(room, target_room)
                print()
                display.narrate(f"The void crossing takes its toll. By the time you reach")
                display.narrate(f"the skerry, it is morning. Day {self.state['day']}.")
                self._day_transition()
            else:
                self._narrate_void_crossing(room, target_room)
            display.display_room(target_room, self.game_context())
            if self.state["current_phase"] == "explorer":
                self._on_room_enter(target_room)
            else:
                self._check_passive_artifact_discovery(target_room)
            return

        # Multiple crossings — show what the seed senses and prompt SEEK
        self._show_landing_pad_destinations(room)


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
            if self.state["current_phase"] != "explorer":
                display.seed_speak(f"The void crossing is too dangerous. {self.explorer_name} can handle it.")
                return
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
        first_visit = not target_room.discovered
        target_room.discover()

        if first_visit:
            self._log_event("room_discovered", comic_weight=2,
                            room_id=target_id, room_name=target_room.name,
                            zone=target_room.zone)
        else:
            self._log_event("room_entered", comic_weight=1,
                            room_id=target_id, room_name=target_room.name)

        # Clear pending NPC question when leaving the room
        self.state.pop("pending_npc_question", None)

        # Followers move with the explorer
        if phase == "explorer":
            self._move_followers(target_id)

        display.display_room(target_room, self.game_context())

        # Show destinations if we just arrived at the landing pad
        if target_id == "skerry_landing":
            self._show_landing_pad_destinations(target_room)

        # Contextual quest hints on room entry
        self._quest_room_hints(target_room)

        # Seed senses a survivor — hint to TALK (fires once, first non-recruited NPC)
        if not self.state.get("_npc_talk_hint_shown"):
            for npc_id in target_room.npcs:
                npc = self.npcs_db.get(npc_id)
                if npc and not npc.get("recruited"):
                    self.state["_npc_talk_hint_shown"] = True
                    print()
                    display.seed_speak("I sense a survivor here. Someone who knows this place.")
                    display.seed_speak("GREET them — they might know something useful.")
                    break

        # Check for aggressive enemies (explorer only) + passive artifact discovery
        if self.state["current_phase"] == "explorer":
            self._on_room_enter(target_room)
        else:
            # Steward still gets passive artifact discovery
            self._check_passive_artifact_discovery(target_room)

            # Social compels on skerry room entry (steward phase)
            if target_room.zone == "skerry" and not self.in_compel:
                from engine.social import check_social_compel, mark_social_compel_used
                social_compel = check_social_compel(self)
                if social_compel:
                    mark_social_compel_used(self, social_compel["aspect"])
                    self._present_compel(social_compel)
                    return

        # First-visit building hints (steward phase, skerry buildings)
        if self.state["current_phase"] == "steward" and target_room.zone == "skerry":
            visited_key = f"_visited_{target_room.id}"
            if not self.state.get(visited_key) and target_room.role:
                self.state[visited_key] = True
                _BUILDING_HINTS = {
                    "craft": "This is your workshop. CRAFT items here, or ASSIGN someone and set a QUEUE for them to follow.",
                    "salvage": "The junkyard. ASSIGN someone to salvage — they'll sort and strip materials.",
                    "garden": "A garden! PLANT specimens here, and ASSIGN someone to tend the plots.",
                    "guard": "A lookout post. ASSIGN someone to watch for threats.",
                    "storage": "The storehouse. CHECK STORES to see food supplies, CHECK VAULT for seeds.",
                    "healing": "An apothecary. REQUEST TREATMENT for injuries, or ASSIGN a healer.",
                }
                hint = _BUILDING_HINTS.get(target_room.role)
                if hint:
                    print()
                    display.seed_speak(hint)

        # World seed flavor message occasionally
        if not self.in_combat and not self.in_compel and random.random() < 0.3:
            print()
            display.seed_speak(self.seed.communicate(self.seed_name))

    def _check_passive_artifact_discovery(self, room):
        """Passive Notice check for undiscovered artifacts on room entry.

        Works for both explorer and steward — uses current character's Notice skill.
        """
        char = self.current_character()
        for art_id, art in self._artifacts_in_room(room.id):
            if art_id in self.state.get("artifacts_status", {}):
                continue
            dc = art.get("notice_dc", 2)
            notice_val = char.get_skill("Notice")
            total, shifts, dice_result = dice.skill_check(notice_val, dc)
            if shifts >= 0:
                print()
                display.header(art["name"])
                display.narrate(self.sub(art.get("discovery_text", art["description"])))
                self.state.setdefault("artifacts_status", {})[art_id] = "discovered"
                display.info(f"  Feed to {self.seed_name}: {art['mote_value']} motes")
                if art.get("stat_bonuses"):
                    bonuses = ", ".join(f"+{v} {k}" for k, v in art["stat_bonuses"].items())
                    display.info(f"  Keep for: {bonuses}")
                if art.get("keep_effect"):
                    display.info(f"  Special: {self.sub(art['keep_effect'][:80])}...")
                self._log_event("artifact_noticed", comic_weight=3,
                                artifact_id=art_id, artifact_name=art["name"])

    def _on_room_enter(self, room):
        """Check for hazards and aggressive enemies when entering a room."""
        # Environmental compels (burning biodome, etc.)
        from engine.quest import check_fire_compel
        fire_compel = check_fire_compel(self)
        if fire_compel:
            self._present_compel(fire_compel, environmental=True)
            return  # don't also trigger enemy ambush in a burning room

        # Passive artifact discovery — Notice check
        self._check_passive_artifact_discovery(room)

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
                self._log_event("ambush", comic_weight=3,
                                enemy=enemy_data.get("name", enemy_id),
                                enemy_id=enemy_id, initiative="enemy")
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
                            self._log_event("consequence_taken", comic_weight=4,
                                            severity=sev, description=con_text,
                                            source=enemy_data.get("name", "unknown"))
                    stress_str = "".join("[X]" if s else "[ ]" for s in self.explorer.stress)
                    display.info(f"  Stress: {stress_str}")
                else:
                    display.narrate(f"  You dodge the ambush! {enemy_data['name']} snarls.")

                display.info(f"  You're locked in combat with {enemy_data['name']}!")
                return
            else:
                # Player wins initiative — they noticed it first
                self._start_combat(enemy_id)
                display.warning(f"  {enemy_data['name']} tenses, ready to spring!")
                display.info("  You have the initiative. ATTACK or EXPLOIT to act first.")
                return
