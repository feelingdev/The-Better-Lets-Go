"""Build The Better Let's Go for Let's Go, Pikachu! or Let's Go, Eevee! 1.0.2: one standalone IPS patch.
The game is told apart by the build ID in main. Every original instruction is checked first, so a different game build stops
the script.
Addresses in this file are Pikachu's. For Eevee, A() maps each one through address_map_eevee.py, made by make_address_map.py
from both games; the two builds have the same code, shifted by small amounts.
Args: decompressed_main (0x100-byte header attached) out_ips"""
import os
import re
import struct
import sys

from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs

import option_text

image_raw = open(sys.argv[1], "rb").read()
image = image_raw[0x100:]
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)

BUILD_IDS = {
    "C208DB6A4EF4361F28B8402BE0F7CD9A": "pikachu",
    "5831EC64D6B696FD69E69505821B97B1": "eevee",
}
BUILD_ID = image_raw[0x40:0x50].hex().upper()
assert BUILD_ID in BUILD_IDS, f"not Let's Go Pikachu or Eevee 1.0.2: build {BUILD_ID}"
GAME = BUILD_IDS[BUILD_ID]
print("game", GAME, "build", BUILD_ID)
TEXT_END = struct.unpack_from("<I", image_raw, 0x14)[0] + struct.unpack_from("<I", image_raw, 0x18)[0]
RO_DATA_END = struct.unpack_from("<I", image_raw, 0x24)[0] + struct.unpack_from("<I", image_raw, 0x28)[0]

RECORD = os.environ.get("TBLG_RECORD")    # make_address_map.py: list every address a Pikachu build uses
recorded = set()
if GAME == "eevee":
    from address_map_eevee import ADDRESSES


def A(addr):
    """A Pikachu address, in the game being built."""
    if RECORD:
        recorded.add(addr)
    return addr if GAME == "pikachu" else ADDRESSES[addr]


def original(addr):
    """The game's own instruction at a Pikachu address."""
    return struct.unpack_from("<I", image, A(addr))[0]


CAVE = A(0x6F6830)      # protobuf Tokenizer::ConsumeString and ConsumeNumber: only text-format parsing reaches them
LIMIT = A(0x6F7B10)     # also the tokenizer's comment functions and Tokenizer::Next itself up to here: only the text-format parser calls them, and nothing reaches it (no data reference, nor address taken, anywhere in its call tree)
FLAG = 0x1EE0F00      # page padding past the end of .bss (1EE06F8); nothing references past 1EE0678
WILD_OFF = FLAG + 4   # 1 when the "Enable Wild Battle" option is off; refreshed when an encounter or battle event starts
EXP_VALUE = FLAG + 0x10   # the Options screen's working value for Exp. Share: 1 = off
FOUGHT = FLAG + 0x11      # this battle's fighters: bit n = the player's Pokemon with battle ID n
NEXT_FIGHTER = FLAG + 0x12   # catch screen: 1 + the next party slot to name in an EXP message, 0 = not naming anyone
WILD_FAINT = FLAG + 0x13     # a wild Pokemon's faint sequence is playing: leave out its recall effects
WORD_SET = FLAG + 0x18    # catch screen: the word set its messages fill in, 8 bytes
FIELD_PTR = A(0x15FAD08)
SIZE_HEADER = 0x100

NOP = 0xD503201F
RET = 0xD65F03C0
MOV_W0_ZERO = 0x2A1F03E0


def b(src, dst):
    return 0x14000000 | (((dst - src) >> 2) & 0x3FFFFFF)


def bl(src, dst):
    return 0x94000000 | (((dst - src) >> 2) & 0x3FFFFFF)


def adrp(src, rd, target):
    delta = ((target & ~0xFFF) - (src & ~0xFFF)) >> 12
    return 0x90000000 | ((delta & 3) << 29) | (((delta >> 2) & 0x7FFFF) << 5) | rd


def cbz(src, dst, rt, wide=False, nz=False):
    op = (0xB4000000 if wide else 0x34000000) | (0x01000000 if nz else 0)
    return op | ((((dst - src) >> 2) & 0x7FFFF) << 5) | rt


