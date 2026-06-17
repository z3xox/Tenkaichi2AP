from .data import Constants as C

BT2_LOC_BASE = 0xDB7000

# ─── Mission (Dragon Adventure fight) locations ──────────────────────────────
# 200 missions, one per fight byte at 0x63100C + index. Location id is the
# linear mission index. Name encodes scenario + mission for readability.
MISSION_LOCATIONS: dict[str, int] = {}
_mission_meta: dict[str, tuple[int, int, int]] = {}  # name -> (scenario_idx, mission_idx, addr)

_lin = 0
for _si, (_scen, _count) in enumerate(C.SCENARIOS):
    for _mi in range(_count):
        _addr = C.DA_FIGHTS_BASE + _lin
        _name = f"{_scen} - Mission {_mi:02d}"
        MISSION_LOCATIONS[_name] = BT2_LOC_BASE + 0x0000 + _lin
        _mission_meta[_name] = (_si, _mi, _addr)
        _lin += 1

# ─── Character unlock locations ──────────────────────────────────────────────
# 129 roster flags at 0x6335E8 + index*4. Only the unlockable ones (those with
# a recipe) are checks; starters are not (they're available from the start).
CHARACTER_LOCATIONS: dict[str, int] = {}
_character_meta: dict[str, tuple[int, int]] = {}  # name -> (roster_idx, addr)


def _build_character_locations():
    """Built lazily to keep import order clean."""
    from .data import Recipes as R
    starters = set(R.starters())
    for idx, cname in enumerate(C.CHARACTERS):
        if cname in starters:
            continue  # starters aren't checks
        loc_name = f"Unlock: {cname}"
        CHARACTER_LOCATIONS[loc_name] = BT2_LOC_BASE + 0x1000 + idx
        _character_meta[loc_name] = (idx, C.character_addr(idx))


_build_character_locations()


# ─── Fusion result locations (performing a fusion = a check) ──────────────────
# Each fusion-result character is obtained ONLY by performing its fusion in
# Evolution Z. Doing so flips that character's roster flag, which the client
# detects to fire this check. Logic (in Regions) requires the base character +
# the ingredient item(s).
FUSE_LOCATIONS: dict[str, int] = {}
_fuse_meta: dict[str, tuple[int, int]] = {}  # name -> (roster_idx, addr)


def _build_fuse_locations():
    from .data import Recipes as R
    fusion_results = [n for n, (k, _r) in R.RECIPES.items() if k == "FUSION"]
    for cname in fusion_results:
        try:
            idx = C.CHARACTERS.index(cname)
        except ValueError:
            continue  # result not in roster list (shouldn't happen)
        loc_name = f"Fuse: {cname}"
        FUSE_LOCATIONS[loc_name] = BT2_LOC_BASE + 0x3000 + idx
        _fuse_meta[loc_name] = (idx, C.character_addr(idx))


_build_fuse_locations()


def fuse_meta(name: str) -> tuple[int, int]:
    return _fuse_meta[name]


# ─── Ingredient discovery locations (first time obtaining an ingredient) ──────
# The FIRST time the player obtains/owns each fusion ingredient capsule is a
# check. The client detects the ingredient's owned flag going non-zero. Logic
# requires having received that ingredient item from AP.
DISCOVER_LOCATIONS: dict[str, int] = {}
_discover_meta: dict[str, tuple[int, str]] = {}  # name -> (ingredient_index, ingredient_name)

for _ii, _ingname in enumerate(C.FUSION_ITEM_ADDR.keys()):
    if _ingname == "Z Item Fusion":
        continue  # universal capsule is precollected, not a discoverable check
    if _ingname in C.NON_RECIPE_INGREDIENTS:
        continue  # not used in any fusion recipe — no Discover check
    if _ingname in C.UNDISCOVERABLE_INGREDIENTS:
        continue  # used in a fusion but has no reliable discovery signal — the
                  # fusion stays intact, but no false-firing Discover check
    _loc = f"Discover: {_ingname}"
    DISCOVER_LOCATIONS[_loc] = BT2_LOC_BASE + 0x5000 + _ii
    _discover_meta[_loc] = (_ii, _ingname)


def discover_meta(name: str) -> tuple[int, str]:
    return _discover_meta[name]


# ─── Secret what-if scenario unlock locations (Philosophy B) ──────────────────
# The 3 what-if sagas unlock via in-game conditions (completing specific trigger
# missions). Meeting the condition is itself a CHECK. The scenario stays GATED
# (locked until AP grants it); the unlock check fires once when the game sets
# the secret scenario's gate flag.
SECRET_UNLOCK_LOCATIONS: dict[str, int] = {}
_secret_meta: dict[str, int] = {}  # name -> scenario_index

for _si, _sname in C.SECRET_SCENARIOS.items():
    _loc = f"Unlock Saga: {_sname}"
    SECRET_UNLOCK_LOCATIONS[_loc] = BT2_LOC_BASE + 0x2000 + _si
    _secret_meta[_loc] = _si


def secret_meta(name: str) -> int:
    return _secret_meta[name]


# ─── Wish location ───────────────────────────────────────────────────────────
# Dragon Balls themselves are AP ITEMS (granted via the multiworld; the client
# enforces the in-game flags to match). The wish — reaching a summon node — is
# the check. (DB collection is NOT a check: in-game drops are rare/RNG-heavy.)
WISH_LOCATION_NAME = "Make a Wish"
WISH_LOCATIONS: dict[str, int] = {WISH_LOCATION_NAME: BT2_LOC_BASE + 0x3100}


# ─── Shop check locations ────────────────────────────────────────────────────
# Up to len(SHOP_CHECK_SLOTS) Item Shop purchase checks, NAMED after the item
# shown in that slot (so hints reference the real item). The client shows the
# matching item; buying it (Zeni drops by its unique price) sends the check.
SHOP_LOCATIONS: dict[str, int] = {}
SHOP_SLOT_ORDER: list[str] = []   # ordered list of shop location names
for _i, (_cat, _item) in enumerate(C.SHOP_CHECK_SLOTS):
    _loc = f"Shop: {_item}"
    SHOP_LOCATIONS[_loc] = BT2_LOC_BASE + 0x4000 + _i
    SHOP_SLOT_ORDER.append(_loc)
SHOP_CHECK_COUNT = len(SHOP_LOCATIONS)


# ─── Master table ────────────────────────────────────────────────────────────
location_table: dict[str, int] = {}
location_table.update(MISSION_LOCATIONS)
# NOTE: CHARACTER_LOCATIONS are intentionally NOT registered — non-fusion
# characters are AP ITEMS now, and fusion-result characters are obtained via
# the FUSE_LOCATIONS checks below.
location_table.update(FUSE_LOCATIONS)
location_table.update(DISCOVER_LOCATIONS)
location_table.update(SECRET_UNLOCK_LOCATIONS)
location_table.update(WISH_LOCATIONS)
location_table.update(SHOP_LOCATIONS)


def get_location_names() -> dict[str, int]:
    return dict(location_table)


def mission_meta(name: str) -> tuple[int, int, int]:
    return _mission_meta[name]


def character_meta(name: str) -> tuple[int, int]:
    return _character_meta[name]


def scenario_mission_locations(scenario_index: int) -> list[str]:
    """All mission location names belonging to a scenario."""
    return [n for n, (si, _mi, _a) in _mission_meta.items() if si == scenario_index]
