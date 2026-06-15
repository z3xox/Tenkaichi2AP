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
    from .Locations import (SHOP_LOCATIONS, SHOP_SLOT_ORDER,
                            scenario_mission_locations, SECRET_UNLOCK_LOCATIONS,
                            secret_meta)
    shop_checks = int(world.options.shop_checks.value)
    shop_allowed = set(SHOP_SLOT_ORDER[:shop_checks])

    # Build the set of location names to SKIP because their saga is disabled.
    excluded_sagas = getattr(world, "_excluded_sagas", set())
    excluded_loc_names = set()
    for si in excluded_sagas:
        excluded_loc_names.update(scenario_mission_locations(si))
    # Also skip secret-unlock locations whose target scenario is disabled.
    for loc_name in SECRET_UNLOCK_LOCATIONS:
        try:
            if secret_meta(loc_name) in excluded_sagas:
                excluded_loc_names.add(loc_name)
        except Exception:
            pass

    # Characters are now AP ITEMS (Model B), so their unlock LOCATIONS are no
    # longer checks — skip all of them when building regions.
    from .Locations import CHARACTER_LOCATIONS as _CHAR_LOCS
    excluded_loc_names.update(_CHAR_LOCS.keys())

    # Skip a MAPPED ingredient's Discover location if ALL of its drop sagas are
    # excluded (it could never be won in-game). Unmapped ingredients use the
    # owned-flag fallback and are unaffected by exclusions.
    if excluded_sagas:
        from .Locations import DISCOVER_LOCATIONS as _DISC_LOCS, discover_meta as _dm
        from .data import Discovery as _Disc
        for _loc_name in _DISC_LOCS:
            _ii, _ing = _dm(_loc_name)
            _sigs = _Disc.discovery_fights(_ing)
            if _sigs and all(_Disc.live_scenario_to_list(s) in excluded_sagas
                             for (s, _c, _f) in _sigs):
                excluded_loc_names.add(_loc_name)

    for loc_name, loc_id in location_table.items():
        if loc_name in SHOP_LOCATIONS and loc_name not in shop_allowed:
            continue
        if loc_name in excluded_loc_names:
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

    # Sagas disabled via the excluded_sagas option: their locations were never
    # created, so skip setting rules on them (get_location would KeyError).
    excluded_sagas = getattr(world, "_excluded_sagas", set())

    # ── Mission locations: require their scenario unlock ──
    # EXCEPTION: when the goal uses Time Scrolls, the Final Saga's missions are
    # gated by gathering the scrolls (which unlock it), not by a scenario item.
    for loc_name in MISSION_LOCATIONS:
        si, _mi, _addr = mission_meta(loc_name)
        if si in excluded_sagas:
            continue
        loc = multiworld.get_location(loc_name, player)
        if goal in (1, 2) and si == final_saga:
            set_rule(loc, lambda state: state.has(TIME_SCROLL_ITEM, player, scrolls_req))
        else:
            set_rule(loc, lambda state, s=si: has_scenario(state, s))

    # ── Character availability (Model B: characters are AP ITEMS) ──
    # A character is available for Z-Fusion/Duel when it's a starter OR you have
    # received its "<char> Character" item from AP. Fusion characters ALSO need
    # their recipe ingredients (consumable fusion items) to actually fuse, so a
    # fusion char requires BOTH its character item AND the fusion ingredients.
    starters = set(R.starters())
    roster = set(C.CHARACTERS)
    from .Items import CHARACTER_UNLOCK_ITEMS as _CHAR_ITEMS

    def _char_item_name(cname):
        return f"{cname} Character"

    def char_rule(state, cname, _seen=None):
        """Reachability for using a character. Starters are free; everything else
        requires its AP character item. Fusion characters additionally require
        their fusion ingredients (the consumable fusion-item capsules)."""
        if _seen is None:
            _seen = set()
        if cname in starters:
            return True
        if cname in _seen:
            return True  # break cycles defensively
        _seen.add(cname)

        # Must have the character item (if it's an unlockable roster char).
        item_name = _char_item_name(cname)
        has_char_item = (item_name in _CHAR_ITEMS)
        if has_char_item and not state.has(item_name, player):
            return False

        entry = R.RECIPES.get(cname)
        if entry is None:
            return True  # no recipe -> just the character item gates it
        kind, req = entry
        if kind == "BATTLE":
            # Battle-unlock chars: now gated purely by the character item above.
            # (No longer require playing a specific saga.)
            return True
        if kind == "FUSION":
            if not fusion_full:
                return True  # free mode: ingredients auto-granted
            ok = True
            for ing in req:
                canon = R._canon(ing)
                if canon in roster:
                    # ingredient is a character: require ITS availability too
                    ok = ok and char_rule(state, canon, _seen)
                else:
                    need = max(1, _ing_demand.get(canon, 1))
                    ok = ok and state.has(ingredient_item_name(canon), player, need)
            return ok
        return True

    # NOTE: characters are now ITEMS (Model B), not locations — there is no
    # per-character location rule loop. char_rule above is used by fusion logic
    # to gate fusion-character availability on the required character items and
    # ingredients.

    # ── Secret what-if saga unlock locations ──
    # Reachable when the TRIGGER mission's scenario is unlocked (completing the
    # trigger mission is what fires the unlock; fighter randomization doesn't
    # block it since the trigger is mission completion, not a specific char).
    from .Locations import SECRET_UNLOCK_LOCATIONS, secret_meta
    for loc_name in SECRET_UNLOCK_LOCATIONS:
        sec_si = secret_meta(loc_name)
        if sec_si in excluded_sagas:
            continue  # disabled saga's unlock location wasn't created
        trig = C.SECRET_TRIGGERS.get(sec_si)
        if trig is None:
            continue
        trig_si, _trig_mi = trig
        loc = multiworld.get_location(loc_name, player)
        set_rule(loc, lambda state, s=trig_si: has_scenario(state, s))

    # ── Fusion result locations (performing the fusion) ──
    # Each "Fuse: <result>" check requires the fusion to be performable:
    # char_rule(result) already encodes "have the base (char item or its own
    # fuse) AND the ingredient item(s)" recursively for chains.
    from .Locations import FUSE_LOCATIONS, fuse_meta
    for loc_name in FUSE_LOCATIONS:
        ridx, _addr = fuse_meta(loc_name)
        cname = C.CHARACTERS[ridx]
        loc = multiworld.get_location(loc_name, player)
        set_rule(loc, lambda state, c=cname: char_rule(state, c))

    # ── Ingredient discovery locations ──
    # "Discover: <ingredient>" — how it's obtained depends on whether the
    # ingredient's drop fight is MAPPED:
    #   - mapped: won in-game by beating a drop fight -> require reaching ANY of
    #     its drop sagas (has_scenario). Excluded-saga drops are filtered out;
    #     if none remain, the location was skipped in create_regions.
    #   - unmapped: fires from the owned-flag when AP grants the item -> require
    #     having the ingredient item.
    from .Locations import DISCOVER_LOCATIONS, discover_meta
    from .data import Discovery as _Disc
    excluded_sagas = getattr(world, "_excluded_sagas", set())
    # Ingredients discovered via recurring-enemy fight_id (e.g. General Tao):
    # the enemy appears across many sagas, so treat as reachable once any
    # enabled saga is reachable.
    fight_id_ings = set()
    for _ings in _Disc.INGREDIENT_BY_FIGHT_ID.values():
        fight_id_ings.update(_ings)
    enabled_sagas = [i for i in range(len(C.SCENARIOS)) if i not in excluded_sagas]
    for loc_name in DISCOVER_LOCATIONS:
        _ii, ingname = discover_meta(loc_name)
        sigs = _Disc.discovery_fights(ingname)
        if ingname in fight_id_ings:
            # Recurring enemy: reachable if any enabled saga is reachable.
            loc = multiworld.get_location(loc_name, player)
            set_rule(loc, lambda state, ss=tuple(enabled_sagas):
                     any(has_scenario(state, s) for s in ss))
            continue
        # Skip locations that create_regions didn't create (all drop sagas
        # excluded for a mapped ingredient).
        if sigs and all(_Disc.live_scenario_to_list(s) in excluded_sagas
                        for (s, _c, _f) in sigs):
            continue
        loc = multiworld.get_location(loc_name, player)
        if sigs:
            drop_sagas = sorted({_Disc.live_scenario_to_list(s)
                                 for (s, _c, _f) in sigs
                                 if _Disc.live_scenario_to_list(s) not in excluded_sagas})
            set_rule(loc, lambda state, ss=tuple(drop_sagas):
                     any(has_scenario(state, s) for s in ss))
        else:
            set_rule(loc, lambda state, n=ingname:
                     state.has(ingredient_item_name(n), player))

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
    # Clamp required scenarios to the number of ENABLED sagas, so the scenarios
    # goal stays winnable when sagas are excluded.
    _excluded = getattr(world, "_excluded_sagas", set())
    _enabled_count = len(C.SCENARIOS) - len(_excluded)
    required = min(required, _enabled_count)

    from .Items import TIME_SCROLL_ITEM

    excluded_sagas = getattr(world, "_excluded_sagas", set())

    # Precompute, per scenario, its mission location names. Skip excluded sagas
    # (their locations don't exist) so victory logic never references them.
    scen_missions = {}
    for loc_name in MISSION_LOCATIONS:
        si, _mi, _a = mission_meta(loc_name)
        if si in excluded_sagas:
            continue
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
