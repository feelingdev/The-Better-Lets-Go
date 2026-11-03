"""Map every game address build_patch.py uses from Let's Go, Pikachu! 1.0.2 to Let's Go, Eevee! 1.0.2, and write
address_map_eevee.py. Only needed when build_patch.py starts using a new address; building needs just the one game.

The two games have the same code, shifted by small amounts that change from place to place. A code address is found by
matching the instructions around it, with everything that depends on where things are (branches, adrp and the low 12 bits
that pair with it) masked out. The match must be unique, and the instruction itself must be the same apart from addresses.
A data address is found through code that refers to it: the referring instruction is mapped, and its target read in Eevee.

Args: pikachu_main eevee_main (decompressed, 0x100-byte header attached)
"""
import os
import struct
import subprocess
import sys
import tempfile

from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs

HERE = os.path.dirname(os.path.abspath(__file__))
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)


def load(path):
    raw = open(path, "rb").read()
    text_size = struct.unpack_from("<I", raw, 0x18)[0]
    return raw[0x100:], text_size


pk, pk_text = load(sys.argv[1])
ev, ev_text = load(sys.argv[2])


def mask_word(w):
    if (w & 0x7C000000) == 0x14000000:          # b, bl
        return w & 0xFC000000
    if (w & 0x1F000000) == 0x10000000:          # adr, adrp
        return w & 0x9F00001F
    if (w & 0xFF000010) == 0x54000000:          # b.cond
        return w & 0xFF00001F
    if (w & 0x7E000000) in (0x34000000, 0x36000000):   # cbz, cbnz, tbz, tbnz
        return w & 0xFFF8001F if w & 0x02000000 else w & 0xFF00001F
    if (w & 0x3B000000) == 0x18000000:          # ldr literal
        return w & 0xFF00001F
    if (w & 0x7F800000) == 0x11000000:          # add immediate, 64-bit or 32-bit
        return w & 0xFFC003FF
    if (w & 0x3B000000) == 0x39000000:          # load or store, unsigned offset
        return w & 0xFFC003FF
    return w


def masked(image, end):
    words = struct.unpack_from(f"<{end // 4}I", image, 0)
    return struct.pack(f"<{len(words)}I", *(mask_word(w) for w in words))


pk_m = masked(pk, pk_text)
ev_m = masked(ev, ev_text)
SEARCH = 0x40000
WINDOWS = ((8, 8), (16, 16), (4, 12), (12, 4), (0, 16), (16, 0), (32, 32), (4, 4), (0, 8), (8, 0), (64, 64))


def same_instruction(a, b):
    """The same instruction, apart from addresses."""
    ia = next(md.disasm(pk[a:a + 4], a), None)
    ib = next(md.disasm(ev[b:b + 4], b), None)
    if ia is None or ib is None:
        return pk[a:a + 4] == ev[b:b + 4]
    return ia.mnemonic == ib.mnemonic and (mask_word(struct.unpack_from("<I", pk, a)[0])
                                           == mask_word(struct.unpack_from("<I", ev, b)[0]))


def map_code(addr):
    found = set()
    for before, after in WINDOWS:
        start = addr - before * 4
        pattern = pk_m[start:addr + (after + 1) * 4]
        lo = max(0, start - SEARCH)
        hits = []
        at = ev_m.find(pattern, lo, start + SEARCH + len(pattern))
        while at != -1 and len(hits) < 2:
            if at % 4 == 0:
                hits.append(at)
            at = ev_m.find(pattern, at + 1, start + SEARCH + len(pattern))
        if len(hits) == 1:
            found.add(hits[0] + before * 4)
    assert len(found) == 1, f"{addr:#x}: no single match {sorted(map(hex, found))}"
    result = found.pop()
    assert same_instruction(addr, result), f"{addr:#x} -> {result:#x}: different instruction"
    return result


