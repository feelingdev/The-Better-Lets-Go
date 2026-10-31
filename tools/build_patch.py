"""Build The Better Let's Go, for Let's Go, Pikachu! 1.0.2: one standalone IPS patch.
Every original instruction is checked first, so a different game build stops the script.
Args: decompressed_main (0x100-byte header attached) out_ips"""
import struct
import sys

from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs

image = open(sys.argv[1], "rb").read()[0x100:]
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)

CAVE = 0x6F6830       # protobuf Tokenizer::ConsumeString and ConsumeNumber: only text-format parsing reaches them
LIMIT = 0x6F70F0
FLAG = 0x1EE0F00      # page padding past the end of .bss (1EE06F8); nothing references past 1EE0678
WILD_OFF = FLAG + 4   # 1 when the "Enable Wild Battle" option is off; refreshed when an encounter or battle event starts
FIELD_PTR = 0x15FAD08
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
emit(bl(pc(), 0x28BC40))
emit(0x9100A3E0)                  # add x0, sp, #0x28
emit(0x910103E8)                  # add x8, sp, #0x40
emit(bl(pc(), 0x17EEE0))
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
emit(b(pc(), 0x28CB14))

# --- After a loss: run the same return step a finished battle runs.
mark("after_loss")
load_off()
loss_skip = pc() + 20
emit(cbz(pc(), loss_skip, 16, nz=True))
emit(adrp(pc(), 1, FIELD_PTR))
emit(ldr(1, 1, FIELD_PTR & 0xFFF))
emit(ldr(1, 1, 0))
emit(bl(pc(), 0x28D830))
assert pc() == loss_skip
emit(cbz(pc(), pc() + 8, 20, wide=True, nz=True))
emit(b(pc(), 0x28C1AC))
emit(b(pc(), 0x28BF20))

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
emit(b(pc(), 0x319DA8))

# --- Early saves: the trainer model must carry the partner in a wild battle.
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
emit(struct.unpack_from("<I", image, 0xA993E0)[0])
emit(0x52800028)                  # mov w8, #1
emit(0x39044008)                  # strb w8, [x0, #0x110]
assert pc() == early_end
emit(struct.unpack_from("<I", image, 0xA993E0)[0])
emit(b(pc(), 0xA993E4))


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


exp_stub("catch_exp_eligible", 0x830410)
exp_stub("catch_exp_amount", 0x82D3F0)

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
emit(b(pc(), 0xA10E30))

# --- Marker off at the start of each battle.
mark("battle_start")
emit(adrp(pc(), 8, FLAG))
emit(strb_flag(31, 8))
emit(adrp(pc(), 21, 0x15FA000))
emit(b(pc(), 0x28BDBC))


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
    emit(b(pc(), site + 4))


# --- Battle Bag: Master, Ultra, Great, Poke and Premier Balls list in the battle items tab, only with the option on.
mark("bag_filter")
emit(struct.unpack_from("<I", image, 0xD2D7C4)[0])  # the original byte load
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
emit(b(pc(), 0xD2D7C8))

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
emit(struct.unpack_from("<I", image, 0x7E5F00)[0])
emit(b(pc(), 0x7E5F04))

# --- Intro skip with the game's demo skip input (pad +0x40, bit 61). Falls through when not pressed.
PAD_GOT = 0x15FAEA0
TITLE_FLAG = FLAG + 1     # set while the boot event's title demo runs
SKIP_TO = 500             # title demo: where the sparkle intro ends and the logo idle begins


def skip_pressed(done):
    """Branch to the label named `done` unless skip is pressed. Uses x9 only."""
    emit(adrp(pc(), 9, PAD_GOT))
    emit(ldr(9, 9, PAD_GOT & 0xFFF))
    emit(ldr(9, 9, 0))
    pending.append((len(code), "cbz", done))
    emit(0)
    emit(ldr(9, 9, 0xB0))         # first pad (+0x70) buttons (+0x40)
    pending.append((len(code), "tbz61", done))
    emit(0)


pending = []


