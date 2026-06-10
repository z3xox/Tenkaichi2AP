# DBZ Budokai Tenkaichi 2 — Archipelago

An [Archipelago](https://archipelago.gg) randomizer for **Dragon Ball Z: Budokai Tenkaichi 2** (PS2, NTSC-U / SLUS-21441) via **PCSX2**.

Dragon Adventure missions, character unlocks, secret what-if sagas, and Dragon Ball wishes become Archipelago checks and items. Scenarios are gated behind unlock items, and an optional Time Scroll goal sends you hunting across the whole game for the final confrontation.

> Alpha — back up your saves.

## Requirements
- PCSX2 with **PINE** enabled
- DBZ Budokai Tenkaichi 2 (NTSC-U, SLUS-21441, CRC `FE961D28`)

## Setup
1. Drop `budokai_tenkaichi2.apworld` into Archipelago's `custom_worlds/`.
2. Enable PINE in PCSX2 and load Budokai Tenkaichi 2.
3. Edit `budokai_tenkaichi2_player.yaml` (see options below), put it in `Players/`, and generate.
4. Launch the **Budokai Tenkaichi 2 Client**, connect to your server. It auto-detects the game.
5. Play — clear Dragon Adventure missions to send checks.

## Options
| Option | Default | Description |
|---|---|---|
| `goal` | time_scrolls | `scenarios` = complete N scenarios; `time_scrolls` = gather scrolls and beat the final saga; `both` |
| `final_saga` | evil_dragon | Which saga the Time Scrolls unlock as the finale (Evil Dragon, Destined Rivals, Beautiful Treachery, Fateful Brothers, Majin Buu) |
| `time_scrolls_required` | 7 | Time Scrolls needed to unlock the final saga |
| `time_scrolls_total` | 10 | Time Scrolls placed in the pool (≥ required) |
| `required_scenarios` | 5 | Scenarios to fully complete (scenarios/both goals), of 24 |
| `starting_scenarios` | 1 | How many scenarios are unlocked from the start |
| `fusion_logic` | full | `full` = Z-Fusion characters need their ingredients; `free` = ingredients auto-granted |
| `difficulty_floor` | any | Minimum game level a mission must be cleared on to count (any / medium / hard) |
| `randomize_fighters` | off | Randomize Dragon Adventure fighters: `both` / `enemies` / `players` / `off` |
| `fighter_pool` | any | Pool for randomized fighters: `any` (full roster) or `unlocked` |
| `filler_ratio` | 25 | % of filler locations that are Zeni (vs useful Z-Item boosts) |

## Checks (293)
- **Dragon Adventure missions (200)** — clear a mission = a check (respects `difficulty_floor`)
- **Character unlocks (89)** — unlock a roster character (starters excluded)
- **Secret saga unlocks (3)** — meet the in-game condition for a what-if saga:
  - *Fateful Brothers* — clear Saiyan Saga 00
  - *Beautiful Treachery* — clear Frieza Saga 00
  - *Destined Rivals* — clear Majin Buu Saga 01
- **Make a Wish (1)** — reach Shenron or Porunga after gathering all 7 Dragon Balls
- **Shop (up to 50)** - using "Shop Restock" grants 10 more items in the shop

## Items (250)
- **Scenario unlocks (24)** — gate each Dragon Adventure scenario; received via the multiworld
- **Z-Fusion ingredients (60)** — progression for Z-Fusion logic
- **Z-Item ability boosts (155)** — useful stat items
- **Dragon Balls (7)** — collected via the multiworld; the client enforces the in-game flags to match (random in-game drops are cleared). Gather all 7 to summon and claim the wish
- **Time Scrolls** — McGuffin goal items; gather enough to unlock the final saga
- **Zeni** filler bundles

## Goal
- **scenarios** — fully complete `required_scenarios` Dragon Adventure scenarios.
- **time_scrolls** — gather `time_scrolls_required` Time Scrolls scattered across the multiworld. They unlock the **Final Saga** (default: *Evil Dragon of Absolute Destruction*), which stays locked until then; completing it repairs the timeline and wins.
- **both** — satisfy both conditions.

## Fighter randomizer
With `randomize_fighters` on, Dragon Adventure matchups are shuffled — your team and/or the enemy team. It's deterministic per mission (the same fight always randomizes the same way for a given seed) and cosmetic only: it never affects checks or logic.

## Known limitations
- Shop checks/control are not yet implemented (Zeni currency address unconfirmed).
- Some unlocks may need one normal in-game save to persist into menus.
- The fresh-save starting roster is still being finalized; default-unlocked characters are suppressed from firing spurious checks on boot.

## Troubleshooting
- *Client can't find game* → check PCSX2 is running Budokai Tenkaichi 2 (CRC `FE961D28`) with PINE enabled.
- *Checks flooded on emulator close* → fixed; the client guards against garbage reads from a dying PINE connection. Update to the latest `.apworld` if you see this.