def targets(image, end):
    """Every adrp-based address the code forms, as {address: [instruction address, ...]}: the adrp page alone, and page plus the
    low 12 bits of the next add or load/store on the same register within 8 instructions."""
    out = {}
    words = struct.unpack_from(f"<{end // 4}I", image, 0)
    for i, w in enumerate(words):
        if (w & 0x9F000000) != 0x90000000:
            continue
        pc = i * 4
        imm = ((w >> 29) & 3) | (((w >> 5) & 0x7FFFF) << 2)
        if imm & (1 << 20):
            imm -= 1 << 21
        page = (pc & ~0xFFF) + (imm << 12)
        reg = w & 0x1F
        out.setdefault(page, []).append(pc)
        for j in range(i + 1, min(i + 9, len(words))):
            u = words[j]
            if (u >> 5) & 0x1F != reg:
                continue
            if (u & 0x7F800000) == 0x11000000:
                lo = (u >> 10) & 0xFFF
            elif (u & 0x3B000000) == 0x39000000:
                lo = ((u >> 10) & 0xFFF) << (u >> 30)
            else:
                continue
            out.setdefault(page + lo, []).append(pc)
            break
    return out


pk_targets = targets(pk, pk_text)
ev_targets = targets(ev, ev_text)
ev_by_ref = {}
for target, refs in ev_targets.items():
    for ref in refs:
        ev_by_ref.setdefault(ref, set()).add(target)


def map_data(addr):
    if addr not in pk_targets:
        # reached as a field of a nearby base address, such as 0x1614B30 + 4
        bases = [t for t in pk_targets if addr - 0x40 <= t < addr and t & 0xFFF]
        assert bases, f"{addr:#x}: no code refers to it"
        base = max(bases)
        return map_data(base) + addr - base
    refs = pk_targets[addr]
    pk_pages = set()
    answers = {}
    for ref in refs[:12]:
        try:
            e_ref = map_code(ref)
        except AssertionError:
            continue
        # the Eevee adrp at the mapped instruction forms the same kind of address: page alone, or page plus low bits
        cand = ev_by_ref.get(e_ref, set())
        want_page_only = (addr & 0xFFF) == 0 and addr in pk_targets and ref in pk_targets[addr]
        pick = [t for t in cand if (t & 0xFFF) == (addr & 0xFFF)] if not want_page_only else [t for t in cand if t & 0xFFF == 0]
        if len(pick) == 1:
            answers[pick[0]] = answers.get(pick[0], 0) + 1
    assert len(answers) == 1, f"{addr:#x}: references disagree {answers}"
    result, votes = answers.popitem()
    assert votes >= 1
    return result


# Which addresses: whatever a Pikachu build asks A() for.
record = os.path.join(tempfile.gettempdir(), "tblg_addresses.txt")
env = dict(os.environ, TBLG_RECORD=record)
subprocess.run([sys.executable, os.path.join(HERE, "build_patch.py"), sys.argv[1], os.devnull], env=env, check=True,
               stdout=subprocess.DEVNULL)
wanted = [int(line, 16) for line in open(record) if line.strip()]

mapping = {}
for addr in wanted:
    mapping[addr] = map_code(addr) if addr < pk_text else map_data(addr)

# The cave must stay one piece of the same size, and padding past both games' code is free.
lines = ['"""Let\'s Go, Pikachu! 1.0.2 address -> Let\'s Go, Eevee! 1.0.2 address. Made by make_address_map.py; don\'t edit."""',
         "ADDRESSES = {"]
for addr in sorted(mapping):
    lines.append(f"    {addr:#09x}: {mapping[addr]:#09x},   # {mapping[addr] - addr:+#x}")
lines.append("}")
open(os.path.join(HERE, "address_map_eevee.py"), "w", newline="\n").write("\n".join(lines) + "\n")
deltas = sorted(set(mapping[a] - a for a in mapping))
print(len(mapping), "addresses; shifts", [hex(d) for d in deltas])
