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
from Utils import async_start
from CommonClient import (
    CommonContext, get_base_parser, server_loop,
    gui_enabled, logger, ClientCommandProcessor,
)
from NetUtils import ClientStatus

from .BT2Interface import BT2Interface
from .data import Constants as C
from .Items import (item_table, SCENARIO_ITEMS, FUSION_INGREDIENT_ITEMS,
                    ABILITY_ITEMS, SUPPORT_ITEMS, FILLER_ITEMS, TIME_SCROLL_ITEM,
                    DRAGONBALL_ITEM_NAMES, SHOP_RESTOCK_ITEM,
                    CHARACTER_UNLOCK_ITEMS)
from .Locations import (location_table, MISSION_LOCATIONS, CHARACTER_LOCATIONS,
                        mission_meta, character_meta,
                        FUSE_LOCATIONS, fuse_meta,
                        DISCOVER_LOCATIONS, discover_meta)

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
        self.granted_supports: set[str] = set()
        self.granted_characters: set[int] = set()    # roster indices (from AP, if any)
        self._lockable_char_indices = None            # non-starter roster indices (cached)
        self._last_battle_won: bool = False           # latch for victory-edge discovery detection
        self.granted_dragonballs: set[int] = set()    # 0-based ball indices from AP
        self.difficulty_floor = 1
        self.time_scrolls_received = 0
        self.goal = 1
        self.time_scrolls_required = 0
        self.final_saga = 20
        # Shop dispenser
        self.shop_checks = 0
        self.shop_initial = 10
        self.shop_restock_amount = 10
        self.shop_restocks_received = 0
        self._shop_cleared_this_visit = False
        self._shop_prev_screen = None
        self._zeni_last = None
        self._da_shop_prev = False           # DA Namek shop presence (prev poll)
        self._da_zeni_last = None            # Zeni baseline for DA shop detection
        self._scroll_label = None            # GUI Time Scroll progress label
        self._pending_shop_checks: set = set()
        self._shop_hint_pending: list = []   # shop loc names to auto-hint
        self._shop_hinted: set = set()       # already-hinted shop locs
        self._shop_owned_zeroed = False      # one-time: zero check-item owned qty
        self._shop_bought_cats: set = set()  # catalog idx bought this session (keep at owned=0)

        # Fighter randomization (v2)
        self.randomize_fighters = 0     # 0=off,1=both,2=enemies,3=players
        self.fighter_pool = 0           # 0=any, 1=unlocked
        self.disable_giants = 0         # 1=exclude giant fighters from randomizer
        self.death_link = 0             # 1=DeathLink enabled
        self.skip_cutscenes = 1         # 1=auto-skip in-game dialogue cutscenes
        self._pending_death = False     # incoming death waiting to apply (buffered)
        self._deathlink_caused = False  # our defeat was caused by incoming DL
        self._fight_went_live = False   # observed pending(0x00) while in Battle
        self._victory_lock = False      # victory seen this fight -> no death fires
        self._loss_sent = False         # already broadcast this fight's loss
        self._killing = False           # actively re-zeroing rotating fighters
        self._last_battle_status = 0x00 # for edge-detect of defeat/surrender
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

    def make_gui(self):
        ui = super().make_gui()
        ui.base_title = "Dragon Ball Z Budokai Tenkaichi 2 Archipelago Client"
        return ui

    def draw_scroll_counter(self):
        """Add/update a small Time Scroll progress label in the client's top
        connect bar (mirrors the proven Melee pattern). Best-effort: never let a
        GUI hiccup break the client. Only meaningful for the time_scrolls/both
        goals; for other goals the label stays blank."""
        try:
            if not getattr(self, "ui", None):
                return
            # KivyMD support, with fallback to plain Kivy.
            try:
                from kvui import MDLabel as Label
            except ImportError:
                from kvui import Label

            if getattr(self, "_scroll_label", None) is None:
                self._scroll_label = Label(text="", size_hint_x=None,
                                           width=160, halign="center")
                self.ui.connect_layout.add_widget(self._scroll_label)

            if self.goal in (1, 2) and self.time_scrolls_required > 0:
                self._scroll_label.text = (
                    f"Time Scrolls: {self.time_scrolls_received}"
                    f"/{self.time_scrolls_required}")
            else:
                self._scroll_label.text = ""
        except Exception:
            pass

    def on_package(self, cmd: str, args: dict):
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            self.difficulty_floor = int(self.slot_data.get("difficulty_floor", 1))
            self.randomize_fighters = int(self.slot_data.get("randomize_fighters", 0))
            self.fighter_pool = int(self.slot_data.get("fighter_pool", 0))
            self.disable_giants = int(self.slot_data.get("disable_giants", 0))
            self.death_link = int(self.slot_data.get("death_link", 0))
            self.skip_cutscenes = int(self.slot_data.get("skip_cutscenes", 1))
            self.goal = int(self.slot_data.get("goal", 1))
            self.time_scrolls_required = int(self.slot_data.get("time_scrolls_required", 0))
            self.final_saga = int(self.slot_data.get("final_saga", 20))
            self.shop_checks = int(self.slot_data.get("shop_checks", 0))
            self.shop_initial = int(self.slot_data.get("shop_initial", 10))
            self.shop_restock_amount = int(self.slot_data.get("shop_restock_amount", 10))
            # Starting scenarios from slot_data (names) -> indices
            self._apply_starting_scenarios()
            # DeathLink: register the tag / handler if enabled.
            if getattr(self, "death_link", 0):
                async_start(self.update_death_link(True))
        elif cmd == "ReceivedItems":
            for net_item in args["items"]:
                self._receive_item(net_item.item)

    def on_deathlink(self, data: dict):
        """Incoming DeathLink: queue a death to apply to the current/next fight.
        CommonContext calls this when a DeathLink bounce arrives (after we've
        registered the tag via update_death_link)."""
        super().on_deathlink(data)
        self._pending_death = True

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
        elif name in CHARACTER_UNLOCK_ITEMS:
            # "<char> Character" -> roster index. Characters are AP items: mark
            # the roster index so the grant loop unlocks it for Z-Fusion/Duel.
            cname = name[:-len(" Character")]
            try:
                ridx = C.CHARACTERS.index(cname)
                self.granted_characters.add(ridx)
            except ValueError:
                pass
        elif name in FUSION_INGREDIENT_ITEMS:
            # "Ingredient: X" -> X
            self.granted_ingredients.add(name[len("Ingredient: "):])
        elif name in ABILITY_ITEMS:
            self.granted_abilities.add(name[len("Z-Item: "):])
        elif name in SUPPORT_ITEMS:
            self.granted_supports.add(name[len("Z-Support: "):])
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
        elif name == SHOP_RESTOCK_ITEM:
            self.shop_restocks_received += 1


