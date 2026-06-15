"""
Dragon Ball Z: Budokai Tenkaichi 2 - Archipelago data tables.

All addresses are PS2 main-RAM offsets (PINE address space), NTSC-U.
Source: RetroAchievements code notes (set by RyudoSynbios) + community fusion guide.

Flag layout convention (shared by every "Z-Item" category):
    base + 0 : [8-bit] unlocked flag (bit0)
    base + 2 : [16-bit] quantity

Categories:
    DA_FIGHTS        - 200 Dragon Adventure mission completion bytes (RECORD)
    SCENARIO_GATES   - 24 secret-type scenario unlock flags          (ENFORCE)
    CHARACTERS       - 129 secret-type character unlock flags         (RECORD)
    FUSION_ITEMS     - 60 fusion-type Z-Items (ingredients + meta)    (item pool)
    ABILITY_ITEMS    - 155 stat-boost Z-Items                         (filler/useful)
    SUPPORT_ITEMS    - ~95 support Z-Items                            (filler/useful)
"""

# ─────────────────────────────────────────────
#  Context / screen-state addresses
# ─────────────────────────────────────────────
ADDR_SCREEN_TYPE      = 0x76BDDC   # 0x07 = Dragon Adventure map/menu/battle
ADDR_SCREEN_SUBTYPE   = 0x76BDD8   # (Screen Type: 0x08 = DA Navigation)
ADDR_DA_SCENARIO      = 0x76BDF0   # current scenario index (read-only context)
ADDR_DA_CHAPTER       = 0x76BDF4
ADDR_DA_GAME_LEVEL    = 0x76BDF8
ADDR_DA_FIGHT_ID      = 0x76BDFC   # per-fight id within a chapter (main vs optional differ)
ADDR_BATTLE_STATUS    = 0x76BCC0   # 8-bit: 0x00 pending, 0x01 victory, 0x02 defeat, 0x08 surrender
ADDR_ZENI             = 0x63383C   # [32-bit] Current Zeni -- CONFIRMED (write renders live)

SCREEN_DA_MAP = 0x07               # safe-to-write value for DA flags

# ─────────────────────────────────────────────
#  Dragon Adventure fight array (RECORD)
#  Contiguous, 1 byte per mission, base 0x63100C.
#  Value: 0 = uncompleted, 1/2/3 = cleared on Game Level 1/2/3.
# ─────────────────────────────────────────────
DA_FIGHTS_BASE = 0x63100C

# (scenario name, number of missions) -- order matches the contiguous array
# and the 0x76BDF0 scenario index.
SCENARIOS = [
    ("Saiyan Saga", 17),
    ("Tree of Might", 3),
    ("Lord Slug", 3),
    ("Final Battle", 3),
    ("Frieza Saga", 20),
    ("Makyo Star", 3),
    ("Cooler's Revenge", 5),
    ("The Return of Cooler", 7),
    ("The Story of Trunks", 3),
    ("Android Saga", 24),
    ("Super Android 13", 5),
    ("Broly: The Legendary Super Saiyan", 7),
    ("Ultimate Future Warrior", 3),
    ("Bojack Unbound", 8),
    ("Majin Buu Saga", 21),
    ("Broly: The Second Coming", 6),
    ("Fusion Reborn", 11),
    ("Wrath of the Dragon", 7),
    ("Baby, The Avenger", 5),
    ("Ultimate Android", 6),
    ("Evil Dragon of Absolute Destruction", 6),
    ("Fateful Brothers", 9),
    ("Beautiful Treachery...", 9),
    ("Destined Rivals", 9),
]

TOTAL_MISSIONS = sum(n for _, n in SCENARIOS)  # 200


def scenario_mission_range(scenario_index: int) -> range:
    """Return the range of DA_FIGHTS addresses belonging to a scenario."""
    offset = sum(n for _, n in SCENARIOS[:scenario_index])
    count = SCENARIOS[scenario_index][1]
    start = DA_FIGHTS_BASE + offset
    return range(start, start + count)


def all_mission_addresses() -> list[tuple[int, int, int]]:
    """Return [(scenario_index, mission_index, address), ...] for all 200."""
    out = []
    addr = DA_FIGHTS_BASE
    for si, (_, count) in enumerate(SCENARIOS):
        for mi in range(count):
            out.append((si, mi, addr))
            addr += 1
    return out


# ─────────────────────────────────────────────
#  Scenario unlock gates (ENFORCE) - secret-type
#  Stride 4, base 0x633548; Destined Rivals is the exception at 0x6335A8.
# ─────────────────────────────────────────────
SCENARIO_GATE_BASE = 0x633548


def scenario_gate_addr(scenario_index: int) -> int:
    if scenario_index == 23:          # Destined Rivals (gap before it)
        return 0x6335A8
    return SCENARIO_GATE_BASE + scenario_index * 4


# ─────────────────────────────────────────────
#  Character roster (RECORD) - secret-type
#  Fully contiguous, stride 4, base 0x6335E8 .. 0x6337E8.
# ─────────────────────────────────────────────
CHARACTER_BASE = 0x6335E8

