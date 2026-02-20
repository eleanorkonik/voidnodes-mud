"""Items domain — take, drop, wear, remove, use, give, inventory."""

from engine import display
from models.character import BODY_SLOTS


class ItemsMixin:
    """Mixin providing item manipulation commands for the Game class."""

    def cmd_inventory(self, args):
        display.display_inventory(self.current_character(), self.items_db, self.artifacts_db, self.specimens_db)

    def cmd_take(self, args):
        if not args:
            display.error("Take what?")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        # GET ALL / TAKE ALL — grab all loose items and specimens (not artifacts/fixtures)
        if target == "all":
            if not room.items:
                display.narrate("There's nothing here to pick up.")
                return
            picked = []
            for item_id in list(room.items):
                is_fixture = self.items_db.get(item_id, {}).get("type") == "fixture"
                is_takeable = item_id in self.items_db or item_id in self.specimens_db
                if is_takeable and not is_fixture:
                    room.remove_item(item_id)
                    self.current_character().add_to_inventory(item_id)
                    picked.append(item_id)
            if not picked:
                display.narrate("There's nothing here to pick up.")
                return
            counts = {}
            for mid in picked:
                spec = self.specimens_db.get(mid)
                name = spec["name"] if spec else self.items_db.get(mid, {}).get("name", mid)
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

        # Check for specimen items in room
        for rid in list(room.items):
            spec = self.specimens_db.get(rid)
            if spec and (target in spec["name"].lower() or target == rid):
                room.remove_item(rid)
                self.current_character().add_to_inventory(rid)
                display.success(f"You pick up {spec['name']}. (specimen)")
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
