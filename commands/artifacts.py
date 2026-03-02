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
            results = aspects.check_auto_heal(self)
            for char_key, original_sev, consequence_text, event_type in results:
                char_name = self.state.get(f"{char_key}_name", char_key.title())
                if event_type == "cleared":
                    display.success(f"  {char_name}'s {original_sev} injury ({consequence_text}) has fully healed.")
                else:
                    display.info(f"  {char_name}'s {original_sev} injury ({consequence_text}) is improving.")

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
        """FEED <item> — shorthand for GIVE <item> TO <seed>."""
        if not args:
            display.error(f"Feed what to {self.seed_name}?")
            return
        self.cmd_give(args + ["to", self.seed_name.lower()])

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
