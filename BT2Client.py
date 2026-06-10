"""
Dragon Ball Z Budokai Tenkaichi 2 — Archipelago Client.
Connects to PCSX2 via PINE and the AP server simultaneously.

Loop model:
  RECORD  (game -> AP): poll mission flags + character flags; when a mission is
          completed (value >= difficulty_floor) or a character is unlocked, send
          the corresponding location check. These flags are the player's real
          progress and are never overwritten.
  ENFORCE (AP -> game): hold scenario gates at the AP-authorized set (granted
          scenarios on, everything else off) while on the DA map; grant fusion
          ingredients / ability items / characters as AP sends them.
"""
import asyncio
from typing import Optional

import Utils
from CommonClient import (
    CommonContext, get_base_parser, server_loop,
    gui_enabled, logger, ClientCommandProcessor,
)
from NetUtils import ClientStatus

from .BT2Interface import BT2Interface
from .data import Constants as C
from .Items import (item_table, SCENARIO_ITEMS, FUSION_INGREDIENT_ITEMS,
                    ABILITY_ITEMS, FILLER_ITEMS, TIME_SCROLL_ITEM,
                    DRAGONBALL_ITEM_NAMES)
from .Locations import (location_table, MISSION_LOCATIONS, CHARACTER_LOCATIONS,
                        mission_meta, character_meta)

# Reverse lookups
ID_TO_ITEM = {code: name for name, code in item_table.items()}
ID_TO_LOCATION = {code: name for name, code in location_table.items()}


class BT2CommandProcessor(ClientCommandProcessor):
    def _cmd_status(self):
        """Show connection and game state."""
        ctx: "BT2Context" = self.ctx
        logger.info(f"[BT2] Game connected: {ctx.connected_to_game}")
        logger.info(f"[BT2] Server connected: {ctx.server is not None}")
        logger.info(f"[BT2] Checks sent: {len(ctx.checked_locations)}")
        logger.info(f"[BT2] Scenarios unlocked: {sorted(ctx.unlocked_scenarios)}")


class BT2Context(CommonContext):
    command_processor = BT2CommandProcessor
    game = "Dragon Ball Z Budokai Tenkaichi 2"
    items_handling = 0b111  # receive all items

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.iface = BT2Interface(logger)
        self.connected_to_game = False
        self.slot_data: Optional[dict] = None

        # Authorized state derived from received items
        self.unlocked_scenarios: set[int] = set()   # scenario indices
        self.granted_ingredients: set[str] = set()
        self.granted_abilities: set[str] = set()
        self.granted_characters: set[int] = set()    # roster indices (from AP, if any)
        self.granted_dragonballs: set[int] = set()    # 0-based ball indices from AP
        self.difficulty_floor = 1
        self.time_scrolls_received = 0
        self.goal = 1
        self.time_scrolls_required = 0
        self.final_saga = 20

        # Fighter randomization (v2)
        self.randomize_fighters = 0     # 0=off,1=both,2=enemies,3=players
        self.fighter_pool = 0           # 0=any, 1=unlocked
        self._last_matchup_sig = None   # detect new fight (matchup block change)
        self._randomized_sig = None     # which matchup sig we've already randomized

        # Detection caches
        self._prev_missions: Optional[bytes] = None
        self._prev_characters: Optional[list] = None
        # Baseline: flags already set when we first read the game. Checks only
        # fire for flags that turn on AFTER this baseline, so default-unlocked
        # characters / pre-completed missions don't spuriously send checks.
        self._char_baseline: Optional[list] = None
        self._mission_baseline: Optional[bytes] = None
        self._secret_baseline: Optional[dict] = None  # {scenario_idx: bool} at connect
        self._pending_secret_checks: set = set()  # earned secret-unlock loc_ids awaiting send

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict):
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            self.difficulty_floor = int(self.slot_data.get("difficulty_floor", 1))
            self.randomize_fighters = int(self.slot_data.get("randomize_fighters", 0))
            self.fighter_pool = int(self.slot_data.get("fighter_pool", 0))
            self.goal = int(self.slot_data.get("goal", 1))
            self.time_scrolls_required = int(self.slot_data.get("time_scrolls_required", 0))
            self.final_saga = int(self.slot_data.get("final_saga", 20))
            # Starting scenarios from slot_data (names) -> indices
            self._apply_starting_scenarios()
        elif cmd == "ReceivedItems":
            for net_item in args["items"]:
                self._receive_item(net_item.item)

    def _scenario_name_to_index(self, unlock_item_name: str) -> Optional[int]:
        # "Saiyan Saga Unlock" -> index
        base = unlock_item_name[:-len(" Unlock")] if unlock_item_name.endswith(" Unlock") else None
        if base is None:
            return None
        for i, (n, _c) in enumerate(C.SCENARIOS):
            if n == base:
                return i
        return None

    def _apply_starting_scenarios(self):
        for nm in (self.slot_data or {}).get("starting_scenarios", []):
            idx = self._scenario_name_to_index(nm)
            if idx is not None:
                self.unlocked_scenarios.add(idx)

    def _receive_item(self, item_id: int):
        name = ID_TO_ITEM.get(item_id)
        if name is None:
            return
        if name in SCENARIO_ITEMS:
            idx = self._scenario_name_to_index(name)
            if idx is not None:
                self.unlocked_scenarios.add(idx)
        elif name in FUSION_INGREDIENT_ITEMS:
            # "Ingredient: X" -> X
            self.granted_ingredients.add(name[len("Ingredient: "):])
        elif name in ABILITY_ITEMS:
            self.granted_abilities.add(name[len("Z-Item: "):])
        elif name in FILLER_ITEMS:
            amt = {"Zeni x1000": 1000, "Zeni x5000": 5000, "Zeni x10000": 10000}.get(name, 0)
            if amt and self.connected_to_game:
                try:
                    self.iface.add_zeni(amt)
                except Exception:
                    pass
        elif name == TIME_SCROLL_ITEM:
            self.time_scrolls_received += 1
        elif name in DRAGONBALL_ITEM_NAMES:
            self.granted_dragonballs.add(DRAGONBALL_ITEM_NAMES.index(name))