CHARACTERS = [
    "Goku", "Super Saiyan Goku", "Super Saiyan 2 Goku", "Super Saiyan 3 Goku", "Kid Gohan",
    "Teen Gohan", "Super Saiyan Teen Gohan", "Super Saiyan 2 Teen Gohan", "Piccolo", "Krillin",
    "Yamcha", "Tien", "Chiaotzu", "Raditz", "Saibamen", "Nappa", "Vegeta", "Super Saiyan Vegeta",
    "Super Vegeta", "Zarbon", "Zarbon Post Transformation", "Dodoria", "Ginyu", "Recoome", "Burter",
    "Jeice", "Guldo", "Frieza 1st Form", "Frieza 2nd Form", "Frieza 3rd Form", "Frieza Final Form",
    "Full Power Frieza", "Mecha Frieza", "Trunks (Sword)", "Super Saiyan Trunks (Sword)", "Super Trunks",
    "Android #16", "Android #17", "Android #18", "Android #19", "Dr. Gero", "Cell 1st Form", "Cell 2nd Form",
    "Cell Perfect Form", "Perfect Cell", "Cell Jr.", "Hercule", "Gohan", "Super Saiyan Gohan",
    "Super Saiyan 2 Gohan", "Great Saiyaman", "Ultimate Gohan", "Goten", "Super Saiyan Goten", "Kid Trunks",
    "Super Saiyan Kid Trunks", "Gotenks", "Super Gotenks", "Super Gotenks 3", "Videl", "Demon King Dabura",
    "Majin Buu", "Majin Buu (Pure Evil)", "Super Buu", "Kid Buu", "Vegito", "Super Vegito",
    "Super Saiyan 2 Vegeta", "Super Gogeta", "Great Ape", "Great Ape Vegeta", "Legendary Super Saiyan Broly",
    "Full Power Bojack", "Cooler Final Form", "Super Janemba", "Super Saiyan 4 Goku", "Super Saiyan 4 Vegeta",
    "Super Saiyan 4 Gogeta", "Bardock", "Vegeta (Scouter)", "Majin Vegeta", "Trunks", "Super Saiyan Trunks",
    "Super 17", "Super Baby 2", "Kid Goku", "Super Buu 1", "Super Buu 2", "Master Roshi", "General Tao",
    "Garlic Jr.", "Super Garlic Jr.", "Pan", "Cooler", "Meta-Cooler", "MAX Power Master Roshi", "Slug",
    "Super Slug", "Zangya", "Salza", "Broly", "Super Saiyan Broly", "Bojack", "Janemba", "Super Baby 1",
    "Great Ape Baby", "Great Ape Raditz", "Great Ape Nappa", "Great Ape Bardock", "Great Saiyaman 2", "Cui",
    "Pikkon", "Yajirobe", "Uub", "Majuub", "Syn Shenron", "Omega Shenron", "Android 13", "Fusion Android 13",
    "Turles", "Great Ape Turles", "Supreme Kai", "Kibitokai", "Hirudegarn", "Tapion", "Grandpa Gohan",
    "Vegeta (second form)", "Super Saiyan Vegeta (second form)", "Baby Vegeta",
]

assert len(CHARACTERS) == 129, f"expected 129 characters, got {len(CHARACTERS)}"


def character_addr(index: int) -> int:
    return CHARACTER_BASE + index * 4


CHARACTER_ADDR = {name: character_addr(i) for i, name in enumerate(CHARACTERS)}


# ─────────────────────────────────────────────
#  Fusion-type Z-Items (ingredients + meta-gate)
#  Non-uniform stride; addresses hardcoded from code notes.
# ─────────────────────────────────────────────
FUSION_ITEM_ADDR = {
    "Z Item Fusion": 0x633354,        # ingredient capsule (NOT a subsystem gate)
    "Miracle": 0x633358,
    "Dragon Power": 0x63335C,
    "Wicked Heart Revealed": 0x633368,
    "Babidi's Brainwashing": 0x63336C,
    "One Who Loves Justice": 0x633370,
    "King Yemma's Stamp": 0x633374,
    "Tortoise Shell": 0x633378,
    "Ultimate God Water": 0x63337C,
    "Elder Releases Potential": 0x633380,
    "100G Training": 0x633384,
    "Elder Kai's Ritual": 0x633388,
    "Unsealed": 0x63338C,
    "Ultimate transformation": 0x633390,
    "Remodeling surgery": 0x633394,
    "Super Saiyan": 0x63339C,
    "Human gunman's gun": 0x6333A0,
    "Frieza's brother": 0x6333B0,
    "Galactic Warrior": 0x6333B4,
    "Saike demon": 0x6333B8,
    "People's bad energy": 0x6333BC,
    "Artificial Blutz wave": 0x6333C0,
    "breakthrough the limit": 0x6333C4,
    "Self Destruction": 0x6333C8,
    "Power Ball": 0x6333DC,
    "Lower class Saiyan": 0x6333E0,
    "HFIL fighter #17": 0x6333F0,
    "Power from lower class": 0x6333F4,
    "Absorb Gotenks": 0x633400,
    "Absorb Gohan": 0x633404,
    "Bros. of Crane Hermit": 0x633410,
    "Memorial campaign": 0x633414,
    "Makyo Star (fusion)": 0x633418,
    "Dead Zone": 0x63341C,
    "Giant Form": 0x633420,
    "Hatred of Goku": 0x633424,
    "Big Gete Star": 0x633428,
    "Seriousness": 0x63342C,
    "Namekian": 0x633430,
    "Mutation": 0x633434,
    "The Flowers of Evil": 0x633438,
    "Armored cavalry": 0x63343C,
    "Cooler's soldier": 0x633440,
    "Son of Paragus": 0x633444,
    "Lower class Saiyan (2)": 0x633448,
    "Frieza's soldier": 0x63344C,
    "Vegeta's rival": 0x633450,
    "Evil Dragon": 0x633470,
    "Negative Energy": 0x633474,
    "Ultimate Dragonball": 0x633478,
    "Computer": 0x63347C,
    "Hatred": 0x633480,
    "Parts of #14/#15": 0x633484,
    "Fruit of the Tree of Might": 0x633488,
    "Kibito": 0x63348C,
    "Hirudegarn's top half": 0x633490,
    "Hirudegarn's lower half": 0x633494,
    "Master Roshi's pupil": 0x63349C,
    "Fox Mask": 0x6334A0,
    "Baby": 0x6334A4,
}

assert len(FUSION_ITEM_ADDR) == 60, f"expected 60 fusion items, got {len(FUSION_ITEM_ADDR)}"

# In-game fusion capsules that are NOT used as an ingredient in any fusion
# recipe. They exist in the game's item list but feed no fusion, so we don't
# create AP ingredient items or Discover checks for them (they would just be
# clutter/filler). "Z Item Fusion" is handled separately (precollected).
NON_RECIPE_INGREDIENTS = frozenset({
    "100G Training",
    "Babidi's Brainwashing",
    "Dragon Power",
    "Elder Kai's Ritual",
    "Elder Releases Potential",
    "Human gunman's gun",
    "King Yemma's Stamp",
    "Lower class Saiyan (2)",
    "Miracle",
    "One Who Loves Justice",
    "Tortoise Shell",
    "Ultimate God Water",
    "Wicked Heart Revealed",
})


# ─────────────────────────────────────────────
#  Ability-type Z-Items (filler/useful) - contiguous stride 4 from 0x632F30
#  Stat boosts: Health/Ki/Attack/Defense/Speed +1..19, Equip Slots +2..4,
#  Blast1/Blast2/Ultimate Blast +1..19.
# ─────────────────────────────────────────────
ABILITY_BASE = 0x632F30