def _difficulty_ok(value: int, floor: int) -> bool:
    # value 0=uncompleted, 1/2/3 = cleared on Level 1/2/3.
    return value >= floor and value != 0


def _handle_deathlink(ctx, status):
    """DeathLink handling — runs EVERY cycle BEFORE the mission-validity guard,
    because it depends only on battle status + screen type + health addrs, not
    on the (sometimes-unstable-mid-fight) mission region. Running it after that
    guard caused intermittent misses when a mid-fight garbage mission read
    triggered a continue and skipped the whole block."""
    if not getattr(ctx, 'death_link', 0):
        return
    screen = ctx.iface.read_screen_type()
    in_battle = (screen == C.SCREEN_DL_BATTLE)

    if in_battle and status == 0x00:
        ctx._fight_went_live = True
    if not in_battle:
        ctx._fight_went_live = False
        ctx._loss_sent = False
        ctx._victory_lock = False
        ctx._killing = False

    # Victory lockout: victory seen this fight -> no death may fire.
    if in_battle and status == C.BATTLE_STATUS_VICTORY:
        ctx._victory_lock = True

    live = getattr(ctx, '_fight_went_live', False)
    is_loss_status = status in (C.BATTLE_STATUS_DEFEAT, C.BATTLE_STATUS_SURRENDER)

    # OUTGOING: send once on a genuine loss (fight went live, ended in loss,
    # victory never seen). Anti-chain: a death we were handed doesn't echo.
    if (live and is_loss_status
            and not getattr(ctx, '_victory_lock', False)
            and not getattr(ctx, '_loss_sent', False)):
        ctx._loss_sent = True
        if getattr(ctx, '_deathlink_caused', False):
            ctx._deathlink_caused = False
        else:
            cause = ('surrendered' if status == C.BATTLE_STATUS_SURRENDER
                     else 'was defeated')
            async_start(ctx.send_death(
                f"{ctx.player_names.get(ctx.slot, 'Player')} {cause} in battle."))

    # INCOMING: apply a queued death once the fight is live; PERSIST the kill
    # (re-zero every poll) for multi-char teams until Defeat or leaving battle.
    if getattr(ctx, '_pending_death', False) and in_battle and live:
        ctx._killing = True
        ctx._pending_death = False
        ctx._deathlink_caused = True
    if getattr(ctx, '_killing', False):
        if in_battle and status not in (C.BATTLE_STATUS_DEFEAT, C.BATTLE_STATUS_SURRENDER):
            ctx.iface.kill_player()
        else:
            ctx._killing = False

    ctx._last_battle_status = status


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

        # Update the GUI Time Scroll progress label (best-effort).
        ctx.draw_scroll_counter()

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

            # ── Cutscene auto-skip (run EARLY, every poll) ─────────────────
            # The active-cutscene list head (0x003B0F00) is 0 in the overworld
            # and only nonzero while an in-game dialogue cutscene is active.
            # Zeroing it removes the scene -> the game tears it down cleanly
            # (same as the pause-menu Skip). Self-gating: a no-op when there's
            # no cutscene, so this is safe to call on every screen.
            if getattr(ctx, "skip_cutscenes", 1):
                try:
                    if ctx.iface.skip_cutscene():
                        logger.debug("[BT2] auto-skipped a cutscene")
                except Exception as e:
                    logger.debug(f"[BT2] cutscene-skip error: {e}")

            # ── DeathLink (run EARLY) ──────────────────────────────────────
            # Handle DeathLink BEFORE the mission-validity guard below, which can
            # `continue` (skip the rest of the cycle) on a mid-fight garbage
            # mission read. DeathLink only needs battle status + screen type +
            # health, so it must not be gated by mission-region validity, or
            # received deaths intermittently fail to apply.
            if getattr(ctx, "death_link", 0):
                try:
                    _handle_deathlink(ctx, ctx.iface.read_battle_status())
                except Exception as e:
                    logger.debug(f"[BT2] deathlink handler error: {e}")

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
                # ── Character lock (Model B): roster starts LOCKED ──
                # Lock every unlockable BATTLE character AP hasn't granted yet,
                # so only received characters are selectable in Z-Fusion/Duel.
                # EXCLUDE fusion-result characters — those are earned by actually
                # performing the fusion in-game (which fires their Fuse check),
                # so we must NOT re-lock them or the player could never fuse.
                if ctx._lockable_char_indices is None:
                    from .data import Recipes as _R
                    starter_names = set(_R.starters())
                    fusion_results = {n for n, (k, _r) in _R.RECIPES.items()
                                      if k == "FUSION"}
                    ctx._lockable_char_indices = [
                        i for i, nm in enumerate(C.CHARACTERS)
                        if nm not in starter_names and nm not in fusion_results
                    ]
                for ridx in ctx._lockable_char_indices:
                    if ridx not in ctx.granted_characters:
                        ctx.iface.lock_character(ridx)

                # grant ingredients/abilities/characters AP has sent
                for ing in ctx.granted_ingredients:
                    ctx.iface.grant_ingredient(ing)
                for ab in ctx.granted_abilities:
                    ctx.iface.grant_ability(ab)
                for sp in ctx.granted_supports:
                    ctx.iface.grant_support(sp)
                for ridx in ctx.granted_characters:
                    ctx.iface.grant_character(ridx)

            # ── Fighter randomization (v2): detect new DA fight, randomize once ──
            if ctx.randomize_fighters:
                _maybe_randomize_fighters(ctx)

            # ── Shop check dispenser: take over the Item Shop (screen 0x05) ──
            if ctx.shop_checks:
                _service_shop(ctx, screen)
                # The DA Namek shop is a SECOND shop inside Dragon Adventure;
                # detected by map location, not screen. Shares the check pool.
                _service_da_shop(ctx, screen)

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

            # NOTE: non-fusion characters are AP ITEMS now — no character-unlock
            # check detection. The roster is locked/granted via the lock/grant
            # loop above. Fusion-result characters ARE checks (detected below).

            # ── Fusion result checks: a fused character's roster flag turned on ──
            # Performing a fusion in Evolution Z flips the result's roster flag.
            # Fire the "Fuse: <result>" check when that happens (and wasn't set
            # at baseline / already granted as a starter).
            for loc_name, loc_id in FUSE_LOCATIONS.items():
                ridx, _addr = fuse_meta(loc_name)
                if not chars[ridx]:
                    continue
                if loc_id in ctx.checked_locations:
                    continue
                if ctx._char_baseline is not None and ctx._char_baseline[ridx]:
                    continue  # already fused/unlocked before we attached
                new_checks.append(loc_id)

            # ── Ingredient discovery checks ──
            # For MAPPED ingredients: fire "Discover: <ingredient>" when the
            # player WINS the specific in-game fight that drops it, identified
            # by (scenario, chapter, fight_id) + Battle Status == Victory. This
            # is independent of the inventory flag, so AP-granted ingredients
            # don't false-fire.
            # For UNMAPPED ingredients: fall back to the owned-flag heuristic so
            # discovery still works until every fight is mapped.
            from .data import Discovery as _Disc
            scen, chap, fid = ctx.iface.read_da_fight_context()
            status = ctx.iface.read_battle_status()
            won = (status == 0x01)
            # Latch: only act on a fresh victory transition (status just became
            # 0x01), so we don't re-fire every poll while the result screen sits.
            fresh_victory = won and not getattr(ctx, "_last_battle_won", False)
            ctx._last_battle_won = won


            # Recurring-enemy ingredients: discovered by winning ANY fight with
            # a matching fight_id (e.g. General Tao). Resolve the set of such
            # ingredients for the current victory's fight_id.
            fight_id_ings = set()
            if fresh_victory and fid is not None:
                fight_id_ings = set(_Disc.fight_id_ingredients(fid))

            for loc_name, loc_id in DISCOVER_LOCATIONS.items():
                _ii, ingname = discover_meta(loc_name)
                if loc_id in ctx.checked_locations:
                    continue
                sigs = _Disc.discovery_fights(ingname)
                if ingname in fight_id_ings:
                    # Recurring-enemy match: any fight with this fight_id.
                    new_checks.append(loc_id)
                elif sigs:
                    # Mapped: require winning one of its specific drop fights.
                    if fresh_victory and scen is not None:
                        if (scen, chap, fid) in sigs:
                            new_checks.append(loc_id)
                else:
                    # Unmapped fallback: owned-flag heuristic.
                    try:
                        if ctx.iface.read_ingredient_owned(ingname):
                            new_checks.append(loc_id)
                    except Exception:
                        pass

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

            # Merge earned shop purchase checks.
            if ctx._pending_shop_checks:
                new_checks.extend(
                    lid for lid in ctx._pending_shop_checks
                    if lid not in ctx.checked_locations
                )
                ctx._pending_shop_checks.clear()

            if new_checks:
                await ctx.send_msgs([{
                    "cmd": "LocationChecks",
                    "locations": new_checks,
                }])

            # ── Auto-hint available shop checks (queued on shop entry) ──
            if ctx._shop_hint_pending:
                to_hint_ids = []
                for loc_name in ctx._shop_hint_pending:
                    if loc_name in ctx._shop_hinted:
                        continue
                    lid = location_table.get(loc_name)
                    if lid is None or lid in ctx.checked_locations:
                        continue
                    to_hint_ids.append(lid)
                    ctx._shop_hinted.add(loc_name)
                ctx._shop_hint_pending = []
                if to_hint_ids:
                    # LocationScouts with create_as_hint=2 creates hints for these.
                    await ctx.send_msgs([{
                        "cmd": "LocationScouts",
                        "locations": to_hint_ids,
                        "create_as_hint": 2,
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

    # ALWAYS exclude non-spawnable/debug fighters (e.g. "Delete Character" 98)
    # from every pool, regardless of options.
    always_exclude = set(C.FIGHTER_CRASH_EXCLUDE)
    if always_exclude:
        filtered = [i for i in pool if i not in always_exclude]
        if filtered:
            pool = filtered

    # Disable Giants: remove giant-class fighter IDs from the pool. Falls back to
    # the unfiltered pool if filtering would leave nothing to pick from.
    if getattr(ctx, "disable_giants", 0):
        giants = set(C.FIGHTER_GIANT_IDS)
        filtered = [i for i in pool if i not in giants]
        if filtered:
            pool = filtered

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


def _service_shop(ctx: BT2Context, screen: int):
    """Take over the Item Shop. Clear all rows each poll (the shop rebuilds from
    source, so re-clearing keeps every tab empty), show the available NAMED
    check-items at unique prices, detect purchases by Zeni DROP (immune to AP
    grants), and queue auto-hints for the available shop checks on entry.
    """
    from .Locations import SHOP_SLOT_ORDER, location_table
    iface = ctx.iface
    SHOP_ID = 0x05

    on_shop = (screen == SHOP_ID)
    entering = on_shop and (ctx._shop_prev_screen != SHOP_ID)
    ctx._shop_prev_screen = screen

    if not on_shop:
        ctx._zeni_last = None
        return

    n_total = min(ctx.shop_checks, len(SHOP_SLOT_ORDER))
    available = min(
        n_total,
        ctx.shop_initial + ctx.shop_restocks_received * ctx.shop_restock_amount,
    )

    def slot_loc_id(i):
        return location_table[SHOP_SLOT_ORDER[i]]

    # A slot is "done" if its check is confirmed OR already detected this session
    # (pending send). Both hide it immediately to prevent wasted re-purchases.
    def slot_done(i):
        lid = slot_loc_id(i)
        return lid in ctx.checked_locations or lid in ctx._pending_shop_checks

    # Show the unbought slots whose index is within the unlocked range
    # [0, available). Slots beyond `available` are restock-gated and stay hidden
    # until enough Shop Restock items are received. Bought/pending slots within
    # range are simply not shown (they don't get replaced by gated ones).
    to_show = [i for i in range(available) if i < n_total and not slot_done(i)]

    # Clear the whole shop every poll (matches the proven PoC).
    try:
        iface.shop_grant_members_card()  # unlock full shop (weak card caps rows)
        # One-time: zero owned qty of every check-item so a stock of 1 yields
        # exactly one buyable (buyable = stock - owned). Without this, items the
        # player already owns (e.g. starting Health +1) show 0 buyable.
        if not ctx._shop_owned_zeroed:
            for (cat_idx, _name) in C.SHOP_CHECK_SLOTS:
                iface.zero_item_owned(cat_idx)
            ctx._shop_owned_zeroed = True
        # Keep already-bought check-items at owned=0 every poll. The game adds
        # the real stat item on purchase (possibly a frame after the Zeni drop we
        # detect), so a one-shot decrement can miss; re-zeroing here guarantees
        # bought check-items never accumulate in inventory.
        for cat_idx in ctx._shop_bought_cats:
            iface.zero_item_owned(cat_idx)
        iface.shop_clear_all()
        if ctx._zeni_last is None:
            ctx._zeni_last = iface.read_zeni()
    except Exception:
        return

    # Re-assert shown rows: curated catalog index (named item) + unique price.
    for i in to_show:
        cat_idx, _item = C.SHOP_CHECK_SLOTS[i]
        price = C.SHOP_CHECK_PRICE_BASE + i * C.SHOP_CHECK_PRICE_STEP
        iface.shop_show_row(cat_idx, price, stock=1, category=0)

    # Queue auto-hints for the available (shown) shop checks, once on entry.
    if entering:
        ctx._shop_hint_pending = [SHOP_SLOT_ORDER[i] for i in to_show
                                  if slot_loc_id(i) not in ctx.checked_locations]

    # Purchase detection via Zeni drop.
    # The client always grants the Gold Member's Card, which applies a ~50%
    # discount, so the actual Zeni drop is the DISCOUNTED price. Prices are
    # spaced by STEP (100), so discounted amounts are ~50 apart -> match the drop
    # to the shown slot whose discounted price is closest, within a tolerance.
    try:
        zeni = iface.read_zeni()
    except Exception:
        return
    if ctx._zeni_last is not None and zeni < ctx._zeni_last:
        drop = ctx._zeni_last - zeni
        best_i, best_err = None, None
        for i in to_show:
            full = C.SHOP_CHECK_PRICE_BASE + i * C.SHOP_CHECK_PRICE_STEP
            disc = full // 2  # Gold card ~50% off (client always grants it)
            err = abs(drop - disc)
            if best_err is None or err < best_err:
                best_err, best_i = err, i
        if best_i is not None and best_err is not None and best_err <= 20:
            lid = slot_loc_id(best_i)
            if lid not in ctx.checked_locations and lid not in ctx._pending_shop_checks:
                ctx._pending_shop_checks.add(lid)
                # The shop check-item is just a trigger; remove the real stat
                # item the game added to inventory so it doesn't accumulate.
                bought_cat_idx, _name = C.SHOP_CHECK_SLOTS[best_i]
                iface.decrement_item_owned(bought_cat_idx, 1)
                ctx._shop_bought_cats.add(bought_cat_idx)
                logger.info(f"[BT2] Shop purchase -> {SHOP_SLOT_ORDER[best_i]}")
    ctx._zeni_last = zeni

def _service_da_shop(ctx: BT2Context, screen: int):
    """Take over any in-Dragon-Adventure item shop (Namek, Earth, ...). These
    are SECOND shops with the same record layout as the main shop, each at its
    own table base, detected by the DA map location id (DA_SHOPS registry).
    Clears all rows each poll, shows available stat-ladder check-items at unique
    prices, and detects purchases by Zeni drop. SHARES the main shop's check
    pool and guards, so a given shop check fires once across ALL shops.

    Only the 57 stat-ladder checks (Health/Ki/Attack +1..+19) map to DA slots
    (DA slot == main catalog index for catalog 0-56). Blast / Ultimate Blast
    (catalog 100/150) have no DA stat slot and stay main-shop-only.
    """
    from .Locations import SHOP_SLOT_ORDER, location_table
    iface = ctx.iface

    rec0_base = iface.current_da_shop_base()   # None unless in a known DA shop
    on_shop = rec0_base is not None
    entering = on_shop and not getattr(ctx, "_da_shop_prev", False)
    ctx._da_shop_prev = on_shop

    if not on_shop:
        ctx._da_zeni_last = None
        return

    n_total = min(ctx.shop_checks, len(SHOP_SLOT_ORDER))
    available = min(
        n_total,
        ctx.shop_initial + ctx.shop_restocks_received * ctx.shop_restock_amount,
    )

    def slot_loc_id(i):
        return location_table[SHOP_SLOT_ORDER[i]]

    def slot_done(i):
        lid = slot_loc_id(i)
        return lid in ctx.checked_locations or lid in ctx._pending_shop_checks

    def da_slot_for(i):
        cat_idx, _name = C.SHOP_CHECK_SLOTS[i]
        return cat_idx if cat_idx <= 56 else None

    to_show = [i for i in range(available)
               if i < n_total and not slot_done(i) and da_slot_for(i) is not None]

    try:
        iface.shop_grant_members_card()       # Gold card -> 50% discount (same as main)
        iface.da_shop_clear_all(rec0_base)    # hide all DA rows every poll
        if ctx._da_zeni_last is None:
            ctx._da_zeni_last = iface.read_zeni()
    except Exception:
        return

    for i in to_show:
        da_slot = da_slot_for(i)
        price = C.SHOP_CHECK_PRICE_BASE + i * C.SHOP_CHECK_PRICE_STEP
        iface.da_shop_show_row(rec0_base, da_slot, price, stock=1)

    if entering:
        ctx._shop_hint_pending = [SHOP_SLOT_ORDER[i] for i in to_show
                                  if slot_loc_id(i) not in ctx.checked_locations]

    try:
        zeni = iface.read_zeni()
    except Exception:
        return
    if ctx._da_zeni_last is not None and zeni < ctx._da_zeni_last:
        drop = ctx._da_zeni_last - zeni
        best_i, best_err = None, None
        for i in to_show:
            full = C.SHOP_CHECK_PRICE_BASE + i * C.SHOP_CHECK_PRICE_STEP
            disc = full // 2
            err = abs(drop - disc)
            if best_err is None or err < best_err:
                best_err, best_i = err, i
        if best_i is not None and best_err is not None and best_err <= 20:
            lid = slot_loc_id(best_i)
            if lid not in ctx.checked_locations and lid not in ctx._pending_shop_checks:
                ctx._pending_shop_checks.add(lid)
                bought_cat_idx, _name = C.SHOP_CHECK_SLOTS[best_i]
                iface.decrement_item_owned(bought_cat_idx, 1)
                ctx._shop_bought_cats.add(bought_cat_idx)
                logger.info(f"[BT2] DA shop purchase -> {SHOP_SLOT_ORDER[best_i]}")
    ctx._da_zeni_last = zeni


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
