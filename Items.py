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
    if name not in C.NON_RECIPE_INGREDIENTS
}

# ─── Character Unlock Items ──────────────────────────────────────────────────
# Characters are AP ITEMS, EXCEPT fusion-result characters (obtained only by
# performing the fusion in-game, which fires a "Fuse: <result>" check).
#
# Among the non-fusion-result characters, only a small set are MEANINGFUL
# progression: the "LEAF BASES" — characters that some fusion recipe requires
# as a base ingredient AND that are not themselves fusion results (so they can't
# be fused for; you must be granted them). Everything else (standalone BATTLE
# fighters that gate no fusion) is FILLER — still a receivable character item,
# but it unlocks nothing downstream, so the generator treats it as non-essential.
#
# Chains are handled automatically by the recursive char_rule in Regions.py:
# e.g. Super Baby 2 <- Super Baby 1 <- Baby Vegeta <- (Baby + Vegeta). Each rung
# is its own Fuse check; only the true leaves (here Vegeta etc.) need to be items.
_FUSION_RESULTS = {n for n, (k, _r) in R.RECIPES.items() if k == "FUSION"}

# Every character referenced as a base part of any fusion recipe.
_FUSION_CHAR_PARTS = {
    part
    for n, (k, parts) in R.RECIPES.items() if k == "FUSION"
    for part in parts
    if part in set(C.CHARACTERS)
}
# Leaf bases = fusion base-parts that are NOT themselves fusion results.
_LEAF_BASE_CHARS = [c for c in C.CHARACTERS if c in (_FUSION_CHAR_PARTS - _FUSION_RESULTS)]

# All non-starter, non-fusion-result roster characters that have a recipe entry
# (the BATTLE-unlock pool). The ones that aren't leaf bases become filler.
_UNLOCKABLE_CHARS = [c for c in C.CHARACTERS
                     if c in R.RECIPES and c not in _FUSION_RESULTS]
_FILLER_CHARS = [c for c in _UNLOCKABLE_CHARS if c not in set(_LEAF_BASE_CHARS)]

# Every non-fusion-result character still gets a "<name> Character" item so it
# can be received; classification (progression vs filler) is decided in classify().
CHARACTER_UNLOCK_ITEMS = {
    f"{name} Character": BT2_BASE_ID + 0x600 + i
    for i, name in enumerate(_UNLOCKABLE_CHARS)
}
# The subset that is genuine progression (gates a fusion).
PROGRESSION_CHARACTER_ITEMS = {
    f"{name} Character" for name in _LEAF_BASE_CHARS
}
# The subset that gates nothing -> filler.
FILLER_CHARACTER_ITEMS = {
    f"{name} Character" for name in _FILLER_CHARS
}

# ─── Ability Items (useful / filler) ─────────────────────────────────────────
ABILITY_ITEMS = {
    f"Z-Item: {name}": BT2_BASE_ID + 0x400 + i
    for i, name in enumerate(C.ABILITY_ITEM_ADDR.keys())
}

# ─── Support Items (useful / filler) ─────────────────────────────────────────
# Support-type Z-Items (~105). Same flag layout as abilities; pooled as filler.
# Distinct "Z-Support:" prefix and 0x800 id base to avoid colliding with the
# 0x400-based ability ids.
SUPPORT_ITEMS = {
    f"Z-Support: {name}": BT2_BASE_ID + 0x800 + i
    for i, name in enumerate(C.SUPPORT_ITEM_ADDR.keys())
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
item_table.update(CHARACTER_UNLOCK_ITEMS)
item_table.update(ABILITY_ITEMS)
item_table.update(SUPPORT_ITEMS)
item_table.update(FILLER_ITEMS)
item_table.update(MCGUFFIN_ITEMS)
item_table.update(DRAGONBALL_ITEMS)
item_table.update(SHOP_ITEMS)


# Classification helper
_PROGRESSION = (set(SCENARIO_ITEMS) | set(FUSION_INGREDIENT_ITEMS)
                | PROGRESSION_CHARACTER_ITEMS  # only leaf-base chars gate fusions
                | set(MCGUFFIN_ITEMS) | set(DRAGONBALL_ITEMS)
                | set(SHOP_ITEMS))  # Shop Restock GATES shop locations -> must be
                                    # progression, or the generator treats the
                                    # restock-gated shop slots as unreachable and
                                    # fill fails (FillError: no more spots).
_FILLER = set(FILLER_ITEMS) | FILLER_CHARACTER_ITEMS  # non-gating character items
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