def _ability_table():
    table = {}
    addr = ABILITY_BASE
    groups = [
        ("Health", range(1, 20)),
        ("Ki", range(1, 20)),
        ("Attack", range(1, 20)),
        ("Defense", range(1, 20)),
        ("Speed", range(1, 20)),
        ("Equipment Slots", range(2, 5)),
        ("Blast 1", range(1, 20)),
        ("Blast 2", range(1, 20)),
        ("Ultimate Blast", range(1, 20)),
    ]
    for label, rng in groups:
        for n in rng:
            table[f"{label} +{n}"] = addr
            addr += 4
    return table

ABILITY_ITEM_ADDR = _ability_table()


# ─────────────────────────────────────────────
#  AP id allocation
# ─────────────────────────────────────────────
BASE_ID = 0x420000  # arbitrary stable namespace base for AP ids

# Location id ranges
LOC_MISSION_BASE   = BASE_ID + 0x0000   # 200 mission checks
LOC_CHARACTER_BASE = BASE_ID + 0x1000   # 129 character checks

# Item id ranges
ITEM_SCENARIO_BASE = BASE_ID + 0x2000   # 24 scenario gates
ITEM_FUSION_BASE   = BASE_ID + 0x2100   # 60 fusion items
ITEM_ABILITY_BASE  = BASE_ID + 0x2200   # 155 ability items
ITEM_ZENI          = BASE_ID + 0x2FFF   # filler currency


# ─────────────────────────────────────────────
#  Battle RAM (ROADMAP - not used in v1)
#  Volatile per-battle slot data. 5 fighter slots per player, stride 0x80.
#  Enables future features: opponent randomization, forced-character modes,
#  HP/Ki traps. Requires an empirical Character-ID mapping + battle-timed
#  writes (continuous re-assert, like the watcher's `force`/`lock`), so this
#  is deferred until after the core menu-flag apworld is proven.
# ─────────────────────────────────────────────
BATTLE_P1_BASE = 0x17E88D0   # P1 Character 1: Character (ID byte)
BATTLE_P2_BASE = 0x17E9E20   # P2 Character 1: Character (ID byte)
BATTLE_SLOT_STRIDE = 0x80    # +0x80 per fighter slot (5 slots per player)

# Per-slot field offsets from a slot base:
BATTLE_OFF_CHARACTER = 0x00  # [8-bit] character id  (encoding TBD)
BATTLE_OFF_COSTUME   = 0x04  # [8-bit] costume id
BATTLE_OFF_HEALTH    = 0x38  # [32-bit] health gauge
BATTLE_OFF_KI        = 0x44  # [32-bit] ki gauge
BATTLE_OFF_BLAST     = 0x4C  # [32-bit] blast gauge


def battle_slot_addr(player: int, slot: int) -> int:
    """player: 1 or 2; slot: 1..5. Returns the slot's Character-ID address."""
    base = BATTLE_P1_BASE if player == 1 else BATTLE_P2_BASE
    return base + (slot - 1) * BATTLE_SLOT_STRIDE


# ─────────────────────────────────────────────
#  Item Shop stock table  (STATUS: DEFERRED to v2)
#  Partially mapped and confirmed CONTROLLABLE in places, but the full control
#  path proved fiddly: multiple buffers (definition vs Flash UI), type-dependent
#  price layout (0x34 vs 0x36 records), build-on-shop-entry timing, and writes
#  that render for some slots but not others. Read-breakpoints on 0x00B0531C
#  only caught the kernel exception handler (0x80000240), suggesting the UI does
#  not render directly from this buffer.
#  v1 ships WITHOUT shop checks (329 locations from missions+characters is ample).
#  A cleaner v2 approach is likely a single hook on the Zeni-decrement / purchase
#  routine rather than re-asserting these record buffers. All findings retained
#  below for when the shop is revisited.
#
#  BREAKPOINT FINDINGS (price read/render path):
#    * Price read instruction: PC 0x002455E8  `lw v0, 0x18(t2)`.
#    * t2 is COMPUTED, not a flat record pointer:
#        0x002455B4  sll  a3, v0, 0x04     (a3 = index << 4)
#        0x002455DC  addu t2, a3, v0       (t2 = base + index*16-ish)
#        0x002455E8  lw   v0, 0x18(t2)     (read price base)
#        0x002455F0  mult v0, v0, a3       (price * a3)
#        0x002455F4  div  v0, s5           (/ s5 ; a3=s5=100 -> identity now)
#    * Writing a base price (e.g. 0x00B0531C = 7777) DID render live, so control
#      is possible -- but the addressing is computed/irregular and the routine is
#      shared (t2 seen as both 1 and 0x00B05304), making static stride mapping
#      unreliable. Defer; prefer a purchase-event hook for v2.
# ─────────────────────────────────────────────
SHOP_STOCK_BASE   = 0x00B05300
SHOP_RECORD_STRIDE = 0x30
SHOP_OFF_ITEM_ID  = 0x00   # derived price-tier stepping value (NOT the selector)
SHOP_OFF_TYPE     = 0x04   # derived display type/tier (NOT the selector)
SHOP_OFF_ITEM_INDEX = 0x08 # ITEM CATALOG INDEX — the REAL item selector.
                           # CONFIRMED: write index -> that catalog item renders
                           # (idx 0 = Health +1, idx 5 = Health +6, ...).
                           # (Was mislabeled "slot index"; it is the item index.)
SHOP_OFF_SLOT_IDX = 0x08   # (alias kept for back-compat)
SHOP_OFF_CATEGORY = 0x0C   # category/color: 0=ability(blue) 1=support(orange)
                           # 2=fusion(purple) 3=secret(green). Invalid -> no icon.
SHOP_OFF_STOCK    = 0x14   # stock available to buy (CONFIRMED; default 999=0x3E7)
SHOP_OFF_BASE999  = 0x14   # (alias kept for back-compat)
SHOP_OFF_PRICE    = 0x1C   # buy price (CONFIRMED: 5000=0x1388, 10000=0x2710)
SHOP_OFF_RESALE   = 0x20   # resale value when selling (CONFIRMED)
SHOP_OFF_PRICE2   = 0x20   # (alias kept for back-compat)
SHOP_SCREEN_ID    = 0x05   # value of 0x76BDDC on the Item Shop menu

