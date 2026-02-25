"""Artifacts domain — feed, keep, offer, artifact location tracking."""

from engine import display, aspects


class ArtifactsMixin:
    """Mixin providing artifact commands and helpers for the Game class."""

    def _on_artifact_resolved(self, art_id):
        """Called when any artifact is resolved. Increments zones_cleared for zone artifacts."""
        # Only zone artifacts count as zone clears
        from commands.movement import MovementMixin
        if art_id in MovementMixin._ZONE_ARTIFACTS.values():
            self.state["zones_cleared"] = self.state.get("zones_cleared", 0) + 1
            cleared = aspects.check_mild_auto_heal(self)
            for char_key, consequence_text in cleared:
                char_name = self.state.get(f"{char_key}_name", char_key.title())
                display.success(f"  {char_name}'s mild injury ({consequence_text}) has healed with time.")

            # Unload the cleared zone's rooms and enemies from runtime
            zone_id = None
            for zid, aid in MovementMixin._ZONE_ARTIFACTS.items():
                if aid == art_id:
                    zone_id = zid
                    break
            if zone_id:
                self._unload_zone(zone_id)

    def _unload_zone(self, zone_id):
        """Remove a cleared zone's rooms and enemies from runtime dicts.

        Keeps the entry room so the landing pad can still show the zone
        as a (depleted) destination. NPCs stay in npcs_db (their source
        of truth). Zone data stays in state["zones"] for save/load.
        """
        zone = self.state.get("zones", {}).get(zone_id)
        if not zone:
            return
        entry_room = zone.get("entry_room")
        # Remove zone rooms from self.rooms (except entry room)
        for room_data in zone.get("rooms", []):
            room_id = room_data["id"]
            if room_id == entry_room:
                continue
            # Don't unload the room if a player character is currently in it
            if self.state.get("explorer_location") == room_id:
                continue
            if self.state.get("steward_location") == room_id:
                continue
            self.rooms.pop(room_id, None)
        # Remove zone enemies from self.enemies_db
        for enemy in zone.get("enemies_data", []):
            self.enemies_db.pop(enemy["id"], None)
        # Track which zones have been unloaded
        self.state.setdefault("unloaded_zones", [])
        if zone_id not in self.state["unloaded_zones"]:
            self.state["unloaded_zones"].append(zone_id)

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
                display.success(f"\n  \u2727 {self.seed_name.upper()} GROWS STRONGER! \u2727")
                display.seed_speak(self.seed.communicate(self.seed_name))
                self._log_event("seed_growth", comic_weight=5,
                                new_stage=self.seed.growth_stage,
                                total_motes=new_total)

            self._log_event("artifact_fed", comic_weight=5,
                            artifact_id=art_id, artifact_name=art["name"],
                            motes_gained=motes, total_motes=new_total)
            display.display_seed(self.seed.to_dict(), name=self.seed_name)
            return

        # Check regular items
        item_id, item = self._find_entity(list(char.inventory), target, self.items_db)
        if item:
            from engine.masterwork import get_display_name
            motes = item.get("mote_value", 1)
            new_total, stage_changed = self.seed.feed(motes)
            char.remove_from_inventory(item_id)

            feed_name = get_display_name(item_id, self.items_db)
            display.success(f"You feed {feed_name} to {self.seed_name}. +{motes} motes!")
            self._log_event("item_fed", comic_weight=2,
                            item_id=item_id, item_name=feed_name,
                            motes_gained=motes, total_motes=new_total)
            if stage_changed:
                self._log_event("seed_growth", comic_weight=5,
                                new_stage=self.seed.growth_stage,
                                total_motes=new_total)
                display.success(f"\n  \u2727 {self.seed_name.upper()} GROWS STRONGER! \u2727")
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
                self._log_event("artifact_kept", comic_weight=5,
                                artifact_id=art_id, artifact_name=art["name"],
                                bonuses=art.get("stat_bonuses", {}))
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
                    display.success(f"\n  \u2727 {self.seed_name.upper()} GROWS STRONGER! \u2727")
                    display.seed_speak(self.seed.communicate(self.seed_name))
                    self._log_event("seed_growth", comic_weight=5,
                                    new_stage=self.seed.growth_stage,
                                    total_motes=new_total)

                self._log_event("artifact_fed", comic_weight=5,
                                artifact_id=art_id, artifact_name=art["name"],
                                motes_gained=motes, total_motes=new_total)
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
                self._log_event("item_fed", comic_weight=2,
                                item_id=item_id, item_name=item.get("name", item_id),
                                motes_gained=motes, total_motes=new_total)
                if stage_changed:
                    display.success(f"\n  \u2727 {self.seed_name.upper()} GROWS STRONGER! \u2727")
                    display.seed_speak(self.seed.communicate(self.seed_name))

                display.display_seed(self.seed.to_dict(), name=self.seed_name)
                return

            display.narrate(f"You don't have '{item_name_str}' to offer.")
            return

        # Target is an NPC — future functionality
        display.narrate("They don't seem interested.")

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
