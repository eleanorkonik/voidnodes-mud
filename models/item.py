"""Item model — materials, artifacts, crafted items."""


class Item:
    def __init__(self, data):
        self.id = data["id"]
        self.name = data["name"]
        self.description = data["description"]
        self.item_type = data.get("type", "material")  # material, artifact, crafted, consumable
        self.aspects = list(data.get("aspects", []))
        self.mote_value = data.get("mote_value", 1)  # motes gained when fed to Tuft
        self.stat_bonuses = dict(data.get("stat_bonuses", {}))  # {skill: bonus} when kept
        self.stackable = data.get("stackable", True)
        self.special = data.get("special", None)  # special effect ID (e.g., "eliok_house")
        self.slot = data.get("slot", None)  # body slot for wearable items

    def to_dict(self):
        """Serialize to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.item_type,
            "aspects": self.aspects,
            "mote_value": self.mote_value,
            "stat_bonuses": self.stat_bonuses,
            "stackable": self.stackable,
            "special": self.special,
            "slot": self.slot,
        }