# CRITICAL TIMING (confirmed by before/after dumps): the record table is
# EMPTY/STALE before entering the shop and FULLY POPULATED once the shop is
# open. Earlier slot-2 price writes failed because they hit the pre-entry
# empty state, not a layout error. (Not a progressive per-slot build — it's
# "not built until the shop screen is active".)
#   -> Client writes/re-asserts records only while 0x76BDDC == 0x05 AND the
#      records are populated (type field != 0). Writes render live; they revert
#      on leaving the shop (rebuilt from the packed source at 0x00B5C600).
# Record stride 0x30 confirmed; price at +0x1C confirmed.

# TODO: confirm purchase-detection field (buy a dummy slot, watch what changes:
# Zeni decrease + likely a per-item quantity flag or slot record update).
#
# SHOP MODEL (v1) - confirmed by EE debugger investigation:
#   * 0x00B05300 is the REAL shop item-record table (id/type/price), and it is
#     REBUILT FROM SOURCE every time the shop opens (edits revert on leaving).
#     -> client must RE-ASSERT its dummy stock on every shop-screen entry,
#        forcing records each poll while 0x76BDDC == 0x05.
#   * 0x00B5C600 is the packed/encoded SOURCE the rebuild reads (hard to edit;
#     do NOT target it).
#   * 0x01FFD858 / 0x01FFD0B8 are UI scene data (Flash MovieClip plates +
#     element counts: "mc_text_off_1", "mc_plate_black2"...). NOT the item
#     list; the "count" there is a UI layout counter -> writing it does nothing.
#   * 4 tabs (lengths 9/12/5/1). Client overwrites the open tab's records with
#     dummy check-items and blanks other tabs' records when shown.
SHOP_TAB_LENGTHS = [9, 12, 5, 1]
SHOP_TAB1_SLOT_COUNT = 9
SHOP_SLOT_COUNT = SHOP_TAB1_SLOT_COUNT  # v1: checks live on tab 1

# UI / source addresses recorded for reference (NOT control points):
SHOP_SOURCE_TABLE = 0x00B5C600   # packed source the rebuild reads (do not edit)
SHOP_UI_SCENE     = 0x01FFD858   # Flash UI scene data (not item list)
SHOP_UI_COUNT     = 0x01FFD0B8   # UI element count mirror (derived; not control)

# Tab 1 confirmed contents (the entry-tier +1 of each ability stat), in slot
# order. Recorded for reference; pool/exclusion decisions still open.
SHOP_TAB1_ITEMS = [
    "Health +1",
    "Ki +1",
    "Attack +1",
    "Defense +1",
    "Speed +1",
    "Equipment Slots +2",
    "Blast 1 +1",
    "Blast 2 +1",
    "Ultimate Blast +1",
]
# Known shop item-id mapping (from live reads): shop record +0x00 field.
# 0x243 (579) = Health +1. Full id catalog TBD.
SHOP_ITEM_ID_KNOWN = {
    "Health +1": 0x243,
}


def shop_slot_addr(slot: int, field: int = SHOP_OFF_ITEM_ID) -> int:
    return SHOP_STOCK_BASE + slot * SHOP_RECORD_STRIDE + field


# ─────────────────────────────────────────────
#  P1/P2 CHARACTER RANDOMIZER  (STATUS: DEFERRED to v2 — source not yet found)
# ─────────────────────────────────────────────
#  CONFIRMED:
#    * Battle character ID == roster index (CHARACTERS[]). Verified live:
#        P1 slot 0x017E88D0 read 8  = CHARACTERS[8]  = Piccolo
#        P2 slot 0x017E9E20 read 13 = CHARACTERS[13] = Raditz
#      So no separate ID table is needed; the roster array IS the mapping.
#    * Slot stride P1->P2 = 0x1550.
#    * Instruction 0x001F5CFC  `sw v0, 0x0(a1)` writes roster IDs into the
#      slots during load. Observed v0 sequence per load: 8,13,8,13 (each slot
#      written TWICE). a1 = destination slot address.
#
#  BLOCKER:
#    * Substituting v0 at 0x001F5CFC (even on BOTH writes of a slot) does NOT
#      change the spawned fighter. Editing the slot memory at the break also
#      does nothing. => 0x017E9E20/0x017E88D0 are a STAGING/parallel buffer,
#      not the structure the fighter is instantiated from.
#    * Polling/force writes lose the race (game writes in the load burst).
#
#  NEXT STEP IF REVISITED:
#    1. value-search the ID across two different matchups (e.g. vs Raditz=13
#       then vs Vegeta=16); the address holding 13 then 16 (NOT the slot) is
#       the real matchup/character source.
#    2. read-breakpoint that source to find the instruction that reads it into
#       the fighter object — THAT is the cave hook.
#    3. Build a code cave there (B3 build_cave is the template); polling won't
#       work, must be an in-execution hook.
ADDR_P1_BATTLE_SLOT = 0x017E88D0
ADDR_P2_BATTLE_SLOT = 0x017E9E20
BATTLE_SLOT_STRIDE  = 0x1550
CHAR_WRITE_INSTR    = 0x001F5CFC   # sw v0,0x0(a1) — staging write, NOT fighter source

#  ── UPDATE (deeper investigation): still blocked, indirection too deep ──
#  Traced a SECOND, upstream writer of the character:
#    PC 0x0025E024  `sw v0, 0x4(s2)`  (in fn ~0x0025DFD4..0x0025E064)
#      preceded by  `lbu v0, 0x3D(v1)` (reads char ID from [v1+0x3D])
#      For P1: s2=0x01701740 -> writes ID to 0x01701744 (the fighter struct);
#              v1=0x00981640 -> source byte at 0x0098167D.
#    BUT: 0x0025E024 is a SHARED/generic function — it also fires with
#    unrelated args (e.g. s2=0x01719CC0, v0=4). Must gate on s2==0x01701740.
#  TESTED: substituting v0 on the correct (s2==0x01701740) call STILL does not
#  change the spawned fighter. => 0x01701744 is also a downstream copy.
#  Character data is indirected beyond this point; the real source is one or
#  more hops further back (source byte 0x0098167D -> whatever writes it -> ...),
#  possibly DMA-fed (value has appeared at the slot with no EE write-bp hit).
#  CONCLUSION: P1/P2 randomization is NOT achievable by simple value
#  substitution at any address found so far. Would require tracing the full
#  copy chain back to its origin (shop-style deep dig) and then a cave there.
#  Deferred. Every address/instruction in the chain is recorded above.
ADDR_CHAR_STRUCT_P1   = 0x01701740   # fighter struct base (P1); ID at +0x04
CHAR_STRUCT_WRITER    = 0x0025E024   # sw v0,0x4(s2) — SHARED fn, gate on s2

