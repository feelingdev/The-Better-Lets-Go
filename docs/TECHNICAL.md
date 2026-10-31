# How the patch works

These are notes on `tools/build_patch.py`, from static analysis of `main` in Let's Go, Pikachu! 1.0.2 (build `C208DB6A4EF4361F28B8402BE0F7CD9A`). Addresses are memory addresses: IPS offset minus 0x100. Names are descriptive guesses, because the game ships without symbols.

## Format

One IPS file, named after the build ID, in `atmosphere/exefs_patches/<folder>/`. Atmosphère applies it when the game loads.

## Where the code lives

| Range | Use | Why it's safe |
|---|---|---|
| `0x6F6830-0x6F70F0` | Main code | Protobuf `Tokenizer::ConsumeString` and `ConsumeNumber`, entered only from `Tokenizer::Next` during text-format parsing, which normal play doesn't appear to use. If it ever ran, the game would crash |
| `0xD32BB0-0xD33000` | Option code and text | Zero padding after the text section |
| `0x1EE0F00` onward | Runtime state | Padding past the end of `.bss`, in the same mapped page |

Runtime bytes:

| Address | Meaning |
|---|---|
| `0x1EE0F00` | Item ID of the ball picked from the Bag; nonzero means this catch came from a ball |
| `0x1EE0F01` | The title demo is running |
| `0x1EE0F02` | Skip already pressed in this run of the demo |
| `0x1EE0F04` | 1 when the option is Off |
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

- The Options row list at `0x426B4` adds row 3 (Hiragana/Kanji) only in Japanese. `0x426DC` adds it in every other language, and it's reused here.
- The choice is bit 31 of the saved settings word (`+0x54`): 0 = On, so existing saves start On. Accessors for this word only use bits 0-19.
- `0x3B2BC`, `0x3B3B8`, `0x3B3D4`, `0x3F4AC`, `0x3F4E4` and `0x3B450` are redirected so the row uses that bit and never changes the Kanji setting.
- `0x678710`, the text lookup, returns the row's text for its four labels.
- The setting is copied to `0x1EE0F04` at each encounter (`0x3057B8`) and scripted event (`0x289B80`), and each patched behaviour checks it.

## Intro skip

The running Pikachu is frames 0-500 of the title demo `sd9010_title`. The frame counter is `sequence+0x680`, advanced only at `0x1F1D20`. Timeline commands catch up through every frame they passed, so jumping to frame 500 still fires what was skipped.

The Pokémon logo is a layout animation on its own clock, so `anime_in` is also set to its last frame. The set-frame call clamps anything past the end.

The input is bit 61 of the pad's buttons, which the game maps from + and −.
