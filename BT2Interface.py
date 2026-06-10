"""
BT2Interface — PCSX2/PINE memory interface for Budokai Tenkaichi 2 (SLUS-21441).
Handles all game memory reads/writes. No code caves in v1; pure flag I/O.

Supported version:
    CRC FE961D28 — SLUS-21441, NTSC-U v1.00
"""
import os
import socket
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

    # ── Fusion ingredients (granted to inventory) ──
    def grant_ingredient(self, ingredient_name: str):
        addr = C.FUSION_ITEM_ADDR.get(ingredient_name)
        if addr is None:
            return
        cur = self.pine.read8(addr)
        self.pine.write8(addr, cur | 0x01)
        # bump quantity so it's usable in fusion
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

    # ── Zeni (filler) ──
    def add_zeni(self, amount: int):
        if C.ADDR_ZENI == 0:
            return  # address not yet confirmed
        cur = self.pine.read32(C.ADDR_ZENI)
        self.pine.write32(C.ADDR_ZENI, cur + amount)

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
        pick_fn(slot_seq)) into every occupied slot. Writes ONLY the ID byte
        (write8) so the slot's other params are preserved — this matches the
        confirmed-working manual single-byte write. A 4-byte write would zero
        the trailing params and crash the loader."""
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
                self.pine.write8(slot_addr, new_id)  # ID byte only; preserve params
                written.append((slot_addr, new_id))
                seq += 1
        if written:
            detail = ", ".join(f"0x{a:08X}={v}" for a, v in written)
            self.logger.info(f"[BT2] matchup writes: {detail}")
        return seq