def _difficulty_ok(value: int, floor: int) -> bool:
    # value 0=uncompleted, 1/2/3 = cleared on Level 1/2/3.
    return value >= floor and value != 0


async def game_watcher(ctx: BT2Context):
    """Main RECORD + ENFORCE loop."""
    while not ctx.exit_event.is_set():
        await asyncio.sleep(0.3)

        if not ctx.connected_to_game:
            if ctx.iface.connect():
                ctx.connected_to_game = True
                logger.info("[BT2] Connected to PCSX2.")
            else:
                continue

        if ctx.server is None or ctx.slot is None:
            continue

        try:
            # ── Connection sentinel: read the screen identificator first. It is
            # only ever a small set of low values; if it reads as 0xFF/garbage the
            # PINE link is dead (emulator closing), so abort before any writes or
            # check-sends and drop the connection to reconnect cleanly.
            screen = ctx.iface.get_screen_identificator()
            if screen is None or screen == 0xFF or screen > 0x40:
                ctx.connected_to_game = False
                ctx._mission_baseline = None
                ctx._char_baseline = None
                ctx._secret_baseline = None
                continue

            # ── ENFORCE: hold scenario gates + grant inventory ──
            # Assert on Main Menu (0x04) so lockout is set before the player
            # enters Dragon Adventure, and re-assert on the DA screen (0x07) to
            # catch any in-game re-unlocks. Granting inventory is safe on both.
            if screen in (0x04, 0x07):
                # For the time_scrolls goal: the Final Saga stays LOCKED until
                # the player has gathered enough Time Scrolls, then it OPENS.
                # Build the effective unlock set for this poll.
                effective_unlocks = set(ctx.unlocked_scenarios)
                if ctx.goal in (1, 2):  # time_scrolls or both
                    have_scrolls = ctx.time_scrolls_received >= ctx.time_scrolls_required
                    if have_scrolls:
                        effective_unlocks.add(ctx.final_saga)
                    else:
                        effective_unlocks.discard(ctx.final_saga)  # force locked
                ctx.iface.enforce_scenarios(effective_unlocks)
                # grant ingredients/abilities/characters AP has sent
                for ing in ctx.granted_ingredients:
                    ctx.iface.grant_ingredient(ing)
                for ab in ctx.granted_abilities:
                    ctx.iface.grant_ability(ab)
                for ridx in ctx.granted_characters:
                    ctx.iface.grant_character(ridx)

            # ── Fighter randomization (v2): detect new DA fight, randomize once ──
            if ctx.randomize_fighters:
                _maybe_randomize_fighters(ctx)

            # ── RECORD: missions ──
            missions = ctx.iface.read_all_missions()
            chars = ctx.iface.read_all_characters()

            # ── Validity guard (garbage-read protection) ──
            # Mission values are ONLY ever 0..3; any byte >3 means a corrupt read
            # (a disconnect that slipped past the sentinel). Abort, send NOTHING,
            # and drop the game connection so we reconnect and re-baseline.
            if (missions is None or len(missions) < C.TOTAL_MISSIONS
                    or any(b > 3 for b in missions)
                    or chars is None or len(chars) < len(C.CHARACTERS)):
                ctx.connected_to_game = False
                ctx._mission_baseline = None
                ctx._char_baseline = None
                ctx._secret_baseline = None
                logger.debug("[BT2] invalid read (garbage/disconnect) — skipping cycle")
                continue

            # Capture baselines on first successful read (post-connect). Flags
            # already set now are "pre-existing" (defaults / prior saved progress
            # AP already knows via checked_locations) and won't fire fresh checks.
            if ctx._mission_baseline is None:
                ctx._mission_baseline = missions
            if ctx._char_baseline is None:
                ctx._char_baseline = chars

            new_checks = []
            for loc_name in MISSION_LOCATIONS:
                si, mi, _addr = mission_meta(loc_name)
                offset = sum(c for _n, c in C.SCENARIOS[:si]) + mi
                val = missions[offset]
                if not _difficulty_ok(val, ctx.difficulty_floor):
                    continue
                loc_id = location_table[loc_name]
                if loc_id in ctx.checked_locations:
                    continue
                # Suppress if it was already complete at baseline AND not known
                # to the server (i.e. a pre-existing completion, not earned now).
                base_val = ctx._mission_baseline[offset]
                if _difficulty_ok(base_val, ctx.difficulty_floor) and loc_id not in ctx.checked_locations:
                    # already done before we attached — only count if server
                    # also has it; otherwise treat as pre-existing, skip.
                    continue
                new_checks.append(loc_id)

            # ── RECORD: characters ──
            for loc_name in CHARACTER_LOCATIONS:
                ridx, _addr = character_meta(loc_name)
                if not chars[ridx]:
                    continue
                loc_id = location_table[loc_name]
                if loc_id in ctx.checked_locations:
                    continue
                # Suppress characters that were already unlocked at baseline
                # (defaults like Nappa/Dodoria, or prior saved unlocks).
                if ctx._char_baseline[ridx]:
                    continue
                new_checks.append(loc_id)

            # ── Dragon Balls (ENFORCE to AP grants) + Wish check ──
            _enforce_dragonballs_and_wish(ctx, new_checks)

            # ── Secret what-if saga unlocks: fire on trigger-mission completion
            # (stable RECORD value; no race with gate ENFORCE). ──
            _record_secret_unlocks(ctx, missions)

            # Merge any earned secret-saga unlock checks captured this cycle.
            if ctx._pending_secret_checks:
                new_checks.extend(
                    lid for lid in ctx._pending_secret_checks
                    if lid not in ctx.checked_locations
                )
                ctx._pending_secret_checks.clear()

            if new_checks:
                await ctx.send_msgs([{
                    "cmd": "LocationChecks",
                    "locations": new_checks,
                }])

            # ── Victory: required scenarios fully complete ──
            await _check_victory(ctx, missions)

        except Exception as e:
            logger.debug(f"[BT2] watcher error: {e}")
            ctx.connected_to_game = False


