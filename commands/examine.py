"""Examine domain — look, ih, status, check, probe, investigate, scavenge, map, quests."""

import random

from engine import display, dice, aspects, map_renderer, farming, masterwork


class ExamineMixin:
    """Mixin providing examination and information commands for the Game class."""

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
            aspects_list = ", ".join(display.aspect_text(a) for a in enemy.get("aspects", []))
            if aspects_list:
                print(f"  Aspects: {aspects_list}")
            return

        # Look at artifact at this location
        for art_id, art in self._artifacts_in_room(room.id):
            if target in art.get("name", "").lower() or target == art_id or target in art.get("hint_sensory", "").lower():
                display.header(art["name"])
                display.narrate(f"  {art.get('description', '')}")
                if art.get("aspects"):
                    aspects_list = ", ".join(display.aspect_text(a) for a in art["aspects"])
                    print(f"  Aspects: {aspects_list}")
                return

        # Look at specimen in room
        for item_id in room.items:
            spec = self.specimens_db.get(item_id)
            if spec and (target in spec["name"].lower() or target == item_id):
                display.header(spec["name"])
                display.narrate(f"  {spec.get('description', '')}")
                display.info(f"  Type: {spec['specimen_type']} | Family: {spec['family']}")
                return

        # Look at item in room
        item_id, item = self._find_entity(room.items, target, self.items_db)
        if item:
            name = masterwork.get_display_name(item_id, self.items_db)
            display.header(name)
            if masterwork.is_masterwork(item_id) and item.get("masterwork_desc"):
                display.narrate(f"  {item['masterwork_desc']}")
            else:
                display.narrate(f"  {item.get('description', '')}")
            return

        # Look at room feature (interactable objects — roots, consoles, etc.)
        for feature in room.features:
            if target in feature.get("keywords", []) or target in feature.get("name", "").lower():
                display.header(feature["name"])
                display.narrate(f"  {feature['description']}")
                return

        # Look at specimen in inventory
        char = self.current_character()
        for item_id in char.inventory:
            spec = self.specimens_db.get(item_id)
            if spec and (target in spec["name"].lower() or target == item_id):
                display.header(spec["name"])
                display.narrate(f"  {spec.get('description', '')}")
                display.info(f"  Type: {spec['specimen_type']} | Family: {spec['family']}")
                return

        # Look at artifact in inventory
        art_id, art = self._find_entity(char.inventory, target, self.artifacts_db)
        if art:
            display.header(art["name"])
            display.narrate(f"  {art.get('description', '')}")
            if art.get("aspects"):
                aspects_list = ", ".join(display.aspect_text(a) for a in art["aspects"])
                print(f"  Aspects: {aspects_list}")
            if art.get("stat_bonuses"):
                bonuses = ", ".join(f"+{v} {k}" for k, v in art["stat_bonuses"].items())
                display.info(f"  Bonuses (if kept): {bonuses}")
            display.info(f"  Mote value (if fed): {art.get('mote_value', 1)}")
            return

        # Look at item in inventory
        item_id, item = self._find_entity(char.inventory, target, self.items_db)
        if item:
            name = masterwork.get_display_name(item_id, self.items_db)
            display.header(name)
            if masterwork.is_masterwork(item_id) and item.get("masterwork_desc"):
                display.narrate(f"  {item['masterwork_desc']}")
            else:
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
                aspects_list = ", ".join(display.aspect_text(a) for a in art["aspects"])
                print(f"  Aspects: {aspects_list}")
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

        # Items (including specimens and masterwork)
        if room.items:
            for item_id in room.items:
                if masterwork.is_masterwork(item_id):
                    mw_name = masterwork.get_display_name(item_id, self.items_db)
                    print(f"  {display.BRIGHT_WHITE}{display.BOLD}{mw_name}{display.RESET}")
                elif item_id in self.items_db:
                    print(f"  {display.item_name(self.items_db[item_id]['name'])}")
                elif item_id in self.specimens_db:
                    spec = self.specimens_db[item_id]
                    print(f"  {display.BRIGHT_GREEN}{spec['name']}{display.RESET} {display.DIM}(specimen){display.RESET}")
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

        # Artifacts in this room
        for art_id, art in self._artifacts_in_room(room.id):
            status = self.state.get("artifacts_status", {}).get(art_id)
            if status == "discovered":
                print(f"  {display.BRIGHT_WHITE}{display.BOLD}{art['name']}{display.RESET} {display.DIM}(artifact){display.RESET}")
            else:
                hint = art.get("hint_sensory", "something unusual")
                print(f"  {display.DIM}You notice {hint}.{display.RESET}")
            has_contents = True

        # Room features (interactable objects)
        for feature in room.features:
            print(f"  {display.aspect_text(feature['name'])}")
            has_contents = True

        if not has_contents:
            display.narrate("Nothing of interest here.")

    def cmd_status(self, args):
        char = self.current_character()
        display.display_character_sheet(char)
        print()
        display.display_seed(self.seed.to_dict(), name=self.seed_name)

    def cmd_check(self, args):
        if not args:
            display.error(f"Check what? Try CHECK SEED, CHECK <npc name>, CHECK SKERRY, or CHECK STORES.")
            return

        target = " ".join(args).lower()

        if target == "stores":
            if not self.skerry.has_structure("storehouse"):
                display.error("No storehouse built yet. Build one to track food stores.")
                return
            population = 2 + len(self.state.get("recruited_npcs", []))
            display.display_food_stores(self.skerry.food_stores, population, self.state["day"])
            return

        if target == "vault":
            if not self.skerry.has_structure("storehouse"):
                display.error("No storehouse built yet. Build one to access the seed vault.")
                return
            display.display_seed_vault(self.skerry.seed_vault)
            return

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

        if target == "workshop":
            workshop = self.skerry.get_room("skerry_workshop")
            if not workshop:
                display.error("No workshop built yet.")
                return
            display.header("Workshop")
            tool_bonus = 1 + workshop.tool_level
            print(f"  Tool Level: {workshop.tool_level}/3")
            print(f"  Crafts bonus: +{tool_bonus} (base +1, tools +{workshop.tool_level})")
            # Show workshop-only recipes
            workshop_recipes = [r for r in self.recipes_db.values()
                                if r.get("requires_room") == "skerry_workshop"]
            if workshop_recipes:
                names = [r["name"] for r in workshop_recipes]
                print(f"  Workshop-only recipes: {', '.join(names)}")
            # Show queue
            queue = self.state.get("workshop_queue", [])
            if queue:
                queue_names = [self.recipes_db.get(rid, {}).get("name", rid) for rid in queue]
                print(f"  Craft queue: {', '.join(queue_names)}")
            else:
                print(f"  Craft queue: {display.DIM}empty (use QUEUE <recipe> to add){display.RESET}")
            # Show items in workshop
            if workshop.items:
                from collections import Counter
                counts = Counter(workshop.items)
                mat_parts = []
                for item_id, count in counts.items():
                    name = self.items_db.get(item_id, {}).get("name", item_id.replace("_", " ").title())
                    mat_parts.append(f"{count}x {name}")
                print(f"  Materials on hand: {', '.join(mat_parts)}")
            return

        if target in ("apothecary", "infirmary", "hospital"):
            healing_room = self.skerry.get_room("skerry_apothecary")
            if not healing_room:
                display.error("No apothecary built yet.")
                return
            display.header(healing_room.name)
            tier_names = {0: "Apothecary", 1: "Infirmary", 2: "Hospital"}
            tier_label = tier_names.get(healing_room.healing_level, "Apothecary")
            heal_bonus = healing_room.healing_level
            print(f"  Tier: {tier_label} (Level {healing_room.healing_level}/2)")
            print(f"  Lore bonus: +{heal_bonus}")
            # Show what this tier enables
            tier_perks = {
                0: "Bandage-brewing, basic wound tending.",
                1: "Poultice preparation, mild injuries heal faster, +1 Lore bonus.",
                2: "Surgical care for severe injuries, -1 treatment DC, +2 Lore bonus.",
            }
            print(f"  Capabilities: {tier_perks.get(healing_room.healing_level, '')}")
            # Show upgrade info
            from commands.building import BuildingMixin
            apoth_tiers = BuildingMixin.UPGRADE_TIERS.get("apothecary", {})
            next_tier = apoth_tiers.get("tiers", {}).get(healing_room.healing_level)
            if next_tier:
                cost_str = ", ".join(f"{v}x {self.items_db.get(k, {}).get('name', k)}"
                                    for k, v in next_tier["cost"].items())
                print(f"  Next upgrade: {next_tier['name']} — needs: {cost_str} ({next_tier['skill']} DC {next_tier['dc']})")
            else:
                print(f"  {display.DIM}Fully upgraded.{display.RESET}")
            # Show apothecary-only recipes
            apoth_recipes = [r for r in self.recipes_db.values()
                             if r.get("requires_room") == "skerry_apothecary"]
            if apoth_recipes:
                names = [r["name"] for r in apoth_recipes]
                print(f"  Apothecary recipes: {', '.join(names)}")
            # Show items in room
            if healing_room.items:
                from collections import Counter
                counts = Counter(healing_room.items)
                mat_parts = []
                for item_id, count in counts.items():
                    name = self.items_db.get(item_id, {}).get("name", item_id.replace("_", " ").title())
                    mat_parts.append(f"{count}x {name}")
                print(f"  Supplies on hand: {', '.join(mat_parts)}")
            return

        if target == "skerry":
            display.header("Skerry Status")
            cap = self.skerry.population_cap()
            current = 2 + len(self.state.get("recruited_npcs", []))
            print(f"  Population: {current}/{cap}")
            print()
            for room in self.skerry.get_all_rooms():
                print(f"  {display.npc_name(room.name)}")
                if room.role:
                    # Who lives here
                    settled_names = [n["name"] for n in self.npcs_db.values()
                                     if n.get("recruited") and n.get("settled_room") == room.id]
                    # Explorer and steward live in the basic shelter
                    if room.id == "skerry_shelter":
                        settled_names = [self.explorer.name, self.steward.name] + settled_names
                    beds = f"{len(settled_names)}/{room.max_workers}"
                    if settled_names:
                        print(f"    {display.DIM}Residents:{display.RESET} {', '.join(settled_names)} {display.DIM}({beds}){display.RESET}")
                    else:
                        print(f"    {display.DIM}Residents: — ({beds} beds){display.RESET}")
                    # Who's working on this room's task
                    task_for_role = self._role_to_task(room.role)
                    worker_names = [n["name"] for n in self.npcs_db.values()
                                    if n.get("recruited") and n.get("assignment") == task_for_role]
                    if worker_names:
                        print(f"    {display.DIM}Working:{display.RESET}   {', '.join(worker_names)}")
                    else:
                        print(f"    {display.DIM}Working:   —{display.RESET}")
                elif room.id == "skerry_landing":
                    node_count = sum(1 for dest in room.exits.values()
                                     if not dest.startswith("skerry_"))
                    print(f"    {display.DIM}{node_count} node{'s' if node_count != 1 else ''} within sensing distance{display.RESET}")
                else:
                    print(f"    {display.DIM}—{display.RESET}")

            # Shared inventory counts for upgradable + buildable sections
            inv_counts = self._inventory_counts(self.steward)
            room = self.current_room()
            if room:
                for item_id in room.items:
                    inv_counts[item_id] = inv_counts.get(item_id, 0) + 1
            npc_count = len(self.state.get("recruited_npcs", []))

            # Show upgradable structures
            from commands.building import BuildingMixin
            upgrade_lines = []
            for key, udef in BuildingMixin.UPGRADE_TIERS.items():
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
            if upgrade_lines:
                print(f"\n  {display.BOLD}Upgradable:{display.RESET}")
                for line in upgrade_lines:
                    print(line)

            if self.skerry.expandable:
                print(f"\n  {display.BOLD}Buildable:{display.RESET}")
                for tmpl in self.skerry.expandable:
                    reqs = tmpl.get("requires", {})
                    # Hide structures the seed hasn't unlocked yet
                    if self.seed.growth_stage < reqs.get("seed_stage", 0):
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
                settled_room_id = npc.get("settled_room")
                if settled_room_id:
                    sr = self.skerry.get_room(settled_room_id)
                    display.info(f"  Settled in: {sr.name if sr else settled_room_id}")
                else:
                    display.info(f"  Settled in: nowhere (unsettled)")
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

    def cmd_probe(self, args):
        if not args:
            display.error("Probe what? Specify an item or object to examine.")
            return

        target = " ".join(args).lower()
        room = self.current_room()

        # Check artifacts at this location
        for art_id, art in self._artifacts_in_room(room.id):
            if target in art.get("name", "").lower() or target == art_id or target in art.get("hint_sensory", "").lower():
                if art_id not in self.state.get("artifacts_status", {}):
                    # Undiscovered — can't PROBE what you haven't noticed
                    display.narrate("You sense something here, but you'd need to INVESTIGATE the room to find it.")
                else:
                    display.header(art["name"])
                    display.narrate(self.sub(art["description"]))
                return

        # Check garden plots (PROBE PLOT 1, PROBE PLOT 2, etc.)
        if target.startswith("plot"):
            plot_num = target.replace("plot", "").strip()
            try:
                plot_id = int(plot_num)
                plot = self.skerry.get_plot(plot_id)
                if plot and plot.get("plant"):
                    display.display_probe_plant(plot["plant"], plot_id)
                    return
                elif plot:
                    display.info(f"  Plot {plot_id} is empty.")
                    return
            except (ValueError, TypeError):
                pass

        # Check specimens in room
        phase = self.state["current_phase"]
        for item_id in room.items:
            spec = self.specimens_db.get(item_id)
            if spec and (target in spec["name"].lower() or target == item_id):
                if phase == "steward":
                    display.display_probe_specimen(spec)
                else:
                    display.header(spec["name"])
                    display.narrate(f"  {spec.get('description', '')}")
                    display.info(f"  Type: {spec['specimen_type']} | Family: {spec['family']}")
                return

        # Check specimens in inventory
        char = self.current_character()
        for item_id in char.inventory:
            spec = self.specimens_db.get(item_id)
            if spec and (target in spec["name"].lower() or target == item_id):
                if phase == "steward":
                    display.display_probe_specimen(spec)
                else:
                    display.header(spec["name"])
                    display.narrate(f"  {spec.get('description', '')}")
                    display.info(f"  Type: {spec['specimen_type']} | Family: {spec['family']}")
                return

        # Check items in room
        item_id, item = self._find_entity(room.items, target, self.items_db)
        if item:
            name = masterwork.get_display_name(item_id, self.items_db)
            display.header(name)
            if masterwork.is_masterwork(item_id) and item.get("masterwork_desc"):
                display.narrate(self.sub(item["masterwork_desc"]))
            else:
                display.narrate(self.sub(item["description"]))
            display.info(f"  Mote value: {item.get('mote_value', 1)}")
            return

        # Check inventory items
        inv_item_id, inv_item = self._find_entity(list(char.inventory), target, self.items_db)
        if inv_item:
            name = masterwork.get_display_name(inv_item_id, self.items_db)
            display.header(name)
            if masterwork.is_masterwork(inv_item_id) and inv_item.get("masterwork_desc"):
                display.narrate(self.sub(inv_item["masterwork_desc"]))
            else:
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
        for npc_id in self.state.get("recruited_npcs", []):
            npc = self.npcs_db.get(npc_id, {})
            if npc.get("following") and npc_id not in npc_pool:
                npc_pool.append(npc_id)
        npc_id, npc = self._find_entity(npc_pool, target, self.npcs_db)
        if npc:
            display.header(npc["name"])
            display.narrate(self.sub(npc.get("description", "You see nothing unusual.")))
            npc_aspects = aspects._flatten_npc_aspects(npc)
            if npc_aspects:
                for a in npc_aspects:
                    print(f"    {display.aspect_text(a)}")
            if npc.get("skills"):
                skills_str = ", ".join(f"{k} {v}" for k, v in npc["skills"].items())
                display.info(f"  Skills: {skills_str}")
            return

        display.narrate(f"Nothing called '{target}' to probe here.")

    def cmd_scavenge(self, args):
        if self.state["current_phase"] == "steward":
            self._wrong_phase_narrate("explorer", "scavenge")
            return
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

        char = self.current_character()
        invoke_bonus = self._consume_invoke_bonus()
        skill_val = char.get_skill("Investigate") + invoke_bonus
        total, shifts, dice_result = dice.skill_check(skill_val, difficulty)

        label = f"Investigate+{invoke_bonus}" if invoke_bonus else "Investigate"
        if times_searched > 0:
            display.info(f"  You've searched here {times_searched} time{'s' if times_searched != 1 else ''} before. (DC {difficulty})")
        print(f"  Investigate: {dice.roll_description(dice_result, skill_val, label)} vs DC {difficulty}")

        scavenge_counts[room.id] = times_searched + 1

        if shifts >= 0:
            # Find something from the zone's scavenge pool
            zone_id = room.zone
            zone = self.state["zones"].get(zone_id, {})
            possible_loot = zone.get("scavenge_pool", ["metal_scraps", "torn_fabric", "wire"])

            found = random.choice(possible_loot)
            # Look up name from items_db OR specimens_db
            item_info = self.items_db.get(found, {})
            specimen_info = self.specimens_db.get(found)
            found_name = specimen_info["name"] if specimen_info else item_info.get("name", found)
            found_suffix = " (specimen)" if specimen_info else ""

            if self._can_take_item(char, found, allow_overflow=False):
                char.add_to_inventory(found)
                display.success(f"  Found: {found_name}!{found_suffix}")
            else:
                room.add_item(found)
                display.success(f"  Found: {found_name}!{found_suffix}")
                display.narrate("  But your pack is full. You set it on the ground.")

            if shifts >= 3:  # Succeed with style
                bonus = random.choice(possible_loot)
                bonus_info = self.items_db.get(bonus, {})
                bonus_spec = self.specimens_db.get(bonus)
                bonus_name = bonus_spec["name"] if bonus_spec else bonus_info.get("name", bonus)
                bonus_suffix = " (specimen)" if bonus_spec else ""

                if self._can_take_item(char, bonus, allow_overflow=False):
                    char.add_to_inventory(bonus)
                    display.success(f"  Excellent work! Also found: {bonus_name}!{bonus_suffix}")
                else:
                    room.add_item(bonus)
                    display.success(f"  Excellent work! Also found: {bonus_name}!{bonus_suffix}")
                    display.narrate("  But you can't carry any more. You set it on the ground.")

            self._log_event("scavenge_success", comic_weight=2,
                            item_found=found,
                            item_name=specimen_info["name"] if specimen_info else item_info.get("name", found),
                            zone=zone_id)
            if not self.state.get("tutorial_complete"):
                self.state["tutorial_scavenge_done"] = True
        else:
            display.narrate("  You search carefully but find nothing useful this time.")

    def cmd_investigate(self, args):
        """INVESTIGATE — active Notice check to discover artifacts in the room."""
        room = self.current_room()
        if not room:
            return

        # Find undiscovered artifacts in this room
        undiscovered = []
        for art_id, art in self._artifacts_in_room(room.id):
            if art_id not in self.state.get("artifacts_status", {}):
                undiscovered.append((art_id, art))

        if not undiscovered:
            display.narrate("You search the room carefully but find nothing hidden.")
            return

        char = self.current_character()
        invoke_bonus = self._consume_invoke_bonus()
        notice_val = char.get_skill("Notice") + invoke_bonus
        label = f"Notice+{invoke_bonus}" if invoke_bonus else "Notice"

        for art_id, art in undiscovered:
            dc = art.get("notice_dc", 2)
            total, shifts, dice_result = dice.skill_check(notice_val, dc)
            print(f"  {label}: {dice.roll_description(dice_result, notice_val, label)} vs DC {dc}")

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
                self._log_event("artifact_investigated", comic_weight=3,
                                artifact_id=art_id, artifact_name=art["name"])
            else:
                display.narrate("You search carefully but don't find the source of what you sensed.")

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
            if zone_id == "skerry":
                discovered = any(
                    r.discovered for r in self.rooms.values()
                    if r.id.startswith("skerry_")
                )
            else:
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

    def cmd_aspects(self, args):
        """ASPECTS — Show all invokable aspects, with used ones dimmed."""
        char = self.current_character()
        context = "combat" if self.in_combat else "recruit" if self.in_recruit else "combat"
        all_aspects = aspects.collect_invokable_aspects(self, context=context)

        available = [(a, s) for a, s in all_aspects if a not in self.scene_invoked_aspects]
        used = [(a, s) for a, s in all_aspects if a in self.scene_invoked_aspects]

        print(f"\n{display.BOLD}{display.BRIGHT_CYAN}═══ Aspects ═══{display.RESET}  (FP: {char.fate_points})")
        print()

        if available:
            for a, source in available:
                print(f"  {display.aspect_text(a)} {display.DIM}({source}){display.RESET}")
        else:
            print(f"  {display.DIM}No aspects remaining to invoke.{display.RESET}")

        if used:
            print()
            for a, source in used:
                print(f"  {display.DIM}\u2717 {a} ({source}) (used){display.RESET}")

        print()
        display.info("  INVOKE <aspect> to spend 1 FP for +2 on your next action.")

    def cmd_help(self, args):
        display.display_help(self.state["current_phase"], seed_name=self.seed_name)
