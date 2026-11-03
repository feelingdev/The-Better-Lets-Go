# The Better Let's Go

## AI disclosure

**This project is AI-assisted, about 95% overall by my estimate.** That's a judgement, not a measurement.

| Work | Done by |
|---|---|
| Reverse engineering, patch code, build scripts, documentation | Claude (Anthropic's AI), essentially 100% |
| Feature ideas, design decisions, what to keep or drop | The project owner |
| All testing on real hardware | The project owner |

The AI can't run the game, so every result below comes from the owner testing on a Switch. Expect mistakes, and please report them.

## About

A patch for **Pokémon: Let's Go, Pikachu!** and **Pokémon: Let's Go, Eevee!** on modded Nintendo Switch. It lets you battle wild Pokémon, with EXP and evolution, and catch them when you choose. It also marks species you've already caught, adds an Exp. Share switch, level-up trade evolutions, Sky Dash on D-pad Up and an intro skip, and its options are translated into every language the game has, including Japanese.

> **Status: v1.0.0.** Tested by the owner on one Switch in both games, but not every feature has been checked, and nobody has done a full playthrough yet. Back up your saves. See [Testing status](#testing-status).

## See it in action

| Enable Wild Battle: **On** | Enable Wild Battle: **Off** |
|---|---|
| ![With the option On, a wild Rattata starts a battle with Pikachu](docs/images/option-on.gif) | ![With the option Off, a wild Rattata goes straight to the normal catch screen](docs/images/option-off.gif) |

The options in the Options menu:

<img src="docs/images/option.jpg" width="600" alt="The Options menu with Enable Wild Battle selected and its description shown, above the Level-Up Trade Evolution and Exp. Share rows">

## Features

All of these can be switched off in-game, except the caught marker, Sky Dash on D-pad Up and the intro skip. Everything works the same in both games.

| Feature | What it does |
|---|---|
| **Wild battles** | Wild encounters start a real battle instead of going straight to catching |
| **EXP on a win** | The wild Pokémon faints as in a trainer battle, then you get EXP, then any evolution, then you're back in the overworld |
| **Catch from the Bag** | Pick a Poké Ball in the battle Bag to end the battle and open the catch screen, starting on that ball. You get EXP if you catch it, none if you run |
| **No battle timer** | The time limit on these battles is removed |
| **Caught marker** | In a wild battle, a Poké Ball appears left of the wild Pokémon's name box if you've already caught that species, as in the other Pokémon games. It uses the game's own Poké Ball icon |
| **"Enable Wild Battle" option** | On/Off in the Options menu, saved with your game. On by default. Off uses the original catching mechanic |
| **"Level-Up Trade Evolution" option** | On/Off in the Options menu, saved with your game. Off by default. On lets Kadabra, Machoke, Graveler and Haunter also evolve by leveling up, starting at Level 50. Trading still works |
| **"Exp. Share" option** | On/Off in the Options menu, saved with your game. On by default, as in the original game. Off gives EXP only to Pokémon that fought, in every battle that gives EXP, when you catch with a ball from the Bag, and when you catch Snorlax or a Legendary after fighting it. After those catches, the game names each Pokémon that got EXP. Catching with no battle at all still gives EXP to the whole party |
| **Every game language** | All the options appear and are translated in all the game's languages, including Japanese in kana and kanji |
| **Sky Dash on D-pad Up** | Press **Up** in the overworld to open the town map and pick a place to fly to, once you've unlocked Sky Dash. **B** takes you back to the overworld. Works whatever the options are set to. Not on a single Joy-Con, where Up opens the menu |
| **Intro skip** | Press **+**, **−**, **A**, **B**, **X** or **Y** during the opening animation to jump to the title screen. Works whatever the options are set to |

"Presented By" can't be skipped.

## Requirements

| Requirement | Details |
|---|---|
| Console | Nintendo Switch running custom firmware with [Atmosphère](https://github.com/Atmosphere-NX/Atmosphere) |
| Game | **Pokémon: Let's Go, Pikachu!** or **Pokémon: Let's Go, Eevee!**, each with its own download |
| Game version | **1.0.2**, with the update installed |

| Game | Title ID | Build ID |
|---|---|---|
| Let's Go, Pikachu! | `010003F003A34000` | `C208DB6A4EF4361F28B8402BE0F7CD9A` |
| Let's Go, Eevee! | `0100187003A36000` | `5831EC64D6B696FD69E69505821B97B1` |

Each patch only applies to its game's exact build. On any other version it does nothing.

## Installation

1. **Back up your save** with a tool such as JKSV or Checkpoint.
2. Remove any other wild battle mods, including the original Wild Battles. They change the same code.
3. Download the zip for your game from [Releases](../../releases): `Pikachu` or `Eevee`. You can install both on the same SD card.
4. Unzip it to the root of your SD card, merging with the existing `atmosphere` folder.
5. Fully close the game (press X on the HOME menu), then start it again.

The patch ends up here, named after the game's build ID:

```
/atmosphere/exefs_patches/the_better_lets_go/C208DB6A4EF4361F28B8402BE0F7CD9A00000000000000000000000000000000.ips   (Pikachu)
/atmosphere/exefs_patches/the_better_lets_go/5831EC64D6B696FD69E69505821B97B100000000000000000000000000000000.ips   (Eevee)
```

**To uninstall,** delete that file, or the whole `the_better_lets_go` folder. Each option's saved value is one otherwise unused bit, and nothing was seen to use them without the patch, but this hasn't been tested over a long save, so keep your backup.

## How to play

- **Battle:** walk into a wild Pokémon as usual.
- **Catch:** open **Bag** in battle and pick a Poké Ball.
- **Turn it off:** go to **Options → Enable Wild Battle**.
- **Give EXP only to Pokémon that fought:** go to **Options → Exp. Share** and turn it off.
- **Fly:** press **Up** in the overworld, then pick a place on the map with **A**.
- **Evolve without trading:** turn on **Options → Level-Up Trade Evolution**, then level up at Level 50 or above. A Pokémon at Level 100 can't level up, so it can't evolve this way.

Beating a Pokémon gives no chance to catch it, so **pick a ball before you finish the fight**. Snorlax, Legendaries and other scripted wild fights are different: they play as in the original game, with no balls in the battle Bag, and you catch them after you win.

## Warnings

- **Stay offline.** Stay out of GO Park, and don't use online features with this patch. Modified games can get your console banned, and the patch overwrites part of a library that handles online data, which could crash if online features ever used it.

## Known limitations

- **Translations:** the options' text is translated by AI into every language the game has, including both Japanese modes, using the game's own terms and Pokémon names. It hasn't been checked by native speakers, so corrections are very welcome. They live in [`tools/option_text.py`](tools/option_text.py).

## Testing status

Tested by the author on one Switch. **This build changed how the code is organised, so older results below need rechecking.**

| Area | Status |
|---|---|
| Options row, text and saving the choice | Tested |
| Catch screen opening on the picked ball | Tested |
| Level-Up Trade Evolution option and evolving at Level 50 | Tested |
| +, −, A, B, X and Y skipping the opening animation | Tested |
| Timer, EXP on a win, evolution, early saves | Tested |
| Option Off restoring the original mechanic | Tested |
| No catch screen after a win, catch EXP, ball count | Tested |
| Losing, running, trainer battles, long sessions | Tested |
| The wild Pokémon fainting on a win | Tested |
| Caught marker, in both games | Tested |
| Let's Go, Eevee!: wild battles, the partner Eevee, male and female partners | Tested |
| Exp. Share Off | Partly tested: catching worked, but the per-Pokémon EXP messages and who received EXP haven't been checked |
| Sky Dash on D-pad Up | **Not tested** |
| Snorlax, Legendaries and other scripted wild fights | **Not tested** |
| Other game languages | **Not tested** (only English has been) |
| Let's Go, Eevee!: the remaining features one by one | **Not tested**. They use the same code as Pikachu, moved to Eevee's addresses |
| Shiny and Special Encounters | **Not tested** |
| A full playthrough | **Not done** |

## Help test this

Testers are very welcome, and this is the area that needs the most help. Please back up your save first and stay offline.

**Most useful right now:**

- A full playthrough, especially story catches and any moment that hangs or repeats
- Legendaries and Snorlax, with the option On and Off
- Shiny and Special Encounters
- Other game languages, since only English has been tested
- Other controller setups, such as a single Joy-Con or a Poké Ball Plus

**To report a result,** [open an issue](../../issues/new) and include:

- What you did, what you expected and what happened
- Your Atmosphère version, game language and controller setup
- How far you are in the game, and whether the option was On or Off
- A screenshot or short clip, if you can
- Which game: Pikachu or Eevee
- If the game crashed, the newest report from `/atmosphere/crash_reports/` ending in `_010003f003a34000.log` (Pikachu) or `_0100187003a36000.log` (Eevee)

Reports that something works are useful too. Please don't share save files, keys or game files.

## Building from source

This needs your own decompressed `main` from the game (1.0.2), with its 0x100-byte header still attached. No game files are in this repo. The script tells the two games apart by the build ID inside `main`.

```
pip install capstone
python tools/build_patch.py path/to/main_uncompressed.bin output.ips
python tools/package_release.py output.ips dist/The-Better-Lets-Go-Pikachu.zip pikachu
python tools/package_release.py output.ips dist/The-Better-Lets-Go-Eevee.zip eevee
```

The script checks every original instruction before patching and stops if the game doesn't match. Eevee's addresses come from `tools/address_map_eevee.py`, which `tools/make_address_map.py` makes from both games' `main` files. It only needs running again for code that uses a new address. See [docs/TECHNICAL.md](docs/TECHNICAL.md) for how the patch works.

## Credits

**Inspired by [Wild Battles](https://gamebanana.com/mods/729162) by Rico-Santos.** The idea of battling wild Pokémon before catching them comes from that mod.

This project started as personal fixes to that mod, and its code was studied during development. The code here was then written independently and needs no part of it, and no files from that mod are in this repo. Because it was studied, this is **not** a clean-room rewrite, and some of the logic is necessarily similar, since both change the same game behaviour. Wild Battles is licensed CC BY-NC-ND, so please respect its terms and download it from its own page.

Also built with [Atmosphère](https://github.com/Atmosphere-NX/Atmosphere), which applies the patch, and [Capstone](https://www.capstone-engine.org/), used by the build script.

## License

Copyright (C) 2026 feelingdev. This project is licensed under the [GNU General Public License v3.0](LICENSE) (GPL-3.0). You can use, change and share it, but any version you distribute must also make its source available under the same license. It comes with no warranty.

The license only covers this project's own code, not the game or anything owned by others.

## Legal

This is an unofficial fan project, and isn't affiliated with or endorsed by Nintendo, Game Freak, Creatures Inc. or The Pokémon Company. Pokémon is a trademark of its respective owners. You need your own legal copy of the game. This repo contains no game files, keys or ROMs, and the patch contains its own code plus a few of the game's instructions it has to relocate. The images in `docs/images` are captures of the game, used to show what the patch does, and they aren't covered by this project's license. Use it at your own risk.