def _maybe_randomize_fighters(ctx: BT2Context):
    """Detect entry into a new DA fight (matchup block changed) and write a
    deterministic, seed-based random roster into the occupied slots — once per
    fight. Waits for the block to be STABLE across two polls before writing, so
    we don't randomize mid-population (which would miss slots that fill in
    slightly later, e.g. the ally in slot 2). Cosmetic only."""
    import random as _random

    iface = ctx.iface
    if not iface.matchup_block_valid():
        ctx._last_matchup_sig = None
        return

    sig = iface.read_matchup_signature()
    if sig is None or sig == ctx._randomized_sig:
        return  # already randomized this matchup

    # Stability gate: only randomize once the signature is unchanged across two
    # consecutive polls (block fully populated, not mid-load).
    if sig != ctx._last_matchup_sig:
        ctx._last_matchup_sig = sig
        return  # first sighting — wait one more poll to confirm it's settled

    scen, chap, lin = iface.read_current_mission()
    seed_base = (ctx.slot_data or {}).get("seed", "bt2")
    rng = _random.Random(f"{seed_base}-da-{lin}")

    roster_n = len(C.CHARACTERS)
    if ctx.fighter_pool == 1:
        try:
            unlocked = [i for i, on in enumerate(iface.read_all_characters()) if on]
        except Exception:
            unlocked = list(range(roster_n))
        pool = unlocked if unlocked else list(range(roster_n))
    else:
        pool = list(range(roster_n))

    def pick(_seq):
        return rng.choice(pool)

    sides = {1: ("p1", "p2"), 2: ("p2",), 3: ("p1",)}.get(ctx.randomize_fighters, ())
    if not sides:
        return
    try:
        n = iface.randomize_matchup(pick, sides=sides)
        ctx._randomized_sig = iface.read_matchup_signature()
        logger.info(f"[BT2] Randomized {n} fighter(s) for mission {scen:#x}.{chap}")
    except Exception as e:
        logger.debug(f"[BT2] randomize error: {e}")