#  ── KEY BEHAVIORAL NOTE: battle-instance buffer is STALE-UNTIL-LOAD ──
#  0x017E88D0 (P1 char) is NOT cleared between fights. It retains the PREVIOUS
#  fight's character through the menu, and is only overwritten when the next
#  battle actually loads. Verified: held 0x3D (Majin Buu) from a prior fight,
#  persisted in menu, then became 0x27 (Android 19) on loading the new fight.
#  => This is a battle-INSTANCE readout, written BY the load from the resolved
#     character. Writing it (menu/pre-load/mid-battle) always loses to the
#     load's write. Confirms there is NO simple-write character swap; the only
#     control point is the load-time asset/character resolution (deep, unfound).
#  RA code notes corroborate: these are labeled as battle readouts
#  (Char/Costume/Health/Ki/Blast per slot), NOT a character-select source.
#
#  RA-VERIFIED BATTLE-INSTANCE LAYOUT (5 slots/player, stride 0x80):
#    +0x00 Character (8-bit)     +0x04 Costume (8-bit)
#    +0x38 Health (32-bit)       +0x44 Ki (32-bit)     +0x4C Blast (32-bit)
#    P1 base 0x017E88D0, P2 base 0x017E9E20.
#    (Costume/gauge fields ARE cleanly writable for any future instance-level
#     'for fun' mods — e.g. random costumes, starting health — even though
#     the Character field is not a viable swap control.)

#  ── BREAKTHROUGH: SELECT-SCREEN selection value IS writable (v2 WORKS) ──
#  0x00C18404 = P1 character selection on the Versus character-select screen.
#  Writing this byte BEFORE confirming the fight makes the written character
#  load as P1. CONFIRMED working live. This is UPSTREAM of the load resolver,
#  so there is NO race and NO code cave needed — a simple write8 on the select
#  screen controls the fighter. (All earlier failures were downstream buffers.)
#  TODO: P2 selection address (likely fixed offset from P1), select-screen
#  identificator value (read 0x76BDDC on select screen), and DA-mode equivalent.
ADDR_P1_SELECT = 0x00C18404   # P1 char selection on Versus select screen (WRITABLE)
# ADDR_P2_SELECT = TBD

#  ── BREAKTHROUGH 2: DU MATCHUP SOURCE found & WRITABLE (DU randomization WORKS) ──
#  In Dragon Adventure, the matchup character IDs live in the loaded-data region
#  ~0x008CCxxx (same neighborhood as the fighter asset pointers — i.e. upstream
#  loaded data, NOT the downstream battle slots).
#  CONFIRMED: writing 0x008CC2E0 changed P1's character in a DU fight (live).
#  Layout appears 4-byte stride: 0x008CC2E0 = P1, 0x008CC2E4 = P2 (TBD confirm).
#  This is the DU equivalent of the Duel select value (0x00C18404) — a simple
#  write controls the fighter, NO code cave needed.
#  OPEN QUESTIONS:
#    * Is 0x008CC2E0 STATIC across missions/sessions, or allocated per-load
#      (needs a signature scan to relocate, like B3 shop-base)?  <-- must verify
#    * Confirm 0x008CC2E4 = P2; identify the trailing entries (0x18 etc.).
#    * When is it read (write window): pre-fight/map screen up to load?
ADDR_DU_MATCHUP_P1 = 0x008CC2E0   # P1 char in DU matchup (WRITABLE, confirmed)
# ADDR_DU_MATCHUP_P2 = 0x008CC2E4  # TBD confirm

#  ═══════════════════════════════════════════════════════════════════
#  DRAGON ADVENTURE CHARACTER RANDOMIZER  (v2 — CRACKED, buildable)
#  ═══════════════════════════════════════════════════════════════════
#  DA matchup structure (live on the DA character-select; updates per fight):
#    Player team: base 0x008CC2E0, stride 0x14, char ID at slot+0x00,
#                 terminated by 0xFFFFFFFF.
#    Enemy team:  base 0x008CC344, stride 0x14, same layout + terminator.
#    (Each 0x14 slot = [char id (4B)] + params; only +0x00 is the fighter ID.)
#    Confirmed live: writing slot ID changes that fighter; 0xFFFFFFFF = end of
#    team (controls team size). Walk slots until terminator; randomize occupied.
#    NOTE: 0x76BDDC screen id is 0x07 for ALL of DA (menu/map/select/battle),
#    so it cannot detect the select screen alone. Instead TRIGGER on the matchup
#    block changing (0x008CC2E0 only changes when entering a new fight).
#
#  Mission identification (for deterministic per-mission seeding):
#    0x76BDF0 = Current Scenario (game byte; 0x00..0x16 then 0x18=Destined
#               Rivals, skipping 0x17). Map: byte<=0x16 -> our idx; 0x18 -> 23.
#    0x76BDF4 = Current Chapter (mission index within the scenario).
#    -> linear_mission_index = sum(mission counts of prior scenarios) + chapter
#       which is ALSO the completion-flag offset (0x63100C + idx) and the AP
#       location index. Everything aligns on this one index.
#    Deterministic key: RNG(ap_seed + linear_mission_index).
ADDR_DA_MATCHUP_P1_BASE = 0x008CC2E0   # player team, stride 0x14, FF-terminated
ADDR_DA_MATCHUP_P2_BASE = 0x008CC344   # enemy team,  stride 0x14, FF-terminated
#  Matchup slot fields (stride 0x14): +0x00 char ID, +0x0C COSTUME index.
#  When changing a slot's character, the costume MUST be reset to 0 — a costume
#  index the new character lacks crashes the loader (VIF FIFO assertion).
#  CONFIRMED: Salza (id 100) + costume 5 -> crash; costume 0 -> loads fine.
DA_MATCHUP_OFF_COSTUME = 0x0C
DA_MATCHUP_SLOT_STRIDE  = 0x14
DA_MATCHUP_TERMINATOR   = 0xFFFFFFFF
ADDR_DA_CURRENT_SCENARIO = 0x76BDF0    # game scenario byte (0x17 gap before 0x18)
ADDR_DA_CURRENT_CHAPTER  = 0x76BDF4    # mission index within scenario


def da_scenario_byte_to_index(b: int) -> int:
    """Map the game's scenario byte (0x00..0x16, 0x18) to our SCENARIOS index."""
    return b if b <= 0x16 else 23


