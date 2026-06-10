"""
Region / logic construction for BT2.

Layout: a single region ("Menu" -> "Dragon Adventure") is enough; access is
governed entirely by item logic (scenario unlocks + ingredients), not by
geography. We attach access rules per-location.

Logic:
  * Mission location (scenario S): requires the "S Unlock" item.
  * Character unlock (FUSION): requires the recipe ingredients
      - ingredient that is a fusion-item  -> "Ingredient: X"
      - ingredient that is a character    -> that character's unlock location
        reachable (i.e. its own rule), modeled via has() of a synthetic event
        OR by requiring the scenario/ingredients transitively.
    For simplicity and correctness we require:
        all fusion-item ingredients as items, AND
        all character ingredients' own access rules (recursively).
  * Character unlock (BATTLE, scenario S): requires "S Unlock" (or no req if
    scenario is None -> always accessible).
"""

from BaseClasses import Region, Location, ItemClassification
from .Locations import (location_table, MISSION_LOCATIONS, CHARACTER_LOCATIONS,
                        mission_meta, character_meta)
from .Items import ingredient_item_name
from .data import Constants as C
from .data import Recipes as R


class BT2Location(Location):
    game = "Dragon Ball Z Budokai Tenkaichi 2"


def _scenario_unlock_item(scenario_index: int) -> str:
    name = C.SCENARIOS[scenario_index][0]
    return f"{name} Unlock"


def create_regions(world):
    player = world.player
    multiworld = world.multiworld

    menu = Region("Menu", player, multiworld)
    da = Region("Dragon Adventure", player, multiworld)
    multiworld.regions += [menu, da]
    menu.connect(da)

    # Add all locations to the Dragon Adventure region. Shop locations are
    # capped at the shop_checks option (and excluded entirely if 0).
    from .Locations import SHOP_LOCATIONS, SHOP_SLOT_ORDER
    shop_checks = int(world.options.shop_checks.value)
    shop_allowed = set(SHOP_SLOT_ORDER[:shop_checks])
    for loc_name, loc_id in location_table.items():
        if loc_name in SHOP_LOCATIONS and loc_name not in shop_allowed:
            continue
        loc = BT2Location(player, loc_name, loc_id, da)
        da.locations.append(loc)


