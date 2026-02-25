"""Room model — locations in void zones and on the skerry."""


class Room:
    def __init__(self, data):
        self.id = data["id"]
        self.name = data["name"]
        self.description = data["description"]
        self.zone = data.get("zone", "skerry")
        self.exits = dict(data.get("exits", {}))
        self.locked_exits = dict(data.get("locked_exits", {}))
        self.aspects = list(data.get("aspects", []))
        self.items = list(data.get("items", []))
        self.npcs = list(data.get("npcs", []))
        self.enemies = list(data.get("enemies", []))
        self.features = list(data.get("features", []))
        self.discovered = data.get("discovered", False)
        # Skerry-specific
        self.structures = list(data.get("structures", []))
        self.assigned_npcs = list(data.get("assigned_npcs", []))
        self.resources = dict(data.get("resources", {}))
        self.role = data.get("role")
        self.max_workers = data.get("max_workers", 2)
        self.tool_level = data.get("tool_level", 0)
        self.healing_level = data.get("healing_level", 0)
        self.barracks_spaces = data.get("barracks_spaces", 0)

    def discover(self):
        """Mark room as discovered."""
        self.discovered = True

    def remove_item(self, item_id):
        """Remove an item from the room. Returns True if found."""
        if item_id in self.items:
            self.items.remove(item_id)
            return True
        return False

    def add_item(self, item_id):
        """Add an item to the room."""
        self.items.append(item_id)

    def remove_npc(self, npc_id):
        """Remove an NPC from the room."""
        if npc_id in self.npcs:
            self.npcs.remove(npc_id)
            return True
        return False

    def add_npc(self, npc_id):
        """Add an NPC to the room."""
        if npc_id not in self.npcs:
            self.npcs.append(npc_id)

    def remove_enemy(self, enemy_id):
        """Remove an enemy from the room."""
        if enemy_id in self.enemies:
            self.enemies.remove(enemy_id)
            return True
        return False

    def has_enemies(self):
        """Check if room has active enemies."""
        return len(self.enemies) > 0

    def get_exit_directions(self):
        """Return list of available exit directions."""
        return list(self.exits.keys())

    def to_dict(self):
        """Serialize to dict for saving."""
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "zone": self.zone,
            "exits": self.exits,
            "aspects": self.aspects,
            "items": self.items,
            "npcs": self.npcs,
            "enemies": self.enemies,
            "features": self.features,
            "discovered": self.discovered,
        }
        if self.locked_exits:
            d["locked_exits"] = self.locked_exits
        if self.structures:
            d["structures"] = self.structures
        if self.assigned_npcs:
            d["assigned_npcs"] = self.assigned_npcs
        if self.resources:
            d["resources"] = self.resources
        if self.role is not None:
            d["role"] = self.role
        if self.max_workers:
            d["max_workers"] = self.max_workers
        if self.tool_level:
            d["tool_level"] = self.tool_level
        if self.healing_level:
            d["healing_level"] = self.healing_level
        if self.barracks_spaces:
            d["barracks_spaces"] = self.barracks_spaces
        return d