def da_linear_mission_index(scenario_byte: int, chapter: int) -> int:
    """(scenario byte, chapter) -> linear mission index (== completion offset
    == AP location index)."""
    our_idx = da_scenario_byte_to_index(scenario_byte)
    base = sum(c for _n, c in SCENARIOS[:our_idx])
    return base + chapter

#  ── ENEMY BLOCK CAVEAT (display vs real ID) ──
#  0x008CC344 drives the enemy on the SELECT screen but is NOT the field the
#  loader uses: regular Turles (id 0x77) showed as 0x78 here, and writing
#  0x008CC344 renamed the enemy in select but CRASHED on load (display/real
#  desync). So enemy randomization via 0x008CC344 is UNSAFE.
#  Player block (0x008CC2E0, stride 0x14) is confirmed safe (real chars, write
#  works). v2: ship PLAYERS-only randomization; enemy randomization needs the
#  enemy's REAL char field mapped (value-search for the correct id e.g. 0x77).

#  ── SECRET / WHAT-IF SCENARIO UNLOCK CONDITIONS (Philosophy B: as checks) ──
#  Several scenarios unlock via special in-game conditions (e.g. beat Raditz
#  under the timer -> a what-if saga). Under the randomizer these stay GATED
#  (locked until AP grants them), but MEETING the condition is itself a CHECK.
#  The client reads these gate flags at the TOP of the cycle (before ENFORCE
#  re-locks them); if a gated secret scenario's flag is set, the player earned
#  it legitimately -> send the unlock check, then ENFORCE re-locks as normal.
#  These are the what-if / alternate scenarios (by our SCENARIOS index):
SECRET_SCENARIOS = {
    21: "Fateful Brothers",
    22: "Beautiful Treachery...",
    23: "Destined Rivals",
}

#  Secret scenario -> its TRIGGER (the mission whose completion unlocks it).
#  (trigger scenario index, trigger mission index within that scenario)
#  Fateful Brothers   <- Saiyan Saga (0) mission 00
#  Beautiful Treachery<- Frieza Saga (4) mission 00
#  Destined Rivals    <- Majin Buu Saga (14) mission 01
#  Per community FAQs the in-game text says "as Piccolo/Kid Gohan/Goten", but
#  the actual trigger is COMPLETING the mission (the player is defaulted to that
#  character there) — so fighter randomization does NOT block these unlocks.
SECRET_TRIGGERS = {
    21: (0, 0),    # Fateful Brothers
    22: (4, 0),    # Beautiful Treachery
    23: (14, 1),   # Destined Rivals
}

#  ── TIME SCROLL FINALE (McGuffin goal) ──
#  In the time_scrolls goal, collecting N Time Scrolls unlocks the FINAL saga,
#  "Evil Dragon of Absolute Destruction" (scenario 20). Completing that saga is
#  the win. The saga is scroll-gated (NOT unlocked by a normal scenario item in
#  this goal); ENFORCE opens its gate only once scroll count is met.
FINAL_SAGA_INDEX = 20  # Evil Dragon of Absolute Destruction

#  ── TIME SCROLL GOAL: final saga ──
#  The time_scrolls goal gates the final saga (Evil Dragon of Absolute
#  Destruction, scenario 20) behind collecting N Time Scrolls. Once the player
#  has the scrolls, the client unlocks this saga; completing it is the win.
GOAL_FINAL_SCENARIO = 20  # Evil Dragon of Absolute Destruction

#  ── DRAGON BALL CHECKS + WISH ──
#  The 7 Dragon Balls are a REAL in-game collectible (distinct from the abstract
#  Time Scroll McGuffin). Collecting each is a CHECK; making a wish (reaching the
#  summon node) is one more CHECK.
#  Dragon Ball flags: base 0x6334C0, stride 4. Per ball: +0x00 unlocked (bit0),
#  +0x02 quantity (16-bit). 7 balls (1★..7★).
DRAGONBALL_BASE = 0x6334C0
DRAGONBALL_STRIDE = 0x04
DRAGONBALL_COUNT = 7
DRAGONBALL_NAMES = [
    "1 Star Dragon Ball", "2 Star Dragon Ball", "3 Star Dragon Ball",
    "4 Star Dragon Ball", "5 Star Dragon Ball", "6 Star Dragon Ball",
    "7 Star Dragon Ball",
]

#  Map location (16-bit) and the two summon nodes. Reaching EITHER counts as the
#  single "wish" check.
ADDR_DA_MAP_LOCATION = 0x387AB8
MAP_NODE_SHENRON = 0x09B7   # Earth - Shenron
MAP_NODE_PORUNGA = 0x09CE   # Namek - Porunga


def dragonball_unlocked_addr(n: int) -> int:
    """n is 0-based (0 = 1★ ... 6 = 7★). Returns the unlocked-flag address."""
    return DRAGONBALL_BASE + n * DRAGONBALL_STRIDE

#  ── SHOP ITEM CATALOG (via +0x08 index) — CRACKED ──
#  The +0x08 field on each shop record is an INDEX into the item catalog; the
#  game resolves the item name/icon from it. CONFIRMED samples:
#     idx 0=Health+1, 5=Health+6, 6=Health+7, 10=Health+11,
#     idx 20=Ki+2, 50=Attack+13, 100=Blast+2, 150=Ultimate Blast+14.
#  Catalog is organized in contiguous stat BLOCKS (each a +1,+2,+3... ladder),
#  spanning at least 0..150+. So 150+ distinct valid items can be placed.
#  To place an item: write its catalog index to record+0x08. Other fields
#  (+0x00 price-tier value, +0x04 type) are derived display props that must stay
#  consistent with the selected item, so only drive identity through +0x08.
SHOP_CATALOG_SAMPLES = {
    0: "Health +1", 5: "Health +6", 6: "Health +7", 10: "Health +11",
    20: "Ki +2", 50: "Attack +13", 100: "Blast +2", 150: "Ultimate Blast +14",
}
SHOP_CATALOG_MAX = 150  # confirmed valid up to here (likely more)