def resolve(target):
    for idx, kind, _ in pending:
        at = CAVE + idx * 4
        if kind == "cbz":
            code[idx] = cbz(at, target, 9, wide=True)
        else:
            code[idx] = 0xB6000000 | (29 << 19) | ((((target - at) >> 2) & 0x3FFF) << 5) | 9
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
emit(bl(pc(), 0x36C0C0))
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
emit(bl(pc(), 0x36BE40))
emit(ldr(0, 31, 0x10))
emit(bl(pc(), marks["logo_finish"]))
emit(0xA8C27BFD)                                     # ldp x29, x30, [sp], #0x20
emit(RET)
tail = pc()
code[to_tail_a] = cbz(CAVE + to_tail_a * 4, tail, 17)
code[to_tail_b] = 0x54000001 | (((tail - (CAVE + to_tail_b * 4)) >> 2) << 5)  # b.ne tail
code[to_tail_c] = cbz(CAVE + to_tail_c * 4, tail, 17)
emit(b(pc(), 0x36BE40))

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
emit(b(pc(), 0x1F1D20))

# Boot event: marker on and skip state cleared when it starts the title demo; off when that demo returns.
mark("title_on")
emit(adrp(pc(), 16, TITLE_FLAG))
emit(0x52800031)                                     # mov w17, #1
emit(flag_strb(17, 16, TITLE_FLAG))
emit(flag_strb(31, 16, SKIPPED))
emit(str_x(31, 16, LOGO_VIEW & 0xFFF))
emit(struct.unpack_from("<I", image, 0xF144)[0])
emit(b(pc(), 0xF148))
mark("title_off")
emit(adrp(pc(), 16, TITLE_FLAG))
emit(flag_strb(31, 16, TITLE_FLAG))
emit(str_x(31, 16, LOGO_VIEW & 0xFFF))
emit(struct.unpack_from("<I", image, 0xE580)[0])
emit(b(pc(), 0xE584))

# --- Option gates for sites that had no cave of their own.
mark("heap_pick")                 # encounter object's heap; also the moment we refresh the option
sync_off()
load_off()
emit(cbz(pc(), pc() + 12, 16))
emit(ldr(20, 8, 0x248))
emit(b(pc(), 0x3057BC))
emit(ldr(20, 8, 0x68))
emit(b(pc(), 0x3057BC))

mark("event_sync")                # battle-then-catch event from a script: refresh too
sync_off()
emit(b(pc(), 0x28BC40))

mark("encounter_start")
load_off()
emit(cbz(pc(), pc() + 8, 16))
emit(b(pc(), 0x2F6470))
emit(b(pc(), marks["start_battle"]))

mark("post_catch")                # the original follow-up only belongs to the normal catch flow
load_off()
emit(cbz(pc(), pc() + 8, 16))
emit(b(pc(), 0x305970))
emit(RET)

mark("tier")
load_off()
emit(0x52000218)                  # eor w24, w16, #1
emit(b(pc(), 0x319FF8))

mark("state8")
load_off()
emit(cbz(pc(), pc() + 12, 16))
emit(0xB9006A68)                  # str w8, [x19, #0x68]
emit(b(pc(), 0x28BE90))
emit(b(pc(), 0x28BE94))

mark("fade")
emit(0x52800143)                  # mov w3, #0xa
load_off()
emit(cbz(pc(), pc() + 8, 16))
emit(0x52800043)                  # mov w3, #2
emit(b(pc(), 0x28C1A4))

mark("timer")
emit(0x52802588)                  # mov w8, #0x12c
load_off()
emit(cbz(pc(), pc() + 8, 16, nz=True))
emit(0x52800008)                  # mov w8, #0
emit(b(pc(), 0x28C898))

mark("exp_a")
load_off()
emit(cbz(pc(), pc() + 8, 16, nz=True))
emit(b(pc(), 0x9D8A58))
emit(cbz(pc(), pc() + 8, 9))
emit(b(pc(), 0x9D8A48))
emit(b(pc(), 0x9D8A58))

mark("exp_b")
load_off()
emit(cbz(pc(), pc() + 8, 16))
emit(0x37380000 | (2 << 5) | 8)   # tbnz w8, #7, to the next branch
emit(b(pc(), 0x9D8A60))
emit(b(pc(), 0x9D8A6C))