def ldr(t, n, imm):
    return 0xF9400000 | ((imm // 8) << 10) | (n << 5) | t


def str_x(t, n, imm):
    return 0xF9000000 | ((imm // 8) << 10) | (n << 5) | t


def ldrb_flag(rt, rn):
    return 0x39400000 | ((FLAG & 0xFFF) << 10) | (rn << 5) | rt


def strb_flag(rt, rn):
    return 0x39000000 | ((FLAG & 0xFFF) << 10) | (rn << 5) | rt


def dec(data, addr):
    return [f"{i.mnemonic} {i.op_str}".strip() for i in md.disasm(data, addr)]


code = []
marks = {}


def pc():
    return CAVE + len(code) * 4


def mark(name):
    marks[name] = pc()


def emit(*words):
    code.extend(words)



def load_off():
    # w16 = 1 when the option is off. NZCV untouched.
    emit(adrp(pc(), 16, WILD_OFF))
    emit(0x39400210 | ((WILD_OFF & 0xFFF) << 10))    # ldrb w16, [x16, #off]


def read_setting(reg, skip_slots):
    # reg = saved settings object, or branch to a patched slot if it isn't there yet. Uses only reg.
    emit(adrp(pc(), reg, FIELD_PTR))
    emit(ldr(reg, reg, FIELD_PTR & 0xFFF))
    emit(ldr(reg, reg, 0))
    emit(ldr(reg, reg, 0x98))
    skip_slots.append(len(code))
    emit(0)
    emit(ldr(reg, reg, 0x58))
    emit(ldr(reg, reg, 0x98))
    skip_slots.append(len(code))
    emit(0)


def sync_off():
    # Refresh WILD_OFF from the save. Uses x9 and x16.
    skips = []
    read_setting(9, skips)
    emit(0xB9400000 | ((0x54 // 4) << 10) | (9 << 5) | 9)   # ldr w9, [x9, #0x54]
    emit(0x531F7D29)                                        # lsr w9, w9, #31
    emit(adrp(pc(), 16, WILD_OFF))
    emit(0x39000209 | ((WILD_OFF & 0xFFF) << 10))           # strb w9, [x16, #off]
    for slot in skips:
        code[slot] = cbz(CAVE + slot * 4, pc(), 9, wide=True)


def release(reg_slot):
    """Drop the reference held in the stack slot, if any. The game's own pattern."""
    emit(ldr(0, 31, reg_slot))
    at = pc()
    emit(cbz(at, at + 16, 0, wide=True))
    emit(0xF8448C08)              # ldr x8, [x0, #0x48]!
    emit(ldr(8, 8, 0x18))
    emit(0xD63F0100)              # blr x8


# --- Start a battle-then-catch event for this encounter, the way the game's own event at 289AEC does.
# x0 = encounter object, x1 = heap, x2 = encounter details, x8 = result slot.
mark("start_battle")
emit(0xA9BB7BFD)                  # stp x29, x30, [sp, #-0x50]!
emit(0xA90153F3)                  # stp x19, x20, [sp, #0x10]
emit(0x910003FD)                  # mov x29, sp
emit(0xAA0803F3)                  # mov x19, x8
emit(0xAA0003F4)                  # mov x20, x0
emit(0xD2800009)                  # mov x9, #0
loop = pc()
emit(0xF869684A)                  # ldr x10, [x2, x9]
emit(0x8B09028B)                  # add x11, x20, x9
emit(str_x(10, 11, 0x58))
emit(0x91002129)                  # add x9, x9, #8
emit(0xF101813F)                  # cmp x9, #0x60
at = pc()
emit(0x54000001 | (((loop - at) >> 2 & 0x7FFFF) << 5))  # b.ne loop
emit(0x52800029)                  # mov w9, #1
emit(0xB9029A89)                  # str w9, [x20, #0x298]
emit(str_x(31, 19, 0))            # no catch event for the caller to follow
emit(adrp(pc(), 9, FIELD_PTR))
emit(ldr(9, 9, FIELD_PTR & 0xFFF))
emit(ldr(9, 9, 0))
emit(ldr(9, 9, 0x68))
emit(str_x(9, 31, 0x20))
emit(0xB90033FF)                  # str wzr, [sp, #0x30]: kind 0
emit(str_x(20, 31, 0x38))
emit(str_x(31, 31, 0x28))
emit(0x910083E0)                  # add x0, sp, #0x20
emit(0x9100C3E2)                  # add x2, sp, #0x30
emit(0x9100A3E8)                  # add x8, sp, #0x28
emit(bl(pc(), A(0x28BC40)))
emit(0x9100A3E0)                  # add x0, sp, #0x28
emit(0x910103E8)                  # add x8, sp, #0x40
emit(bl(pc(), A(0x17EEE0)))
emit(ldr(0, 31, 0x40))
at = pc()
emit(cbz(at, at + 8, 0, wide=True))
emit(0x391CD01F)                  # strb wzr, [x0, #0x734]; the constructor's defaults cover the other flags
release(0x40)
release(0x28)
emit(0xA94153F3)                  # ldp x19, x20, [sp, #0x10]
emit(0xA8C57BFD)                  # ldp x29, x30, [sp], #0x50
emit(RET)

# --- Battle intro: wild-style transition when flag 0x735 is on.
mark("intro")
emit(0x52800142)                  # mov w2, #0xa
load_off()
intro_skip = pc() + 12
emit(cbz(pc(), intro_skip, 16, nz=True))
emit(0x395CD668)                  # ldrb w8, [x19, #0x735]
emit(0x4B080042)                  # sub w2, w2, w8
assert pc() == intro_skip
emit(b(pc(), A(0x28CB14)))

# --- After a loss: run the same return step a finished battle runs.
mark("after_loss")
load_off()
loss_skip = pc() + 20
emit(cbz(pc(), loss_skip, 16, nz=True))
emit(adrp(pc(), 1, FIELD_PTR))
emit(ldr(1, 1, FIELD_PTR & 0xFFF))
emit(ldr(1, 1, 0))
emit(bl(pc(), A(0x28D830)))
assert pc() == loss_skip
emit(cbz(pc(), pc() + 8, 20, wide=True, nz=True))
emit(b(pc(), A(0x28C1AC)))
emit(b(pc(), A(0x28BF20)))

# --- End of the post-battle evolution loop: catch only after a ball was picked.
mark("after_evolution")
emit(0x52800088)                  # mov w8, #4: finish
load_off()
evo_back = pc() + 32
emit(cbz(pc(), evo_back, 16, nz=True))
emit(0xB940BA69)                  # ldr w9, [x19, #0xb8]
emit(0x7100093F)                  # cmp w9, #2
emit(0x54000001 | (((evo_back - pc()) >> 2) << 5))  # b.ne back
emit(adrp(pc(), 16, FLAG))
emit(ldrb_flag(16, 16))
emit(cbz(pc(), evo_back, 16))
emit(0x52800068)                  # mov w8, #3: catch setup
assert pc() == evo_back
emit(b(pc(), A(0x319DA8)))

# --- Early saves: the trainer model must carry the partner in a wild battle. Byte 0 of the trainer's +0x110 record is the partner's
# kind, 0 on early saves. Use the value the game's own initialiser (0xA7600) gives it: 1 = Pikachu, 2 = Eevee.
PARTNER_INIT = struct.unpack_from("<I", image, A(0xA7600) + 0x30)[0]   # differs between the games, so it can't be mapped itself
PARTNER_KIND = {"pikachu": 1, "eevee": 2}[GAME]
assert dec(struct.pack("<I", PARTNER_INIT), 0)[0] == f"mov w9, #{PARTNER_KIND}", dec(struct.pack("<I", PARTNER_INIT), 0)
mark("early_save")
load_off()
early_end = pc() + 36
emit(cbz(pc(), early_end, 16, nz=True))
emit(ldr(0, 19, 0xE0))
emit(ldr(8, 0, 0))
emit(ldr(8, 8, 0x6F0))
emit(0xD63F0100)                  # blr x8: setup field 0, 0 = wild
at = pc()
emit(cbz(at, early_end, 0, nz=True))
emit(original(0xA993E0))
emit(0x52800008 | (PARTNER_KIND << 5))   # mov w8, #kind
emit(0x39044008)                  # strb w8, [x0, #0x110]
assert pc() == early_end
emit(original(0xA993E0))
emit(b(pc(), A(0xA993E4)))


# --- Catch EXP: normal when the option is off; otherwise only with the marker set.
def exp_stub(name, target):
    mark(name)
    emit(adrp(pc(), 16, WILD_OFF))
    emit(0x39400211 | ((WILD_OFF & 0xFFF) << 10))    # ldrb w17, [x16, #off]
    emit(ldrb_flag(16, 16))
    emit(0x2A110210)                                 # orr w16, w16, w17
    emit(cbz(pc(), pc() + 8, 16))
    emit(b(pc(), target))
    emit(MOV_W0_ZERO)
    emit(RET)


exp_stub("catch_exp_eligible", A(0x830410))
exp_stub("catch_exp_amount", A(0x82D3F0))

# --- Ball from the Bag in a wild battle: no roll, no EXP, marker on, catch screen follows. Other battles run the real handler.
mark("ball")
emit(ldr(8, 1, 0x60))
emit(ldr(8, 8, 0x80))
emit(0xB9400108)                  # ldr w8, [x8]: setup field 0, 0 = wild
real_at = pc()
emit(0)                           # cbnz w8, real handler
emit(0x3900009F)                  # strb wzr, [x4]: nothing to record as used
emit(0x52800088)                  # mov w8, #4
emit(0x790000A8)                  # strh w8, [x5]: no target, flag bytes clear
emit(0x390008BF)                  # strb wzr, [x5, #2]
emit(0x528000C8)                  # mov w8, #6
emit(0xB9008428)                  # str w8, [x1, #0x84]: same outcome the catch sets
emit(adrp(pc(), 8, FLAG))
emit(0x52800029)                  # mov w9, #1
emit(strb_flag(3, 8))              # the marker holds the picked ball's item ID
emit(0x5282A188)                  # mov w8, #0x150c
emit(0x38286829)                  # strb w9, [x1, x8]: target slot, as the catch sets it
emit(MOV_W0_ZERO)
emit(RET)
code[(real_at - CAVE) // 4] = cbz(real_at, pc(), 8, nz=True)
emit(b(pc(), A(0xA10E30)))

# --- Marker off at the start of each battle.
mark("battle_start")
emit(adrp(pc(), 8, FLAG))
emit(strb_flag(31, 8))
emit(0x39000000 | ((FOUGHT & 0xFFF) << 10) | (8 << 5) | 31)   # strb wzr, [x8, #FOUGHT]
emit(adrp(pc(), 21, A(0x15FA000)))
emit(b(pc(), A(0x28BDBC)))


# --- A ball-skip ends as a win, so the normal post-battle flow runs.
def result_stub(name, site, reg):
    mark(name)
    emit(adrp(pc(), 16, FLAG))
    emit(ldrb_flag(16, 16))
    store = pc() + 16
    emit(cbz(pc(), store - 4 + 4, 16))
    emit(0xB9400111)              # ldr w17, [x8]: setup field 0, 0 = wild
    emit(cbz(pc(), store, 17, nz=True))
    emit(0x52800020 | reg)        # mov wN, #1: win
    assert pc() == store
    emit(0xB9050900 | reg)        # str wN, [x8, #0x508]
    emit(b(pc(), A(site + 4)))


# --- Battle Bag: Master, Ultra, Great, Poke and Premier Balls list in the battle items tab, only with the option on.
mark("bag_filter")
emit(original(0xD2D7C4))  # the original byte load
load_off()                        # no balls in the game's own scripted fights
bag_special_slot = len(code)
emit(0)
bag_skips = []
read_setting(10, bag_skips)
emit(0xB9400000 | ((0x54 // 4) << 10) | (10 << 5) | 10)  # ldr w10, [x10, #0x54]
bag_off_slot = len(code)
emit(0)
for slot in bag_skips:
    code[slot] = cbz(CAVE + slot * 4, pc(), 10, wide=True)
emit(0x51000430)                  # sub w16, w1, #1
emit(0x71000E1F)                  # cmp w16, #3
at = pc()
emit(0x54000009 | (3 << 5))       # b.ls, to the ball case
emit(0x7100303F)                  # cmp w1, #12
emit(0x54000001 | (2 << 5))       # b.ne, to the branch back
assert pc() == at + 12
emit(0x52800048)                  # mov w8, #2
code[bag_off_slot] = 0x37000000 | (31 << 19) | (((pc() - (CAVE + bag_off_slot * 4)) >> 2) << 5) | 10  # tbnz w10, #31, back
code[bag_special_slot] = cbz(CAVE + bag_special_slot * 4, pc(), 16, nz=True)
emit(b(pc(), A(0xD2D7C8)))

result_stub("result_a", 0x9D3860, 20)
result_stub("result_b", 0x9DA378, 0)

# --- Catch screen's starting ball: the one picked from the Bag, for the first player. The game still checks it's owned.
mark("start_ball")
emit(adrp(pc(), 16, FLAG))
emit(ldrb_flag(16, 16))
orig_at = pc() + 16
emit(cbz(pc(), orig_at, 16))
emit(cbz(pc(), orig_at, 0, nz=True))
emit(0x2A1003E0)                  # mov w0, w16
emit(RET)
assert pc() == orig_at
emit(original(0x7E5F00))
emit(b(pc(), A(0x7E5F04)))

# --- Intro skip on + - A B X Y. Pad +0x40 keeps the raw button bits alongside the game's action bits (see the map at 0x14C550);
# the action bits can't be used, because bit 57 also covers L, R, ZL, ZR and the stick clicks. Falls through when not pressed.
SKIP_BUTTONS = 0x1 | 0x2 | 0x4 | 0x8 | 0x400 | 0x800   # A, B, X, Y, +, -
PAD_GOT = A(0x15FAEA0)
TITLE_FLAG = FLAG + 1     # set while the boot event's title demo runs
SKIP_TO = 500             # title demo: where the sparkle intro ends and the logo idle begins


def skip_pressed(done):
    """Branch to the label named `done` unless skip is pressed. Uses x9 and x10."""
    emit(adrp(pc(), 9, PAD_GOT))
    emit(ldr(9, 9, PAD_GOT & 0xFFF))
    emit(ldr(9, 9, 0))
    pending.append(len(code))
    emit(0)
    emit(ldr(9, 9, 0xB0))         # first pad (+0x70) buttons (+0x40)
    emit(0x5280000A | (SKIP_BUTTONS << 5))   # mov w10, #SKIP_BUTTONS
    emit(0x8A0A0129)              # and x9, x9, x10
    pending.append(len(code))
    emit(0)


pending = []


def resolve(target):
    for idx in pending:
        code[idx] = cbz(CAVE + idx * 4, target, 9, wide=True)
    pending.clear()


SKIPPED = FLAG + 2        # skip was pressed during this run of the title demo
LOGO_VIEW = FLAG + 8      # layout view playing anime_in
ANIME_IN = 0x08E89686F5660E8F


def mov64(rd, value):
    emit(0xD2800000 | ((value & 0xFFFF) << 5) | rd)
    for shift in (1, 2, 3):
        emit(0xF2800000 | (shift << 21) | (((value >> (16 * shift)) & 0xFFFF) << 5) | rd)


def flag_ldrb(rt, rn, addr):
    return 0x39400000 | ((addr & 0xFFF) << 10) | (rn << 5) | rt


def flag_strb(rt, rn, addr):
    return 0x39000000 | ((addr & 0xFFF) << 10) | (rn << 5) | rt


# x0 = layout: put anime_in on its last frame. The set-frame call clamps anything past the end.
mark("logo_finish")
mov64(9, ANIME_IN)
# x0 = layout, x9 = animation hash.
mark("anim_finish")
emit(0xA9BE7BFD)                                     # stp x29, x30, [sp, #-0x20]!
emit(0x910003FD)                                     # mov x29, sp
emit(str_x(9, 31, 0x10))
emit(0x910043E1)                                     # add x1, sp, #0x10
emit(0x528D6509)                                     # mov w9, #0x6b28
emit(0x72A9CDC9)                                     # movk w9, #0x4e6e, lsl #16
emit(0x1E270120)                                     # fmov s0, w9: 1e9
emit(bl(pc(), A(0x36C0C0)))
emit(0xA8C27BFD)                                     # ldp x29, x30, [sp], #0x20
emit(RET)

# Sequence command that plays a layout animation: remember the title's anime_in view; finish it if skip came first.
mark("layout_play")
emit(adrp(pc(), 16, TITLE_FLAG))
emit(flag_ldrb(17, 16, TITLE_FLAG))
to_tail_a = len(code)
emit(0)
emit(ldr(9, 1, 0))
mov64(10, ANIME_IN)
emit(0xEB0A013F)                                     # cmp x9, x10
to_tail_b = len(code)
emit(0)
emit(str_x(0, 16, LOGO_VIEW & 0xFFF))
emit(flag_ldrb(17, 16, SKIPPED))
to_tail_c = len(code)
emit(0)
emit(0xA9BE7BFD)                                     # stp x29, x30, [sp, #-0x20]!
emit(0x910003FD)                                     # mov x29, sp
emit(str_x(0, 31, 0x10))
emit(bl(pc(), A(0x36BE40)))
emit(ldr(0, 31, 0x10))
emit(bl(pc(), marks["logo_finish"]))
emit(0xA8C27BFD)                                     # ldp x29, x30, [sp], #0x20
emit(RET)
tail = pc()
code[to_tail_a] = cbz(CAVE + to_tail_a * 4, tail, 17)
code[to_tail_b] = 0x54000001 | (((tail - (CAVE + to_tail_b * 4)) >> 2) << 5)  # b.ne tail
code[to_tail_c] = cbz(CAVE + to_tail_c * 4, tail, 17)
emit(b(pc(), A(0x36BE40)))

# Title demo tick: move the frame counter on (commands catch up and fire what they passed), and finish the logo.
mark("title_skip")
emit(adrp(pc(), 16, TITLE_FLAG))
emit(flag_ldrb(17, 16, TITLE_FLAG))
tail_slot = len(code)
emit(0)
emit(flag_ldrb(17, 16, SKIPPED))
done_slot = len(code)
emit(0)
skip_pressed("tail")
emit(0xB9400000 | ((0x680 // 4) << 10) | 9)          # ldr w9, [x0, #0x680]
emit(0x7100013F | (SKIP_TO << 10))                   # cmp w9, #500
ge_slot = len(code)
emit(0)
emit(0x52800009 | (SKIP_TO << 5))                    # mov w9, #500
emit(0xB9000000 | ((0x680 // 4) << 10) | 9)          # str w9, [x0, #0x680]
past_frame = pc()
code[ge_slot] = 0x5400000A | (((past_frame - (CAVE + ge_slot * 4)) >> 2) << 5)  # b.ge
emit(0x52800029)                                     # mov w9, #1
emit(flag_strb(9, 16, SKIPPED))
emit(ldr(9, 16, LOGO_VIEW & 0xFFF))
view_slot = len(code)
emit(0)
emit(0xA9BE7BFD)                                     # stp x29, x30, [sp, #-0x20]!
emit(0x910003FD)                                     # mov x29, sp
emit(str_x(0, 31, 0x10))
emit(0xAA0903E0)                                     # mov x0, x9
emit(bl(pc(), marks["logo_finish"]))
emit(ldr(0, 31, 0x10))
emit(0xA8C27BFD)                                     # ldp x29, x30, [sp], #0x20
tail = pc()
resolve(tail)
code[tail_slot] = cbz(CAVE + tail_slot * 4, tail, 17)
code[done_slot] = cbz(CAVE + done_slot * 4, tail, 17, nz=True)
code[view_slot] = cbz(CAVE + view_slot * 4, tail, 9, wide=True)
emit(b(pc(), A(0x1F1D20)))

# Boot event: marker on and skip state cleared when it starts the title demo; off when that demo returns.
mark("title_on")
emit(adrp(pc(), 16, TITLE_FLAG))
emit(0x52800031)                                     # mov w17, #1
emit(flag_strb(17, 16, TITLE_FLAG))
emit(flag_strb(31, 16, SKIPPED))
emit(str_x(31, 16, LOGO_VIEW & 0xFFF))
emit(original(0xF144))
emit(b(pc(), A(0xF148)))
mark("title_off")
emit(adrp(pc(), 16, TITLE_FLAG))
emit(flag_strb(31, 16, TITLE_FLAG))
emit(str_x(31, 16, LOGO_VIEW & 0xFFF))
emit(original(0xE580))
emit(b(pc(), A(0xE584)))

# --- Option gates for sites that had no cave of their own.
mark("heap_pick")                 # encounter object's heap; also the moment we refresh the option
sync_off()
load_off()
emit(cbz(pc(), pc() + 12, 16))
emit(ldr(20, 8, 0x248))
emit(b(pc(), A(0x3057BC)))
emit(ldr(20, 8, 0x68))
emit(b(pc(), A(0x3057BC)))

mark("event_sync")                # the game's own battle-then-catch event (Snorlax, Legendaries and other scripted fights): always the original mechanic. The next encounter refreshes this.
emit(adrp(pc(), 16, WILD_OFF))
emit(0x52800029)                  # mov w9, #1
emit(0x39000209 | ((WILD_OFF & 0xFFF) << 10))       # strb w9, [x16, #off]
emit(b(pc(), A(0x28BC40)))

mark("encounter_start")
load_off()
emit(cbz(pc(), pc() + 8, 16))
emit(b(pc(), A(0x2F6470)))
emit(b(pc(), marks["start_battle"]))

mark("post_catch")                # the original follow-up only belongs to the normal catch flow. Reads the save: this may run before an encounter refreshes WILD_OFF.
post_catch_skips = []
read_setting(9, post_catch_skips)
emit(0xB9405529)                  # ldr w9, [x9, #0x54]
emit(0x37F80049)                  # tbnz w9, #31, over the next instruction
emit(RET)
for slot in post_catch_skips:
    code[slot] = cbz(CAVE + slot * 4, pc(), 9, wide=True)
emit(b(pc(), A(0x305970)))

mark("tier")
load_off()
emit(0x52000218)                  # eor w24, w16, #1
emit(b(pc(), A(0x319FF8)))

mark("state8")
load_off()
emit(cbz(pc(), pc() + 12, 16))
emit(0xB9006A68)                  # str w8, [x19, #0x68]
emit(b(pc(), A(0x28BE90)))
emit(b(pc(), A(0x28BE94)))

mark("fade")
emit(0x52800143)                  # mov w3, #0xa
load_off()
emit(cbz(pc(), pc() + 8, 16))
emit(0x52800043)                  # mov w3, #2
emit(b(pc(), A(0x28C1A4)))

mark("timer")
emit(0x52802588)                  # mov w8, #0x12c
load_off()
emit(cbz(pc(), pc() + 8, 16, nz=True))
emit(0x52800008)                  # mov w8, #0
emit(b(pc(), A(0x28C898)))

mark("exp_a")
load_off()
emit(cbz(pc(), pc() + 8, 16, nz=True))
emit(b(pc(), A(0x9D8A58)))
emit(cbz(pc(), pc() + 8, 9))
emit(b(pc(), A(0x9D8A48)))
emit(b(pc(), A(0x9D8A58)))

mark("exp_b")
load_off()
emit(cbz(pc(), pc() + 8, 16))
emit(0x37380000 | (2 << 5) | 8)   # tbnz w8, #7, to the next branch
emit(b(pc(), A(0x9D8A60)))
emit(b(pc(), A(0x9D8A6C)))

mark("evo_start")
load_off()
emit(cbz(pc(), pc() + 16, 16, nz=True))
emit(0x52800088)                  # mov w8, #4
emit(0x1A9F1508)                  # csinc w8, w8, wzr, ne
emit(b(pc(), A(0x319EBC)))
emit(original(0x319EB4))  # the original two instructions
emit(original(0x319EB8))
emit(b(pc(), A(0x319EBC)))

# --- Options rows 12 "Enable Wild Battle", 11 "Level-Up Trade Evolution" and 13 "Exp. Share", last in the list in every
# language. Saved as bits of the settings word (+0x54): bit 31 = wild battles off (0 = on), bit 30 = trade evolution on
# (0 = off), bit 29 = Exp. Share off (0 = on), so existing saves start with wild battles on, trade evolution off and
# Exp. Share on. The bytes below are the screen's working values.
TRADE_EVO = FLAG + 5
WILD_VALUE = FLAG + 6
EXP_INFO_AT = 0xD32FA0    # the rows' description label names, at the end of the padding used by the text table below
WILD_INFO_AT = 0xD32FC0
TRADE_INFO_AT = 0xD32FE0
WILD_INFO_NAME = "tbl_wild_battle_info"
TRADE_INFO_NAME = "tbl_trade_evo_info"
EXP_INFO_NAME = "tbl_exp_share_info"
ROW_TRADE = 11
ROW_WILD = 12
ROW_EXP = 13


def label_hash(name):
    """The game's label hash: FNV-1a with its own start value."""
    h = 0xCBF29CE484222645
    for c in name.encode():
        h = ((h ^ c) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


assert label_hash("msg_option_02_info") == 0x72DC9B7C22B155DE
WILD_TITLE = label_hash("tbl_wild_battle_title")
WILD_INFO = label_hash(WILD_INFO_NAME)
TRADE_TITLE = label_hash("tbl_trade_evo_title")
TRADE_INFO = label_hash(TRADE_INFO_NAME)
EXP_TITLE = label_hash("tbl_exp_share_title")
EXP_INFO = label_hash(EXP_INFO_NAME)
# Movie Skipping's value text: translated, and neutral enough for these rows in every language.
LABEL_ON = label_hash("msg_option_10_01")
LABEL_OFF = label_hash("msg_option_10_02")


def mov_x1(value):
    for shift, op in ((0, 0xD2800001), (16, 0xF2A00001), (32, 0xF2C00001), (48, 0xF2E00001)):
        emit(op | (((value >> shift) & 0xFFFF) << 5))


def b_cond(src, dst, cond):
    assert -0x100000 <= dst - src < 0x100000, (hex(src), hex(dst))
    return 0x54000000 | (((dst - src) >> 2 & 0x7FFFF) << 5) | cond


EQ = 0


def row_id_check(compares, original_word, resume):
    """Compare against each of our rows; anything else runs the original instruction and goes back. Returns the b.eq slots."""
    slots = []
    for compare in compares:
        emit(compare)
        slots.append(len(code))
        emit(0)                   # b.eq, patched by the caller
    emit(original_word)
    emit(b(pc(), resume))
    return slots


def patch_eq(slot):
    code[slot] = b_cond(CAVE + slot * 4, pc(), EQ)


# List allocation: room for three more rows, so adding ours doesn't need the vector to grow. The caller's count is put back.
mark("row_alloc")
emit(0xA9BE7BFD)                  # stp x29, x30, [sp, #-0x20]!
emit(0x910003FD)                  # mov x29, sp
emit(str_x(2, 31, 0x10))
emit(0xB9400049)                  # ldr w9, [x2]
emit(0x11000D29)                  # add w9, w9, #3
emit(0xB9000049)                  # str w9, [x2]
emit(bl(pc(), A(0x45F00)))
emit(ldr(2, 31, 0x10))
emit(0xB9400049)                  # ldr w9, [x2]
emit(0x51000D29)                  # sub w9, w9, #3
emit(0xB9000049)                  # str w9, [x2]
emit(0xA8C27BFD)                  # ldp x29, x30, [sp], #0x20
emit(RET)

# End of the row builder: add our three rows last, the way its own loop adds the others.
mark("row_add")
for row in (ROW_WILD, ROW_TRADE, ROW_EXP):
    emit(ldr(8, 19, 0x278))
    emit(0x91028100)              # add x0, x8, #0xa0
    emit(0xD100A3A1)              # sub x1, x29, #0x28
    emit(0x52800009 | (row << 5)) # mov w9, #row
    emit(original(0x427E8))       # stur w9, [x29, #-0x28]
    emit(original(0x427EC))       # sturb wzr, [x29, #-0x24]
    emit(bl(pc(), A(0x46980)))
emit(original(0x42804))
emit(b(pc(), A(0x42808)))


def row_text_body(title, value_addr, value_when_on):
    mov_x1(title)
    emit(0xAA1303E0)              # mov x0, x19
    emit(0xAA1503E2)              # mov x2, x21
    emit(bl(pc(), A(0x44130)))
    emit(adrp(pc(), 8, value_addr))
    emit(flag_ldrb(8, 8, value_addr))
    emit(cbz(pc(), pc() + 24, 8, nz=True))
    mov_x1(LABEL_OFF if value_when_on else LABEL_ON)
    emit(b(pc(), pc() + 20))
    mov_x1(LABEL_ON if value_when_on else LABEL_OFF)
    emit(b(pc(), A(0x45164)))


# Row text: title and current value.
mark("row_text")
wild_slot, trade_slot, exp_slot = row_id_check((0x7100331F, 0x71002F1F, 0x7100371F), original(0x44DD4), A(0x44DD8))   # cmp w24, #12 / #11 / #13
patch_eq(wild_slot)
row_text_body(WILD_TITLE, WILD_VALUE, 0)
patch_eq(trade_slot)
row_text_body(TRADE_TITLE, TRADE_EVO, 1)
patch_eq(exp_slot)
row_text_body(EXP_TITLE, EXP_VALUE, 0)


def row_toggle_body(value_addr):
    emit(adrp(pc(), 8, value_addr))
    emit(flag_ldrb(9, 8, value_addr))
    emit(0x52000129)              # eor w9, w9, #1
    emit(flag_strb(9, 8, value_addr))
    emit(b(pc(), A(0x3FAB4)))


# Left or right on a row: flip it.
mark("row_toggle")
wild_slot, trade_slot, exp_slot = row_id_check((0x7100291F, 0x7100251F, 0x71002D1F), original(0x3F8D8), A(0x3F8DC))   # cmp w8, #10 / #9 / #11 (row - 2)
patch_eq(wild_slot)
row_toggle_body(WILD_VALUE)
patch_eq(trade_slot)
row_toggle_body(TRADE_EVO)
patch_eq(exp_slot)
row_toggle_body(EXP_VALUE)


def row_arrow_body(value_addr):
    emit(adrp(pc(), 8, value_addr))
    emit(flag_ldrb(8, 8, value_addr))
    emit(0x52800029)              # mov w9, #1
    emit(0x37F80042)              # tbnz w2, #31, over the next branch
    emit(b(pc(), A(0x45388)))
    emit(b(pc(), A(0x4536C)))


# The arrow reaction after a change, as the other On/Off rows do it.
mark("row_arrow")
wild_slot, trade_slot, exp_slot = row_id_check((0x7100291F, 0x7100251F, 0x71002D1F), original(0x452D4), A(0x452D8))   # cmp w8, #10 / #9 / #11 (row - 2)
patch_eq(wild_slot)
row_arrow_body(WILD_VALUE)
patch_eq(trade_slot)
row_arrow_body(TRADE_EVO)
patch_eq(exp_slot)
row_arrow_body(EXP_VALUE)


def row_info_body(name_addr):
    emit(adrp(pc(), 10, name_addr))
    emit(0x91000000 | ((name_addr & 0xFFF) << 10) | (10 << 5) | 10)   # add x10, x10, #lo
    emit(b(pc(), A(0x3EBC4)))


# Description: the game's label name table stops at row 10 (entry 11 is null), so our rows bring their own names.
mark("row_info")
wild_slot, trade_slot, exp_slot = row_id_check((0x7100329F, 0x71002E9F, 0x7100369F), original(0x3EBC0), A(0x3EBC4))   # cmp w20, #12 / #11 / #13
patch_eq(wild_slot)
row_info_body(WILD_INFO_AT)
patch_eq(trade_slot)
row_info_body(TRADE_INFO_AT)
patch_eq(exp_slot)
row_info_body(EXP_INFO_AT)

# Screen opens: working values from the save.
mark("row_load")
emit(ldr(9, 8, 8))
emit(0xB9405529)                  # ldr w9, [x9, #0x54]
emit(adrp(pc(), 10, TRADE_EVO))
emit(0x531E792B)                  # ubfx w11, w9, #30, #1
emit(flag_strb(11, 10, TRADE_EVO))
emit(0x531D752B)                  # ubfx w11, w9, #29, #1
emit(flag_strb(11, 10, EXP_VALUE))
emit(0x531F7D29)                  # lsr w9, w9, #31
emit(flag_strb(9, 10, WILD_VALUE))
emit(original(0x3B37C))
emit(b(pc(), A(0x3B380)))

# Settings applied: working values to the save.
mark("row_apply")
emit(original(0x3B404))           # ldr x0, [x8, #8]
emit(0xB9405409)                  # ldr w9, [x0, #0x54]
emit(adrp(pc(), 10, TRADE_EVO))
emit(flag_ldrb(11, 10, TRADE_EVO))
emit(0x33020169)                  # bfi w9, w11, #30, #1
emit(flag_ldrb(11, 10, WILD_VALUE))
emit(0x33010169)                  # bfi w9, w11, #31, #1
emit(flag_ldrb(11, 10, EXP_VALUE))
emit(0x33030169)                  # bfi w9, w11, #29, #1
emit(0xB9005409)                  # str w9, [x0, #0x54]
emit(b(pc(), A(0x3B408)))

# Changed check: our values count too, or changing only these rows wouldn't be saved.
mark("row_changed")
emit(original(0x3F494))           # ldr x0, [x19, #8]
emit(0xB9405409)                  # ldr w9, [x0, #0x54]
emit(adrp(pc(), 10, TRADE_EVO))
emit(0x531E792B)                  # ubfx w11, w9, #30, #1
emit(flag_ldrb(12, 10, TRADE_EVO))
emit(0x6B0C017F)                  # cmp w11, w12
emit(b_cond(pc(), pc() + 8, EQ))
emit(b(pc(), A(0x3F4D0)))            # changed
emit(0x531D752B)                  # ubfx w11, w9, #29, #1
emit(flag_ldrb(12, 10, EXP_VALUE))
emit(0x6B0C017F)                  # cmp w11, w12
emit(b_cond(pc(), pc() + 8, EQ))
emit(b(pc(), A(0x3F4D0)))            # changed
emit(0x531F7D29)                  # lsr w9, w9, #31
emit(flag_ldrb(12, 10, WILD_VALUE))
emit(0x6B0C013F)                  # cmp w9, w12
emit(b_cond(pc(), pc() + 8, EQ))
emit(b(pc(), A(0x3F4D0)))            # changed
emit(b(pc(), A(0x3F498)))

# --- Level-up evolution check, x19 = Pokemon, x20 = evolution record. With the row on, a trade evolution (method 5)
# passes at TRADE_EVO_LEVEL, the way a level-up evolution (method 4) passes at its own level. Trading is untouched.
TRADE_EVO_LEVEL = 50
mark("trade_evolution")
emit(original(0x722BF8))  # ldr w8, [x20]
emit(0x7100151F)                  # cmp w8, #5
evo_slot = len(code)
emit(0)                           # b.eq check
emit(b(pc(), A(0x722BFC)))
patch_eq(evo_slot)
trade_skips = []
read_setting(9, trade_skips)
emit(0xB9405529)                  # ldr w9, [x9, #0x54]
trade_off = len(code)
emit(0)                           # tbz w9, #30, off
emit(0xAA1303E0)                  # mov x0, x19
emit(bl(pc(), A(0x726580)))
emit(0x7100001F | (TRADE_EVO_LEVEL << 10))   # cmp w0, #50
emit(0x1A9F37F5)                  # cset w21, hs
emit(b(pc(), A(0x722F50)))
code[trade_off] = 0x36F00009 | (((pc() - (CAVE + trade_off * 4)) >> 2) << 5)
for slot in trade_skips:
    code[slot] = cbz(CAVE + slot * 4, pc(), 9, wide=True)
emit(b(pc(), A(0x722BFC)))

# --- D-pad Up: the town map, where Sky Dash is chosen, once Sky Dash is unlocked. Up is treated as a press of the menu
# button, so every rule for when the menu can open applies. Where the menu would open, the map opens instead.
# On a single sideways Joy-Con, Up already is the menu button (see the map at 0x14C2B0), so the menu wins there.
SKY_DASH_UP = FLAG + 7    # Up was what asked for the menu
SKY_DASH_MAP = FLAG + 3   # the event being opened should go straight to its town map
SKY_DASH_FLAG = label_hash("FSYS_HIDEN_OPEN_SORAWOTOBU")
assert SKY_DASH_FLAG == 0x15C149D11F0E8188
UP_BIT = 13               # raw D-pad Up, pad +0x40

# x0 = pad, x1 = the menu button's mask. Returns whether the menu was asked for.
mark("menu_button")
emit(0xA9BE7BFD)                  # stp x29, x30, [sp, #-0x20]!
emit(0x910003FD)                  # mov x29, sp
emit(ldr(9, 0, 0x40))
emit(adrp(pc(), 10, SKY_DASH_UP))
emit(flag_strb(31, 10, SKY_DASH_UP))
emit(0xEA01013F)                  # tst x9, x1
menu_pressed_slot = len(code)
emit(0)                           # b.ne yes
up_slot = len(code)
emit(0)                           # tbz x9, #13, no
emit(adrp(pc(), 0, FIELD_PTR))
emit(ldr(0, 0, FIELD_PTR & 0xFFF))
emit(ldr(0, 0, 0))
emit(ldr(0, 0, 0x98))
no_slot_a = len(code)
emit(0)                           # cbz x0, no
emit(ldr(0, 0, 0x58))
emit(ldr(0, 0, 0x80))
no_slot_b = len(code)
emit(0)                           # cbz x0, no
mov_x1(SKY_DASH_FLAG)
emit(bl(pc(), A(0x1C3F10)))
no_slot_c = len(code)
emit(0)                           # tbz w0, #0, no
emit(adrp(pc(), 10, SKY_DASH_UP))
emit(0x52800029)                  # mov w9, #1
emit(flag_strb(9, 10, SKY_DASH_UP))
code[menu_pressed_slot] = b_cond(CAVE + menu_pressed_slot * 4, pc(), 1)
emit(0x52800020)                  # mov w0, #1
emit(b(pc(), pc() + 8))
no_at = pc()
emit(MOV_W0_ZERO)
emit(0xA8C27BFD)                  # ldp x29, x30, [sp], #0x20
emit(RET)
code[up_slot] = 0x36000000 | (UP_BIT << 19) | (((no_at - (CAVE + up_slot * 4)) >> 2) << 5) | 9
code[no_slot_a] = cbz(CAVE + no_slot_a * 4, no_at, 0, wide=True)
code[no_slot_b] = cbz(CAVE + no_slot_b * 4, no_at, 0, wide=True)
code[no_slot_c] = 0x36000000 | (((no_at - (CAVE + no_slot_c * 4)) >> 2) << 5)

# Where the menu opens: if Up asked, the game's other route into its menu event, which flies by itself (mode 1). The script
# command's town map event can't be used: it leaves the map's "can fly" byte (+0x20, read at 0x984D54) at 0 and ignores the result.
mark("menu_open")
emit(adrp(pc(), 9, SKY_DASH_UP))
emit(flag_ldrb(10, 9, SKY_DASH_UP))
open_menu_slot = len(code)
emit(0)                           # cbz w10, menu
emit(flag_strb(31, 9, SKY_DASH_UP))
emit(flag_strb(10, 9, SKY_DASH_MAP))
emit(b(pc(), A(0x2F8D64)))
code[open_menu_slot] = cbz(CAVE + open_menu_slot * 4, pc(), 10)
emit(original(0x2F8D10))
emit(b(pc(), A(0x2F8D14)))

# --- Exp. Share off. 0x9DBD70 is the game's own test for sharing EXP with Pokemon that didn't fight: its only callers are the
# EXP calculation (0xA67C64, 0xA67E20), and when it answers no, the formula at 0x9D0D40 gives those Pokemon nothing.
mark("exp_share")
exp_skips = []
read_setting(9, exp_skips)
emit(0xB9405529)                  # ldr w9, [x9, #0x54]
exp_off_slot = len(code)
emit(0)                           # tbnz w9, #29, off
for slot in exp_skips:
    code[slot] = cbz(CAVE + slot * 4, pc(), 9, wide=True)
emit(original(0x9DBD70))
emit(b(pc(), A(0x9DBD74)))
code[exp_off_slot] = 0x37E80000 | (((pc() - (CAVE + exp_off_slot * 4)) >> 2) << 5) | 9
emit(MOV_W0_ZERO)
emit(RET)

# 0x9E3C60 records who a Pokemon has faced, as each one enters the field, in both directions. A ball ends the battle before any
# EXP is worked out, so keep the player's side (IDs 0-5) for the catch screen below. x0 and w1 are the function's arguments.
mark("fought")
emit(0x12001C29)                  # and w9, w1, #0xff
emit(0x7100193F)                  # cmp w9, #6
fought_slot = len(code)
emit(0)                           # b.hs original
emit(0x5280002A)                  # mov w10, #1
emit(0x1AC9214A)                  # lsl w10, w10, w9
emit(adrp(pc(), 9, FOUGHT))
emit(flag_ldrb(11, 9, FOUGHT))
emit(0x2A0A016B)                  # orr w11, w11, w10
emit(flag_strb(11, 9, FOUGHT))
code[fought_slot] = b_cond(CAVE + fought_slot * 4, pc(), 2)
emit(original(0x9E3C60))
emit(b(pc(), A(0x9E3C64)))

# 0x2F6470 launches a catch with no battle, so nobody fought in it: forget the last battle. Its route through 0x2F6440 is left
# out, because that is only called from the battle-then-catch event, whose fight may still count.
mark("catch_launch")
emit(adrp(pc(), 9, FOUGHT))
emit(flag_strb(31, 9, FOUGHT))
mark("catch_launch_keep")
emit(original(0x2F6470))
emit(b(pc(), A(0x2F6474)))

# Catch screen, each party member's EXP. After a fight, whether it ended with a ball from the Bag or was a scripted fight such as
# Snorlax, Exp. Share off leaves out Pokemon that didn't fight. With no fight on record, the whole party gets it as in the game.
# The loop's index is x21 at 0x830828 and w22 at 0x8315E4.
mark("catch_amount_a")
emit(0x2A1503E9)                  # mov w9, w21
emit(b(pc(), pc() + 8))
mark("catch_amount_b")
emit(0x2A1603E9)                  # mov w9, w22
emit(adrp(pc(), 10, FOUGHT))
emit(flag_ldrb(11, 10, FOUGHT))
go_slots = [len(code)]
emit(0)                           # cbz w11, go: nobody on record
emit(0x1AC9256B)                  # lsr w11, w11, w9
fought_go_slot = len(code)
emit(0)                           # tbnz w11, #0, go
catch_skips = []
read_setting(11, catch_skips)
emit(0xB940556B)                  # ldr w11, [x11, #0x54]
on_go_slot = len(code)
emit(0)                           # tbz w11, #29, go
emit(MOV_W0_ZERO)
emit(RET)
for slot in go_slots:
    code[slot] = cbz(CAVE + slot * 4, pc(), 11)
code[fought_go_slot] = 0x37000000 | (((pc() - (CAVE + fought_go_slot * 4)) >> 2) << 5) | 11
for slot in catch_skips:
    code[slot] = cbz(CAVE + slot * 4, pc(), 11, wide=True)
code[on_go_slot] = 0x36E80000 | (((pc() - (CAVE + on_go_slot * 4)) >> 2) << 5) | 11
emit(b(pc(), marks["catch_exp_amount"]))


# --- A wild Pokemon's faint. Setup flag 0x80 marks a battle that leads to a catch, so the game keeps the opponent standing: no
# "fainted" line (0x9FCF38), no animation (0xA8A958). Our wins don't lead to one, so show both. Scripted fights still catch after
# a win and set WILD_OFF, so they keep the original. w0 holds the flag test's answer at both sites.
def faint_stub(name, shown, hidden):
    mark(name)
    load_off()
    normal_slot = len(code)
    emit(0)                       # cbz w16, shown
    emit(0x37000040)              # tbnz w0, #0, hidden (the next branch but one)
    code[normal_slot] = cbz(CAVE + normal_slot * 4, pc(), 16)
    emit(b(pc(), shown))
    emit(b(pc(), hidden))


faint_stub("faint_text", A(0x9FCF4C), A(0x9FCF3C))
faint_stub("faint_anim", A(0xA8A984), A(0xA8A95C))

mark("faint_done")                # the faint sequence has finished: see faint_target below
emit(adrp(pc(), 9, WILD_FAINT))
emit(flag_strb(31, 9, WILD_FAINT))
emit(original(0xA8AC14))
emit(b(pc(), A(0xA8AC18)))


# --- Caught marker: in a wild battle, a Poke Ball left of the wild Pokemon's HP box when its species is already caught, as in the
# other games. The battle HUD (battle_top_00) has no such icon, but it has the trainer-battle ball row, whose enemy copy
# (L_ballPlate_01) the game hides in wild battles (0xAF8170). Each frame, after the game updates that row, show it with ball 0
# only, set to the normal ball, and place it next to the HP box, following the box as it slides. Pane hashes come from
# layout_setting_battle_top_00.bin, identical in both games. Panes: +0x30 x, +0x34 y, +0x48/+0x4C scale, +0x50/+0x54 size,
# +0x58 flags (bit 0 visible, bit 4 matrix out of date), as the layout animation code at 0x4A5C50 and 0x4A5BD8 uses them.
H_BALL_ROW = 0x28551600E02F94AA      # L_ballPlate_01
H_BALL_HIDE = (0x6BEF562FD7235B5D, 0x6BEF552FD72359AA,          # its P_ballBG_00, P_ballBG_01
               0xC0E1F98BCDF598E0, 0xC0E1FC8BCDF59DF9, 0xC0E1FB8BCDF59C46, 0xC0E1FE8BCDF5A15F, 0xC0E1FD8BCDF59FAC)   # balls 1-5
H_BALL_0 = 0xC0E1FA8BCDF59A93        # L_ballPlate_01/P_ballIcon_00
H_PLATE = ((0xC299D666CB84FCDC, 0xC44BA763E06B406C),             # L_pokePlate_03 and its P_plateBG_00 (single battles)
           (0xC299D766CB84FE8F, 0xC5F9F2BEEEBFDFC9))             # L_pokePlate_02 and its P_plateBG_00
H_POS_PLATE = 0x0C9ED29D0ACA7DC7     # N_pos_RT_00, the HP boxes' parent, which slides them in and out
H_POS_ROW = 0x0C9ED19D0ACA7C14       # N_pos_RT_01, the ball row's parent
BALL_GAP = 4                         # pixels between the ball and the box
BALL_0_X = -45                       # ball 0 inside the row (battle_ballPlate_00.bflyt); balls are 16 pixels wide


def ldr_s(t, n, imm):
    return 0xBD400000 | ((imm // 4) << 10) | (n << 5) | t


def str_s(t, n, imm):
    return 0xBD000000 | ((imm // 4) << 10) | (n << 5) | t


def fop(op, d, n, m):
    return {"add": 0x1E202800, "sub": 0x1E203800, "mul": 0x1E200800}[op] | (m << 16) | (n << 5) | d


# x0 = layout, x1 = pane hash. Returns the pane or 0. Leaf; uses x8-x10. The same table 0x36BDA0 searches.
mark("find_pane")
emit(ldr(8, 0, 0x220))
emit(ldr(9, 0, 0x228))
find_none = len(code)
emit(0)                               # cbz x9, none
find_loop = pc()
emit(ldr(10, 8, 0))
emit(0xEB01015F)                      # cmp x10, x1
find_hit = len(code)
emit(0)                               # b.eq hit
emit(0x91004108)                      # add x8, x8, #0x10
emit(0xF1000529)                      # subs x9, x9, #1
emit(b_cond(pc(), find_loop, 1))      # b.ne loop
code[find_none] = cbz(CAVE + find_none * 4, pc(), 9, wide=True)
emit(0xD2800000)                      # mov x0, #0
emit(RET)
code[find_hit] = b_cond(CAVE + find_hit * 4, pc(), EQ)
emit(ldr(0, 8, 8))
emit(RET)

# x0 = layout, x1 = pane hash, w2 = visible. Leaf; uses x8-x10.
mark("set_visible")
emit(0xAA1E03EB)                      # mov x11, x30
emit(bl(pc(), marks["find_pane"]))
emit(0xAA0B03FE)                      # mov x30, x11
emit(cbz(pc(), pc() + 16, 0, wide=True))
emit(0x39416008)                      # ldrb w8, [x0, #0x58]
emit(0x33000048)                      # bfxil w8, w2, #0, #1
emit(0x39016008)                      # strb w8, [x0, #0x58]
emit(RET)

# The HUD's last step each frame, x0 = the enemy ball row object (+0x58 layout, +0x60 battle view, +0x70 party).
mark("caught_ball")
emit(0xA9BC7BFD)                      # stp x29, x30, [sp, #-0x40]!
emit(0x910003FD)                      # mov x29, sp
emit(0xA90153F3)                      # stp x19, x20, [sp, #0x10]
emit(0xA9025BF5)                      # stp x21, x22, [sp, #0x20]
emit(0xA90363F7)                      # stp x23, x24, [sp, #0x30]
emit(0xAA0003F3)                      # mov x19, x0
emit(bl(pc(), A(0xAF8530)))           # the row's own update
to_out = []
to_hide = []


def jump(slots, kind="cbz", reg=0, wide=True):
    slots.append((len(code), kind, reg, wide))
    emit(0)


emit(ldr(0, 19, 0x60))
jump(to_out, "cbz", 0)
emit(bl(pc(), A(0xAC0790)))           # battle kind: 1 = wild
emit(0x7100041F)                      # cmp w0, #1
jump(to_out, "b.ne")
emit(ldr(20, 19, 0x58))
jump(to_out, "cbz", 20)
emit(0xAA1403E0)                      # mov x0, x20
mov64(1, H_BALL_ROW)
emit(bl(pc(), marks["find_pane"]))
emit(0xAA0003F5)                      # mov x21, x0
jump(to_out, "cbz", 21)
# The enemy HP box being shown: L_pokePlate_03, else 02. x22 = box, x23 = its background's hash.
plate_found = []
for i, (h_plate, h_bg) in enumerate(H_PLATE):
    emit(0xAA1403E0)                  # mov x0, x20
    mov64(1, h_plate)
    emit(bl(pc(), marks["find_pane"]))
    emit(0xAA0003F6)                  # mov x22, x0
    next_slot = len(code)
    emit(0)                           # cbz x22, next
    emit(0x39416008 | (22 << 5))      # ldrb w8, [x22, #0x58]
    next_slot2 = len(code)
    emit(0)                           # tbz w8, #0, next
    mov64(23, h_bg)
    jump(plate_found, "b")
    code[next_slot] = cbz(CAVE + next_slot * 4, pc(), 22, wide=True)
    code[next_slot2] = 0x36000008 | (((pc() - (CAVE + next_slot2 * 4)) >> 2) << 5)
jump(to_hide, "b")
for slot, *_ in plate_found:
    code[slot] = b(CAVE + slot * 4, pc())
plate_found.clear()
# Already caught? The opponent in battle position 1, fetched the way the HP box fetches its Pokemon (0xAC3B20), its species, and
# the Pokedex bit the catch screen checks for "New Pokemon" (0x827BBC, Pokedex via the field object as 0x827B58 finds it).
emit(ldr(0, 19, 0x60))
emit(0x52800021)                      # mov w1, #1: the opponent
emit(bl(pc(), A(0xABE6F0)))
jump(to_hide, "cbz", 0)
emit(ldr(0, 0, 0x60))                 # its Pokemon data
jump(to_hide, "cbz", 0)
emit(bl(pc(), A(0x7247C0)))           # species
emit(0x2A0003F8)                      # mov w24, w0
emit(adrp(pc(), 8, FIELD_PTR))
emit(ldr(8, 8, FIELD_PTR & 0xFFF))
emit(ldr(8, 8, 0))
emit(ldr(8, 8, 0x98))
jump(to_hide, "cbz", 8)
emit(ldr(8, 8, 0x58))
jump(to_hide, "cbz", 8)
emit(ldr(0, 8, 0x88))                 # the Pokedex
jump(to_hide, "cbz", 0)
emit(0x2A1803E1)                      # mov w1, w24
emit(bl(pc(), A(0x1D0150)))           # caught?
jump(to_hide, "tbz0", 0)
# Panes for the position: the box's background (x23), and both parents (x24, x0).
emit(0xAA1403E0)                      # mov x0, x20
emit(0xAA1703E1)                      # mov x1, x23
emit(bl(pc(), marks["find_pane"]))
emit(0xAA0003F7)                      # mov x23, x0
jump(to_hide, "cbz", 23)
emit(0xAA1403E0)                      # mov x0, x20
mov64(1, H_POS_PLATE)
emit(bl(pc(), marks["find_pane"]))
emit(0xAA0003F8)                      # mov x24, x0
jump(to_hide, "cbz", 24)
emit(0xAA1403E0)                      # mov x0, x20
mov64(1, H_POS_ROW)
emit(bl(pc(), marks["find_pane"]))
jump(to_hide, "cbz", 0)
# x: box parent + box + background - background width / 2 (it is centred), less the gap and half a ball, then into the row's
# parent and onto ball 0. y: the background's middle (it hangs from its top edge), into the row's parent.
emit(ldr_s(0, 24, 0x30))
emit(ldr_s(1, 22, 0x30))
emit(fop("add", 0, 0, 1))
emit(ldr_s(1, 23, 0x30))
emit(fop("add", 0, 0, 1))
emit(ldr_s(1, 23, 0x50))
emit(ldr_s(2, 23, 0x48))
emit(fop("mul", 1, 1, 2))
emit(0x1E2C1002)                      # fmov s2, #0.5
emit(fop("mul", 1, 1, 2))
emit(fop("sub", 0, 0, 1))
emit(ldr_s(1, 0, 0x30))
emit(fop("sub", 0, 0, 1))
emit(0x52800009 | ((-(BALL_GAP + 8) - BALL_0_X) << 5))   # mov w9, #(offset)
emit(0x1E220121)                      # scvtf s1, w9
emit(fop("add", 0, 0, 1))
emit(ldr_s(3, 24, 0x34))
emit(ldr_s(1, 22, 0x34))
emit(fop("add", 3, 3, 1))
emit(ldr_s(1, 23, 0x34))
emit(fop("add", 3, 3, 1))
emit(ldr_s(1, 23, 0x54))
emit(ldr_s(2, 23, 0x4C))
emit(fop("mul", 1, 1, 2))
emit(0x1E2C1002)                      # fmov s2, #0.5
emit(fop("mul", 1, 1, 2))
emit(fop("sub", 3, 3, 1))
emit(ldr_s(1, 0, 0x34))
emit(fop("sub", 3, 3, 1))
emit(str_s(0, 21, 0x30))
emit(str_s(3, 21, 0x34))
emit(0x39416008 | (21 << 5))          # ldrb w8, [x21, #0x58]
emit(0x321C0108)                      # orr w8, w8, #0x10
emit(0x32000108)                      # orr w8, w8, #1
emit(0x39016008 | (21 << 5))          # strb w8, [x21, #0x58]
# One normal Poke Ball (the game's own setter, ball 0, look 0), nothing else of the row.
emit(0xAA1303E0)                      # mov x0, x19
emit(0x2A1F03E1)                      # mov w1, wzr
emit(0x2A1F03E2)                      # mov w2, wzr
emit(bl(pc(), A(0xAF83A0)))
for h in H_BALL_HIDE:
    emit(0xAA1403E0)                  # mov x0, x20
    mov64(1, h)
    emit(0x2A1F03E2)                  # mov w2, wzr
    emit(bl(pc(), marks["set_visible"]))
emit(0xAA1403E0)                      # mov x0, x20
mov64(1, H_BALL_0)
emit(0x52800022)                      # mov w2, #1
emit(bl(pc(), marks["set_visible"]))
jump(to_out, "b")
hide_at = pc()
emit(0x39416008 | (21 << 5))          # ldrb w8, [x21, #0x58]
emit(0x121F7908)                      # and w8, w8, #0xfffffffe
emit(0x39016008 | (21 << 5))          # strb w8, [x21, #0x58]
out_at = pc()
emit(0xA94363F7)                      # ldp x23, x24, [sp, #0x30]
emit(0xA9425BF5)                      # ldp x21, x22, [sp, #0x20]
emit(0xA94153F3)                      # ldp x19, x20, [sp, #0x10]
emit(0xA8C47BFD)                      # ldp x29, x30, [sp], #0x40
emit(RET)
for slots, target in ((to_out, out_at), (to_hide, hide_at)):
    for slot, kind, reg, wide in slots:
        at = CAVE + slot * 4
        if kind == "cbz":
            code[slot] = cbz(at, target, reg, wide=wide)
        elif kind == "tbz0":
            code[slot] = 0x36000000 | (((target - at) >> 2 & 0x3FFF) << 5) | reg
        elif kind == "b":
            code[slot] = b(at, target)
        else:
            code[slot] = b_cond(at, target, {"b.ne": 1, "b.eq": 0}[kind])

blob = b"".join(struct.pack("<I", w) for w in code)
assert CAVE + len(blob) <= LIMIT, hex(CAVE + len(blob))


def site(addr, want, word):
    want = re.sub(r"#0x([0-9a-f]{5,})", lambda m: f"#{A(int(m.group(1), 16)):#x}", want)   # Pikachu addresses in the expected text
    got = dec(image[addr:addr + 4], addr)[0]
    assert got == want, (hex(addr), got, want)
    return addr, struct.pack("<I", word)


edits = [
    # Encounters start a battle rather than the catch app. Details object comes from the field heap, as the event outlives the app heap.
    site(A(0x3057B8), "ldr x20, [x8, #0x248]", b(A(0x3057B8), marks["heap_pick"])),
    site(A(0x289B80), "bl #0x28bc40", bl(A(0x289B80), marks["event_sync"])),
    site(A(0x305934), "bl #0x2f6470", bl(A(0x305934), marks["encounter_start"])),
    site(A(0x2FDF34), "bl #0x305970", bl(A(0x2FDF34), marks["post_catch"])),
    site(A(0x2FDF80), "bl #0x305970", bl(A(0x2FDF80), marks["post_catch"])),
    site(A(0x319FF4), "mov w24, wzr", b(A(0x319FF4), marks["tier"])),
    site(A(0x28BE8C), "str w8, [x19, #0x68]", b(A(0x28BE8C), marks["state8"])),
    site(A(0x28C1A0), "mov w3, #2", b(A(0x28C1A0), marks["fade"])),
    site(A(0x28CB10), "mov w2, #0xa", b(A(0x28CB10), marks["intro"])),
    site(A(0x28BF1C), "cbz x20, #0x28c1ac", b(A(0x28BF1C), marks["after_loss"])),
    # No timer.
    site(A(0x28C894), "mov w8, #0x12c", b(A(0x28C894), marks["timer"])),
    # EXP on a win.
    site(A(0x9D8A44), "cbz w9, #0x9d8a58", b(A(0x9D8A44), marks["exp_a"])),
    site(A(0x9D8A5C), "tbnz w8, #7, #0x9d8a6c", b(A(0x9D8A5C), marks["exp_b"])),
    # A win shows the wild Pokemon fainting.
    site(A(0x9FCF38), "tbz w0, #0, #0x9fcf4c", b(A(0x9FCF38), marks["faint_text"])),
    site(A(0xA8A958), "tbz w0, #0, #0xa8a984", b(A(0xA8A958), marks["faint_anim"])),
    # Catch EXP after a ball-skip only.
    site(A(0x830074), "bl #0x830410", bl(A(0x830074), marks["catch_exp_eligible"])),
    site(A(0x830828), "bl #0x82d3f0", bl(A(0x830828), marks["catch_amount_a"])),
    site(A(0x8315E4), "bl #0x82d3f0", bl(A(0x8315E4), marks["catch_amount_b"])),
    # Evolution after a win; catch only after a ball.
    site(A(0x319EB4), "mov w8, #3", b(A(0x319EB4), marks["evo_start"])),
    site(A(0x319DA4), "mov w8, #4", b(A(0x319DA4), marks["after_evolution"])),
    # Early saves.
    site(A(0xA993E0), "ldur x0, [x29, #-0x48]", b(A(0xA993E0), marks["early_save"])),
    # Ball from the Bag.
    site(A(0xA0FB90), "bl #0xa10e30", bl(A(0xA0FB90), marks["ball"])),
    site(A(0x28BDB8), "adrp x21, #0x15fa000", b(A(0x28BDB8), marks["battle_start"])),
    site(A(0xD2D7C4), "ldrb w8, [x8, w1, uxtw]", b(A(0xD2D7C4), marks["bag_filter"])),
]

edits.append(site(A(0x7E5F00), "str x21, [sp, #-0x30]!", b(A(0x7E5F00), marks["start_ball"])))
# Intro skip on + / -.
edits.append(site(A(0x202F44), "bl #0x36be40", bl(A(0x202F44), marks["layout_play"])))
edits.append(site(A(0x1DDE9C), "bl #0x1f1d20", bl(A(0x1DDE9C), marks["title_skip"])))
edits.append(site(A(0xF144), "mov x8, #0x2645", b(A(0xF144), marks["title_on"])))
edits.append(site(A(0xE580), "ldr w8, [x19, #0xf8]", b(A(0xE580), marks["title_off"])))
edits.append(site(A(0x9D3860), "str w20, [x8, #0x508]", b(A(0x9D3860), marks["result_a"])))
edits.append(site(A(0x9DA378), "str w0, [x8, #0x508]", b(A(0x9DA378), marks["result_b"])))
edits.append((CAVE, blob))

# --- Option text. The lookup lives in the padding after the code section. The strings, one set per message folder,
# are in the read-only padding after the build ID note, which is why the patch uses IPS32.
TAIL = 0xD32BB0
TAIL_END = 0xD33000
RO_TEXT = 0x1526180
RO_END = 0x1527000
assert TEXT_END <= TAIL and not any(image[TEXT_END:TAIL_END])
assert RO_DATA_END <= RO_TEXT and not any(image[RO_DATA_END:RO_END])
EXP_TEXT_AT = (CAVE + len(blob) + 3) & ~3   # the third row's strings: no room left beside the others, so they follow the code
LANG_INDEX = A(0x1614B34)   # the active message folder, as set at 0x1B31E0 (Japanese kana 0, kanji 1, others 2-9)
tail = []
tail_marks = {}


def tpc():
    return TAIL + len(tail) * 4


def tmark(name):
    tail_marks[name] = tpc()


# Text lookup, x1 = &label hash, x2 = output. Our four labels are written directly, in the current language.
tmark("option_text")
tail.append(ldr(9, 1, 0))
table_slot = len(tail)
tail.append(0)                    # adr x10, table
loop_at = tpc()
tail.append(ldr(11, 10, 0))
orig_slot = len(tail)
tail.append(0)                    # cbz x11, original
tail.append(0xEB09017F)           # cmp x11, x9
match_slot = len(tail)
tail.append(0)                    # b.eq match
tail.append(0x9100414A)           # add x10, x10, #0x10
tail.append(b(tpc(), loop_at))
match = tpc()
tail.append(0xA9BC7BFD)           # stp x29, x30, [sp, #-0x40]!
tail.append(0xA90153F3)           # stp x19, x20, [sp, #0x10]
tail.append(0xF90013F5)           # str x21, [sp, #0x20]
tail.append(0x910003FD)           # mov x29, sp
tail.append(0xAA0203F3)           # mov x19, x2
tail.append(0xB9400949)           # ldr w9, [x10, #8]: which string
tail.append(adrp(tpc(), 11, LANG_INDEX))
tail.append(0xB9400000 | (((LANG_INDEX & 0xFFF) // 4) << 10) | (11 << 5) | 11)   # ldr w11, [x11, #lo]
tail.append(0x7100257F)           # cmp w11, #9
tail.append(0x54000049)           # b.ls, over the next instruction
tail.append(0x5280004B)           # mov w11, #2: English
tail.append(0xB9400D4E)           # ldr w14, [x10, #0xc]: which set of strings
exp_text_slot = len(tail)
tail.append(0)                    # cbnz w14, the Exp. Share set
tail.append(0x0B0B0929)           # add w9, w9, w11, lsl #2
tail.append(adrp(tpc(), 12, RO_TEXT))
tail.append(0x91000000 | ((RO_TEXT & 0xFFF) << 10) | (12 << 5) | 12)   # add x12, x12, #lo
text_base_slot = len(tail)
tail.append(0)                    # b, past the other set
tail[exp_text_slot] = cbz(TAIL + exp_text_slot * 4, tpc(), 14, nz=True)
tail.append(0x0B0B0529)           # add w9, w9, w11, lsl #1
tail.append(adrp(tpc(), 12, EXP_TEXT_AT))
tail.append(0x91000000 | ((EXP_TEXT_AT & 0xFFF) << 10) | (12 << 5) | 12)   # add x12, x12, #lo
tail[text_base_slot] = b(TAIL + text_base_slot * 4, tpc())
tail.append(0x8B09098D)           # add x13, x12, x9, lsl #2
tail.append(0x794001B4)           # ldrh w20, [x13]: offset
tail.append(0x794005B5)           # ldrh w21, [x13, #2]: characters
tail.append(0x8B140194)           # add x20, x12, x20
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(bl(tpc(), A(0x3A860)))
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(bl(tpc(), A(0x3AA40)))
char_at = tpc()
tail.append(0x78402681)           # ldrh w1, [x20], #2
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(bl(tpc(), A(0x3A9A0)))
tail.append(0x710006B5)           # subs w21, w21, #1
tail.append(0x54000001 | (((char_at - tpc()) >> 2 & 0x7FFFF) << 5))  # b.ne
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(bl(tpc(), A(0x3AA10)))
tail.append(MOV_W0_ZERO)
tail.append(0xF94013F5)           # ldr x21, [sp, #0x20]
tail.append(0xA94153F3)           # ldp x19, x20, [sp, #0x10]
tail.append(0xA8C47BFD)           # ldp x29, x30, [sp], #0x40
tail.append(RET)
orig = tpc()
tail.append(original(0x678710))
tail.append(b(tpc(), A(0x678714)))

at = TAIL + orig_slot * 4
tail[orig_slot] = cbz(at, orig, 11, wide=True)
at = TAIL + match_slot * 4
tail[match_slot] = 0x54000000 | (((match - at) >> 2) << 5)            # b.eq match

# Menu event, state 2 (opens the menu): when Up opened the event, record "town map" as the choice and take the map's state.
tmark("sky_dash_state")
tail.append(adrp(tpc(), 9, SKY_DASH_MAP))
tail.append(flag_ldrb(10, 9, SKY_DASH_MAP))
sky_menu_slot = len(tail)
tail.append(0)                    # cbz w10, the menu
tail.append(0xB900A26A)           # str w10, [x19, #0xa0]
tail.append(b(tpc(), A(0x28007C)))
tail[sky_menu_slot] = cbz(TAIL + sky_menu_slot * 4, tpc(), 10)
tail.append(original(0x27FFF8))
tail.append(b(tpc(), A(0x27FFFC)))

# Menu event, state 5 (the map has closed). A destination flies as usual. Backing out would reopen the menu, so when Up opened
# the event, leave as if the menu had closed with nothing chosen: 5 is the constructor's default, and state 6 ignores it.
tmark("sky_dash_back")
tail.append(adrp(tpc(), 9, SKY_DASH_MAP))
tail.append(flag_ldrb(10, 9, SKY_DASH_MAP))
tail.append(flag_strb(31, 9, SKY_DASH_MAP))
tail.append(original(0x2802EC))
tail.append(0x7100051F)           # cmp w8, #1
sky_chosen_slot = len(tail)
tail.append(0)                    # b.ne not chosen
tail.append(b(tpc(), A(0x2802F8)))
tail[sky_chosen_slot] = 0x54000001 | (((tpc() - (TAIL + sky_chosen_slot * 4)) >> 2) << 5)
sky_ours_slot = len(tail)
tail.append(0)                    # cbnz w10, ours
tail.append(b(tpc(), A(0x2803A0)))
tail[sky_ours_slot] = cbz(TAIL + sky_ours_slot * 4, tpc(), 10, nz=True)
tail.append(0x528000A9)           # mov w9, #5
tail.append(0xB900A269)           # str w9, [x19, #0xa0]
tail.append(b(tpc(), A(0x2803B0)))

# Catch screen with Exp. Share off, after a fight. The game's generic "Your Pokemon got N" would read as the whole party, so show
# its other line, "<name> got N" (poke_get_result_01_01_mb, in every language), once per fighter.
def t_branch(op, dst, reg):
    # cbz, cbnz, tbz or tbnz (bit 0), backward or forward.
    tail.append(op | ((((dst - tpc()) >> 2) & (0x7FFFF if op >> 25 & 0x3F == 0x1A else 0x3FFF)) << 5) | reg)


T_CBZ = 0x34000000
T_CBNZ = 0x35000000
T_TBZ = 0x36000000
T_TBNZ = 0x37000000
NAMED_LINE = [original(0x8301A0 + i * 4) for i in range(4)]   # mov x8, hash of poke_get_result_01_01_mb

# x0 = this screen. Shows the next fighter's line and returns 1, or returns 0 if nobody is left. Who can get EXP, and how much,
# are the same tests and call as the EXP step at 0x830830 and 0x830828. The parameter block at +0x48 has the layout that step copies.
tmark("name_fighter")
tail.append(0xA9BC7BFD)           # stp x29, x30, [sp, #-0x40]!
tail.append(0xA90153F3)           # stp x19, x20, [sp, #0x10]
tail.append(0xA9025BF5)           # stp x21, x22, [sp, #0x20]
tail.append(0x910003FD)           # mov x29, sp
tail.append(0xAA0003F3)           # mov x19, x0
name_loop = tpc()
tail.append(adrp(tpc(), 9, NEXT_FIGHTER))
tail.append(flag_ldrb(22, 9, NEXT_FIGHTER))
name_none_slot = len(tail)
tail.append(0)                    # cbz w22, none
tail.append(0x71001EDF)           # cmp w22, #7
name_end_slot = len(tail)
tail.append(0)                    # b.hs, nobody left
tail.append(0x110006C8)           # add w8, w22, #1
tail.append(flag_strb(8, 9, NEXT_FIGHTER))
tail.append(0x510006D6)           # sub w22, w22, #1
tail.append(flag_ldrb(8, 9, FOUGHT))
tail.append(0x1AD62508)           # lsr w8, w8, w22
t_branch(T_TBZ, name_loop, 8)
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(bl(tpc(), A(0x82F7E0)))
tail.append(ldr(21, 0, 0x78))
tail.append(ldr(0, 21, 0x30))
tail.append(ldr(8, 0, 0))
tail.append(ldr(8, 8, 0x50))
tail.append(0x2A1603E1)           # mov w1, w22
tail.append(0xD63F0100)           # blr x8
tail.append(0xAA0003F4)           # mov x20, x0
tail.append(bl(tpc(), A(0x726530)))
t_branch(T_TBNZ, name_loop, 0)
tail.append(0xAA1403E0)           # mov x0, x20
tail.append(bl(tpc(), A(0x7247A0)))
t_branch(T_TBNZ, name_loop, 0)
tail.append(0xAA1403E0)           # mov x0, x20
tail.append(0x52800041)           # mov w1, #2
tail.append(bl(tpc(), A(0x727FB0)))
t_branch(T_TBNZ, name_loop, 0)
tail.append(0xAA1403E0)           # mov x0, x20
tail.append(bl(tpc(), A(0x726580)))
tail.append(0x7101901F)           # cmp w0, #100
tail.append(0x54000000 | (((name_loop - tpc()) >> 2 & 0x7FFFF) << 5))   # b.eq loop
tail.append(0xAA1403E0)           # mov x0, x20
tail.append(0x910122A1)           # add x1, x21, #0x48
tail.append(0x2A1F03E2)           # mov w2, wzr
tail.append(bl(tpc(), A(0x82D3F0)))
t_branch(T_CBZ, name_loop, 0)
tail.append(0x2A0003F6)           # mov w22, w0
tail.append(adrp(tpc(), 9, WORD_SET))
tail.append(ldr(21, 9, WORD_SET & 0xFFF))
tail.append(0xAA1503E0)           # mov x0, x21
tail.append(0x2A1F03E1)           # mov w1, wzr
tail.append(0xAA1403E2)           # mov x2, x20
tail.append(bl(tpc(), A(0x1BA580)))
tail.append(0xAA1503E0)           # mov x0, x21
tail.append(0x52800021)           # mov w1, #1
tail.append(0x2A1603E2)           # mov w2, w22
tail.append(0x528000C3)           # mov w3, #6
tail.append(0x2A1F03E4)           # mov w4, wzr
tail.append(0x52800025)           # mov w5, #1
tail.append(bl(tpc(), A(0x1BC110)))
tail.extend(NAMED_LINE)
tail.append(0xF9001BE8)           # str x8, [sp, #0x30]
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(0x9100C3E1)           # add x1, sp, #0x30
tail.append(0x52800082)           # mov w2, #4
tail.append(bl(tpc(), A(0x830220)))
tail.append(0x52800020)           # mov w0, #1
name_out_slot = len(tail)
tail.append(0)                    # b out
tail[name_end_slot] = 0x54000002 | (((tpc() - (TAIL + name_end_slot * 4)) >> 2) << 5)
tail.append(flag_strb(31, 9, NEXT_FIGHTER))
tail[name_none_slot] = cbz(TAIL + name_none_slot * 4, tpc(), 22)
tail.append(MOV_W0_ZERO)
tail[name_out_slot] = b(TAIL + name_out_slot * 4, tpc())
tail.append(0xA9425BF5)           # ldp x21, x22, [sp, #0x20]
tail.append(0xA94153F3)           # ldp x19, x20, [sp, #0x10]
tail.append(0xA8C47BFD)           # ldp x29, x30, [sp], #0x40
tail.append(RET)

# The result screen's first message, x19 = this screen, x21 = its frame. Off after a fight: start naming fighters.
tmark("fighter_message")
tail.append(adrp(tpc(), 9, FOUGHT))
tail.append(flag_ldrb(8, 9, FOUGHT))
generic_slots = [len(tail)]
tail.append(0)                    # cbz w8, generic
tail.append(adrp(tpc(), 10, FIELD_PTR))
tail.append(ldr(10, 10, FIELD_PTR & 0xFFF))
tail.append(ldr(10, 10, 0))
tail.append(ldr(10, 10, 0x98))
generic_wide_slots = [len(tail)]
tail.append(0)                    # cbz x10, generic
tail.append(ldr(10, 10, 0x58))
tail.append(ldr(10, 10, 0x98))
generic_wide_slots.append(len(tail))
tail.append(0)                    # cbz x10, generic
tail.append(0xB940554A)           # ldr w10, [x10, #0x54]
generic_on_slot = len(tail)
tail.append(0)                    # tbz w10, #29, generic
tail.append(ldr(8, 21, 0x2A8))
generic_wide_slots.append(len(tail))
tail.append(0)                    # cbz x8, generic
tail.append(str_x(8, 9, WORD_SET & 0xFFF))
tail.append(0x52800028)           # mov w8, #1
tail.append(flag_strb(8, 9, NEXT_FIGHTER))
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(bl(tpc(), tail_marks["name_fighter"]))
generic_slots.append(len(tail))
tail.append(0)                    # cbz w0, generic: nobody can get any, so the game's flow runs
tail.append(0x52800068)           # mov w8, #3
tail.append(b(tpc(), A(0x8301F8)))
tail[generic_slots[0]] = cbz(TAIL + generic_slots[0] * 4, tpc(), 8)
tail[generic_slots[1]] = cbz(TAIL + generic_slots[1] * 4, tpc(), 0)
for slot in generic_wide_slots:
    tail[slot] = cbz(TAIL + slot * 4, tpc(), 8 if slot == generic_wide_slots[-1] else 10, wide=True)
tail[generic_on_slot] = 0x36E80000 | (((tpc() - (TAIL + generic_on_slot * 4)) >> 2) << 5) | 10
tail.append(original(0x83008C))
tail.append(b(tpc(), A(0x830090)))

# The message has finished. While fighters are left, show the next and keep waiting in this state.
tmark("fighter_next")
tail.append(adrp(tpc(), 9, NEXT_FIGHTER))
tail.append(flag_ldrb(8, 9, NEXT_FIGHTER))
fighter_done_a = len(tail)
tail.append(0)                    # cbz w8, done
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(bl(tpc(), tail_marks["name_fighter"]))
fighter_done_b = len(tail)
tail.append(0)                    # cbz w0, done
tail.append(b(tpc(), A(0x8301FC)))
tail[fighter_done_a] = cbz(TAIL + fighter_done_a * 4, tpc(), 8)
tail[fighter_done_b] = cbz(TAIL + fighter_done_b * 4, tpc(), 0)
tail.append(original(0x830024))
tail.append(b(tpc(), A(0x830028)))

# The faint sequence (ee620) aims at the fainted Pokemon's trainer: target 4 is the view stored here. A wild Pokemon has no
# trainer model, and the joint lookup at 0xA9C650 would crash on it, so give it the game's own "no target" value, which the
# sequence commands skip. Flag 0x80 marks the wild battles; position 1 is the opponent, so the player's side is untouched.
# x21 is free here: the function saved it on entry and reloads it at 0xA8A9E0.
tmark("faint_target")
tail.append(0x2A0803F5)           # mov w21, w8
tail.append(ldr(8, 19, 0))
tail.append(ldr(8, 8, 0x7F0))
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(0x52801001)           # mov w1, #0x80
tail.append(0xD63F0100)           # blr x8
tail.append(0x2A1F03EA)           # mov w10, wzr
faint_tbz = len(tail)
tail.append(0)                    # tbz w0, #0, keep
tail.append(0xB949A269)           # ldr w9, [x19, #0x9a0]
tail.append(0x7100053F)           # cmp w9, #1
faint_bne = len(tail)
tail.append(0)                    # b.ne keep
tail.append(0x52801FF5)           # mov w21, #0xff
tail.append(0x5280002A)           # mov w10, #1
tail[faint_tbz] = 0x36000000 | (((tpc() - (TAIL + faint_tbz * 4)) >> 2) << 5)
tail[faint_bne] = 0x54000001 | (((tpc() - (TAIL + faint_bne * 4)) >> 2) << 5)
tail.append(adrp(tpc(), 9, WILD_FAINT))
tail.append(flag_strb(10, 9, WILD_FAINT))
tail.append(0xB909BA75)           # str w21, [x19, #0x9b8]
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(b(tpc(), A(0xA8A9DC)))

# That sequence is a return to the Poke Ball, which a wild Pokemon shouldn't do. Its motion, shrink and hide stay. While it plays,
# these commands read their arguments as usual and then do nothing: the particles (blue aura) and the ball's sound. x9 is free at
# each site.
tmark("faint_particle")           # no particles to switch on: x8 = 0 takes the function's own empty-list exit
tail.append(adrp(tpc(), 9, WILD_FAINT))
tail.append(flag_ldrb(9, 9, WILD_FAINT))
tail.append(0xAA1F03E8)           # mov x8, xzr
tail.append(cbz(tpc(), tpc() + 8, 9, nz=True))
tail.append(original(0xAE09D0))
tail.append(b(tpc(), A(0xAE09D4)))


tmark("faint_sound")              # go to the command's exit
tail.append(adrp(tpc(), 9, WILD_FAINT))
tail.append(flag_ldrb(9, 9, WILD_FAINT))
tail.append(cbz(tpc(), tpc() + 8, 9))
tail.append(b(tpc(), A(0xAE9EF0)))
tail.append(original(0xAE9D38))
tail.append(b(tpc(), A(0xAE9D3C)))

table_at = tpc()
at = TAIL + table_slot * 4
delta = table_at - at
tail[table_slot] = 0x10000000 | ((delta & 3) << 29) | (((delta >> 2) & 0x7FFFF) << 5) | 10   # adr x10, table
LABELS = (WILD_TITLE, WILD_INFO, TRADE_TITLE, TRADE_INFO)
labels_blob = b"".join(struct.pack("<QII", h, i, 0) for i, h in enumerate(LABELS))
labels_blob += b"".join(struct.pack("<QII", h, i, 1) for i, h in enumerate((EXP_TITLE, EXP_INFO))) + bytes(16)
tail_code = b"".join(struct.pack("<I", w) for w in tail)
tail_blob = tail_code + labels_blob
assert TAIL + len(tail_blob) <= EXP_INFO_AT, hex(TAIL + len(tail_blob))
exp_info_name = EXP_INFO_NAME.encode() + b"\0"
assert EXP_INFO_AT + len(exp_info_name) <= WILD_INFO_AT
wild_info_name = WILD_INFO_NAME.encode() + b"\0"
trade_info_name = TRADE_INFO_NAME.encode() + b"\0"
assert WILD_INFO_AT + len(wild_info_name) <= TRADE_INFO_AT
assert TRADE_INFO_AT + len(trade_info_name) <= TAIL_END

# Strings: a table of (offset from RO_TEXT, characters) for each folder's four strings, then the text.
assert sorted(option_text.TEXT) == list(range(10))
ro_table = bytearray()
ro_pool = bytearray()
ro_start = 10 * 4 * 4
for folder in range(10):
    assert len(option_text.TEXT[folder]) == 4
    for string in option_text.TEXT[folder]:
        ro_table += struct.pack("<HH", ro_start + len(ro_pool), len(string))
        ro_pool += string.encode("utf-16-le")
ro_blob = bytes(ro_table) + bytes(ro_pool)
assert RO_TEXT + len(ro_blob) <= RO_END, hex(RO_TEXT + len(ro_blob))
print("option text", len(ro_blob), "bytes, free", RO_END - RO_TEXT - len(ro_blob))

# The same layout for the Exp. Share row, two strings per folder.
assert sorted(option_text.EXP_SHARE_TEXT) == list(range(10))
exp_table = bytearray()
exp_pool = bytearray()
for folder in range(10):
    assert len(option_text.EXP_SHARE_TEXT[folder]) == 2
    for string in option_text.EXP_SHARE_TEXT[folder]:
        exp_table += struct.pack("<HH", 10 * 2 * 4 + len(exp_pool), len(string))
        exp_pool += string.encode("utf-16-le")
exp_blob = bytes(exp_table) + bytes(exp_pool)
assert EXP_TEXT_AT + len(exp_blob) <= LIMIT, hex(EXP_TEXT_AT + len(exp_blob))
print("exp share text", len(exp_blob), "bytes, cave free", LIMIT - EXP_TEXT_AT - len(exp_blob))

edits.append(site(A(0x678710), "stp x20, x19, [sp, #-0x20]!", b(A(0x678710), tail_marks["option_text"])))
edits.append((TAIL, tail_blob))
edits.append((RO_TEXT, ro_blob))
edits.append((EXP_TEXT_AT, exp_blob))
edits.append((EXP_INFO_AT, exp_info_name))
edits.append((WILD_INFO_AT, wild_info_name))
edits.append((TRADE_INFO_AT, trade_info_name))
# Options rows.
edits.append(site(A(0x4276C), "bl #0x45f00", bl(A(0x4276C), marks["row_alloc"])))
edits.append(site(A(0x42804), "ldp x29, x30, [sp, #0x60]", b(A(0x42804), marks["row_add"])))
edits.append(site(A(0x44DD4), "cmp w24, #0xa", b(A(0x44DD4), marks["row_text"])))
edits.append(site(A(0x3F8D8), "cmp w8, #8", b(A(0x3F8D8), marks["row_toggle"])))
edits.append(site(A(0x452D4), "cmp w8, #8", b(A(0x452D4), marks["row_arrow"])))
edits.append(site(A(0x3EBC0), "ldr x10, [x10, w20, sxtw #3]", b(A(0x3EBC0), marks["row_info"])))
edits.append(site(A(0x3B37C), "ldp x29, x30, [sp, #0x10]", b(A(0x3B37C), marks["row_load"])))
edits.append(site(A(0x3B404), "ldr x0, [x8, #8]", b(A(0x3B404), marks["row_apply"])))
edits.append(site(A(0x3F494), "ldr x0, [x19, #8]", b(A(0x3F494), marks["row_changed"])))
edits.append(site(A(0x722BF8), "ldr w8, [x20]", b(A(0x722BF8), marks["trade_evolution"])))
# Exp. Share.
edits.append(site(A(0x9DBD70), "ldr x8, [x0, #0x80]", b(A(0x9DBD70), marks["exp_share"])))
edits.append(site(A(0x9E3C60), "ldrb w9, [x0, #0x212]", b(A(0x9E3C60), marks["fought"])))
edits.append(site(A(0x83008C), "ldr x21, [x21, #0x2a8]", b(A(0x83008C), tail_marks["fighter_message"])))
edits.append(site(A(0x830024), "mov w8, #5", b(A(0x830024), tail_marks["fighter_next"])))
# A wild Pokemon's faint has no trainer to aim at.
edits.append(site(A(0xA8A9D8), "str w8, [x19, #0x9b8]", b(A(0xA8A9D8), tail_marks["faint_target"])))
# Nor a Poke Ball to go back to.
edits.append(site(A(0xA8AC14), "mov x0, x19", b(A(0xA8AC14), marks["faint_done"])))
edits.append(site(A(0xAE09D0), "ldr x8, [x19, #0xa8]", b(A(0xAE09D0), tail_marks["faint_particle"])))
edits.append(site(A(0xAE9D38), "ldr x20, [x21, #0xb0]", b(A(0xAE9D38), tail_marks["faint_sound"])))
edits.append(site(A(0x2F6470), "sub sp, sp, #0x80", b(A(0x2F6470), marks["catch_launch"])))
edits.append(site(A(0x2F6458), "b #0x2f6470", b(A(0x2F6458), marks["catch_launch_keep"])))
# D-pad Up.
edits.append(site(A(0x2F810C), "bl #0x13f540", bl(A(0x2F810C), marks["menu_button"])))
edits.append(site(A(0x2F8D10), "ldr x1, [x19]", b(A(0x2F8D10), marks["menu_open"])))
edits.append(site(A(0x27FFF8), "mov x20, x19", b(A(0x27FFF8), tail_marks["sky_dash_state"])))
edits.append(site(A(0x2802EC), "ldr w8, [x19, #0x218]", b(A(0x2802EC), tail_marks["sky_dash_back"])))
# Caught marker: the battle HUD's update ends with the enemy ball row's.
edits.append(site(A(0xAC2540), "b #0xaf8530", b(A(0xAC2540), marks["caught_ball"])))

print("--- tail code")
names2 = {v: k for k, v in tail_marks.items()}
for ins in md.disasm(tail_code, TAIL):
    if ins.address in names2:
        print(f"-- {names2[ins.address]}")
    print(f"{ins.address:08X}  {ins.mnemonic} {ins.op_str}")
print("tail ends", hex(TAIL + len(tail_blob)), "free", TAIL_END - TAIL - len(tail_blob))

spans = sorted((a, a + len(d)) for a, d in edits)
for (a1, e1), (a2, _) in zip(spans, spans[1:]):
    assert e1 <= a2, f"overlap at {a2:#x}"

out = bytearray(b"IPS32")     # the option text is past what 3-byte IPS offsets can reach
for addr, data in edits:
    if addr == CAVE:
        continue
    print(f"{addr:08X}  {(dec(data[:4], addr) or ['(data)'])[0]}")
    out += (addr + SIZE_HEADER).to_bytes(4, "big") + len(data).to_bytes(2, "big") + data
out += (CAVE + SIZE_HEADER).to_bytes(4, "big") + len(blob).to_bytes(2, "big") + blob + b"EEOF"

print()
names = {v: k for k, v in marks.items()}
listing = list(md.disasm(blob, CAVE))
assert len(listing) == len(code), "a word did not decode"
assert 0 not in code and 0 not in tail, "an unpatched slot"
for ins in listing:
    if ins.address in names:
        print(f"-- {names[ins.address]}")
    print(f"{ins.address:08X}  {ins.mnemonic} {ins.op_str}")
open(sys.argv[2], "wb").write(out)
if RECORD:
    open(RECORD, "w").write("".join(f"{a:#x}\n" for a in sorted(recorded)))
print("\nwrote", len(out), "bytes; cave ends", hex(CAVE + len(blob)))
