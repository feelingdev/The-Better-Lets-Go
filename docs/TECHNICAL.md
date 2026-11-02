# How the patch works

These are notes on `tools/build_patch.py`, from static analysis of `main` in Let's Go, Pikachu! 1.0.2 (build `C208DB6A4EF4361F28B8402BE0F7CD9A`). Addresses are memory addresses: IPS offset minus 0x100. Names are descriptive guesses, because the game ships without symbols.

## Format

One IPS32 file, named after the build ID, in `atmosphere/exefs_patches/<folder>/`. Atmosphère applies it when the game loads. It's IPS32 rather than IPS because the option text is past what 3-byte offsets can reach.

## Where the code lives

| Range | Use | Why it's safe |
|---|---|---|
| `0x6F6830-0x6F70F0` | Main code | Protobuf `Tokenizer::ConsumeString` and `ConsumeNumber`, entered only from `Tokenizer::Next` during text-format parsing, which normal play doesn't appear to use. If it ever ran, the game would crash |
| `0xD32BB0-0xD33000` | Option text lookup and label names | Zero padding after the text section |
| `0x1526180-0x1527000` | Option text in every language | Zero padding after the read-only section |
| `0x1EE0F00` onward | Runtime state | Padding past the end of `.bss`, in the same mapped page |

Runtime bytes:

| Address | Meaning |
|---|---|
| `0x1EE0F00` | Item ID of the ball picked from the Bag; nonzero means this catch came from a ball |
| `0x1EE0F01` | The title demo is running |
| `0x1EE0F02` | Skip already pressed in this run of the demo |
| `0x1EE0F04` | 1 when the option is Off |
| `0x1EE0F05` | The Options screen's working value for Level-Up Trade Evolution |
| `0x1EE0F06` | The Options screen's working value for Enable Wild Battle |
| `0x1EE0F08` | Layout playing the logo animation |

## Encounters

`0x305934` normally launches the catch app (`0x2F6470`). With the option On, it starts the same battle-then-catch event the game uses for scripted fights (`0x28BC40`, as at `0x289AEC`). Other edits adjust that event's flow.

## EXP, evolution and catching

- The battle's EXP gate at `0x9D8A30` is opened at `0x9D8A44` and `0x9D8A5C`.
- The time limit written at `0x28C894` becomes 0.
- After a win, the post-battle object goes to its evolution loop (`0x319EB4`). When that ends, `0x319DA4` only continues to catch setup if a ball was picked.
- The catch screen's EXP calls (`0x830074`, `0x830828`, `0x8315E4`) only run if a ball was picked.

## Catching from the Bag

The battle Bag's filter at `0xD2D7C4` lists Master, Ultra, Great, Poké and Premier Balls. The battle engine still has a working ball action (`0xA10E30`). In wild battles, `0xA0FB90` replaces it: no catch roll, the item ID is stored, and the result writers at `0x9D3860` and `0x9DA378` report a win so the normal route to catching runs. `0x7E5F00`, which gives the catch screen its starting ball, returns the stored ball.

## Early saves

On early saves, the partner's send-out needs a buddy model the trainer doesn't have. `0xA993E0` sets a byte on the trainer object (`+0x110`) in wild battles. The cause is a theory that the fix supports, not something proven.

## The option

- "Enable Wild Battle" is its own row, ID 12, in every language. The Hiragana/Kanji row is left alone.
- The choice is bit 31 of the saved settings word (`+0x54`): 0 = On, so existing saves start On. Accessors for this word only use bits 0-19.
- The setting is copied to `0x1EE0F04` at each encounter (`0x3057B8`), and each patched behaviour checks it.
- The game's own battle-then-catch event (`0x289B80`, its only route to `0x28BC40`, used for scripted fights such as Snorlax and the Legendaries) sets `0x1EE0F04` to 1 instead, whatever the option says, so those fights run the original mechanic. The patch's normal encounters call `0x28BC40` directly, so they don't pass through it. The value can stay set after the fight, which only means original behaviour, until the next encounter refreshes it. The Bag filter (`0xD2D7C4`) checks it too, so no balls are listed. `0x2FDF34` and `0x2FDF80` read the save directly, because they may run before that refresh.

## The new Options rows

Rows 11 and 12 are added last in every language, so Japanese shows 13 rows and the others 12.

- `0x4276C` allocates room for two more rows, and `0x42804` adds them through `0x46980`. The builder's own array holds only 11 IDs.
- `0x44DD4` (text), `0x3F8D8` (toggle) and `0x452D4` (arrow reaction) stop at ID 10, so each is extended.
- `0x3EBC0` reads the description's label name from a table at `0x152A028` whose entry 11 is null, so these rows bring their own names.
- `0x3B37C` loads both choices to the working bytes, `0x3B404` applies them, and `0x3F494` counts them as a change.

## Option text

- `0x678710`, the text lookup, watches for this patch's four labels: each row's title and description. Anything else goes to the game as usual.
- It picks the language from the word at `0x1614B34`, the message folder the game is using (`0x1B31E0`): 0 Japanese kana, 1 Japanese kanji, 2 English, 3 French, 4 Italian, 5 German, 6 Spanish, 7 Korean, 8 Simplified Chinese, 9 Traditional Chinese. Anything else falls back to English.
- The strings come from `tools/option_text.py`. On and Off use Movie Skipping's own labels, already translated by the game.

## Level-Up Trade Evolution

This is row ID 11. The layout has 10 row slots (`item_button_00`-`09`) that the list recycles as it scrolls, so its length comes from the data. The choice is bit 30 of the saved settings word (`+0x54`): 0 = Off.

`0x722B90` decides whether a Pokémon can evolve for a given record, and its first check is the record's minimum level. Method 4 (level-up) then passes and method 5 (trade) fails. `0x722BF8` makes method 5 pass at Level 50 or above when the bit is set, so it follows the same route as a normal level-up evolution. Trading doesn't use this check, since method 5 always fails there.

## Intro skip

The running Pikachu is frames 0-500 of the title demo `sd9010_title`. The frame counter is `sequence+0x680`, advanced only at `0x1F1D20`. Timeline commands catch up through every frame they passed, so jumping to frame 500 still fires what was skipped.

The Pokémon logo is a layout animation on its own clock, so `anime_in` is also set to its last frame. The set-frame call clamps anything past the end.

The input is the pad's button field (`+0x40`) masked with `0xC0F`: the raw bits for A, B, X, Y, + and −. The field also holds the game's action bits, set by the maps at `0x14C2B0` and `0x14C550`, but those can't be used, because bit 57 also covers L, R, ZL, ZR and the stick clicks.