mark("evo_start")
load_off()
emit(cbz(pc(), pc() + 16, 16, nz=True))
emit(0x52800088)                  # mov w8, #4
emit(0x1A9F1508)                  # csinc w8, w8, wzr, ne
emit(b(pc(), 0x319EBC))
emit(struct.unpack_from("<I", image, 0x319EB4)[0])  # the original two instructions
emit(struct.unpack_from("<I", image, 0x319EB8)[0])
emit(b(pc(), 0x319EBC))

blob = b"".join(struct.pack("<I", w) for w in code)
assert CAVE + len(blob) <= LIMIT, hex(CAVE + len(blob))


def site(addr, want, word):
    got = dec(image[addr:addr + 4], addr)[0]
    assert got == want, (hex(addr), got, want)
    return addr, struct.pack("<I", word)


edits = [
    # Encounters start a battle rather than the catch app. Details object comes from the field heap, as the event outlives the app heap.
    site(0x3057B8, "ldr x20, [x8, #0x248]", b(0x3057B8, marks["heap_pick"])),
    site(0x289B80, "bl #0x28bc40", bl(0x289B80, marks["event_sync"])),
    site(0x305934, "bl #0x2f6470", bl(0x305934, marks["encounter_start"])),
    site(0x2FDF34, "bl #0x305970", bl(0x2FDF34, marks["post_catch"])),
    site(0x2FDF80, "bl #0x305970", bl(0x2FDF80, marks["post_catch"])),
    site(0x319FF4, "mov w24, wzr", b(0x319FF4, marks["tier"])),
    site(0x28BE8C, "str w8, [x19, #0x68]", b(0x28BE8C, marks["state8"])),
    site(0x28C1A0, "mov w3, #2", b(0x28C1A0, marks["fade"])),
    site(0x28CB10, "mov w2, #0xa", b(0x28CB10, marks["intro"])),
    site(0x28BF1C, "cbz x20, #0x28c1ac", b(0x28BF1C, marks["after_loss"])),
    # No timer.
    site(0x28C894, "mov w8, #0x12c", b(0x28C894, marks["timer"])),
    # EXP on a win.
    site(0x9D8A44, "cbz w9, #0x9d8a58", b(0x9D8A44, marks["exp_a"])),
    site(0x9D8A5C, "tbnz w8, #7, #0x9d8a6c", b(0x9D8A5C, marks["exp_b"])),
    # Catch EXP after a ball-skip only.
    site(0x830074, "bl #0x830410", bl(0x830074, marks["catch_exp_eligible"])),
    site(0x830828, "bl #0x82d3f0", bl(0x830828, marks["catch_exp_amount"])),
    site(0x8315E4, "bl #0x82d3f0", bl(0x8315E4, marks["catch_exp_amount"])),
    # Evolution after a win; catch only after a ball.
    site(0x319EB4, "mov w8, #3", b(0x319EB4, marks["evo_start"])),
    site(0x319DA4, "mov w8, #4", b(0x319DA4, marks["after_evolution"])),
    # Early saves.
    site(0xA993E0, "ldur x0, [x29, #-0x48]", b(0xA993E0, marks["early_save"])),
    # Ball from the Bag.
    site(0xA0FB90, "bl #0xa10e30", bl(0xA0FB90, marks["ball"])),
    site(0x28BDB8, "adrp x21, #0x15fa000", b(0x28BDB8, marks["battle_start"])),
    site(0xD2D7C4, "ldrb w8, [x8, w1, uxtw]", b(0xD2D7C4, marks["bag_filter"])),
]

