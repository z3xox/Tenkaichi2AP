import logging
from typing import Any, Mapping

logger = logging.getLogger(__name__)

from BaseClasses import Item, ItemClassification, Tutorial
from worlds.AutoWorld import World, WebWorld
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from .Items import (item_table, create_item, BT2Item,
                    SCENARIO_ITEMS, FUSION_INGREDIENT_ITEMS,
                    ABILITY_ITEMS, SUPPORT_ITEMS, FILLER_ITEMS)
from .Locations import location_table, get_location_names
from .Options import BT2Options
from .Regions import create_regions, set_location_rules, set_completion
from .data import Constants as C


def run_client():
    from worlds.budokai_tenkaichi2.BT2Client import launch_client
    launch_subprocess(launch_client, name="BT2Client")


components.append(
    Component("BT2 Client", func=run_client, component_type=Type.CLIENT)
)


class BT2Web(WebWorld):
    theme = "stone"
    tutorials = [Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Dragon Ball Z Budokai Tenkaichi 2 for Archipelago.",
        "English",
        "setup_en.md",
        "setup/en",
        ["BT2AP"],
    )]


class BT2World(World):
    """
    Dragon Ball Z: Budokai Tenkaichi 2 — fight through 200 Dragon Adventure
    missions across 24 scenarios, unlock scenarios and 129 characters via
    fusions and battle conditions, in a multiworld randomizer.
    """

    game = "Dragon Ball Z Budokai Tenkaichi 2"
    item_name_to_id = {name: code for name, code in item_table.items()}
    location_name_to_id = get_location_names()
    options_dataclass = BT2Options
    options: BT2Options
    web = BT2Web()

    def generate_early(self):
        # Resolve which sagas are DISABLED. excluded_sagas lists saga NAMES; map
        # them to indices. The Final Saga (the goal scenario) is ALWAYS kept
        # enabled, so it's removed from the excluded set even if the player
        # listed it. The result drives both location creation (skip disabled
        # sagas' mission checks) and item creation (skip their unlock items).
        name_to_idx = {name: i for i, (name, _c) in enumerate(C.SCENARIOS)}
        excluded_names = set(self.options.excluded_sagas.value)
        excluded_idx = {name_to_idx[n] for n in excluded_names if n in name_to_idx}
        # Never exclude the Final Saga.
        final_saga = int(self.options.final_saga.value)
        excluded_idx.discard(final_saga)
        # Safety: never allow ALL sagas to be excluded (need something to play).
        if len(excluded_idx) >= len(C.SCENARIOS):
            excluded_idx.discard(final_saga)  # keep at least the final saga
        self._excluded_sagas = excluded_idx

        # Balance guard: excluding sagas removes their mission LOCATIONS faster
        # than it removes items (only 1 scenario item each), and characters are
        # now items too. If the player excludes so many sagas that the remaining
        # locations can't host the mandatory item pool, fail early with a clear
        # message instead of a cryptic FillError deep in generation.
        from .Items import (SCENARIO_ITEMS, FUSION_INGREDIENT_ITEMS,
                            CHARACTER_UNLOCK_ITEMS, DRAGONBALL_ITEMS)
        from . import Locations as _L
        # Remaining mission locations after exclusions.
        excluded_mission_count = sum(C.SCENARIOS[i][1] for i in excluded_idx)
        remaining_missions = len(_L.MISSION_LOCATIONS) - excluded_mission_count
        shop_checks = int(self.options.shop_checks.value)
        remaining_locs = (remaining_missions
                          + len(_L.SECRET_UNLOCK_LOCATIONS)
                          + len(_L.WISH_LOCATIONS)
                          + len(_L.FUSE_LOCATIONS)
                          + len(_L.DISCOVER_LOCATIONS)
                          + min(shop_checks, len(_L.SHOP_LOCATIONS)))
        # Mandatory items: scenario unlocks for ENABLED sagas + ingredients +
        # character items + dragonballs (+ time scrolls handled as filler-ish).
        n_scen_items = len(SCENARIO_ITEMS) - len(excluded_idx)
        mandatory = (n_scen_items + len(FUSION_INGREDIENT_ITEMS)
                     + len(CHARACTER_UNLOCK_ITEMS) + len(DRAGONBALL_ITEMS))
        if remaining_locs < mandatory:
            from Options import OptionError
            raise OptionError(
                f"[BT2] excluded_sagas removes too many checks: {remaining_locs} "
                f"locations remain but {mandatory} mandatory items must be placed. "
                f"Exclude fewer sagas, or enable more shop_checks to add locations.")

        # Precollect a random subset of scenario unlocks as the starting set.
        n_start = min(int(self.options.starting_scenarios.value), len(C.SCENARIOS))
        scenario_item_names = list(SCENARIO_ITEMS.keys())
        # Don't precollect unlocks for DISABLED sagas (they aren't in the pool).
        excluded_unlock_names = {f"{C.SCENARIOS[i][0]} Unlock" for i in self._excluded_sagas}
        scenario_item_names = [n for n in scenario_item_names
                               if n not in excluded_unlock_names]
        # When the goal uses Time Scrolls, the Final Saga must stay locked until
        # the scrolls are gathered — never precollect it as a starter.
        goal = int(self.options.goal.value)
        if goal in (1, 2):
            final_saga = int(self.options.final_saga.value)
            final_name = f"{C.SCENARIOS[final_saga][0]} Unlock"
            scenario_item_names = [n for n in scenario_item_names if n != final_name]
            n_start = min(n_start, len(scenario_item_names))
        start = self.random.sample(scenario_item_names, n_start)
        for name in start:
            self.multiworld.push_precollected(create_item(self, name))
        self._starting_scenarios = set(start)

    def create_regions(self):
        create_regions(self)

    def create_item(self, name: str) -> BT2Item:
        """Create a single item by name. Required as a World METHOD (distinct
        from the module-level helper) because Archipelago core and tools like
        Universal Tracker call multiworld.create_item(name) -> world.create_item.
        Without this override the base World.create_item raises NotImplementedError."""
        return create_item(self, name)

    def create_items(self):
        pool = []

        # Scenario unlocks: all except the precollected starting ones.
        # For the time_scrolls goal, also exclude the Final Saga's unlock item —
        # that saga is gated by gathering Time Scrolls, not by a scenario item,
        # so its unlock item would be dead weight in the pool.
        starting = getattr(self, "_starting_scenarios", set())
        excluded_unlocks = set()
        # Disabled sagas: their unlock items are not placed (no checks there).
        for i in getattr(self, "_excluded_sagas", set()):
            excluded_unlocks.add(f"{C.SCENARIOS[i][0]} Unlock")
        goal = int(self.options.goal.value)
        if goal in (1, 2):
            fs = int(self.options.final_saga.value)
            excluded_unlocks.add(f"{C.SCENARIOS[fs][0]} Unlock")
        for name in SCENARIO_ITEMS:
            if name in starting or name in excluded_unlocks:
                continue
            pool.append(create_item(self, name))

        # Fusion ingredients (consumable). Fusion ITEMS are used up when fused,
        # so an ingredient shared by N recipes — or feeding a chain — must be
        # supplied N times. ingredient_demand() computes copies needed to unlock
        # every fusion character once (roster-character ingredients are NOT
        # consumed, so they're excluded). In "free" mode logic doesn't require
        # them, but we still place 1 each to preserve location count.
        # "Z Item Fusion" is the universal fusion capsule consumed by EVERY fuse,
        # so rather than gate all fusions behind one findable check, we START
        # with it (precollected) and skip it in the pool. The client grants it as
        # an effectively unlimited supply (999, refilled each poll).
        ZIF_ITEM = "Ingredient: Z Item Fusion"
        if ZIF_ITEM in FUSION_INGREDIENT_ITEMS:
            self.multiworld.push_precollected(create_item(self, ZIF_ITEM))

        fusion_full = (int(self.options.fusion_logic.value) == 0)
        if fusion_full:
            from .data import Recipes as _R
            demand = _R.ingredient_demand()
            for name in FUSION_INGREDIENT_ITEMS:
                if name == ZIF_ITEM:
                    continue  # started with it
                canon = name[len("Ingredient: "):]
                copies = max(1, demand.get(canon, 1))
                for _ in range(copies):
                    pool.append(create_item(self, name))
        else:
            for name in FUSION_INGREDIENT_ITEMS:
                if name == ZIF_ITEM:
                    continue  # started with it
                pool.append(create_item(self, name))

        # Character unlock items (Model B): one per non-starter roster character.
        # These are progression items — receiving one unlocks that fighter for
        # Z-Fusion/Duel (the client locks the roster until granted).
        from .Items import CHARACTER_UNLOCK_ITEMS
        for name in CHARACTER_UNLOCK_ITEMS:
            pool.append(create_item(self, name))

        # Time Scroll McGuffins (only when the goal involves them).
        from .Items import TIME_SCROLL_ITEM
        goal = int(self.options.goal.value)
        if goal in (1, 2):  # time_scrolls or both
            req = int(self.options.time_scrolls_required.value)
            total = max(req, int(self.options.time_scrolls_total.value))
            self._time_scrolls_required = req
            for _ in range(total):
                pool.append(create_item(self, TIME_SCROLL_ITEM))
        else:
            self._time_scrolls_required = 0

        # The 7 Dragon Balls as AP items (progression). The client enforces the
        # in-game flags to match what AP grants; gathering all 7 enables the wish
        # at the summon node.
        from .Items import DRAGONBALL_ITEM_NAMES
        for name in DRAGONBALL_ITEM_NAMES:
            pool.append(create_item(self, name))

        # Shop Restock items: enough to reveal all shop checks beyond the initial
        # set. count = ceil((shop_checks - shop_initial) / restock_amount).
        from .Items import SHOP_RESTOCK_ITEM
        sc = int(self.options.shop_checks.value)
        if sc > 0:
            si = int(self.options.shop_initial.value)
            ra = max(1, int(self.options.shop_restock_amount.value))
            n_restock = max(0, -(-(sc - si) // ra))  # ceil division
            for _ in range(n_restock):
                pool.append(create_item(self, SHOP_RESTOCK_ITEM))

        # Fill the remaining locations with useful (ability) + filler (Zeni)
        # according to filler_ratio.
        total_locs = len(self.multiworld.get_unfilled_locations(self.player))
        remaining = max(0, total_locs - len(pool))

        filler_pct = int(self.options.filler_ratio.value)
        n_filler = (remaining * filler_pct) // 100
        n_useful = remaining - n_filler

        ability_names = list(ABILITY_ITEMS.keys())
        support_names = list(SUPPORT_ITEMS.keys())
        filler_names = list(FILLER_ITEMS.keys())

        # Useful slots: ability stat-boosts AND support Z-Items at EQUAL priority.
        # Shuffle the combined pool so neither category is front-loaded (a plain
        # ability+support concatenation would place all abilities first and only
        # reach supports if there were >155 useful slots).
        useful_pool = ability_names + support_names
        self.random.shuffle(useful_pool)
        for i in range(n_useful):
            pool.append(create_item(self, useful_pool[i % len(useful_pool)]))

        # Filler slots: a VARIED mix of Zeni AND scattered stat-boost / support
        # items, so filler isn't monotonous Zeni. ~40% Zeni, ~60% random Z-Items,
        # with abilities and supports drawn from a single combined bucket.
        stat_filler = [n for n in ability_names if any(
            s in n for s in ("Health +", "Ki +", "Attack +", "Defense +",
                             "Speed +", "Blast"))] + support_names
        for i in range(n_filler):
            if not stat_filler or self.random.random() < 0.4:
                pool.append(create_item(self, self.random.choice(filler_names)))
            else:
                pool.append(create_item(self, self.random.choice(stat_filler)))

        self.multiworld.itempool.extend(pool)

    def set_rules(self):
        set_location_rules(self)
        set_completion(self)

    def get_filler_item_name(self) -> str:
        return "Zeni x5000"

    def fill_slot_data(self) -> Mapping[str, Any]:
        return {
            "goal": self.options.goal.value,
            "final_saga": self.options.final_saga.value,
            "time_scrolls_required": self.options.time_scrolls_required.value,
            "required_scenarios": self.options.required_scenarios.value,
            "starting_scenarios": sorted(getattr(self, "_starting_scenarios", set())),
            "excluded_sagas": sorted(getattr(self, "_excluded_sagas", set())),
            "fusion_logic": self.options.fusion_logic.value,
            "difficulty_floor": self.options.difficulty_floor.value,
            "randomize_fighters": self.options.randomize_fighters.value,
            "fighter_pool": self.options.fighter_pool.value,
            "disable_giants": self.options.disable_giants.value,
            "death_link": self.options.death_link.value,
            "shop_checks": self.options.shop_checks.value,
            "shop_initial": self.options.shop_initial.value,
            "shop_restock_amount": self.options.shop_restock_amount.value,
            "skip_cutscenes": self.options.skip_cutscenes.value,
            "skip_saves": self.options.skip_saves.value,
            "seed": self.multiworld.seed_name,
        }
