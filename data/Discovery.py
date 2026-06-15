"""Ingredient discovery fight signatures.

An ingredient is "discovered" by WINNING the specific in-game fight that drops
it. Each fight is uniquely identified by the live Dragon Adventure context:

    scenario  (ADDR_DA_SCENARIO  0x76BDF0)
    chapter   (ADDR_DA_CHAPTER   0x76BDF4)   -- 0-based, matches in-game Chapter NN
    fight_id  (ADDR_DA_FIGHT_ID  0x76BDFC)   -- distinguishes main vs optional fights
                                                within the same chapter

A discovery fires when (scenario, chapter, fight_id) matches AND the Battle
Status (ADDR_BATTLE_STATUS 0x76BCC0) reads 0x01 (Victory).

This is completely independent of the ingredient inventory flag, so ingredients
can still be auto-granted by AP for fusion use without any conflict.

An ingredient may have MULTIPLE drop fights (it can be obtained in several
chapters/sagas). Discovery fires on winning ANY of them.

Format:
    INGREDIENT_DISCOVERY = {
        "<ingredient name>": [
            (scenario_index, chapter_index, fight_id),
            ...   # one tuple per fight that drops it
        ],
        ...
    }

scenario_index follows the SCENARIOS list order in Constants.py:
    0 Saiyan Saga, 1 Tree of Might, 2 Lord Slug, 3 Final Battle, 4 Frieza Saga,
    5 Makyo Star, 6 Cooler's Revenge, 7 The Return of Cooler, 8 The Story of
    Trunks, 9 Android Saga, 10 Super Android 13, 11 Broly: TLSS, 12 Ultimate
    Future Warrior, 13 Bojack Unbound, 14 Majin Buu Saga, 15 Broly: TSC,
    16 Fusion Reborn, 17 Wrath of the Dragon, 18 Baby The Avenger, 19 Ultimate
    Android, 20 Evil Dragon, 21 Fateful Brothers, 22 Beautiful Treachery,
    23 Destined Rivals.
"""