edits.append(site(0x7E5F00, "str x21, [sp, #-0x30]!", b(0x7E5F00, marks["start_ball"])))
# Intro skip on + / -.
edits.append(site(0x202F44, "bl #0x36be40", bl(0x202F44, marks["layout_play"])))
edits.append(site(0x1DDE9C, "bl #0x1f1d20", bl(0x1DDE9C, marks["title_skip"])))
edits.append(site(0xF144, "mov x8, #0x2645", b(0xF144, marks["title_on"])))
edits.append(site(0xE580, "ldr w8, [x19, #0xf8]", b(0xE580, marks["title_off"])))
edits.append(site(0x9D3860, "str w20, [x8, #0x508]", b(0x9D3860, marks["result_a"])))
edits.append(site(0x9DA378, "str w0, [x8, #0x508]", b(0x9DA378, marks["result_b"])))
edits.append((CAVE, blob))

# --- Options row "Enable Wild Battle": lives in the padding after the code section. Not on Japanese, which needs this row.
# The choice is bit 31 of the saved settings word (+0x54): 0 = on, so existing saves start on.
TAIL = 0xD32BB0
TAIL_END = 0xD33000
assert not any(image[0xD32BA8:TAIL_END])
tail = []
tail_marks = {}
LANG_GOT = 0x15FAEF0


def tpc():
    return TAIL + len(tail) * 4


def tmark(name):
    tail_marks[name] = tpc()


def not_japanese_else(target):
    """Falls through on any language but Japanese; on Japanese, branches to the original function."""
    tail.append(adrp(tpc(), 9, LANG_GOT))
    tail.append(ldr(9, 9, LANG_GOT & 0xFFF))
    tail.append(ldr(9, 9, 0))
    tail.append(0x39414129)       # ldrb w9, [x9, #0x50]
    tail.append(0x7100053F)       # cmp w9, #1
    at = tpc()
    tail.append(0x54000041)       # b.ne, over the branch
    tail.append(b(at + 4, target))


# x0 = save settings. Read our bit where the screen asks for its Characters value.
tmark("wild_get")
not_japanese_else(0x1C35A0)
tail.append(0xB9405400)           # ldr w0, [x0, #0x54]
tail.append(0x531F7C00)           # lsr w0, w0, #31
tail.append(RET)

# Apply step, x0 = save settings, x8 = screen values: store our bit and report no change, so no language work runs.
tmark("wild_apply")
not_japanese_else(0x1C35A0)
tail.append(0x39405509)           # ldrb w9, [x8, #0x15]
tail.append(0xB940540A)           # ldr w10, [x0, #0x54]
tail.append(0x3301012A)           # bfi w10, w9, #31, #1
tail.append(0xB900540A)           # str w10, [x0, #0x54]
tail.append(0x2A0903E0)           # mov w0, w9
tail.append(RET)

# The Characters setter is skipped.
tmark("wild_set")
not_japanese_else(0x1C3550)
tail.append(RET)

# Text lookup, x1 = &label hash, x2 = output. Our four labels are written directly.
tmark("wild_text")
not_japanese_else_at = tpc()
tail.append(adrp(tpc(), 9, LANG_GOT))
tail.append(ldr(9, 9, LANG_GOT & 0xFFF))
tail.append(ldr(9, 9, 0))
tail.append(0x39414129)           # ldrb w9, [x9, #0x50]
tail.append(0x7100053F)           # cmp w9, #1
orig_slot_a = len(tail)
tail.append(0)                    # b.eq original
tail.append(ldr(9, 1, 0))
table_slot = len(tail)
tail.append(0)                    # adr x10, table
loop_at = tpc()
tail.append(ldr(11, 10, 0))
orig_slot_b = len(tail)
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
tail.append(0xB9400954)           # ldr w20, [x10, #8]
tail.append(0x8B140154)           # add x20, x10, x20
tail.append(0xB9400D55)           # ldr w21, [x10, #0xc]
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(bl(tpc(), 0x3A860))
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(bl(tpc(), 0x3AA40))
char_at = tpc()
tail.append(0x78402681)           # ldrh w1, [x20], #2
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(bl(tpc(), 0x3A9A0))
tail.append(0x710006B5)           # subs w21, w21, #1
tail.append(0x54000001 | (((char_at - tpc()) >> 2 & 0x7FFFF) << 5))  # b.ne
tail.append(0xAA1303E0)           # mov x0, x19
tail.append(bl(tpc(), 0x3AA10))
tail.append(MOV_W0_ZERO)
tail.append(0xF94013F5)           # ldr x21, [sp, #0x20]
tail.append(0xA94153F3)           # ldp x19, x20, [sp, #0x10]
tail.append(0xA8C47BFD)           # ldp x29, x30, [sp], #0x40
tail.append(RET)
orig = tpc()
tail.append(struct.unpack_from("<I", image, 0x678710)[0])
tail.append(b(tpc(), 0x678714))

