"""Masterwork item system — quality craftsmanship with social value.

Masterwork items are stored as "masterwork:<base_id>" in inventory/room item lists.
They display with a ✦ prefix, can be gifted to NPCs for mood/loyalty boosts,
and enhance workrooms with passive skill bonuses.
"""

PREFIX = "masterwork:"


def is_masterwork(item_id):
    """Check if an item ID represents a masterwork item."""
    return item_id.startswith(PREFIX)


def base_id(item_id):
    """Strip the masterwork prefix, returning the base item ID."""
    if is_masterwork(item_id):
        return item_id[len(PREFIX):]
    return item_id


def masterwork_id(item_id):
    """Add the masterwork prefix to a base item ID."""
    if is_masterwork(item_id):
        return item_id
    return PREFIX + item_id


def get_item_data(item_id, items_db):
    """Look up item data, transparently handling masterwork prefix."""
    return items_db.get(base_id(item_id))


def get_display_name(item_id, items_db):
    """Return display name: '✦ Rope' for masterwork, 'Rope' for normal."""
    data = get_item_data(item_id, items_db)
    name = data["name"] if data else base_id(item_id).replace("_", " ").title()
    if is_masterwork(item_id):
        return f"✦ {name}"
    return name
