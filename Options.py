from dataclasses import dataclass
from Options import Toggle, Choice, Range, OptionSet, PerGameCommonOptions
from .data import Constants as _C


class Goal(Choice):
    """How to win the multiworld.
      scenarios   = complete `required_scenarios` Dragon Adventure scenarios
                    (the classic goal).
      time_scrolls= collect `time_scrolls_required` Time Scrolls (McGuffin items
                    shuffled across the multiworld). Collecting them all UNLOCKS
                    the Final Saga (otherwise locked); you then complete that
                    saga to 'repair the timeline' and win. Encourages exploring
                    far more of the game to find your scrolls.
      both        = satisfy BOTH conditions to win (N scenarios AND the Final
                    Saga completed after gathering the scrolls).
    """
    display_name = "Goal"
    option_scenarios = 0
    option_time_scrolls = 1
    option_both = 2
    default = 1


class FinalSaga(Choice):
    """For the time_scrolls goal: which saga the Time Scrolls unlock as the
    final confrontation. It stays locked until you've gathered enough scrolls,
    then opens; completing it wins. Defaults to Evil Dragon of Absolute
    Destruction — the climactic Shadow Dragon saga, a fitting finale for
    repairing the shattered timeline."""
    display_name = "Final Saga"
    option_evil_dragon = 20
    option_destined_rivals = 23
    option_beautiful_treachery = 22
    option_fateful_brothers = 21
    option_majin_buu = 14
    default = 20


class TimeScrollsRequired(Range):
    """For the time_scrolls goal: how many Time Scrolls you must collect to win.
    Must be <= Time Scrolls Total."""
    display_name = "Time Scrolls Required"
    range_start = 1
    range_end = 20
    default = 7


class TimeScrollsTotal(Range):
    """For the time_scrolls goal: how many Time Scrolls exist in the item pool.
    Extra scrolls beyond 'required' give the generator flexibility and let you
    win without finding literally all of them. Clamped to >= required."""
    display_name = "Time Scrolls Total"
    range_start = 1
    range_end = 25
    default = 10


class RequiredScenarios(Range):
    """Number of Dragon Adventure scenarios that must be fully completed
    (all missions cleared) to win. There are 24 scenarios total."""
    display_name = "Required Scenarios"
    range_start = 1
    range_end = 24
    default = 5


class StartingScenarios(Range):
    """How many random scenarios are unlocked from the start (their unlock
    items are precollected). The rest are gated behind unlock items in the
    multiworld."""
    display_name = "Starting Scenarios"
    range_start = 1
    range_end = 24
    default = 1


class FusionLogic(Choice):
    """How Z-Fusion character checks are gated.
    - full: Z-Fusion characters require their recipe ingredients (state.has).
    - free: ingredients are auto-granted; Z-Fusion characters only require
      that you can reach the relevant content (lighter logic)."""
    display_name = "Z-Fusion Logic"
    option_full = 0
    option_free = 1
    default = 0


class FillerRatio(Range):
    """Approximate percentage of non-progression locations filled with Zeni
    filler (vs. useful Z-Item ability boosts). 0 = all useful, 100 = all Zeni."""
    display_name = "Filler Ratio"
    range_start = 0
    range_end = 100
    default = 25


class DifficultyFloor(Choice):
    """Minimum game level a mission must be cleared on to count as a check /
    toward scenario completion. any = Level 1+, hard = Level 3 only."""
    display_name = "Difficulty Floor"
    option_any = 1
    option_medium = 2
    option_hard = 3
    default = 1


class RandomizeFighters(Choice):
    """Randomize the characters in Dragon Adventure fights (player team and/or
    opponents). Deterministic per mission (same fight always randomizes the same
    way for a given seed). Cosmetic/gameplay only — does NOT affect logic or
    checks. 'off' disables it.
      both    = randomize player team and enemies
      enemies = randomize only opponents
      players = randomize only your team
    """
    display_name = "Randomize Fighters"
    option_off = 0
    option_both = 1
    option_enemies = 2
    option_players = 3
    default = 0


class FighterPool(Choice):
    """Which characters randomized fighters can be drawn from.
      any       = the entire 129-character roster
      unlocked  = only characters you've unlocked so far (read live)
    """
    display_name = "Fighter Pool"
    option_any = 0
    option_unlocked = 1
    default = 0


class ShopChecks(Range):
    """How many Item Shop purchase checks to add. The client takes over the
    shop, hides all default items, and shows named check-items the player buys
    to send checks. Each is detected by Zeni decreasing by that slot's unique
    price (immune to AP item grants, which don't cost Zeni). 0 disables shop
    checks. Capped at the number of confidently-named shop items (25)."""
    display_name = "Shop Checks"
    range_start = 0
    range_end = 59
    default = 50


class ShopInitial(Range):
    """How many shop checks are available from the start. The rest are revealed
    by receiving Shop Restock items."""
    display_name = "Shop Initial Slots"
    range_start = 1
    range_end = 59
    default = 10


class ShopRestockAmount(Range):
    """How many additional shop checks each Shop Restock item reveals."""
    display_name = "Shop Restock Amount"
    range_start = 1
    range_end = 25
    default = 10


class ExcludedSagas(OptionSet):
    """Sagas (chapters) to DISABLE. By default this is empty, meaning ALL 24
    sagas are included. List any saga names here to exclude them: their mission
    checks and unlock item are removed from the pool and you never need to play
    them. The Final Saga (your goal) is ALWAYS kept enabled even if listed here.
    Example: ['Lord Slug', 'Makyo Star'].

    Valid saga names: Saiyan Saga, Tree of Might, Lord Slug, Final Battle,
    Frieza Saga, Makyo Star, Cooler's Revenge, The Return of Cooler, The Story
    of Trunks, Android Saga, Super Android 13, Broly: The Legendary Super Saiyan,
    Ultimate Future Warrior, Bojack Unbound, Majin Buu Saga, Broly: The Second
    Coming, Fusion Reborn, Wrath of the Dragon, Baby, The Avenger, Ultimate
    Android, Evil Dragon of Absolute Destruction, Fateful Brothers, Beautiful
    Treachery..., Destined Rivals."""
    display_name = "Excluded Sagas"
    valid_keys = frozenset(name for name, _count in _C.SCENARIOS)
    default = frozenset()


@dataclass
class BT2Options(PerGameCommonOptions):
    goal: Goal
    final_saga: FinalSaga
    excluded_sagas: ExcludedSagas
    time_scrolls_required: TimeScrollsRequired
    time_scrolls_total: TimeScrollsTotal
    required_scenarios: RequiredScenarios
    starting_scenarios: StartingScenarios
    fusion_logic: FusionLogic
    filler_ratio: FillerRatio
    difficulty_floor: DifficultyFloor
    randomize_fighters: RandomizeFighters
    fighter_pool: FighterPool
    shop_checks: ShopChecks
    shop_initial: ShopInitial
    shop_restock_amount: ShopRestockAmount
