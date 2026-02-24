"""Building domain — craft, recipes, build, and build-site helpers."""

from engine import display, dice, parser, tutorial, farming


class BuildingMixin:
    """Mixin providing building and crafting commands for the Game class."""

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

        # Check room requirement
        required_room = recipe.get("requires_room")
        if required_room:
            room = self.current_room()
            if not room or room.id != required_room:
                req_room_obj = self.rooms.get(required_room)
                req_name = req_room_obj.name if req_room_obj else required_room
                display.error(f"This recipe requires the {req_name}. Go there first.")
                return

        # Check materials — inventory + room items + food stores (for food recipes)
        char = self.current_character()
        room = self.current_room()
        inv_counts = self._inventory_counts(char)
        # Also count materials in the room
        if room:
            for item_id in room.items:
                inv_counts[item_id] = inv_counts.get(item_id, 0) + 1
        # Food recipes can source from food stores
        is_food_recipe = recipe.get("from_stores") or recipe.get("recipe_type") == "food"
        if is_food_recipe:
            for entry in self.skerry.food_stores:
                inv_counts[entry["item_id"]] = inv_counts.get(entry["item_id"], 0) + entry["quantity"]

        missing = []
        for mat, needed in recipe["materials"].items():
            if inv_counts.get(mat, 0) < needed:
                mat_name = self.items_db.get(mat, {}).get("name", mat.replace("_", " ").title())
                missing.append(f"{needed}x {mat_name} (have {inv_counts.get(mat, 0)})")

        if missing:
            display.error(f"Missing materials: {', '.join(missing)}")
            return

        # Skill check
        skill_name = recipe.get("skill", "Crafts")
        dc = recipe["difficulty"]
        invoke_bonus = self._consume_invoke_bonus()
        skill_val = char.get_skill(skill_name) + invoke_bonus
        # Workshop bonus when crafting in the workshop
        workshop_bonus = 0
        craft_room = self.current_room()
        if craft_room and craft_room.id == "skerry_workshop":
            workshop_bonus = 1 + craft_room.tool_level
            skill_val += workshop_bonus
        label = f"{skill_name}+{invoke_bonus}" if invoke_bonus else skill_name
        total, shifts, dice_result = dice.skill_check(skill_val, dc)
        print(f"  {label}: {dice.roll_description(dice_result, skill_val, label)}")
        if workshop_bonus:
            print(f"  Workshop bonus: +{workshop_bonus}")
        print(f"  DC: {dc:+d}")

        if shifts >= 0:
            # Consume materials — take from food stores first (food recipes), then room, then inventory
            for mat, needed in recipe["materials"].items():
                for _ in range(needed):
                    consumed_from_stores = False
                    if is_food_recipe:
                        for entry in self.skerry.food_stores:
                            if entry["item_id"] == mat and entry["quantity"] > 0:
                                entry["quantity"] -= 1
                                consumed_from_stores = True
                                break
                        # Clean up empty store entries
                        self.skerry.food_stores[:] = [e for e in self.skerry.food_stores if e["quantity"] > 0]
                    if not consumed_from_stores:
                        if room and mat in room.items:
                            room.remove_item(mat)
                        else:
                            char.remove_from_inventory(mat)

            # Create result
            result_id = recipe["result"]
            char.add_to_inventory(result_id)
            result_info = self.items_db.get(result_id, {})
            display.success(f"Crafted: {result_info.get('name', result_id)}!")

            masterwork = shifts >= 3
            if masterwork:
                display.success("Masterwork! You crafted it with exceptional quality.")
                # Bonus: extra item or better version
                char.add_to_inventory(result_id)
                display.success(f"  Bonus: crafted a second {result_info.get('name', result_id)}!")
            self._log_event("item_crafted", comic_weight=3,
                            recipe=recipe.get("name", target),
                            result=result_info.get("name", result_id),
                            masterwork=masterwork)
        else:
            # Fail — lose some materials
            lost_mat = list(recipe["materials"].keys())[0]
            char.remove_from_inventory(lost_mat)
            lost_name = self.items_db.get(lost_mat, {}).get("name", lost_mat)
            display.warning(f"Crafting failed! Lost 1x {lost_name} in the attempt.")
            self._log_event("item_crafted", comic_weight=2,
                            recipe=recipe.get("name", target),
                            result=None, success=False, material_lost=lost_name)

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
                print(f"  {display.BRIGHT_WHITE}{display.BOLD}{recipe.get('name', rid)}{display.RESET}: {mats} → {result_name} (DC {recipe.get('difficulty', 0):+d})")
            else:
                print(f"  {display.DIM}{recipe.get('name', rid)}: {mats} → {result_name} (DC {recipe.get('difficulty', 0):+d}){display.RESET}")

    OPPOSITE_DIR = {
        "north": "south", "south": "north",
        "east": "west", "west": "east",
        "up": "down", "down": "up",
        "northwest": "southeast", "southeast": "northwest",
        "northeast": "southwest", "southwest": "northeast",
    }

    BUILD_DIRECTIONS = (
        "north", "south", "east", "west",
        "northwest", "northeast", "southwest", "southeast",
    )

    def _get_build_sites(self):
        """Get available build sites — open directions on existing skerry rooms."""
        sites = []
        for room in self.skerry.get_all_rooms():
            used = set(room.exits.keys())
            for direction in self.BUILD_DIRECTIONS:
                if direction not in used:
                    sites.append((room.id, room.name, direction))
        return sites

    def _parse_build_location(self, words):
        """Parse '<direction> of <room>' from build args. Returns (room_id, direction) or None."""
        # Find 'of' to split direction from room name
        if "of" not in words:
            return None
        of_idx = words.index("of")
        dir_part = " ".join(words[:of_idx]).lower()
        room_part = " ".join(words[of_idx + 1:]).lower()
        if not dir_part or not room_part:
            return None

        # Resolve direction alias
        direction = parser.DIRECTION_ALIASES.get(dir_part, dir_part)
        if direction not in self.OPPOSITE_DIR:
            return None

        # Find the anchor room
        for room in self.skerry.get_all_rooms():
            if room_part in room.name.lower() or room_part in room.id.lower():
                if direction not in room.exits:
                    return room.id, direction
                else:
                    display.error(f"{room.name} already has an exit to the {direction}.")
                    return "occupied"
        return None

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
            self._log_event("house_built", comic_weight=3,
                            npc_name=npc["name"], npc_id=npc_id,
                            level=npc["house_level"], label=label)
            if npc.get("mood") == "restless":
                npc["mood"] = "content"
                display.success(f"  {npc['name']}'s mood improves to content.")
            return

        # Match structure name, then parse optional location
        matched_tmpl = None
        location_words = []
        for tmpl in self.skerry.expandable:
            tmpl_name = tmpl["name"].lower()
            # Check if args start with the structure name
            name_words = tmpl_name.split()
            arg_words = args
            if len(arg_words) >= len(name_words):
                if [w.lower() for w in arg_words[:len(name_words)]] == name_words:
                    matched_tmpl = tmpl
                    location_words = arg_words[len(name_words):]
                    break
            # Also check substring match for single-word names
            if tmpl_name in target and not matched_tmpl:
                # Find where the name ends in args
                for i in range(len(args)):
                    if " ".join(args[:i+1]).lower() == tmpl_name or tmpl_name in " ".join(args[:i+1]).lower():
                        matched_tmpl = tmpl
                        location_words = args[i+1:]
                        break
                if matched_tmpl:
                    break

        if not matched_tmpl:
            display.error(f"Nothing called '{target}' to build. Type CHECK SKERRY for options.")
            return

        tmpl = matched_tmpl

        # Check if player can afford it
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

        # Parse or prompt for location
        placement = None
        if location_words:
            result = self._parse_build_location(location_words)
            if result == "occupied":
                return
            if result is None:
                display.error("Couldn't understand that location.")
                display.info("  Syntax: BUILD <name> <direction> OF <room>")
                display.info("  Example: BUILD GARDEN NORTH OF CLEARING")
                return
            placement = result
        else:
            # No location given — show available sites
            sites = self._get_build_sites()
            if not sites:
                display.error("No open build sites on the skerry.")
                return
            display.info(f"Where should the {tmpl['name']} go?")
            for room_id, room_name, direction in sites:
                print(f"    {direction} of {room_name}")
            print()
            display.info(f"  Syntax: BUILD {tmpl['name'].upper()} <direction> OF <room>")
            return

        anchor_room_id, direction = placement
        anchor_room = self.rooms.get(anchor_room_id)
        opposite = self.OPPOSITE_DIR[direction]

        # Consume materials
        for mat, count in tmpl.get("requires", {}).get("materials", {}).items():
            for _ in range(count):
                if room and mat in room.items:
                    room.remove_item(mat)
                else:
                    self.steward.remove_from_inventory(mat)

        # Consume specimen if required (garden)
        spec_needed = tmpl.get("requires", {}).get("any_specimen", 0)
        for _ in range(spec_needed):
            for item_id in list(self.steward.inventory):
                if farming.is_specimen(item_id):
                    self.steward.remove_from_inventory(item_id)
                    break

        # Override template exits/connect_to with player's choice
        tmpl_copy = dict(tmpl)
        tmpl_copy["exits"] = {opposite: anchor_room_id}
        tmpl_copy["connect_to"] = {anchor_room_id: direction}

        new_room = self.skerry.build_room(tmpl_copy)
        self.rooms[new_room.id] = new_room
        # Sync connection to Game's rooms (separate from Skerry's Room objects)
        anchor_room.exits[direction] = new_room.id

        display.success(f"Built: {new_room.name}! ({direction} of {anchor_room.name})")
        display.narrate(f"  {new_room.description}")
        self._log_event("structure_built", comic_weight=3,
                        room_name=new_room.name, room_id=new_room.id,
                        direction=direction, anchor=anchor_room.name)

        # Garden walkthrough on first build
        if "garden" in tmpl.get("structures", []):
            tutorial.garden_walkthrough(self)

        # Update skerry state
        self.state["skerry"] = self.skerry.to_dict()