#  ── SHOP CONTROL — FULLY CRACKED ──
#  The record table at 0x00B05300 (stride 0x30) is laid out BY CATALOG INDEX:
#  record N is at 0x00B05300 + N*0x30, and its +0x08 holds catalog index N.
#  The VISIBLE ability tab shows the +1 (block-start) of each of 9 stat blocks.
#  To control a visible slot, edit the record AT THAT ITEM'S CATALOG INDEX:
#    +0x08 = item (catalog index)  -> swaps which item shows  [CONFIRMED]
#    +0x1C = price                 [CONFIRMED]
#    +0x14 = stock                 [CONFIRMED]
#    +0x0C = category/color        [CONFIRMED]
#    +0x20 = resale                [CONFIRMED]
#  CONFIRMED: editing record at idx 0 (0x00B05300) changes visible Health+1;
#  editing record at idx 38 (0x00B05A20) changes visible Attack+1 -> Attack+13.
#  The table REBUILDS FROM SOURCE on shop entry, so the client must RE-ASSERT
#  its desired records every poll while screen==0x05 (Item Shop).
#  Block-start catalog indices for the 9 visible ability slots (Health/Ki/Attack
#  confirmed; remaining 6 to verify in-game):
SHOP_VISIBLE_BLOCK_STARTS = {
    "Health":          0,
    "Ki":              19,
    "Attack":          38,   # CONFIRMED (record 0x00B05A20)
    # "Defense":       ?,    # TODO verify
    # "Speed":         ?,
    # "Equipment":     ?,
    # "Blast 1":       ~98,
    # "Blast 2":       ?,
    # "Ultimate Blast": 137, # from UltBlast+14=150
}
def shop_record_addr(catalog_index: int, field: int = 0x00) -> int:
    """Address of a shop record (by catalog index) and optional field offset."""
    return SHOP_STOCK_BASE + catalog_index * SHOP_RECORD_STRIDE + field

#  ── SHOP ROW VISIBILITY — CRACKED ──
#  +0x04 is the SHOW-IN-SHOP marker:
#     0x36 = item is DISPLAYED as a shop row
#     0x34 = item is hidden (in catalog but not shown)
#  CONFIRMED: setting a hidden item's +0x04 to 0x36 ADDS a visible row for it
#  (Health+2, normally hidden, appeared as a new row). So ROW COUNT is fully
#  controllable: mark items 0x36 to show, 0x34 to hide. A newly-shown row needs
#  its price (+0x1C) set too (it defaulted to 0).
#  The visible set is therefore just "every catalog record whose +0x04==0x36",
#  in catalog order. To build the shop we want: set +0x04=0x36 + price + stock on
#  the records we want shown, and 0x34 on the rest. Re-assert each poll (screen
#  0x05) since the table rebuilds from source on entry.
SHOP_MARKER_SHOWN  = 0x36   # +0x04 value that displays the row
SHOP_MARKER_HIDDEN = 0x34   # +0x04 value that hides it

#  ── SHOP — COMPLETE TAB/MARKER MAP (all confirmed) ──
#  One big catalog table at 0x00B05300, stride 0x30, ~374+ records spanning 4
#  tabs by index range and category (+0x0C):
#     ability (cat 0): low indices (0..~175),  shown marker +0x04 = 0x36
#     support (cat 1): ~176..~314,             shown marker +0x04 = 0x26
#     fusion  (cat 2): ~315..~367,             shown marker +0x04 = 0x14
#     secret  (cat 3): ~368..374+,             shown marker +0x04 = 0x0C
#  UNIVERSAL HIDE: writing +0x04 = 0x00 hides ANY row regardless of category
#  (CONFIRMED). So clearing the whole shop = write 0 to every record's +0x04.
#  To SHOW a row, write that category's shown marker + set price (+0x1C),
#  stock (+0x14), item (+0x08 = catalog index). Re-assert on shop entry (table
#  rebuilds from source). Catalog ~0..374+; sweep ~400 to cover all.
SHOP_CAT_SHOWN_MARKER = {0: 0x36, 1: 0x26, 2: 0x14, 3: 0x0C}  # by category
SHOP_HIDE_MARKER = 0x00    # universal hide (any category)
SHOP_CATALOG_SIZE = 400    # safe sweep upper bound (table ~374+)
SHOP_OFF_CATEGORY2 = 0x0C  # category field (0=ability 1=support 2=fusion 3=secret)

#  ── SHOP CHECK DISPENSER (design) ──
#  Client takes over the shop: clears all rows, shows N check-items in the
#  ability tab, each with a UNIQUE price so the Zeni-drop on purchase identifies
#  which slot was bought. Zeni-drop (not quantity) is the signal -> immune to AP
#  item grants (which don't cost Zeni).
#  Per shop-check slot i (0-based):
#    catalog index = SHOP_CHECK_CATALOG_START + i   (distinct ability items)
#    price         = SHOP_CHECK_PRICE_BASE + i      (unique -> identifies slot)
#    stock         = 1
SHOP_CHECK_CATALOG_START = 0      # first ability catalog index to use
SHOP_CHECK_PRICE_BASE    = 5000   # pre-discount base for slot 0. The Gold card
                                  # halves it, so the player PAYS ~2500 for slot 0.
SHOP_CHECK_PRICE_STEP    = 200    # pre-discount step; charged climbs by 100/slot
                                  # (2500, 2600, 2700, ...). Wide enough that the
                                  # discounted amounts stay unique (no rounding
                                  # collisions) so the Zeni drop identifies the
                                  # slot. slot i price = base + i*step.
# Curated shop-check slots: (catalog_index, item_name). Derived from the
# confirmed 19-per-block ladder: each stat block holds +1..+19 at contiguous
# indices, anchored by multiple confirmed points:
#   Health: start 0  (0=+1, 5=+6, 6=+7, 10=+11 confirmed)
#   Ki:     start 19 (19=+1, 20=+2 confirmed)
#   Attack: start 38 (38=+1, 50=+13 confirmed -> 37+N pattern)
# Plus a couple of scattered confirmed items beyond the ladders. Each location
# is named "Shop: <item>" so hints reference the actual item. Detection is by
# unique price, so the displayed item is cosmetic to detection.
def _ladder(stat, start, count=19):
    return [(start + (n - 1), f"{stat} +{n}") for n in range(1, count + 1)]

SHOP_CHECK_SLOTS = (
    _ladder("Health", 0)
    + _ladder("Ki", 19)
    + _ladder("Attack", 38)
    + [
        (100, "Blast +2"),
        (150, "Ultimate Blast +14"),
    ]
)
SHOP_CHECK_MAX = len(SHOP_CHECK_SLOTS)  # 59
ADDR_ZENI_CONFIRMED      = 0x63383C  # (== ADDR_ZENI) Zeni 32-bit, drop = purchase

