"""Building domain — craft, recipes, build, and build-site helpers."""

from engine import display, dice, parser, tutorial, farming, masterwork


class BuildingMixin:
    """Mixin providing building and crafting commands for the Game class."""

    def _display_buildable_structures(self):
        """Show upgradable and buildable structures with material availability.

        Used by both BUILD (no args) and CHECK SKERRY.
        """
        inv_counts = self._inventory_counts(self.steward)
        room = self.current_room()
        if room:
            for item_id in room.items:
                inv_counts[item_id] = inv_counts.get(item_id, 0) + 1
        npc_count = len(self.state.get("recruited_npcs", []))

        has_output = False

        # Upgradable structures
        upgrade_lines = []
        for key, udef in self.UPGRADE_TIERS.items():
            uroom = self.skerry.get_room(udef["room_id"])
            if not uroom:
                continue
            current_level = getattr(uroom, udef["level_field"], 0)
            tier = udef["tiers"].get(current_level)
            if not tier:
                continue  # maxed out
            mat_parts = []
            can_upgrade = True
            for k, v in tier["cost"].items():
                label = f"{v}x {k.replace('_', ' ')}"
                if inv_counts.get(k, 0) >= v:
                    mat_parts.append(f"{display.BRIGHT_WHITE}{label}{display.RESET}")
                else:
                    mat_parts.append(label)
                    can_upgrade = False
            mats = ", ".join(mat_parts)
            line_name = f"{uroom.name} → {tier['name']}"
            if can_upgrade:
                upgrade_lines.append(f"    {display.BRIGHT_WHITE}{line_name}{display.RESET} — needs: {mats} ({tier['skill']} DC {tier['dc']})")
            else:
                upgrade_lines.append(f"    {line_name} — needs: {mats} ({tier['skill']} DC {tier['dc']})")

        # Garden upgrades (per-room, dynamically resolved)
        for room_id, garden in self.skerry.gardens.items():
            groom = self.skerry.get_room(room_id)
            if not groom:
                continue
            current_level = getattr(groom, "garden_level", 0)
            tier = self.GARDEN_UPGRADE_TIERS.get(current_level)
            if not tier:
                continue  # maxed out
            mat_parts = []
            can_upgrade = True
            for k, v in tier["cost"].items():
                label = f"{v}x {k.replace('_', ' ')}"
                if inv_counts.get(k, 0) >= v:
                    mat_parts.append(f"{display.BRIGHT_WHITE}{label}{display.RESET}")
                else:
                    mat_parts.append(label)
                    can_upgrade = False
            mats = ", ".join(mat_parts)
            plot_count = len(garden.get("plots", []))
            line_name = f"{groom.name} ({plot_count} plots) → {tier['name']}"
            if can_upgrade:
                upgrade_lines.append(f"    {display.BRIGHT_WHITE}{line_name}{display.RESET} — needs: {mats} ({tier['skill']} DC {tier['dc']})")
            else:
                upgrade_lines.append(f"    {line_name} — needs: {mats} ({tier['skill']} DC {tier['dc']})")

        if upgrade_lines:
            print(f"\n  {display.BOLD}Upgradable:{display.RESET}")
            for line in upgrade_lines:
                print(line)
            has_output = True

        # Buildable structures
        if self.skerry.expandable:
            build_lines = []
            for tmpl in self.skerry.expandable:
                reqs = tmpl.get("requires", {})
                # Hide structures the seed hasn't unlocked yet
                if self.seed.growth_stage < reqs.get("seed_stage", 0):
                    continue
                # Garden: only show BUILD option when all existing gardens are at max (20)
                if "garden" in tmpl.get("structures", []) and self.skerry.gardens:
                    if not self.skerry.all_gardens_at_max():
                        continue
                mat_parts = []
                for k, v in reqs.get("materials", {}).items():
                    label = f"{v}x {k.replace('_', ' ')}"
                    if inv_counts.get(k, 0) >= v:
                        mat_parts.append(f"{display.BRIGHT_WHITE}{label}{display.RESET}")
                    else:
                        mat_parts.append(label)
                if reqs.get("any_specimen", 0) > 0:
                    spec_count = sum(1 for i in inv_counts if farming.is_specimen(i) and inv_counts[i] > 0)
                    label = f"{reqs['any_specimen']}x specimen"
                    if spec_count >= reqs["any_specimen"]:
                        mat_parts.append(f"{display.BRIGHT_WHITE}{label}{display.RESET}")
                    else:
                        mat_parts.append(label)
                if reqs.get("npcs", 0) > 0:
                    label = f"{reqs['npcs']} NPC{'s' if reqs['npcs'] > 1 else ''}"
                    if npc_count >= reqs["npcs"]:
                        mat_parts.append(f"{display.BRIGHT_WHITE}{label}{display.RESET}")
                    else:
                        mat_parts.append(label)
                mats = ", ".join(mat_parts)
                can, _ = self.skerry.can_build(tmpl, inv_counts, npc_count, self.seed.growth_stage)
                if can:
                    build_lines.append(f"    {display.BRIGHT_WHITE}{tmpl['name']}{display.RESET} — needs: {mats}")
                else:
                    build_lines.append(f"    {tmpl['name']} — needs: {mats}")
            if build_lines:
                print(f"\n  {display.BOLD}Buildable:{display.RESET}")
                for line in build_lines:
                    print(line)
                has_output = True

        if not has_output:
            print("  No structures available to build or upgrade right now.")

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
        invoke_bonus = self._consume_invoke_bonus(skill=skill_name)
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

            # Bonus tiers: 3 shifts = extra normal item, 4+ = masterwork bonus
            is_food = recipe.get("recipe_type") == "food" or recipe.get("from_stores")
            is_masterwork = False
            if shifts >= 4 and not is_food:
                is_masterwork = True
                mw_id = masterwork.masterwork_id(result_id)
                char.add_to_inventory(mw_id)
                mw_name = masterwork.get_display_name(mw_id, self.items_db)
                display.success("Masterwork! Your hands remembered something precise.")
                display.success(f"  Bonus: {mw_name}")
                display.info("  Masterwork items can be gifted to NPCs or placed in workrooms.")
            elif shifts >= 3:
                display.success("Excellent work! You got enough out of the materials for a second one.")
                char.add_to_inventory(result_id)
                display.success(f"  Bonus: crafted a second {result_info.get('name', result_id)}!")
            self._log_event("item_crafted", comic_weight=3,
                            recipe=recipe.get("name", target),
                            result=result_info.get("name", result_id),
                            masterwork=is_masterwork)
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
        if self.state["current_phase"] == "explorer":
            self._wrong_phase_narrate("steward", "building")
            return
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
        if self.state["current_phase"] == "explorer":
            self._wrong_phase_narrate("steward", "building")
            return
        if not args:
            display.header("Available Structures")
            self._display_buildable_structures()
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

            inv_counts = self._inventory_counts(self.current_character())
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
                        self.current_character().remove_from_inventory(mat)

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

        # Garden: only allow building a new one when all existing gardens are at max
        is_garden = "garden" in tmpl.get("structures", [])
        if is_garden and self.skerry.gardens:
            if not self.skerry.all_gardens_at_max():
                display.error("Upgrade your existing garden first. UPGRADE GARDEN to add more plots.")
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
        char = self.current_character()
        for mat, count in tmpl.get("requires", {}).get("materials", {}).items():
            for _ in range(count):
                if room and mat in room.items:
                    room.remove_item(mat)
                else:
                    char.remove_from_inventory(mat)

        # Consume specimen if required (garden)
        spec_needed = tmpl.get("requires", {}).get("any_specimen", 0)
        for _ in range(spec_needed):
            char = self.current_character()
            for item_id in list(char.inventory):
                if farming.is_specimen(item_id):
                    char.remove_from_inventory(item_id)
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

        # Workshop walkthrough on first build
        if "workshop" in tmpl.get("structures", []):
            # Auto-discover workshop-only recipes
            discovered = self.state.setdefault("discovered_recipes", [])
            for recipe_id, recipe in self.recipes_db.items():
                if recipe.get("requires_room") == "skerry_workshop" and recipe_id not in discovered:
                    discovered.append(recipe_id)
            print()
            display.seed_speak("A proper workspace. Your people can CRAFT here — recipes that need")
            display.seed_speak("precision tools. Assign someone to salvage in the junkyard and")
            display.seed_speak("they'll haul materials here automatically.")
            display.seed_speak("Type RECIPES to see what you can make, and QUEUE to set priorities.")

        # Apothecary walkthrough on first build
        if "apothecary" in tmpl.get("structures", []):
            # Auto-discover apothecary-only recipes
            discovered = self.state.setdefault("discovered_recipes", [])
            for recipe_id, recipe in self.recipes_db.items():
                if recipe.get("requires_room") == "skerry_apothecary" and recipe_id not in discovered:
                    discovered.append(recipe_id)
            print()
            display.seed_speak("Somewhere to tend the wounded. Assign a healer here and they'll")
            display.seed_speak("brew bandages and tend injuries overnight.")
            display.seed_speak("UPGRADE APOTHECARY when you have materials to unlock better care.")

        # Update skerry state
        self.state["skerry"] = self.skerry.to_dict()

    def cmd_queue(self, args):
        """QUEUE [recipe] — Add a recipe to the workshop craft queue, or show current queue."""
        if self.state["current_phase"] == "explorer":
            self._wrong_phase_narrate("steward", "building")
            return
        room = self.current_room()
        if not room or room.id != "skerry_workshop":
            display.error("You need to be in the workshop to manage the craft queue.")
            return

        queue = self.state.setdefault("workshop_queue", [])

        if not args:
            # Show current queue
            display.header("Workshop Craft Queue")
            if not queue:
                print("  Queue is empty. QUEUE <recipe> to add one.")
                return
            for i, recipe_id in enumerate(queue, 1):
                recipe = self.recipes_db.get(recipe_id, {})
                name = recipe.get("name", recipe_id)
                mats = ", ".join(f"{v}x {self.items_db.get(k, {}).get('name', k)}"
                               for k, v in recipe.get("materials", {}).items())
                print(f"  {i}. {name} ({mats})")
            return

        target = " ".join(args).lower()
        _, recipe = self._find_in_db(target, self.recipes_db)
        if not recipe:
            display.error(f"Unknown recipe: '{target}'. Type RECIPES to see options.")
            return

        if recipe["id"] not in self.state.get("discovered_recipes", []):
            display.error(f"You haven't learned the {recipe['name']} recipe yet.")
            return

        if recipe["id"] in queue:
            display.info(f"{recipe['name']} is already in the queue.")
            return

        queue.append(recipe["id"])
        display.success(f"Added {recipe['name']} to the craft queue (position {len(queue)}).")

    def cmd_unqueue(self, args):
        """UNQUEUE <recipe> — Remove a recipe from the workshop craft queue."""
        if self.state["current_phase"] == "explorer":
            self._wrong_phase_narrate("steward", "building")
            return
        room = self.current_room()
        if not room or room.id != "skerry_workshop":
            display.error("You need to be in the workshop to manage the craft queue.")
            return

        if not args:
            display.error("Unqueue what? UNQUEUE <recipe name>")
            return

        queue = self.state.setdefault("workshop_queue", [])
        if not queue:
            display.info("The queue is already empty.")
            return

        target = " ".join(args).lower()
        _, recipe = self._find_in_db(target, self.recipes_db)
        if not recipe:
            display.error(f"Unknown recipe: '{target}'.")
            return

        if recipe["id"] not in queue:
            display.info(f"{recipe['name']} isn't in the queue.")
            return

        queue.remove(recipe["id"])
        display.success(f"Removed {recipe['name']} from the craft queue.")

    # ── Upgrade tiers ────────────────────────────────────────────────

    UPGRADE_TIERS = {
        "apothecary": {
            "room_id": "skerry_apothecary",
            "structure": "apothecary",
            "level_field": "healing_level",
            "max_level": 2,
            "tiers": {
                0: {
                    "name": "Infirmary",
                    "cost": {"metal_scraps": 2, "basic_tools": 1},
                    "dc": 2,
                    "skill": "Crafts",
                    "description": "Upgrade with proper tools and metal framing for a sheltered infirmary.",
                },
                1: {
                    "name": "Hospital",
                    "cost": {"ancient_alloys": 2, "crystal_shards": 1, "bone_needles": 1},
                    "dc": 4,
                    "skill": "Crafts",
                    "description": "Ancient alloys and crystal resonance create a true surgical ward.",
                },
            },
        },
        "shelter": {
            "room_id": "skerry_shelter",
            "structure": "basic_shelter",
            "level_field": "shelter_level",
            "max_level": 2,
            "tiers": {
                0: {
                    "name": "Barracks",
                    "cost": {"metal_scraps": 3, "torn_fabric": 2},
                    "dc": 2,
                    "skill": "Crafts",
                    "description": "Metal framing and fabric partitions — room for more people.",
                    "apply": {"barracks_spaces": 4, "max_workers": 3},
                },
                1: {
                    "name": "Commons",
                    "cost": {"ancient_alloys": 1, "crystal_shards": 1, "torn_fabric": 2},
                    "dc": 3,
                    "skill": "Crafts",
                    "description": "Proper quarters with shared space. Feels like a real home.",
                    "apply": {"barracks_spaces": 6, "max_workers": 4},
                },
            },
        },
        "junkyard": {
            "room_id": "skerry_junkyard",
            "structure": "junkyard",
            "level_field": "salvage_level",
            "max_level": 2,
            "tiers": {
                0: {
                    "name": "Salvage Yard",
                    "cost": {"metal_scraps": 2, "rope": 1},
                    "dc": 1,
                    "skill": "Crafts",
                    "description": "Sorting bins and a proper workspace — faster, cleaner salvage.",
                    "apply": {"max_workers": 2},
                },
                1: {
                    "name": "Reclamation Hub",
                    "cost": {"ancient_alloys": 1, "basic_tools": 1, "wire": 1},
                    "dc": 3,
                    "skill": "Crafts",
                    "description": "Precision tools and magnetic sorting. Nothing gets wasted.",
                    "apply": {"max_workers": 3},
                },
            },
        },
    }

    # Garden upgrades are special: they apply to whichever garden room the
    # player is standing in. The room_id is resolved dynamically.
    GARDEN_UPGRADE_TIERS = {
        0: {
            "name": "Expanded Garden",
            "new_plots": 5,  # 4 → 9
            "cost": {"basic_tools": 1, "rope": 1},
            "dc": 1,
            "skill": "Crafts",
            "description": "More raised beds and a simple irrigation channel. Room for five more plots.",
        },
        1: {
            "name": "Terraced Garden",
            "new_plots": 5,  # 9 → 14
            "cost": {"metal_scraps": 2, "basic_tools": 1},
            "dc": 2,
            "skill": "Crafts",
            "description": "Terraced stone beds with metal-framed trellises. Five more plots, better drainage.",
        },
        2: {
            "name": "Grand Garden",
            "new_plots": 6,  # 14 → 20
            "cost": {"ancient_alloys": 1, "crystal_shards": 1, "basic_tools": 1},
            "dc": 3,
            "skill": "Crafts",
            "description": "Crystal-lit growing beds fed by deep root channels. Six more plots — the garden's full potential.",
        },
    }

    def cmd_upgrade(self, args):
        """UPGRADE <structure> — upgrade a skerry building to the next tier."""
        if self.state["current_phase"] == "explorer":
            self._wrong_phase_narrate("steward", "upgrades")
            return
        if not args:
            display.error("Upgrade what? Usage: UPGRADE <structure>")
            return

        target = " ".join(args).lower()

        # Garden upgrade — resolve to current room or named garden
        if "garden" in target:
            self._upgrade_garden(target)
            return

        # Find matching upgrade definition
        upgrade_def = None
        for key, udef in self.UPGRADE_TIERS.items():
            if target in key or key in target:
                upgrade_def = udef
                break

        if not upgrade_def:
            display.error(f"Nothing called '{target}' can be upgraded.")
            return

        # Find the room
        room = self.skerry.get_room(upgrade_def["room_id"])
        if not room:
            display.error(f"The {target} hasn't been built yet.")
            return

        # Also update the game.rooms reference
        game_room = self.rooms.get(upgrade_def["room_id"])

        current_level = getattr(room, upgrade_def["level_field"], 0)
        if current_level >= upgrade_def["max_level"]:
            display.narrate(f"{room.name} is already at maximum upgrade level.")
            return

        tier = upgrade_def["tiers"].get(current_level)
        if not tier:
            display.error("No further upgrades available.")
            return

        # Check materials
        char = self.current_character()
        inv_counts = self._inventory_counts(char)
        current_room = self.current_room()
        if current_room:
            for item_id in current_room.items:
                inv_counts[item_id] = inv_counts.get(item_id, 0) + 1

        missing = []
        for mat, needed in tier["cost"].items():
            if inv_counts.get(mat, 0) < needed:
                mat_name = self.items_db.get(mat, {}).get("name", mat.replace("_", " ").title())
                missing.append(f"{needed}x {mat_name} (have {inv_counts.get(mat, 0)})")

        if missing:
            display.info(f"  Upgrade to {tier['name']}: {tier['description']}")
            display.error(f"  Missing materials: {', '.join(missing)}")
            return

        # Skill check
        skill_name = tier["skill"]
        dc = tier["dc"]
        invoke_bonus = self._consume_invoke_bonus(skill=skill_name)
        skill_val = char.get_skill(skill_name) + invoke_bonus
        label = f"{skill_name}+{invoke_bonus}" if invoke_bonus else skill_name
        total, shifts, dice_result = dice.skill_check(skill_val, dc)
        print(f"  {label}: {dice.roll_description(dice_result, skill_val, label)}")
        print(f"  DC: {dc:+d}")

        if shifts < 0:
            # Fail — lose one material
            lost_mat = list(tier["cost"].keys())[0]
            if current_room and lost_mat in current_room.items:
                current_room.remove_item(lost_mat)
            else:
                char.remove_from_inventory(lost_mat)
            lost_name = self.items_db.get(lost_mat, {}).get("name", lost_mat)
            display.warning(f"Upgrade failed! Lost 1x {lost_name} in the attempt.")
            return

        # Consume materials
        for mat, count in tier["cost"].items():
            for _ in range(count):
                if current_room and mat in current_room.items:
                    current_room.remove_item(mat)
                else:
                    char.remove_from_inventory(mat)

        # Apply upgrade
        new_level = current_level + 1
        setattr(room, upgrade_def["level_field"], new_level)
        if game_room:
            setattr(game_room, upgrade_def["level_field"], new_level)

        # Apply stat changes (barracks_spaces, max_workers, etc.)
        for attr, val in tier.get("apply", {}).items():
            setattr(room, attr, val)
            if game_room:
                setattr(game_room, attr, val)

        # Update room name and description
        room.name = tier["name"]
        if game_room:
            game_room.name = tier["name"]

        _TIER_DESCRIPTIONS = {
            "Infirmary": "Metal-framed cots and shelving line the walls. Proper bandaging and poultice-work can happen here.",
            "Hospital": "Ancient alloy fixtures hum with faint resonance. Crystal-focused light illuminates a surgical table.",
            "Barracks": "Metal-framed bunks line both walls, separated by fabric curtains. The ceiling is higher now, braced with riveted girders. Room for more people, and almost enough privacy.",
            "Commons": "Alloy-reinforced walls hold in warmth. Crystal sconces cast steady light over a shared table, bunks with actual mattresses, and a corner someone has already claimed for cards.",
            "Salvage Yard": "Sorting bins of bent metal line the perimeter, each labeled by material type. A sturdy workbench sits in the center, its surface scored with cut marks. The chaos is organized now.",
            "Reclamation Hub": "Magnetic racks hum faintly, pulling ferrous scraps into sorted channels. A precision cutting station gleams under crystal-focused light. Nothing that enters here goes to waste.",
        }
        new_desc = _TIER_DESCRIPTIONS.get(tier["name"], room.description)
        room.description = new_desc
        if game_room:
            game_room.description = new_desc

        # Update room aspect if defined for this tier
        _TIER_ASPECTS = {
            "Barracks": ["Cramped but Sturdy"],
            "Commons": ["Feels Like Home"],
            "Salvage Yard": ["Everything in Its Place"],
            "Reclamation Hub": ["Nothing Goes to Waste"],
            "Infirmary": ["A Steady Hand Heals"],
            "Hospital": ["Where Even the Worst Can Be Mended"],
        }
        new_aspects = _TIER_ASPECTS.get(tier["name"])
        if new_aspects:
            room.aspects = new_aspects
            if game_room:
                game_room.aspects = new_aspects

        display.success(f"Upgraded to {tier['name']}!")
        display.narrate(f"  {new_desc}")

        _TIER_HINTS = {
            ("apothecary", 1): ("Better facilities mean better care. Poultice-brewing and wound-tending",
                                "will go smoother with a +1 Lore bonus."),
            ("apothecary", 2): ("Surgical care is now possible. Even severe injuries can be treated here.",),
            ("shelter", 1): ("More beds, sturdier walls. Your people can rest properly now.",),
            ("shelter", 2): ("A real home. Morale will hold steadier with proper quarters.",),
            ("junkyard", 1): ("Better sorting means better yields. Your salvagers get a +1 bonus now.",),
            ("junkyard", 2): ("Precision reclamation. +2 bonus to salvage work — nothing wasted.",),
        }
        # Find which upgrade key we're working with
        upgrade_key = next(k for k, v in self.UPGRADE_TIERS.items() if v is upgrade_def)
        hints = _TIER_HINTS.get((upgrade_key, new_level))
        if hints:
            print()
            for line in hints:
                display.seed_speak(line)

        self._log_event("structure_upgraded", comic_weight=4,
                        room_name=tier["name"], room_id=upgrade_def["room_id"],
                        level=new_level)
        self.state["skerry"] = self.skerry.to_dict()

    def _upgrade_garden(self, target):
        """Handle UPGRADE GARDEN — add plots to a garden room."""
        # Resolve which garden: prefer current room if it's a garden, else first garden
        room = self.current_room()
        garden_room_id = None
        if room and room.id in self.skerry.gardens:
            garden_room_id = room.id
        else:
            # Try to find any garden
            garden_ids = list(self.skerry.gardens.keys())
            if not garden_ids:
                display.error("No garden built yet. BUILD GARDEN first.")
                return
            if len(garden_ids) == 1:
                garden_room_id = garden_ids[0]
            else:
                display.error("Multiple gardens — stand in the one you want to upgrade.")
                return

        garden_room = self.skerry.get_room(garden_room_id)
        game_room = self.rooms.get(garden_room_id)
        if not garden_room:
            display.error("Garden room not found.")
            return

        garden = self.skerry.gardens[garden_room_id]
        current_level = getattr(garden_room, "garden_level", 0)
        tier = self.GARDEN_UPGRADE_TIERS.get(current_level)

        if not tier:
            plot_count = len(garden.get("plots", []))
            display.narrate(f"{garden_room.name} is fully expanded ({plot_count} plots).")
            if plot_count >= 20:
                display.info("  BUILD GARDEN to start a new garden room.")
            return

        # Check materials
        char = self.current_character()
        inv_counts = self._inventory_counts(char)
        current_room = self.current_room()
        if current_room:
            for item_id in current_room.items:
                inv_counts[item_id] = inv_counts.get(item_id, 0) + 1

        missing = []
        for mat, needed in tier["cost"].items():
            if inv_counts.get(mat, 0) < needed:
                mat_name = self.items_db.get(mat, {}).get("name", mat.replace("_", " ").title())
                missing.append(f"{needed}x {mat_name} (have {inv_counts.get(mat, 0)})")

        if missing:
            plot_count = len(garden.get("plots", []))
            display.info(f"  {garden_room.name} ({plot_count} plots) → {tier['name']}: {tier['description']}")
            display.error(f"  Missing materials: {', '.join(missing)}")
            return

        # Skill check
        skill_name = tier["skill"]
        dc = tier["dc"]
        invoke_bonus = self._consume_invoke_bonus(skill=skill_name)
        skill_val = char.get_skill(skill_name) + invoke_bonus
        label = f"{skill_name}+{invoke_bonus}" if invoke_bonus else skill_name
        total, shifts, dice_result = dice.skill_check(skill_val, dc)
        print(f"  {label}: {dice.roll_description(dice_result, skill_val, label)}")
        print(f"  DC: {dc:+d}")

        if shifts < 0:
            lost_mat = list(tier["cost"].keys())[0]
            if current_room and lost_mat in current_room.items:
                current_room.remove_item(lost_mat)
            else:
                char.remove_from_inventory(lost_mat)
            lost_name = self.items_db.get(lost_mat, {}).get("name", lost_mat)
            display.warning(f"Upgrade failed! Lost 1x {lost_name} in the attempt.")
            return

        # Consume materials
        for mat, count in tier["cost"].items():
            for _ in range(count):
                if current_room and mat in current_room.items:
                    current_room.remove_item(mat)
                else:
                    char.remove_from_inventory(mat)

        # Add new plots
        max_plot_id = self.skerry._max_plot_id()
        new_plots = tier["new_plots"]
        for i in range(new_plots):
            garden["plots"].append(farming.make_empty_plot(max_plot_id + i + 1))
        garden["max_plots"] = len(garden["plots"])

        # Bump garden level
        new_level = current_level + 1
        garden_room.garden_level = new_level
        if game_room:
            game_room.garden_level = new_level

        # Update room name/description
        _GARDEN_DESCRIPTIONS = {
            "Expanded Garden": "More raised beds stretch across the turned earth, separated by narrow irrigation channels that glow faintly with root-light. The garden is starting to look like it could actually feed people.",
            "Terraced Garden": "Stone-terraced beds climb in tiers, each bordered by metal-framed trellises. The drainage channels run clean. The soil here is darker, richer — the world seed's roots run deeper.",
            "Grand Garden": "Crystal-lit growing beds spread across the full clearing, fed by deep root channels that pulse with green-gold light. Every square inch is cultivated. The air is warm and humid, heavy with the smell of growth.",
        }
        _GARDEN_ASPECTS = {
            "Expanded Garden": ["Growing Enough to Share"],
            "Terraced Garden": ["Terraces of Living Stone"],
            "Grand Garden": ["A Garden That Could Feed a Village"],
        }

        new_desc = _GARDEN_DESCRIPTIONS.get(tier["name"], garden_room.description)
        garden_room.description = new_desc
        garden_room.name = tier["name"]
        if game_room:
            game_room.description = new_desc
            game_room.name = tier["name"]

        new_aspects = _GARDEN_ASPECTS.get(tier["name"])
        if new_aspects:
            garden_room.aspects = new_aspects
            if game_room:
                game_room.aspects = new_aspects

        total_plots = len(garden["plots"])
        display.success(f"Upgraded to {tier['name']}! ({total_plots} plots now)")
        display.narrate(f"  {new_desc}")

        if total_plots >= 20:
            print()
            display.seed_speak("That's all the space this garden can hold. If you need more plots,")
            display.seed_speak("BUILD GARDEN again somewhere else on the skerry.")

        self._log_event("garden_upgraded", comic_weight=3,
                        room_name=tier["name"], room_id=garden_room_id,
                        level=new_level, total_plots=total_plots)
        self.state["skerry"] = self.skerry.to_dict()
