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


# ─── Master table ────────────────────────────────────────────────────────────
location_table: dict[str, int] = {}
location_table.update(MISSION_LOCATIONS)
location_table.update(CHARACTER_LOCATIONS)
location_table.update(SECRET_UNLOCK_LOCATIONS)
location_table.update(WISH_LOCATIONS)


def get_location_names() -> dict[str, int]:
    return dict(location_table)


def mission_meta(name: str) -> tuple[int, int, int]:
    return _mission_meta[name]


def character_meta(name: str) -> tuple[int, int]:
    return _character_meta[name]


def scenario_mission_locations(scenario_index: int) -> list[str]:
    """All mission location names belonging to a scenario."""
    return [n for n, (si, _mi, _a) in _mission_meta.items() if si == scenario_index]