at = TAIL + orig_slot_a * 4
tail[orig_slot_a] = 0x54000000 | (((orig - at) >> 2) << 5)            # b.eq original
at = TAIL + orig_slot_b * 4
tail[orig_slot_b] = cbz(at, orig, 11, wide=True)
at = TAIL + match_slot * 4
tail[match_slot] = 0x54000000 | (((match - at) >> 2) << 5)            # b.eq match

STRINGS = [
    (0xF889F9ACB608BD95, "Enable Wild Battle"),
    (0xB47AA6D4ACE0ED81, "On"),
    (0xB47AA3D4ACE0E868, "Off"),
    (0x72DC9B7C22B155DE, "Battle wild Pok\u00e9mon before catching them.\nTurn this off for the game\u2019s normal catching."),
]
table_at = tpc()
at = TAIL + table_slot * 4
delta = table_at - at
tail[table_slot] = 0x10000000 | ((delta & 3) << 29) | (((delta >> 2) & 0x7FFFF) << 5) | 10   # adr x10, table
text_at = table_at + (len(STRINGS) + 1) * 16
words = []
pool = bytearray()
for i, (h, t) in enumerate(STRINGS):
    entry = table_at + i * 16
    enc = t.encode("utf-16-le")
    words.append(struct.pack("<QII", h, text_at + len(pool) - entry, len(t)))
    pool += enc
words.append(bytes(16))
tail_code = b"".join(struct.pack("<I", w) for w in tail)
tail_blob = tail_code + b"".join(words) + bytes(pool)
assert TAIL + len(tail_blob) <= TAIL_END, hex(TAIL + len(tail_blob))

edits.append(site(0x426DC, "tbz w0, #0, #0x426fc", 0x36000000 | (((0x426F0 - 0x426DC) >> 2) << 5)))
edits.append(site(0x3B2BC, "bl #0x1c35a0", bl(0x3B2BC, tail_marks["wild_get"])))
edits.append(site(0x3B3B8, "bl #0x1c35a0", bl(0x3B3B8, tail_marks["wild_apply"])))
edits.append(site(0x3B3D4, "bl #0x1c35a0", bl(0x3B3D4, tail_marks["wild_get"])))
edits.append(site(0x3F4AC, "bl #0x1c35a0", bl(0x3F4AC, tail_marks["wild_get"])))
edits.append(site(0x3F4E4, "bl #0x1c35a0", bl(0x3F4E4, tail_marks["wild_get"])))
edits.append(site(0x3B450, "bl #0x1c3550", bl(0x3B450, tail_marks["wild_set"])))
edits.append(site(0x678710, "stp x20, x19, [sp, #-0x20]!", b(0x678710, tail_marks["wild_text"])))
edits.append((TAIL, tail_blob))

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

out = bytearray(b"PATCH")
for addr, data in edits:
    if addr == CAVE:
        continue
    print(f"{addr:08X}  {dec(data[:4], addr)[0]}")
    out += (addr + SIZE_HEADER).to_bytes(3, "big") + len(data).to_bytes(2, "big") + data
out += (CAVE + SIZE_HEADER).to_bytes(3, "big") + len(blob).to_bytes(2, "big") + blob + b"EOF"

print()
names = {v: k for k, v in marks.items()}
listing = list(md.disasm(blob, CAVE))
assert len(listing) == len(code), "a word did not decode"
for ins in listing:
    if ins.address in names:
        print(f"-- {names[ins.address]}")
    print(f"{ins.address:08X}  {ins.mnemonic} {ins.op_str}")
open(sys.argv[2], "wb").write(out)
print("\nwrote", len(out), "bytes; cave ends", hex(CAVE + len(blob)))