def _enforce_dragonballs_and_wish(ctx: BT2Context, new_checks: list):
    """(1) ENFORCE the in-game Dragon Ball flags to match exactly the set AP has
    granted — set granted balls, clear any the game gave that AP didn't (in-game
    drops are rare/RNG and don't count). (2) Fire the Wish check when the player
    reaches a summon node (Shenron/Porunga). Dragon Balls themselves are AP
    items, not checks."""
    from .Locations import WISH_LOCATION_NAME, location_table
    iface = ctx.iface

    # (1) Enforce DB flags to AP-granted set.
    try:
        iface.enforce_dragonballs(ctx.granted_dragonballs)
    except Exception:
        pass

    # (2) Wish check: reaching a summon node (edge-triggered via checked_locations).
    try:
        at_node = iface.at_summon_node()
    except Exception:
        at_node = False
    if at_node:
        wish_id = location_table[WISH_LOCATION_NAME]
        if wish_id not in ctx.checked_locations and wish_id not in new_checks:
            new_checks.append(wish_id)


def _record_secret_unlocks(ctx: BT2Context, missions=None):
    """Fire a secret-saga unlock CHECK when its TRIGGER MISSION is completed.

    We key on the trigger mission's completion flag (in the 0x63100C RECORD
    array), NOT the secret scenario's gate flag. The gate flag is actively held
    at 0 by ENFORCE (the saga stays AP-gated), so reading it would race the
    enforcement. The trigger-mission completion flag is a RECORD value ENFORCE
    never touches, so it's a stable, unambiguous 'player earned it' signal.

    Pre-existing completions (set at baseline) don't fire — that's prior save
    progress AP already accounts for.
    """
    if missions is None:
        return
    sent = []
    for sec_si, trig in C.SECRET_TRIGGERS.items():
        trig_si, trig_mi = trig
        offset = sum(c for _n, c in C.SCENARIOS[:trig_si]) + trig_mi
        if offset >= len(missions):
            continue
        done_now = missions[offset] != 0
        if not done_now:
            continue
        # Pre-existing completion at baseline -> not earned this session.
        if ctx._mission_baseline is not None and ctx._mission_baseline[offset] != 0:
            continue
        loc_name = f"Unlock Saga: {C.SECRET_SCENARIOS[sec_si]}"
        from .Locations import location_table
        loc_id = location_table.get(loc_name)
        if loc_id is None or loc_id in ctx.checked_locations:
            continue
        sent.append(loc_id)
    if sent:
        ctx._pending_secret_checks.update(sent)
        logger.info(f"[BT2] Secret saga unlock(s) earned: {len(sent)}")


async def _check_victory(ctx: BT2Context, missions: bytes):
    if ctx.finished_game:
        return
    floor = ctx.difficulty_floor

    # Scenario condition (classic)
    required = int((ctx.slot_data or {}).get("required_scenarios", 5))
    complete = 0
    for si, (_n, count) in enumerate(C.SCENARIOS):
        start = sum(c for _nn, c in C.SCENARIOS[:si])
        if all(_difficulty_ok(missions[start + m], floor) for m in range(count)):
            complete += 1
    scenarios_ok = complete >= required

    # Time Scroll condition: gather N scrolls AND complete the (now-unlocked)
    # Final Saga. The scrolls unlock the saga; completing it repairs the timeline.
    def saga_complete(si):
        start = sum(c for _nn, c in C.SCENARIOS[:si])
        count = C.SCENARIOS[si][1]
        return all(_difficulty_ok(missions[start + m], floor) for m in range(count))

    have_scrolls = ctx.time_scrolls_received >= ctx.time_scrolls_required
    final_done = saga_complete(ctx.final_saga)
    scrolls_ok = have_scrolls and final_done

    goal = ctx.goal
    if goal == 1:        # time_scrolls
        won = scrolls_ok
    elif goal == 2:      # both
        won = scenarios_ok and scrolls_ok
    else:                # scenarios
        won = scenarios_ok

    if won:
        await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
        ctx.finished_game = True
        saga_name = C.SCENARIOS[ctx.final_saga][0]
        if goal == 1:
            logger.info(f"[BT2] Goal complete: gathered {ctx.time_scrolls_received} Time Scrolls and completed {saga_name} — timeline repaired!")
        elif goal == 2:
            logger.info(f"[BT2] Goal complete: {complete}/{required} scenarios AND {saga_name} (scrolls gathered)!")
        else:
            logger.info(f"[BT2] Goal complete: {complete}/{required} scenarios!")


def launch_client():
    async def main():
        parser = get_base_parser()
        args = parser.parse_args()
        ctx = BT2Context(args.connect, args.password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        watcher = asyncio.create_task(game_watcher(ctx), name="GameWatcher")
        await ctx.exit_event.wait()
        watcher.cancel()
        await ctx.shutdown()

    Utils.init_logging("BT2Client")
    import colorama
    colorama.init()
    asyncio.run(main())
    colorama.deinit()