#  ── SHOP MEMBERSHIP (Member's Card) — controls visible item count ──
#  The shop only displays a LIMITED number of items unless you hold the Gold
#  Member's Card. A weak/no card caps visible rows (~4 per block observed);
#  the Gold card unlocks the full shop. The client grants it so all check-items
#  are visible. Structure mirrors other Z-Items: +0x00 unlocked bit0, +0x02 qty.
ADDR_MEMBERS_CARD_GOLD        = 0x6334E8   # [bit0] unlocked
ADDR_MEMBERS_CARD_GOLD_QTY    = 0x6334EA   # [16-bit] quantity

#  ── Fighter randomizer: excluded characters ──
#  Some characters crash a fight when spawned cold via the matchup block
#  (likely transformation/form states whose required setup/params don't match a
#  generic spawn). Apes are FINE (confirmed). These transformation-state forms
#  are excluded from the randomizer pool by default. Refine via testing.
FIGHTER_EXCLUDE_DEFAULT = [
    20,   # Zarbon Post Transformation
    27, 28, 29, 30,   # Frieza 1st/2nd/3rd/Final Form
    41, 42, 43,       # Cell 1st/2nd/Perfect Form
    62,   # Majin Buu (Pure Evil)
    73,   # Cooler Final Form
    79,   # Vegeta (Scouter)
    126, 127,         # Vegeta (second form) / SSJ Vegeta (second form)
    33, 34,           # Trunks (Sword) / SSJ Trunks (Sword)
]

#  ── DA NAMEK ITEM SHOP (second shop, inside Dragon Adventure) ──────────────────
#  A SEPARATE shop from the main-menu Item Shop. Confirmed live via PINE writes.
#  Detection: read16(DA_MAP_LOCATION) == DA_NAMEK_SHOP_LOC (0x09CC).
#  Table: base DA_SHOP_BASE, stride 0x30. Per-record fields confirmed:
#    +0x00 = price       (write 7777 -> slot showed 7777)
#    +0x18 = item_id / show selector. 52=Health+1, 54=Health+2 (stride 2);
#            writing 0 HIDES the row (universal hide, like the main shop).
#    +0x28 = max stock (999)
#  NOTE: item_id numbering differs from the main shop's catalog index (here it's
#  52,54,... stride 2 for the Health ladder). A full item_id->name map is TBD.
#  Purchase detection: CONFIRMED Zeni drop at ADDR_ZENI by the FULL price (no
#  Gold card in DA, so no 50% discount — simpler than the main shop).
DA_MAP_LOCATION    = 0x387AB8   # 16-bit: current DA map location id
DA_NAMEK_SHOP_LOC  = 0x09CC     # value when at Namek - Item Shop
DA_SHOP_BASE       = 0x0184809C # record 0 of the DA Namek shop table
DA_SHOP_STRIDE     = 0x30
DA_SHOP_OFF_PRICE  = 0x00
DA_SHOP_OFF_ITEM   = 0x18       # item selector; 0 = hide row
DA_SHOP_OFF_MAXSTOCK = 0x28
#  ✅ SOLVED: the DA Namek shop uses the SAME record layout as the MAIN shop
#  (SHOP_STOCK_BASE 0xB05300), just at a different base. Record N starts at
#  DA_SHOP_BASE + N*0x30, and fields mirror the main shop EXACTLY:
#       +0x04 = SHOW MARKER  (0x36/54 = shown, 0 = hidden)   <-- visibility
#       +0x08 = item index
#       +0x14 = stock
#       +0x1C = price (FULL; Gold card applies 50% at charge/display time)
#  CONFIRMED LIVE: writing 0x36 to a hidden item's +0x04 made it appear
#  (Health +2 test). So the main shop's shop_clear_all / shop_show_row logic
#  ports directly to the DA table — same offsets, same marker values.
#  NOTE: the record BASE is 0x18 BEFORE the price field. Health +1's price is
#  at 0x0184809C, so record 0 starts at 0x1848080 (price - 0x1C).
DA_SHOP_REC0_BASE  = 0x1848080  # record 0 start (Health +1); +0x1C = price
DA_SHOP_OFF_MARKER = 0x04       # show marker (0x36 shown, 0 hidden) = main shop
DA_SHOP_OFF_ITEMIDX= 0x08       # item index (main shop +0x08)
DA_SHOP_OFF_STOCK  = 0x14       # stock (main shop +0x14)
DA_SHOP_OFF_PRICE_REAL = 0x1C   # price (main shop +0x1C)
DA_SHOP_SHOWN_MARKER = 0x36     # stat/ability shown marker (same as main shop)
#  Multiple in-DA shops share the SAME record layout, differing only by table
#  base and the map-location id that detects them. Registry: map_loc -> rec0_base.
#  - Namek Item Shop  (0x09CC): confirmed working, rec0 0x1848080
#  - Earth Item Shop  (0x09A9 Baba's Palace): rec0 0x1764840 (Health+1 price
#    0x176485C confirmed live via a 7777 write)
DA_SHOPS = {
    0x09CC: 0x1848080,   # Namek Item Shop
    0x09A9: 0x1764840,   # Earth Item Shop (Baba's Palace)
}
#  ⚠ ALIGNMENT NOTE: earlier slot→address math here was off by ~0x14 bytes.
#  Re-anchored from a live 48-byte dump of the slot-21 (Ki) record at 0x1848460:
#    0x1848460 = 1500 (a price-like field)
#    0x1848470 = 6000 (another price-like field; base vs display TBD)
#    0x1848474 = the VISIBILITY/ITEM field (54 => visible Ki+3; toggling hides/
#                shows and can change the +N level). THIS is the show/hide knob.
#    0x1848478 = 21 = the SLOT NUMBER (1-indexed)
#    0x1848484 = 999 max stock
#  So the real per-record field offsets differ from the main shop AND from the
#  earlier guesses in this block. Before building the DA dispenser, re-derive the
#  record base + field offsets from this anchor (the visibility field sits 0x14
#  into the 48-byte window dumped at 0x1848460, i.e. at 0x1848474; slot# at
#  0x1848478). Two price-like fields (1500 @ +0x00, 6000 @ +0x10 of that window)
#  still need a write test to determine which the game actually charges.
#  CONFIRMED MECHANICS (still valid): table is live & writable; detection is
#  read16(0x387AB8)==0x09CC; purchases drop Zeni at ADDR_ZENI by full price;
#  items are the Health/Ki/Attack ladders by slot block (1-19/20-38/39-57).
#  APPROACH (per user): mirror the main shop's "hide all, show only check slots"
#  via the visibility field — do NOT reselect items.