# Confirmed discovery fight signatures. Expand as fights are mapped in-game.
INGREDIENT_DISCOVERY: dict[str, list[tuple[int, int, int]]] = {
    # Fox Mask: TWO fights (OR).
    #   - Majin Buu Saga (14) "Two Majin Buu's" chapter 11:
    #       fight_id 0xE4 at ALL difficulties (d0==d1==d2, verified)
    #   - Android Saga (9) "Cell Games Begins" chapter 17:
    #       fight_id 0xE4 at ALL difficulties (d0==d1==d2, verified)
    # (Both "survive Yamcha" fights — fight_id 0xE4 is difficulty-invariant.)
    "Fox Mask": [
        (14, 11, 0xE4),
        (9, 17, 0xE4),
    ],

    # Unsealed: two MAIN-fight sources (discover via EITHER).
    #   - Frieza Saga (4) "Vegeta Attacks"  chapter 4
    #       diff0 fight_id 0x24 | diff1 0x2C | diff2 0x78
    #   - Bojack Unbound (13) "Gohan's Desperate Battle"  chapter 5
    #       diff0 fight_id 0x72 | diff1 0xA2 | diff2 0x146
    "Unsealed": [
        (4, 4, 0x24),
        (13, 5, 0x72),
        (4, 4, 0x2C),    # Frieza ch4, difficulty 1
        (4, 4, 0x78),    # Frieza ch4, difficulty 2
        (13, 5, 0xA2),   # Bojack ch5, difficulty 1
        (13, 5, 0x146),  # Bojack ch5, difficulty 2
    ],

    # Ultimate transformation: FOUR drop fights (OR).
    #   - Frieza Saga (4) "Legendary Super Saiyan"  chapter 18
    #       diff0 fight_id 0x2D | diff1 0x66 | diff2 0xAF
    #   - Cooler's Revenge (6) "Ult. Transformation" chapter 4
    #       diff0 fight_id 0x3F | diff1 0x5F | diff2 0xC1
    #   - Bojack Unbound (13) "Deadly Show Begins"   chapter 6
    #       diff0 fight_id 0x4E | diff1 0x96 | diff2 0x146
    #     (SAME fight as Galactic Warrior's (13,6,...) — drops both ingredients)
    #   - Fusion Reborn (16) "Ultimate Fusion"       chapter 9
    #       diff0 fight_id 0x3C | diff1 0x97 | diff2 0xAF
    "Ultimate transformation": [
        (4, 18, 0x2D),
        (6, 4, 0x3F),
        (13, 6, 0x4E),
        (16, 9, 0x3C),
        (4, 18, 0x66),   # Frieza ch18, difficulty 1
        (4, 18, 0xAF),   # Frieza ch18, difficulty 2
        (6, 4, 0x5F),    # Cooler's Revenge ch4, difficulty 1
        (6, 4, 0xC1),    # Cooler's Revenge ch4, difficulty 2
        (13, 6, 0x96),   # Bojack ch6, difficulty 1 (shared w/ Galactic Warrior)
        (13, 6, 0x146),  # Bojack ch6, difficulty 2 (shared w/ Galactic Warrior)
        (16, 9, 0x97),   # Fusion Reborn ch9, difficulty 1
        (16, 9, 0xAF),   # Fusion Reborn ch9, difficulty 2
    ],

    # Remodeling surgery: ONE fight.
    #   - Android Saga (9) "Boy from the Future" (Beat Mecha Frieza) chapter 0
    #       diff0 fight_id 0x4D | diff1 0x56 | diff2 0xE4
    "Remodeling surgery": [
        (9, 0, 0x4D),
        (9, 0, 0x56),   # difficulty 1
        (9, 0, 0xE4),   # difficulty 2
    ],

    # Super Saiyan: ONE capsule fight.
    #   - Broly: The Legendary Super Saiyan (11), chapter 3
    #       diff0 fight_id 0x3F | diff1 0x7A | diff2 0xAF
    "Super Saiyan": [
        (11, 3, 0x3F),
        (11, 3, 0x7A),   # difficulty 1
        (11, 3, 0xAF),   # difficulty 2
    ],

    # Galactic Warrior: TWO fights, both in Bojack Unbound (13).
    #   - chapter 4
    #       diff0 0x3C | diff1 0x66 | diff2 0xC7
    #   - chapter 6 "Deadly Show Begins"
    #       diff0 0x4E | diff1 0x96 | diff2 0x146
    #     (SAME fight as Ultimate transformation's (13,6,...) — drops both)
    "Galactic Warrior": [
        (13, 4, 0x3C),
        (13, 6, 0x4E),
        (13, 6, 0x96),   # Bojack ch6, difficulty 1 (shared w/ Ultimate transformation)
        (13, 6, 0x146),  # Bojack ch6, difficulty 2 (shared w/ Ultimate transformation)
        (13, 4, 0x66),   # Bojack ch4, difficulty 1
        (13, 4, 0xC7),   # Bojack ch4, difficulty 2
    ],

    # Saike demon: ONE fight.
    #   - Fusion Reborn (16) "Innocent Monster, Janemba" chapter 1
    #       diff0 fight_id 0x3C | diff1 0x4D | diff2 0xAF
    "Saike demon": [
        (16, 1, 0x3C),
        (16, 1, 0x4D),   # difficulty 1
        (16, 1, 0xAF),   # difficulty 2
    ],

    # Human gunman's gun: Majin Buu Saga (14) chapter 12.
    #   diff0 fight_id 0x54 | diff1 0x7A | diff2 0xC7
    "Human gunman's gun": [
        (14, 12, 0x54),   # difficulty 0
        (14, 12, 0x7A),   # difficulty 1
        (14, 12, 0xC7),   # difficulty 2
    ],

    # People's bad energy: ONE fight.
    #   - Fusion Reborn (16) "Great Saiyaman 3" chapter 4
    #       diff0 fight_id 0x94 | diff1 0xA6 | diff2 0x176
    "People's bad energy": [
        (16, 4, 0x94),
        (16, 4, 0xA6),    # difficulty 1
        (16, 4, 0x176),   # difficulty 2
    ],

    # Artificial Blutz wave: ONE fight.
    #   - Baby, The Avenger (18) "SS 4 Reborn" chapter 4
    #       diff0 fight_id 0x3C | diff1 0xAF | diff2 0xE4
    "Artificial Blutz wave": [
        (18, 4, 0x3C),
        (18, 4, 0xAF),   # difficulty 1
        (18, 4, 0xE4),   # difficulty 2
    ],

    # breakthrough the limit: ONE fight.
    #   - Broly: The Legendary Super Saiyan (11) "Ultimate Battle" chapter 6
    #       diff0 fight_id 0x3F | diff1 0x97 | diff2 0xAF
    "breakthrough the limit": [
        (11, 6, 0x3F),
        (11, 6, 0x97),   # difficulty 1
        (11, 6, 0xAF),   # difficulty 2
    ],

    # Self Destruction: ONE fight.
    #   - Android Saga (9) "Final Battle" chapter 23
    #       diff0 fight_id 0x53 | diff1 0xC7 | diff2 0xE4
    "Self Destruction": [
        (9, 23, 0x53),
        (9, 23, 0xC7),   # difficulty 1
        (9, 23, 0xE4),   # difficulty 2
    ],

    # Power Ball: FIVE fights (OR). Used with Nappa, Vegeta, Turles, Raditz,
    # Bardock across these sagas. Per-source difficulty fight_ids:
    #   - Saiyan Saga (0) ch12:  d0 0x1B | d1 0x27 | d2 0x4D
    #   - Saiyan Saga (0) ch16:  d0 0x2D | d1 0x2D | d2 0x66
    #   - Tree of Might (1) ch2: d0 0x2D | d1 0x66 | d2 0x7A
    #   - Final Battle (3) ch2:  d0 0x5D | d1 0x85 | d2 0xD7
    #   - Fateful Brothers (21) ch7: d0 0x33 | d1 0x7A | d2 0xAF
    "Power Ball": [
        (0, 12, 0x1B),
        (0, 16, 0x2D),
        (1, 2, 0x2D),
        (3, 2, 0x5D),
        (21, 7, 0x33),
        (0, 12, 0x27),   # Saiyan ch12, difficulty 1
        (0, 12, 0x4D),   # Saiyan ch12, difficulty 2
        (0, 16, 0x66),   # Saiyan ch16, difficulty 2 (d1 == d0 0x2D, already present)
        (1, 2, 0x66),    # Tree of Might ch2, difficulty 1
        (1, 2, 0x7A),    # Tree of Might ch2, difficulty 2
        (3, 2, 0x85),    # Final Battle ch2, difficulty 1
        (3, 2, 0xD7),    # Final Battle ch2, difficulty 2
        (21, 7, 0x7A),   # Fateful Brothers ch7, difficulty 1
        (21, 7, 0xAF),   # Fateful Brothers ch7, difficulty 2
    ],

    # Lower class Saiyan: TWO fights (OR).
    #   - Tree of Might (1) ch0:  d0 0x27 | d1 0x27 | d2 0x4D  (-> Turles fusion)
    #   - Baby, The Avenger (18) ch2: d0 0x3C | d1 0x97 | d2 0xC7  (-> Super Baby 1)
    #     (SHARED fight with Baby — both ingredients drop here)
    # NOTE: "Lower class Saiyan (2)" is a separate in-game capsule not used in
    # any recipe — these fights map to plain "Lower class Saiyan".
    "Lower class Saiyan": [
        (1, 0, 0x27),
        (18, 2, 0x3C),
        (1, 0, 0x4D),    # Tree of Might ch0, difficulty 2 (d1 == d0 0x27, already present)
        (18, 2, 0x97),   # Baby ch2, difficulty 1 (shared w/ Baby)
        (18, 2, 0xC7),   # Baby ch2, difficulty 2 (shared w/ Baby)
    ],

    # HFIL fighter #17: ONE fight.
    #   - Ultimate Android (19) "Impenetrable Defense" chapter 5
    #       diff0 fight_id 0x49 | diff1 0xAF | diff2 0xC7
    "HFIL fighter #17": [
        (19, 5, 0x49),
        (19, 5, 0xAF),   # difficulty 1
        (19, 5, 0xC7),   # difficulty 2
    ],

    # Power from lower class: ONE fight.
    #   - Baby, The Avenger (18) "Immortal Monster" chapter 3
    #       diff0 fight_id 0x3C | diff1 0x7A | diff2 0xC7
    # (Note: at d0 Baby saga chapters 2/3/4 all read fight_id 0x3C — chapter
    #  disambiguates them: ch2 Lower class Saiyan, ch3 here, ch4 Blutz wave.
    #  At higher difficulties the fight_ids diverge per chapter.)
    "Power from lower class": [
        (18, 3, 0x3C),
        (18, 3, 0x7A),   # difficulty 1
        (18, 3, 0xC7),   # difficulty 2
    ],

    # Absorb Gotenks: ONE fight (shared w/ Absorb Gohan).
    #   - Majin Buu Saga (14) "Reversal of Fortunes" chapter 15
    #       diff0 0x4E | diff1 0x97 | diff2 0xAF
    "Absorb Gotenks": [
        (14, 15, 0x4E),
        (14, 15, 0x97),   # difficulty 1 (shared w/ Absorb Gohan)
        (14, 15, 0xAF),   # difficulty 2 (shared w/ Absorb Gohan)
    ],

    # Absorb Gohan: SAME fight as Absorb Gotenks (one fight drops both).
    #   - Majin Buu Saga (14) "Reversal of Fortunes" chapter 15
    #       diff0 0x4E | diff1 0x97 | diff2 0xAF
    "Absorb Gohan": [
        (14, 15, 0x4E),
        (14, 15, 0x97),   # difficulty 1 (shared w/ Absorb Gotenks)
        (14, 15, 0xAF),   # difficulty 2 (shared w/ Absorb Gotenks)
    ],

    # Makyo Star (fusion): ONE fight.
    #   - Makyo Star (5) "Black Mist of Fear" chapter 0
    #       diff0 fight_id 0x30 | diff1 0x48 | diff2 0x9A
    # (NOTE: ingredient name is "Makyo Star (fusion)", not the saga name.)
    "Makyo Star (fusion)": [
        (5, 0, 0x30),
        (5, 0, 0x48),   # difficulty 1
        (5, 0, 0x9A),   # difficulty 2
    ],

    # Dead Zone: ONE fight.
    #   - Makyo Star (5) "Piccolo a Monster" chapter 1
    #       diff0 fight_id 0x2D | diff1 0x4D | diff2 0x7A
    "Dead Zone": [
        (5, 1, 0x2D),
        (5, 1, 0x4D),   # difficulty 1
        (5, 1, 0x7A),   # difficulty 2
    ],

    # Giant Form: TWO fights (OR).
    #   - Makyo Star (5) "Destroy the Makyo Star" ch2:
    #       diff0 0x4D | diff1 0x7A | diff2 0x97
    #   - Lord Slug (2) "Terror! Evil Invaders" ch0:
    #       diff0 0x2F | diff1 0x37 | diff2 0x4D  (SHARED w/ Namekian)
    "Giant Form": [
        (5, 2, 0x4D),
        (2, 0, 0x2F),
        (5, 2, 0x7A),   # Makyo Star ch2, difficulty 1
        (5, 2, 0x97),   # Makyo Star ch2, difficulty 2
        (2, 0, 0x37),   # Lord Slug ch0, difficulty 1 (shared w/ Namekian)
        (2, 0, 0x4D),   # Lord Slug ch0, difficulty 2 (shared w/ Namekian)
    ],

    # Hatred of Goku: TWO fights (OR).
    #   - Cooler's Revenge (6) "Cooler Attacks" ch0:
    #       diff0 0x2A | diff1 0x66 | diff2 0x78
    #   - Broly: TLSS (11) "Mysterious Saiyan Broly" ch0:
    #       diff0 0x3F | diff1 0x45 | diff2 0xAF  (SHARED w/ Son of Paragus)
    # (NOTE: distinct from the separate "Hatred" ingredient.)
    "Hatred of Goku": [
        (6, 0, 0x2A),
        (11, 0, 0x3F),
        (6, 0, 0x66),    # Cooler's Revenge ch0, difficulty 1
        (6, 0, 0x78),    # Cooler's Revenge ch0, difficulty 2
        (11, 0, 0x45),   # Broly ch0, difficulty 1 (shared w/ Son of Paragus)
        (11, 0, 0xAF),   # Broly ch0, difficulty 2 (shared w/ Son of Paragus)
    ],

    # Big Gete Star: ONE fight.
    #   - The Return of Cooler (7) "The Return of Cooler" chapter 6
    #       diff0 fight_id 0x96 | diff1 0x111 | diff2 0x257
    "Big Gete Star": [
        (7, 6, 0x96),
        (7, 6, 0x111),   # difficulty 1
        (7, 6, 0x257),   # difficulty 2
    ],

    # Seriousness: ONE fight.
    #   - The Return of Cooler (7) "Cooler Lives" chapter 0
    #       diff0 fight_id 0x2A | diff1 0x3E | diff2 0xC1
    "Seriousness": [
        (7, 0, 0x2A),
        (7, 0, 0x3E),   # difficulty 1
        (7, 0, 0xC1),   # difficulty 2
    ],

    # Namekian: ONE fight (shared w/ Giant Form).
    #   - Lord Slug (2) "Terror! Evil Invaders" chapter 0
    #       diff0 0x2F | diff1 0x37 | diff2 0x4D
    "Namekian": [
        (2, 0, 0x2F),
        (2, 0, 0x37),   # difficulty 1 (shared w/ Giant Form)
        (2, 0, 0x4D),   # difficulty 2 (shared w/ Giant Form)
    ],

    # Mutation: ONE fight.
    #   - Lord Slug (2) "The Terrible Super Namekian" chapter 1
    #       diff0 fight_id 0x2F | diff1 0x37 | diff2 0x4D
    # (Same fight_ids as Lord Slug ch0 Namekian/Giant Form at each difficulty,
    #  but ch1 — the chapter field keeps these triples distinct.)
    "Mutation": [
        (2, 1, 0x2F),
        (2, 1, 0x37),   # difficulty 1
        (2, 1, 0x4D),   # difficulty 2
    ],

    # The Flowers of Evil: ONE fight.
    #   - Bojack Unbound (13) "Beautiful Assassin" chapter 2
    #       diff0 fight_id 0x36 | diff1 0x3C | diff2 0xAF
    "The Flowers of Evil": [
        (13, 2, 0x36),
        (13, 2, 0x3C),   # difficulty 1
        (13, 2, 0xAF),   # difficulty 2
    ],

    # Armored cavalry: ONE fight.
    #   - Cooler's Revenge (6) chapter 2
    #       diff0 fight_id 0x30 | diff1 0x4D | diff2 0x5F
    "Armored cavalry": [
        (6, 2, 0x30),
        (6, 2, 0x4D),   # difficulty 1
        (6, 2, 0x5F),   # difficulty 2
    ],

    # Cooler's soldier: ONE fight (shared w/ Frieza's brother).
    #   - Cooler's Revenge (6) chapter 3
    #       diff0 0x6F | diff1 0xB7 | diff2 0x135
    "Cooler's soldier": [
        (6, 3, 0x6F),
        (6, 3, 0xB7),    # difficulty 1 (shared w/ Frieza's brother)
        (6, 3, 0x135),   # difficulty 2 (shared w/ Frieza's brother)
    ],

    # Son of Paragus: ONE fight (shared w/ Hatred of Goku).
    #   - Broly: TLSS (11) "Mysterious Saiyan Broly" chapter 0
    #       diff0 0x3F | diff1 0x45 | diff2 0xAF
    "Son of Paragus": [
        (11, 0, 0x3F),
        (11, 0, 0x45),   # difficulty 1 (shared w/ Hatred of Goku)
        (11, 0, 0xAF),   # difficulty 2 (shared w/ Hatred of Goku)
    ],

    # Frieza's soldier + Vegeta's rival: SAME fight drops both.
    #   - Frieza Saga (4) chapter 0
    #       diff0 0x18 | diff1 0x20 | diff2 0x3F
    "Frieza's soldier": [
        (4, 0, 0x18),
        (4, 0, 0x20),   # difficulty 1 (shared w/ Vegeta's rival)
        (4, 0, 0x3F),   # difficulty 2 (shared w/ Vegeta's rival)
    ],
    "Vegeta's rival": [
        (4, 0, 0x18),
        (4, 0, 0x20),   # difficulty 1 (shared w/ Frieza's soldier)
        (4, 0, 0x3F),   # difficulty 2 (shared w/ Frieza's soldier)
    ],

    # Evil Dragon: ONE fight.
    #   - Evil Dragon of Absolute Destruction (20) chapter 0
    #       diff0 fight_id 0x3C | diff1 0x7A | diff2 0xC7
    "Evil Dragon": [
        (20, 0, 0x3C),
        (20, 0, 0x7A),   # difficulty 1
        (20, 0, 0xC7),   # difficulty 2
    ],

    # Negative Energy: ONE fight.
    #   - Evil Dragon of Absolute Destruction (20) chapter 2
    #       diff0 fight_id 0x3C | diff1 0x97 | diff2 0xC7
    "Negative Energy": [
        (20, 2, 0x3C),
        (20, 2, 0x97),   # difficulty 1
        (20, 2, 0xC7),   # difficulty 2
    ],

    # Ultimate Dragonball: ONE fight.
    #   - Evil Dragon of Absolute Destruction (20) chapter 5
    #       diff0 fight_id 0x3C | diff1 0xC7 | diff2 0xE4
    # (At d0 Evil Dragon saga ch0/2/5 all read 0x3C — chapter disambiguates;
    #  higher difficulties diverge per chapter.)
    "Ultimate Dragonball": [
        (20, 5, 0x3C),
        (20, 5, 0xC7),   # difficulty 1
        (20, 5, 0xE4),   # difficulty 2
    ],

    # Computer: ONE fight.
    #   - Super Android 13 (10) chapter 0
    #       diff0 fight_id 0x3D | diff1 0x45 | diff2 0x97
    "Computer": [
        (10, 0, 0x3D),
        (10, 0, 0x45),   # difficulty 1
        (10, 0, 0x97),   # difficulty 2
    ],

    # Hatred: ONE fight.
    #   - Super Android 13 (10) chapter 1
    #       diff0 fight_id 0x43 | diff1 0x4D | diff2 0xAF
    # (Distinct from "Hatred of Goku" — separate ingredient.)
    "Hatred": [
        (10, 1, 0x43),
        (10, 1, 0x4D),   # difficulty 1
        (10, 1, 0xAF),   # difficulty 2
    ],

    # Parts of #14/#15: ONE fight.
    #   - Super Android 13 (10) chapter 4
    #       diff0 fight_id 0x49 | diff1 0x97 | diff2 0xDF
    "Parts of #14/#15": [
        (10, 4, 0x49),
        (10, 4, 0x97),   # difficulty 1
        (10, 4, 0xDF),   # difficulty 2
    ],

    # Fruit of the Tree of Might: ONE fight.
    #   - Tree of Might (1) chapter 1
    #       diff0 fight_id 0x21 | diff1 0x27 | diff2 0x4D
    # (d1/d2 match Tree of Might ch0 fights but this is ch1 — chapter distinct.)
    "Fruit of the Tree of Might": [
        (1, 1, 0x21),
        (1, 1, 0x27),   # difficulty 1
        (1, 1, 0x4D),   # difficulty 2
    ],

    # Kibito: ONE fight.
    #   - Majin Buu Saga (14) chapter 18
    #       diff0 fight_id 0x4E | diff1 0x97 | diff2 0xAF
    # (Same d0 fight_id 0x4E as Absorb pair at ch15, but ch18 — distinct fight.)
    "Kibito": [
        (14, 18, 0x4E),
        (14, 18, 0x97),   # difficulty 1
        (14, 18, 0xAF),   # difficulty 2
    ],

    # Hirudegarn's top half: ONE fight.
    #   - Wrath of the Dragon (17) chapter 1
    #       diff0 fight_id 0x3C | diff1 0x66 | diff2 0xC7
    "Hirudegarn's top half": [
        (17, 1, 0x3C),
        (17, 1, 0x66),   # difficulty 1
        (17, 1, 0xC7),   # difficulty 2
    ],

    # Hirudegarn's lower half: ONE fight.
    #   - Wrath of the Dragon (17) chapter 5
    #       diff0 fight_id 0x3C | diff1 0x66 | diff2 0xE4
    "Hirudegarn's lower half": [
        (17, 5, 0x3C),
        (17, 5, 0x66),   # difficulty 1
        (17, 5, 0xE4),   # difficulty 2
    ],

    # Master Roshi's pupil: ONE fight (optional).
    #   - Destined Rivals "Destined Showdown" (Beat Grandpa Gohan), chapter 3
    #       diff0 fight_id 0x36 | diff1 0x42 | diff2 0xC7
    # NOTE: the LIVE scenario index for this fight reads 24, even though
    # Destined Rivals is index 23 in our SCENARIOS list — the live DA scenario
    # numbering is shifted by +1 for this saga. We store the LIVE value (24)
    # here so the client matches it at runtime; SCENARIO_LIVE_TO_LIST maps it
    # back to 23 for AP logic (has_scenario).
    "Master Roshi's pupil": [
        (24, 3, 0x36),
        (24, 3, 0x42),   # difficulty 1
        (24, 3, 0xC7),   # difficulty 2
    ],

    # Baby: ONE fight (shared w/ Lower class Saiyan).
    #   - Baby, The Avenger (18) chapter 2
    #       diff0 0x3C | diff1 0x97 | diff2 0xC7
    "Baby": [
        (18, 2, 0x3C),
        (18, 2, 0x97),   # difficulty 1 (shared w/ Lower class Saiyan)
        (18, 2, 0xC7),   # difficulty 2 (shared w/ Lower class Saiyan)
    ],

    # Frieza's brother: ONE fight (shared w/ Cooler's soldier).
    #   - Cooler's Revenge (6) chapter 3
    #       diff0 0x6F | diff1 0xB7 | diff2 0x135
    "Frieza's brother": [
        (6, 3, 0x6F),
        (6, 3, 0xB7),    # difficulty 1 (shared w/ Cooler's soldier)
        (6, 3, 0x135),   # difficulty 2 (shared w/ Cooler's soldier)
    ],
}


