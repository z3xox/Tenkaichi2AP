from BaseClasses import Item, ItemClassification
from .data import Constants as C
from .data import Recipes as R

BT2_BASE_ID = 0xDB7000  # distinct namespace from B3 (0xDB3000)


class BT2Item(Item):
    game = "Dragon Ball Z Budokai Tenkaichi 2"


# ─── Scenario Unlock Items (ENFORCE gates / progression) ─────────────────────
# One per Dragon Adventure scenario. Withholding these locks the scenario.
SCENARIO_ITEMS = {
    f"{name} Unlock": BT2_BASE_ID + 0x100 + i
    for i, (name, _count) in enumerate(C.SCENARIOS)
}

# ─── Fusion Ingredient Items (progression) ───────────────────────────────────
# The fusion-type Z-Items AP distributes; recipes consume these to make
# fusion characters. Named "Ingredient: X" to avoid colliding with any
# same-named character.
FUSION_INGREDIENT_ITEMS = {
    f"Ingredient: {name}": BT2_BASE_ID + 0x200 + i
    for i, name in enumerate(C.FUSION_ITEM_ADDR.keys())
}

# ─── Ability Items (useful / filler) ─────────────────────────────────────────
ABILITY_ITEMS = {
    f"Z-Item: {name}": BT2_BASE_ID + 0x400 + i
    for i, name in enumerate(C.ABILITY_ITEM_ADDR.keys())
}

# ─── Filler (Zeni) ───────────────────────────────────────────────────────────
FILLER_ITEMS = {
    "Zeni x1000":  BT2_BASE_ID + 0x010,
    "Zeni x5000":  BT2_BASE_ID + 0x011,
    "Zeni x10000": BT2_BASE_ID + 0x012,
}

# ─── Time Scroll (McGuffin goal item, progression) ───────────────────────────
# A single named item placed into the pool `time_scrolls_total` times. Collect
# `time_scrolls_required` to satisfy the time_scrolls goal. Thematically ties to
# BT2's what-if / alternate-timeline sagas ("repair the fractured timelines").
TIME_SCROLL_ITEM = "Time Scroll"
MCGUFFIN_ITEMS = {
    TIME_SCROLL_ITEM: BT2_BASE_ID + 0x020,
}

# ─── Shop Restock (progression-ish item that reveals more shop checks) ────────
SHOP_RESTOCK_ITEM = "Shop Restock"
SHOP_ITEMS = {
    SHOP_RESTOCK_ITEM: BT2_BASE_ID + 0x040,
}

# ─── Dragon Ball items (progression) ─────────────────────────────────────────
# The 7 Dragon Balls are AP ITEMS, not in-game collectibles. The client enforces
# the in-game DB flags to match exactly what AP has granted (clearing any the
# game hands out via random free events). Gather all 7 to summon at the node.
DRAGONBALL_ITEM_NAMES = [
    "1 Star Dragon Ball", "2 Star Dragon Ball", "3 Star Dragon Ball",
    "4 Star Dragon Ball", "5 Star Dragon Ball", "6 Star Dragon Ball",
    "7 Star Dragon Ball",
]
DRAGONBALL_ITEMS = {
    name: BT2_BASE_ID + 0x030 + i for i, name in enumerate(DRAGONBALL_ITEM_NAMES)
}

# ─── Master table ────────────────────────────────────────────────────────────
item_table: dict[str, int] = {}
item_table.update(SCENARIO_ITEMS)
item_table.update(FUSION_INGREDIENT_ITEMS)
item_table.update(ABILITY_ITEMS)
item_table.update(FILLER_ITEMS)
item_table.update(MCGUFFIN_ITEMS)
item_table.update(DRAGONBALL_ITEMS)
item_table.update(SHOP_ITEMS)


# Classification helper
_PROGRESSION = (set(SCENARIO_ITEMS) | set(FUSION_INGREDIENT_ITEMS)
                | set(MCGUFFIN_ITEMS) | set(DRAGONBALL_ITEMS)
                | set(SHOP_ITEMS))  # Shop Restock GATES shop locations -> must be
                                    # progression, or the generator treats the
                                    # restock-gated shop slots as unreachable and
                                    # fill fails (FillError: no more spots).
_FILLER = set(FILLER_ITEMS)
_USEFUL = set()


def classify(name: str) -> ItemClassification:
    if name in _PROGRESSION:
        return ItemClassification.progression
    if name in _FILLER:
        return ItemClassification.filler
    return ItemClassification.useful


def create_item(world, name: str) -> BT2Item:
    return BT2Item(name, classify(name), item_table[name], world.player)


def ingredient_item_name(ingredient: str) -> str:
    """Map a recipe ingredient (fusion-item name) to its AP item name."""
    return f"Ingredient: {ingredient}"