def set_location_rules(world):
    from worlds.generic.Rules import set_rule, add_rule
    player = world.player
    multiworld = world.multiworld

    fusion_full = (int(world.options.fusion_logic.value) == 0)
    goal = int(world.options.goal.value)
    final_saga = int(world.options.final_saga.value)
    scrolls_req = int(world.options.time_scrolls_required.value)
    from .Items import TIME_SCROLL_ITEM
    # Consumable-ingredient demand: a fusion item shared by N recipes (or feeding
    # a chain) is consumed N times. A location consuming ingredient X requires
    # state.has(X, demand[X]) — i.e. enough copies for every fusion that uses it.
    # Sound (no softlock) and solvable (exactly demand[X] copies are in the pool).
    _ing_demand = R.ingredient_demand()

    def has_scenario(state, scenario_index):
        return state.has(_scenario_unlock_item(scenario_index), player)

    # ── Mission locations: require their scenario unlock ──
    # EXCEPTION: when the goal uses Time Scrolls, the Final Saga's missions are
    # gated by gathering the scrolls (which unlock it), not by a scenario item.
    for loc_name in MISSION_LOCATIONS:
        si, _mi, _addr = mission_meta(loc_name)
        loc = multiworld.get_location(loc_name, player)
        if goal in (1, 2) and si == final_saga:
            set_rule(loc, lambda state: state.has(TIME_SCROLL_ITEM, player, scrolls_req))
        else:
            set_rule(loc, lambda state, s=si: has_scenario(state, s))

    # ── Character unlock locations ──
    starters = set(R.starters())
    roster = set(C.CHARACTERS)

    def char_rule(state, cname, _seen=None):
        """Recursive reachability for a character unlock."""
        if _seen is None:
            _seen = set()
        if cname in starters:
            return True
        if cname in _seen:
            return True  # break cycles defensively
        _seen.add(cname)
        entry = R.RECIPES.get(cname)
        if entry is None:
            return True  # unknown -> treat as starter-ish (shouldn't happen)
        kind, req = entry
        if kind == "BATTLE":
            if req is None:
                return True
            si = next(i for i, (n, _c) in enumerate(C.SCENARIOS) if n == req)
            return has_scenario(state, si)
        if kind == "FUSION":
            if not fusion_full:
                return True  # free mode: ingredients auto-granted
            ok = True
            for ing in req:
                canon = R._canon(ing)
                if canon in roster:
                    # ingredient is a character: require its own rule
                    ok = ok and char_rule(state, canon, _seen)
                else:
                    # consumable fusion item: require enough copies for all the
                    # fusions that consume it (demand count), not just 1.
                    need = max(1, _ing_demand.get(canon, 1))
                    ok = ok and state.has(ingredient_item_name(canon), player, need)
            return ok
        return True

    for loc_name in CHARACTER_LOCATIONS:
        idx, _addr = character_meta(loc_name)
        cname = C.CHARACTERS[idx]
        loc = multiworld.get_location(loc_name, player)
        set_rule(loc, lambda state, c=cname: char_rule(state, c))

    # ── Secret what-if saga unlock locations ──
    # Reachable when the TRIGGER mission's scenario is unlocked (completing the
    # trigger mission is what fires the unlock; fighter randomization doesn't
    # block it since the trigger is mission completion, not a specific char).
    from .Locations import SECRET_UNLOCK_LOCATIONS, secret_meta
    for loc_name in SECRET_UNLOCK_LOCATIONS:
        sec_si = secret_meta(loc_name)
        trig = C.SECRET_TRIGGERS.get(sec_si)
        if trig is None:
            continue
        trig_si, _trig_mi = trig
        loc = multiworld.get_location(loc_name, player)
        set_rule(loc, lambda state, s=trig_si: has_scenario(state, s))

    # ── Wish location ──
    # Dragon Balls are AP ITEMS (the client enforces in-game flags to match).
    # The wish (reaching a summon node) is the only Dragon-Ball-related CHECK.
    # Logically gate it behind owning all 7 Dragon Ball items — that's what the
    # game requires to summon, and it makes the wish a meaningful goal for the
    # DB items rather than free.
    from .Locations import WISH_LOCATION_NAME
    from .Items import DRAGONBALL_ITEM_NAMES
    wish_loc = multiworld.get_location(WISH_LOCATION_NAME, player)
    set_rule(wish_loc, lambda state: all(
        state.has(nm, player) for nm in DRAGONBALL_ITEM_NAMES))

    # ── Shop check locations ──
    # Shop check slot i is reachable once enough Shop Restock items received:
    # Shop Restock items have been received: available = initial + restocks*amt.
    from .Locations import SHOP_LOCATIONS, SHOP_SLOT_ORDER
    from .Items import SHOP_RESTOCK_ITEM
    shop_checks = int(world.options.shop_checks.value)
    shop_initial = int(world.options.shop_initial.value)
    restock_amt = max(1, int(world.options.shop_restock_amount.value))
    shop_names = SHOP_SLOT_ORDER[:shop_checks]
    for i, loc_name in enumerate(shop_names):
        # how many restocks needed for slot i (0-based) to be available
        needed = max(0, -(-(i + 1 - shop_initial) // restock_amt))  # ceil
        loc = multiworld.get_location(loc_name, player)
        if needed == 0:
            set_rule(loc, lambda state: True)
        else:
            set_rule(loc, lambda state, n=needed: state.has(SHOP_RESTOCK_ITEM, player, n))


def set_completion(world):
    """Victory condition for the generator's reachability logic.
      scenarios   = complete `required_scenarios` scenarios.
      time_scrolls= gather `time_scrolls_required` Time Scrolls (which unlock the
                    Final Saga) AND complete that Final Saga.
      both        = satisfy both.
    """
    player = world.player
    multiworld = world.multiworld
    required = min(int(world.options.required_scenarios.value), len(C.SCENARIOS))
    goal = int(world.options.goal.value)
    scrolls_req = int(world.options.time_scrolls_required.value)
    final_saga = int(world.options.final_saga.value)

    from .Items import TIME_SCROLL_ITEM

    # Precompute, per scenario, its mission location names.
    scen_missions = {}
    for loc_name in MISSION_LOCATIONS:
        si, _mi, _a = mission_meta(loc_name)
        scen_missions.setdefault(si, []).append(loc_name)

    def scenario_complete(state, si):
        return all(state.can_reach(n, "Location", player) for n in scen_missions[si])

    def scenarios_done(state):
        return sum(1 for si in scen_missions if scenario_complete(state, si)) >= required

    def has_scrolls(state):
        return state.has(TIME_SCROLL_ITEM, player, scrolls_req)

    def final_saga_done(state):
        # Final saga missions are reachable only once scrolls are gathered.
        return has_scrolls(state) and scenario_complete(state, final_saga)

    if goal == 1:        # time_scrolls
        cond = final_saga_done
    elif goal == 2:      # both
        cond = lambda state: scenarios_done(state) and final_saga_done(state)
    else:                # scenarios
        cond = scenarios_done

    multiworld.completion_condition[player] = cond
