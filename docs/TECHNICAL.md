# How the patch works

These are notes on `tools/build_patch.py`, from static analysis of `main` in Let's Go, Pikachu! 1.0.2 (build `C208DB6A4EF4361F28B8402BE0F7CD9A`). Addresses are memory addresses: IPS offset minus 0x100. Names are descriptive guesses, because the game ships without symbols. All addresses here are Pikachu's; see [Let's Go, Eevee!](#lets-go-eevee) for the other game.

## Format

One IPS32 file, named after the build ID, in `atmosphere/exefs_patches/<folder>/`. Atmosphère applies it when the game loads. It's IPS32 rather than IPS because the option text is past what 3-byte offsets can reach.

## Where the code lives

| Range | Use | Why it's safe |
|---|---|---|
| `0x6F6830-0x6F7B10` | Main code, then the Exp. Share row's text | Protobuf `Tokenizer::ConsumeString`, `ConsumeNumber`, the comment functions after them and `Tokenizer::Next` itself. Only the text-format parser calls them, and nothing in that parser's whole call tree is referenced from data or has its address taken, so normal play can't reach it. If it ever ran, the game would crash |
| `0xD32BB0-0xD33000` | Option text lookup and label names | Zero padding after the text section |
| `0x1526180-0x1527000` | Option text in every language | Zero padding after the read-only section |
| `0x1EE0F00` onward | Runtime state | Padding past the end of `.bss`, in the same mapped page |

Runtime bytes:

| Address | Meaning |
|---|---|
| `0x1EE0F00` | Item ID of the ball picked from the Bag; nonzero means this catch came from a ball |
| `0x1EE0F01` | The title demo is running |
| `0x1EE0F02` | Skip already pressed in this run of the demo |
| `0x1EE0F03` | The menu event being opened should go straight to its town map |
| `0x1EE0F04` | 1 when the option is Off |
| `0x1EE0F05` | The Options screen's working value for Level-Up Trade Evolution |
| `0x1EE0F06` | The Options screen's working value for Enable Wild Battle |
| `0x1EE0F07` | D-pad Up asked for the menu this frame, so open the town map instead |
| `0x1EE0F08` | Layout playing the logo animation |
| `0x1EE0F10` | The Options screen's working value for Exp. Share |
| `0x1EE0F11` | The player's Pokémon that have been on the field in this battle: bit n = battle ID n |
| `0x1EE0F12` | Catch screen: 1 + the next party slot to name in an EXP message, 0 = not naming anyone |
| `0x1EE0F18` | Catch screen: the word set its messages fill in, 8 bytes |

## Encounters

`0x305934` normally launches the catch app (`0x2F6470`). With the option On, it starts the same battle-then-catch event the game uses for scripted fights (`0x28BC40`, as at `0x289AEC`). Other edits adjust that event's flow.

## EXP, evolution and catching

- The battle's EXP gate at `0x9D8A30` is opened at `0x9D8A44` and `0x9D8A5C`.
- The time limit written at `0x28C894` becomes 0.
- Setup flag `0x80` marks a battle that leads to a catch, so the game keeps the opponent standing: no "fainted" line (`0x9FCF38`) and no animation (`0xA8A958`). Normal wild battles show both, because a win doesn't lead to a catch. Scripted fights keep the original. The animation's sequence (`ee620`) aims at the fainted Pokémon's trainer, which a wild Pokémon doesn't have, and the joint lookup at `0xA9C650` crashes on the missing model; `0xA8A9D8` therefore stores the game's "no target" value `0xFF` for an opponent in a flag `0x80` battle. That sequence is also a return to the Poké Ball, so while it plays for a wild Pokémon a marker makes its particles (`0xAE09D0`) and ball sound (`0xAE9D38`) do nothing; its lying-down motion, shrink and hide stay. `0xA8AC14` clears the marker when the sequence ends.
- After a win, the post-battle object goes to its evolution loop (`0x319EB4`). When that ends, `0x319DA4` only continues to catch setup if a ball was picked.
- The catch screen's EXP calls (`0x830074`, `0x830828`, `0x8315E4`) only run if a ball was picked.

## Catching from the Bag

The battle Bag's filter at `0xD2D7C4` lists Master, Ultra, Great, Poké and Premier Balls. The battle engine still has a working ball action (`0xA10E30`). In wild battles, `0xA0FB90` replaces it: no catch roll, the item ID is stored, and the result writers at `0x9D3860` and `0x9DA378` report a win so the normal route to catching runs. `0x7E5F00`, which gives the catch screen its starting ball, returns the stored ball.

## Early saves

On early saves, the partner's send-out needs a buddy model the trainer doesn't have. `0xA993E0` sets a byte on the trainer object (`+0x110`) in wild battles. The cause is a theory that the fix supports, not something proven.

That byte is the partner's kind: 1 is Pikachu and 2 is Eevee, the value each game's initialiser at `0xA7600` writes, and the build reads it from there. Byte 1 of the same record says whether the partner is female, which gives Pikachu its heart-tipped tail (`0xDE500` picks between the model's "male" and "female" tails). The patch doesn't touch it, so the game's own value is used.

## The option

- "Enable Wild Battle" is its own row, ID 12, in every language. The Hiragana/Kanji row is left alone.
- The choice is bit 31 of the saved settings word (`+0x54`): 0 = On, so existing saves start On. Accessors for this word only use bits 0-19.
- The setting is copied to `0x1EE0F04` at each encounter (`0x3057B8`), and each patched behaviour checks it.
- The game's own battle-then-catch event (`0x289B80`, its only route to `0x28BC40`, used for scripted fights such as Snorlax and the Legendaries) sets `0x1EE0F04` to 1 instead, whatever the option says, so those fights run the original mechanic. The patch's normal encounters call `0x28BC40` directly, so they don't pass through it. The value can stay set after the fight, which only means original behaviour, until the next encounter refreshes it. The Bag filter (`0xD2D7C4`) checks it too, so no balls are listed. `0x2FDF34` and `0x2FDF80` read the save directly, because they may run before that refresh.

## The new Options rows

Rows 12, 11 and 13 are added last in every language, in that order, so Japanese shows 14 rows and the others 13.

- `0x4276C` allocates room for three more rows, and `0x42804` adds them through `0x46980`. The builder's own array holds only 11 IDs.
- `0x44DD4` (text), `0x3F8D8` (toggle) and `0x452D4` (arrow reaction) stop at ID 10, so each is extended.
- `0x3EBC0` reads the description's label name from a table at `0x152A028` whose entry 11 is null, so these rows bring their own names.
- `0x3B37C` loads the choices to the working bytes, `0x3B404` applies them, and `0x3F494` counts them as a change.

## Option text

- `0x678710`, the text lookup, watches for this patch's six labels: each row's title and description. Anything else goes to the game as usual.
- It picks the language from the word at `0x1614B34`, the message folder the game is using (`0x1B31E0`): 0 Japanese kana, 1 Japanese kanji, 2 English, 3 French, 4 Italian, 5 German, 6 Spanish, 7 Korean, 8 Simplified Chinese, 9 Traditional Chinese. Anything else falls back to English.
- The strings come from `tools/option_text.py`. On and Off use Movie Skipping's own labels, already translated by the game. The Exp. Share row's strings sit after the main code, because the read-only padding ran out of room, and its titles are the game's own item name in each language.

## Level-Up Trade Evolution

This is row ID 11. The layout has 10 row slots (`item_button_00`-`09`) that the list recycles as it scrolls, so its length comes from the data. The choice is bit 30 of the saved settings word (`+0x54`): 0 = Off.

`0x722B90` decides whether a Pokémon can evolve for a given record, and its first check is the record's minimum level. Method 4 (level-up) then passes and method 5 (trade) fails. `0x722BF8` makes method 5 pass at Level 50 or above when the bit is set, so it follows the same route as a normal level-up evolution. Trading doesn't use this check, since method 5 always fails there.

## Exp. Share

This is row ID 13. The choice is bit 29 of the saved settings word (`+0x54`): 0 = On, so existing saves start On.

- `0x9DBD70` is the game's own test for sharing EXP with Pokémon that didn't fight. Its only callers are the EXP calculation (`0xA67C64`, `0xA67E20`), and when it answers no, the formula at `0x9D0D40` gives those Pokémon nothing. With the row Off, it answers no. This covers every battle that gives EXP, trainer battles included. A Pokémon counts as having fought if it was on the field while the defeated Pokémon was, as the game records at `0x9E3C60`.
- The catch screen works out its own EXP, and neither a ball from the Bag nor a scripted fight such as Snorlax runs the battle's calculation first. So `0x9E3C60` also keeps the player's side of that record in `0x1EE0F11`, cleared at `0x28BDB8`, and the catch screen's per-Pokémon calls (`0x830828`, `0x8315E4`) give 0 to anyone not in it. This assumes a battle ID is the party slot, and that the opponent's IDs are 6 or above; neither has been traced to where it's set.
- The catch screen's single line, "Your Pokémon got N Exp. Points!", would read as the whole party. So with the row Off after a fight, `0x83008C` shows the game's other line, `poke_get_result_01_01_mb` ("*name* got N Exp. Points!"), for the first fighter who can get EXP, and `0x830024`, where the message-wait state ends, shows it for the rest. Each amount comes from the same call the EXP step uses, so it matches what the Pokémon receives. If no fighter can get EXP, such as at Level 100, the game's normal flow runs.
- Catching with no battle keeps the game's own EXP for the whole party. `0x2F6470`, which launches those catches, clears `0x1EE0F11`, and an empty record means nobody is left out. Its route through `0x2F6440` doesn't clear it, because only the battle-then-catch event's own code calls that (`0x28E934` leads to one of the two calls). What those calls are for hasn't been traced.

## Sky Dash on D-pad Up

- `0x2F810C` is the overworld's test for the menu button. It's replaced so that raw D-pad Up (bit 13 of pad `+0x40`) counts as well, if the flag `FSYS_HIDEN_OPEN_SORAWOTOBU` is set, and `0x1EE0F07` records that Up was the reason. Every rule the game then applies to opening the menu still applies.
- `0x2F8D10` is where the menu opens. With `0x1EE0F07` set, it sets `0x1EE0F03` and takes the game's other route into its menu event (`0x2F8D64`, `0x27EF50` with mode 1), which flies by itself once a destination comes back.
- `0x27FFF8` is that event's state 2, which opens the menu. With `0x1EE0F03` set, it records the town map as the choice (`+0xA0 = 1`) and goes to state 4, which opens the map with its "can fly" byte set.
- `0x2802EC` is state 5, after the map closes. A destination flies as usual. Backing out would reopen the menu, so with `0x1EE0F03` set it stores `+0xA0 = 5`, the constructor's "nothing chosen", and leaves through the normal close at `0x2803B0`.
- The script command `ExecuteShowTownMapEvent_` (`0x19E2C0`) can't be used for this. It leaves the map's "can fly" byte (`+0x20`, read at `0x984D54`) at 0, so A does nothing, and its event ignores the map's result.
- The menu button's own press wins. On a single sideways Joy-Con, Up already sets that button's action bit (the map at `0x14C2B0`), so it still opens the menu. Two-handed setups map Up to no action (the table at `0xF49E04`).

## Intro skip

The running Pikachu is frames 0-500 of the title demo `sd9010_title`. The frame counter is `sequence+0x680`, advanced only at `0x1F1D20`. Timeline commands catch up through every frame they passed, so jumping to frame 500 still fires what was skipped.

The Pokémon logo is a layout animation on its own clock, so `anime_in` is also set to its last frame. The set-frame call clamps anything past the end.

The input is the pad's button field (`+0x40`) masked with `0xC0F`: the raw bits for A, B, X, Y, + and −. The field also holds the game's action bits, set by the maps at `0x14C2B0` and `0x14C550`, but those can't be used, because bit 57 also covers L, R, ZL, ZR and the stick clicks.

## Caught marker

The battle HUD (`battle_top_00`) has no "caught" icon, but it has the ball row trainer battles use for their party, and the opponent's copy (`L_ballPlate_01`) is hidden in wild battles (`0xAF8170`, when `0xAC0790` returns 1). The HUD's update ends with that row's own update (`0xAC2540` to `0xAF8530`). The patch runs after it, every frame:

- In a wild battle, it fetches the opponent (battle position 1) the way the HP box does (`0xABE6F0`, then the Pokémon data at `+0x60`), reads its species (`0x7247C0`), and asks the Pokédex whether that species is caught (`0x1D0150`, the check the catch screen uses for "New Pokémon").
- If it is, and an enemy HP box is shown (`L_pokePlate_03`, or `02`), it shows the row with only ball 0, set to the normal Poké Ball through the game's own setter (`0xAF83A0`), and hides the other balls and the row's background. Otherwise it hides the row.
- It places the row so ball 0 sits 4 pixels left of the box's background, vertically centred, from the live positions of the box, its background and both parent panes, so it follows the box as it slides in and out.

Panes are found by hash in the layout's table at `+0x220` (count at `+0x228`), with the hashes read from `layout_setting_battle_top_00.bin`. A pane's position is at `+0x30`, scale at `+0x48`, size at `+0x50` and flags at `+0x58` (bit 0 visible, bit 4 matrix out of date), as the layout animation code uses them (`0x4A5C58`, `0x4A5BD8`).

## Let's Go, Eevee!

Eevee 1.0.2 (build `5831EC64D6B696FD69E69505821B97B1`) has the same code as Pikachu, moved by small amounts that change from place to place (-0x30, -0x10, 0, +0x30 or +0x60). Its data, `.bss` and padding layout are the same, and the game files the patch depends on are identical. `tools/make_address_map.py` finds each address the build uses by matching the instructions around it, with branch targets and page offsets masked out, and checks that every match is unique and the same instruction. It writes `tools/address_map_eevee.py`, and `build_patch.py` translates through it with `A()` when it sees Eevee's build ID. The only difference in the patch itself is the partner's kind (see [Early saves](#early-saves)).
