"""
BT2Interface — PCSX2/PINE memory interface for Budokai Tenkaichi 2 (SLUS-21441).
Handles all game memory reads/writes. No code caves in v1; pure flag I/O.

Supported version:
    CRC FE961D28 — SLUS-21441, NTSC-U v1.00
"""
import os
import socket
import time
from platform import system
from typing import Optional
from logging import Logger

from .data import Constants as C

GAME_ID = "SLUS-21441"
GAME_CRC = "fe961d28"


# ─── PINE CLIENT (identical protocol to B3) ──────────────────────────────────

class Pine:
    def __init__(self, slot=28011):
        self._slot = slot
        self._sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        try:
            if system() == "Windows":
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(5.0)
                self._sock.connect(("127.0.0.1", self._slot))
            elif system() == "Darwin":
                self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._sock.settimeout(5.0)
                self._sock.connect(os.environ.get("TMPDIR", "/tmp") + "/pcsx2.sock")
            else:
                self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._sock.settimeout(5.0)
                self._sock.connect(os.environ.get("XDG_RUNTIME_DIR", "/tmp") + "/pcsx2.sock")
            return True
        except Exception:
            self._sock = None
            return False

    def disconnect(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def is_connected(self) -> bool:
        return self._sock is not None

    def _send(self, req: bytes) -> bytes:
        self._sock.sendall(req)
        result = b""
        end = 4
        while len(result) < end:
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            result += chunk
            if end == 4 and len(result) >= 4:
                end = int.from_bytes(result[:4], "little")
                if end < 5 or end > 65536:
                    break
        return result

    def _req(self, cmd: int, addr: int, extra: bytes = b"") -> bytes:
        size = 9 + len(extra)
        return (size.to_bytes(4, "little") +
                cmd.to_bytes(1, "little") +
                addr.to_bytes(4, "little") +
                extra)

    def read8(self, addr: int) -> int:
        return int.from_bytes(self._send(self._req(0, addr))[-1:], "little")

    def read16(self, addr: int) -> int:
        return int.from_bytes(self._send(self._req(1, addr))[-2:], "little")

    def read32(self, addr: int) -> int:
        return int.from_bytes(self._send(self._req(2, addr))[-4:], "little")

    def write8(self, addr: int, val: int):
        self._send(self._req(4, addr, (val & 0xFF).to_bytes(1, "little")))

    def write16(self, addr: int, val: int):
        self._send(self._req(5, addr, (val & 0xFFFF).to_bytes(2, "little")))

    def write32(self, addr: int, val: int):
        self._send(self._req(6, addr, (val & 0xFFFFFFFF).to_bytes(4, "little")))

    def get_game_id(self) -> str:
        msg = (5).to_bytes(4, "little") + (0x0C).to_bytes(1, "little")
        resp = self._send(msg)
        return resp[9:-1].decode("ascii", errors="ignore").strip()

    def get_game_crc(self) -> str:
        msg = (5).to_bytes(4, "little") + (0x0D).to_bytes(1, "little")
        resp = self._send(msg)
        return resp[9:-1].decode("ascii", errors="ignore").strip()


# ─── BT2 INTERFACE ────────────────────────────────────────────────────────────

class BT2Interface:
    def __init__(self, logger: Logger):
        self.pine = Pine()
        self.logger = logger
        self._game_id: Optional[str] = None

    # ── Connection ──
    def connect(self) -> bool:
        if not self.pine.connect():
            return False
        try:
            crc = (self.pine.get_game_crc() or "").lower()
            gid = self.pine.get_game_id()
            self.logger.info(f"[BT2] Game: {gid!r} CRC: {crc!r}")
            if crc != GAME_CRC:
                self.logger.warning(
                    f"[BT2] Unsupported CRC {crc!r}; expected {GAME_CRC} (SLUS-21441 NTSC-U).")
                return False
            self._game_id = gid or GAME_ID
            self.logger.info(f"[BT2] Connected — DBZ Budokai Tenkaichi 2 ({crc.upper()})")
            return True
        except Exception as e:
            self.logger.warning(f"[BT2] Connect error: {e}")
            return False

    def disconnect(self):
        self.pine.disconnect()
        self._game_id = None

    def is_connected(self) -> bool:
        return self.pine.is_connected() and self._game_id is not None

    # ── Screen-state context ──
    def get_screen_identificator(self) -> int:
        """0x76BDDC: 0x05=Item Shop, 0x07=Dragon Adventure map/menu/battle, etc."""
        return self.pine.read8(C.ADDR_SCREEN_TYPE)

    def on_dragon_adventure(self) -> bool:
        return self.get_screen_identificator() == 0x07

    def on_main_menu(self) -> bool:
        return self.get_screen_identificator() == 0x04

    def on_shop(self) -> bool:
        return self.get_screen_identificator() == 0x05

    def safe_for_da_writes(self) -> bool:
        """Only write DA flags on the DA map/menu (not mid-battle/cutscene)."""
        return self.get_screen_identificator() == 0x07

    # ── Cutscene auto-skip ──
    def cutscene_active(self) -> bool:
        """True when an in-game dialogue cutscene is playing/loading. The list
        head at 0x003B0F00 is 0 in the overworld and only nonzero while a
        cutscene scene is active, so reading nonzero is itself the detector."""
        try:
            return self.pine.read32(C.ADDR_CUTSCENE_LIST_HEAD) != 0
        except Exception:
            return False

    def skip_cutscene(self) -> bool:
        """Remove the active in-game cutscene scene so the game tears it down and
        transitions out cleanly (same effect as the pause-menu Skip). Returns
        True if a cutscene was present and we issued the skip write. Safe to call
        unconditionally: in the overworld the head is already 0, so this no-ops."""
        try:
            if self.pine.read32(C.ADDR_CUTSCENE_LIST_HEAD) != 0:
                self.pine.write32(C.ADDR_CUTSCENE_LIST_HEAD, 0)
                return True
        except Exception:
            pass
        return False

    # ── Post-mission save-prompt auto-skip ──
    def save_prompt_id(self) -> int:
        """Return the active save-popup prompt id IF a real save popup is up,
        else None. A save popup requires ALL gates: save-flow active
        (0x3B26B0==2), Menu screen (0x76BD18==0), modal state (0x76BD1C==0x10),
        a valid Dragon Adventure map location (0x387AB8 != 0 — this is what
        excludes the post-saga SCENARIO-SELECT screen, where every other value
        coincides but the map reads 0), and the prompt id being one of the two
        save popups. Returns the id (0x1C "Save Game Data?" / 0x2F "Exit
        Saving?") or None."""
        try:
            if self.pine.read32(C.ADDR_SAVE_TRANS) != C.SAVE_TRANS_ACTIVE:
                return None
            if self.pine.read8(C.ADDR_SCREEN_TYPE_DL) != C.SCREEN_DL_MENU:
                return None
            if self.pine.read8(C.ADDR_SCREEN_STATE) != C.SCREEN_STATE_MODAL:
                return None
            if self.pine.read16(C.ADDR_DA_MAP_LOCATION) == 0:
                return None  # not on a map (scenario-select) -> not a real popup
            pid = self.pine.read8(C.ADDR_SAVE_PROMPT_ID)
            if pid in (C.PROMPT_SAVE_DATA, C.PROMPT_EXIT_SAVING):
                return pid
        except Exception:
            pass
        return None

    def confirm_save_popup(self) -> bool:
        """Dismiss the currently-showing save popup(s) WITHOUT a card write,
        picking the correct option for whichever popup is up. Returns True only
        if a save popup was dismissed (the prompt actually cleared/changed), so
        the caller never latches 'done' on a confirm that didn't land.

        We force the cursor to our choice and pulse the X confirm (open loop):
        each step writes the cursor IMMEDIATELY before the X so the option is our
        value on the frame the press is read, and repeats so it lands on the
        game's input-poll frame. We re-read the prompt id each step so we target
        the right option for the popup actually on screen and stop as soon as the
        popups are gone. Only ever called while a real save popup is up, so the
        pad write can't reach gameplay."""
        start_pid = self.save_prompt_id()
        if start_pid is None:
            return False
        try:
            misses = 0
            for _ in range(20):
                pid = self.save_prompt_id()
                if pid is None:
                    # Could be fully done, OR a transient gap between popup1
                    # closing and popup2 appearing. Confirm it's really clear by
                    # requiring two consecutive misses before stopping.
                    misses += 1
                    if misses >= 2:
                        break
                    time.sleep(0.016)
                    continue
                misses = 0
                want = (C.SAVE_POPUP1_CURSOR if pid == C.PROMPT_SAVE_DATA
                        else C.SAVE_POPUP2_CURSOR)
                # write cursor twice (settle), then X — cursor is our value on
                # the confirm frame, fixing the occasional wrong-option pick.
                self.pine.write8(C.ADDR_SAVE_CURSOR, want)
                self.pine.write8(C.ADDR_SAVE_CURSOR, want)
                self.pine.write8(C.ADDR_SAVE_PAD, C.SAVE_PAD_CONFIRM)
                time.sleep(0.016)
        except Exception:
            pass
        # success ONLY when no save popup remains. Returning True merely because
        # the prompt CHANGED (e.g. popup1 0x1C -> popup2 0x2F) would let the
        # caller latch 'done' while popup2 is still up, getting stuck on it. So
        # we report success only when fully clear; otherwise the caller retries.
        return self.save_prompt_id() is None

    # ── Missions (RECORD) ──
    def read_mission(self, scenario_index: int, mission_index: int) -> int:
        """Return completion value 0/1/2/3 for a mission."""
        offset = sum(c for _n, c in C.SCENARIOS[:scenario_index]) + mission_index
        return self.pine.read8(C.DA_FIGHTS_BASE + offset)

    def read_all_missions(self) -> bytes:
        """Read the entire 200-byte mission array at once (via 4-byte reads)."""
        data = bytearray()
        addr = C.DA_FIGHTS_BASE
        total = C.TOTAL_MISSIONS
        while len(data) < total:
            word = self.pine.read32(addr + len(data))
            data += word.to_bytes(4, "little")
        return bytes(data[:total])

    # ── Scenario gates (ENFORCE) ──
    def set_scenario_unlocked(self, scenario_index: int, unlocked: bool):
        addr = C.scenario_gate_addr(scenario_index)
        if unlocked:
            cur = self.pine.read8(addr)
            self.pine.write8(addr, cur | 0x01)
            self.pine.write16(addr + 2, 1)
        else:
            cur = self.pine.read8(addr)
            self.pine.write8(addr, cur & ~0x01)
            self.pine.write16(addr + 2, 0)

    def read_scenario_unlocked(self, scenario_index: int) -> bool:
        return (self.pine.read8(C.scenario_gate_addr(scenario_index)) & 0x01) != 0

    def enforce_scenarios(self, unlocked_indices: set):
        """Hold scenario gates: set granted, clear all others. Call on DA map."""
        for si in range(len(C.SCENARIOS)):
            self.set_scenario_unlocked(si, si in unlocked_indices)

    # ── Characters (RECORD; never zeroed once earned) ──
    def read_character_unlocked(self, roster_index: int) -> bool:
        return (self.pine.read8(C.character_addr(roster_index)) & 0x01) != 0

    def read_all_characters(self) -> list:
        """Return list of bools for all 129 character flags."""
        out = []
        for i in range(len(C.CHARACTERS)):
            out.append((self.pine.read8(C.character_addr(i)) & 0x01) != 0)
        return out

    def grant_character(self, roster_index: int):
        addr = C.character_addr(roster_index)
        cur = self.pine.read8(addr)
        self.pine.write8(addr, cur | 0x01)
        self.pine.write16(addr + 2, 1)

    def lock_character(self, roster_index: int):
        """Clear a character's roster unlock flag (the inverse of
        grant_character). Used to keep the roster locked until AP grants the
        character. Only affects Z-Fusion/Duel selectability; story fights use
        their own forced characters and are unaffected."""
        addr = C.character_addr(roster_index)
        cur = self.pine.read8(addr)
        self.pine.write8(addr, cur & ~0x01)
        self.pine.write16(addr + 2, 0)

    # ── Dragon Adventure fight context (for ingredient discovery) ──
    def read_da_fight_context(self):
        """Return (scenario, chapter, fight_id) from the live Dragon Adventure
        context, or (None, None, None) on failure. fight_id distinguishes the
        main vs optional fights within a chapter."""
        try:
            scen = self.pine.read32(C.ADDR_DA_SCENARIO)
            chap = self.pine.read32(C.ADDR_DA_CHAPTER)
            fid = self.pine.read32(C.ADDR_DA_FIGHT_ID)
            return (scen, chap, fid)
        except Exception:
            return (None, None, None)

    def read_battle_status(self) -> int:
        """Battle status: 0x00 pending, 0x01 victory, 0x02 defeat, 0x08
        surrender. Returns -1 on failure."""
        try:
            return self.pine.read8(C.ADDR_BATTLE_STATUS)
        except Exception:
            return -1

    def kill_player(self) -> bool:
        """DeathLink incoming: zero ALL of Player 1's character health gauges to
        force a loss in the current fight. Returns True if any write succeeded.
        Safe to call when not in a fight (writes simply have no visible effect)."""
        ok = False
        for addr in C.ADDR_P1_HEALTH:
            try:
                self.pine.write32(addr, 0)
                ok = True
            except Exception:
                pass
        return ok

    def read_screen_type(self) -> int:
        """Screen Type: 0x00 Menu, 0x01 Battle, 0x08 Dragon Adventure Nav.
        Returns -1 on failure."""
        try:
            return self.pine.read8(C.ADDR_SCREEN_TYPE_DL)
        except Exception:
            return -1

    def in_active_fight(self) -> bool:
        """True only when the Screen Type says we're in Battle (0x01). Incoming
        DeathLinks are applied only here; on Menu/DA-Nav they stay buffered."""
        return self.read_screen_type() == C.SCREEN_DL_BATTLE

    # ── Fusion ingredients (granted to inventory) ──
    def read_ingredient_owned(self, ingredient_name: str) -> bool:
        """True if the fusion ingredient is owned (unlock bit set OR quantity
        > 0). Used to fire 'Discover: <ingredient>' checks the first time the
        player obtains an ingredient."""
        addr = C.FUSION_ITEM_ADDR.get(ingredient_name)
        if addr is None:
            return False
        try:
            owned_bit = (self.pine.read8(addr) & 0x01) != 0
            qty = self.pine.read16(addr + 2)
            return owned_bit or qty > 0
        except Exception:
            return False

    def grant_ingredient(self, ingredient_name: str):
        addr = C.FUSION_ITEM_ADDR.get(ingredient_name)
        if addr is None:
            return
        cur = self.pine.read8(addr)
        self.pine.write8(addr, cur | 0x01)
        # "Z Item Fusion" is the GENERIC fusion capsule consumed by EVERY fusion
        # (one per fuse), so the player needs an effectively unlimited supply.
        # Keep it topped up to 999; the re-assert loop refills it as fusions
        # consume it. All other ingredients are specific, consumable items and
        # stay at quantity 1 (their consumable logic is enforced elsewhere).
        if ingredient_name == "Z Item Fusion":
            self.pine.write16(addr + 2, 999)
        else:
            q = self.pine.read16(addr + 2)
            self.pine.write16(addr + 2, max(q, 1))

    # ── Ability items (useful) ──
    def grant_ability(self, ability_name: str):
        addr = C.ABILITY_ITEM_ADDR.get(ability_name)
        if addr is None:
            return
        cur = self.pine.read8(addr)
        self.pine.write8(addr, cur | 0x01)
        q = self.pine.read16(addr + 2)
        self.pine.write16(addr + 2, max(q, 1))

    def grant_support(self, support_name: str):
        addr = C.SUPPORT_ITEM_ADDR.get(support_name)
        if addr is None:
            return
        cur = self.pine.read8(addr)
        self.pine.write8(addr, cur | 0x01)
        q = self.pine.read16(addr + 2)
        self.pine.write16(addr + 2, max(q, 1))

    # ── Zeni (filler) ──
    def add_zeni(self, amount: int):
        if C.ADDR_ZENI == 0:
            return  # address not yet confirmed
        cur = self.pine.read32(C.ADDR_ZENI)
        self.pine.write32(C.ADDR_ZENI, cur + amount)

    # ── Shop control + Zeni purchase detection ──
    def read_zeni(self) -> int:
        return self.pine.read32(C.ADDR_ZENI)

    def shop_clear_all(self, catalog_n: int = None):
        """Universal clear: write 0 to every record's +0x04 (hides all rows,
        any category). Done once on shop entry."""
        n = catalog_n if catalog_n is not None else C.SHOP_CATALOG_SIZE
        base = C.SHOP_STOCK_BASE
        for idx in range(n):
            try:
                self.pine.write8(base + idx * C.SHOP_RECORD_STRIDE + 0x04, 0x00)
            except Exception:
                pass

    def shop_show_row(self, catalog_index: int, price: int, stock: int = 1,
                      category: int = 0):
        """Show one row: set shown marker, item, price, stock."""
        base = C.SHOP_STOCK_BASE + catalog_index * C.SHOP_RECORD_STRIDE
        marker = C.SHOP_CAT_SHOWN_MARKER.get(category, 0x36)
        try:
            self.pine.write8(base + 0x04, marker)          # show marker
            self.pine.write32(base + 0x08, catalog_index)  # item
            self.pine.write32(base + 0x1C, price)          # unique price
            self.pine.write16(base + 0x14, stock)          # stock
        except Exception:
            pass

    def read_da_map_location(self) -> int:
        """16-bit Dragon Adventure map location id (0x09CC = Namek Item Shop).
        Used to detect when the player is in the in-DA Namek shop."""
        try:
            return self.pine.read16(C.DA_MAP_LOCATION)
        except Exception:
            return 0

    def in_da_namek_shop(self) -> bool:
        return self.read_da_map_location() == C.DA_NAMEK_SHOP_LOC

    def current_da_shop_base(self):
        """If the player is in a known in-DA shop, return its table rec0 base;
        else None. Multiple shops (Namek, Earth) share the same layout, keyed by
        map location id."""
        loc = self.read_da_map_location()
        return C.DA_SHOPS.get(loc)

    def da_shop_clear_all(self, rec0_base: int, count: int = 400):
        """Hide every DA shop row (write 0 to each record's +0x04 marker), for
        the table at rec0_base. Clear a wide range (the shop holds far more than
        the 57 stat slots)."""
        for idx in range(count):
            try:
                self.pine.write8(rec0_base + idx * C.DA_SHOP_STRIDE + C.DA_SHOP_OFF_MARKER, 0x00)
            except Exception:
                pass

    def da_shop_show_row(self, rec0_base: int, slot_index: int, price: int, stock: int = 1):
        """Show one DA shop row (marker 0x36 + price + stock) at rec0_base. The
        stat ladder's item identity is positional, so we set marker/price/stock
        and leave the native item index."""
        base = rec0_base + slot_index * C.DA_SHOP_STRIDE
        try:
            self.pine.write8(base + C.DA_SHOP_OFF_MARKER, C.DA_SHOP_SHOWN_MARKER)
            self.pine.write32(base + C.DA_SHOP_OFF_PRICE_REAL, price)
            self.pine.write16(base + C.DA_SHOP_OFF_STOCK, stock)
        except Exception:
            pass

    def zero_item_owned(self, catalog_index: int):
        """Zero the player's owned quantity of a catalog item so a shop stock of
        1 yields exactly one buyable (the 'buyable' count is stock minus owned).
        catalog index == ability-array slot; quantity is at +0x02."""
        try:
            addr = C.ABILITY_BASE + catalog_index * 4
            self.pine.write16(addr + 0x02, 0)   # owned quantity -> 0
        except Exception:
            pass

    def decrement_item_owned(self, catalog_index: int, amount: int = 1):
        """Subtract `amount` from a catalog item's owned quantity (floored at 0).
        Used after a shop CHECK purchase: the shop item is just a trigger for the
        AP check, so we remove the real stat item the game added to inventory.
        catalog index == ability-array slot; quantity is at +0x02."""
        try:
            addr = C.ABILITY_BASE + catalog_index * 4
            cur = self.pine.read16(addr + 0x02)
            new = max(0, cur - amount)
            self.pine.write16(addr + 0x02, new)
        except Exception:
            pass

    def shop_grant_members_card(self):
        """Grant the Gold Member's Card so the shop displays ALL items (a weak
        card caps the visible item count)."""
        try:
            self.pine.write16(C.ADDR_MEMBERS_CARD_GOLD, 1)       # unlocked bit0
            self.pine.write16(C.ADDR_MEMBERS_CARD_GOLD_QTY, 1)   # quantity
        except Exception:
            pass

    # ── Dragon Balls + Wish (RECORD) ──
    def read_dragonball_unlocked(self, n: int) -> bool:
        """n is 0-based (0=1★..6=7★). True if that ball is collected."""
        return (self.pine.read8(C.dragonball_unlocked_addr(n)) & 0x01) != 0

    def read_all_dragonballs(self) -> list:
        return [self.read_dragonball_unlocked(i) for i in range(C.DRAGONBALL_COUNT)]

    def read_map_location(self) -> int:
        """16-bit current Dragon Adventure map node (0x387AB8)."""
        return self.pine.read16(C.ADDR_DA_MAP_LOCATION)

    def at_summon_node(self) -> bool:
        """True if the player is at Shenron or Porunga (wish trigger)."""
        loc = self.read_map_location()
        return loc in (C.MAP_NODE_SHENRON, C.MAP_NODE_PORUNGA)

    def set_dragonball(self, n: int, owned: bool):
        """Set/clear a Dragon Ball's unlocked flag (bit0) and quantity. n is
        0-based (0=1★..6=7★)."""
        addr = C.dragonball_unlocked_addr(n)
        cur = self.pine.read8(addr)
        if owned:
            self.pine.write8(addr, cur | 0x01)
            self.pine.write16(addr + 2, 1)   # quantity = 1
        else:
            self.pine.write8(addr, cur & ~0x01)
            self.pine.write16(addr + 2, 0)   # quantity = 0

    def enforce_dragonballs(self, granted: set):
        """Hold the 7 Dragon Ball flags to match the AP-granted set: set granted
        balls, clear any the game handed out that AP didn't grant."""
        for n in range(C.DRAGONBALL_COUNT):
            self.set_dragonball(n, n in granted)

    # ── Dragon Adventure character randomizer (v2) ──
    def read_current_mission(self):
        """Return (scenario_byte, chapter, linear_index) for the current DA fight."""
        scen = self.pine.read8(C.ADDR_DA_CURRENT_SCENARIO)
        chap = self.pine.read8(C.ADDR_DA_CURRENT_CHAPTER)
        lin = C.da_linear_mission_index(scen, chap)
        return scen, chap, lin

    def read_matchup_signature(self):
        """Read a signature of both team blocks — enough words to detect when
        the matchup has fully populated and settled (not just slot 1). Used to
        (a) detect a new fight and (b) gate randomization on a stable block."""
        try:
            words = []
            for base in (C.ADDR_DA_MATCHUP_P1_BASE, C.ADDR_DA_MATCHUP_P2_BASE):
                addr = base
                for _ in range(5):  # up to 5 slots per team
                    words.append(self.pine.read32(addr))
                    addr += C.DA_MATCHUP_SLOT_STRIDE
            return tuple(words)
        except Exception:
            return None

    def matchup_block_valid(self) -> bool:
        """True if the matchup block holds a plausible team list (slot 1 is a
        real roster ID and a terminator appears within 5 slots)."""
        try:
            for base in (C.ADDR_DA_MATCHUP_P1_BASE, C.ADDR_DA_MATCHUP_P2_BASE):
                first = self.pine.read32(base)
                if first == C.DA_MATCHUP_TERMINATOR or first > len(C.CHARACTERS):
                    return False
                # require a terminator within 5 slots
                addr = base
                ok = False
                for _ in range(6):
                    if self.pine.read32(addr) == C.DA_MATCHUP_TERMINATOR:
                        ok = True
                        break
                    addr += C.DA_MATCHUP_SLOT_STRIDE
                if not ok:
                    return False
            return True
        except Exception:
            return False

    def _team_slots(self, base):
        """Return a LIST of occupied character slot addresses (until the
        0xFFFFFFFF terminator, max 5). Materialized up front so writes during
        iteration can't disturb the walk."""
        slots = []
        addr = base
        for _ in range(5):
            val = self.pine.read32(addr)
            if val == C.DA_MATCHUP_TERMINATOR:
                break
            slots.append(addr)
            addr += C.DA_MATCHUP_SLOT_STRIDE
        return slots

    def randomize_matchup(self, pick_fn, sides=("p1", "p2")):
        """Walk each requested team and write a randomized roster ID (from
        pick_fn(slot_seq)) into every occupied slot. Writes the ID byte (write8)
        AND resets the slot's COSTUME field (+0x0C) to 0, because the new
        character may not have the original character's costume index, and an
        invalid costume crashes the loader (confirmed: Salza + costume 5 -> VIF
        FIFO crash; costume 0 loads fine). Other params are preserved."""
        bases = []
        if "p1" in sides:
            bases.append(C.ADDR_DA_MATCHUP_P1_BASE)
        if "p2" in sides:
            bases.append(C.ADDR_DA_MATCHUP_P2_BASE)
        seq = 0
        written = []
        for base in bases:
            for slot_addr in self._team_slots(base):
                new_id = pick_fn(seq) & 0xFF
                self.pine.write8(slot_addr, new_id)        # ID byte
                try:
                    self.pine.write8(slot_addr + 0x0C, 0)  # costume -> 0 (always valid)
                except Exception:
                    pass
                written.append((slot_addr, new_id))
                seq += 1
        if written:
            detail = ", ".join(f"0x{a:08X}={v}" for a, v in written)
            self.logger.info(f"[BT2] matchup writes: {detail}")
        return seq