# Some late sagas report a LIVE Dragon Adventure scenario index (ADDR_DA_SCENARIO
# 0x76BDF0) that differs from their position in the SCENARIOS list. Detection
# signatures above use the LIVE value (what the client reads at runtime); this
# map translates a live value to the corresponding SCENARIOS list index for AP
# logic (has_scenario). Live values not present here equal their list index.
SCENARIO_LIVE_TO_LIST: dict[int, int] = {
    24: 23,   # Destined Rivals (live 24 -> list index 23)
}


def live_scenario_to_list(live_index: int) -> int:
    """Translate a live DA scenario index to the SCENARIOS list index."""
    return SCENARIO_LIVE_TO_LIST.get(live_index, live_index)


# Recurring-enemy ingredients: some drop from an enemy who appears in MANY
# missions across different sagas/chapters, always with the SAME fight_id. For
# these, matching the full (scenario, chapter, fight_id) triple would require
# enumerating every appearance — instead we match the fight_id ALONE: winning
# ANY fight with that id discovers the ingredient(s).
#
# DIFFICULTY 0 baseline (fight_id is difficulty-dependent).
#
# NOTE: General Tao (Memorial campaign + Bros. of Crane Hermit) was previously
# mapped here via fight_id 0x12, but its higher-difficulty fight_ids (e.g. 0x2D)
# collide with many unrelated fights, which would cause false discoveries.
# General Tao remains fully in the randomizer (recipe, Fuse check, and both
# ingredient items are intact) — only the FIGHT-BASED discovery is removed, so
# these two ingredients use the owned-flag fallback for their Discover checks.
#
# Format: { fight_id: [ingredient names...] }
INGREDIENT_BY_FIGHT_ID: dict[int, list[str]] = {
    # (empty — see note above)
}


def fight_id_ingredients(fight_id: int) -> list[str]:
    """Ingredients discovered by winning ANY fight with this fight_id
    (recurring-enemy mode). Empty list if none."""
    return INGREDIENT_BY_FIGHT_ID.get(fight_id, [])


def discovery_fights(ingredient_name: str) -> list[tuple[int, int, int]]:
    """Return the list of (scenario, chapter, fight_id) signatures whose victory
    discovers the given ingredient. Empty list if unmapped."""
    return INGREDIENT_DISCOVERY.get(ingredient_name, [])


def all_mapped_ingredients() -> set[str]:
    mapped = set(INGREDIENT_DISCOVERY.keys())
    for ings in INGREDIENT_BY_FIGHT_ID.values():
        mapped.update(ings)
    return mapped
