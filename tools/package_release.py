"""Zip a built patch so it unzips straight onto the root of an SD card.
Args: patch_ips out_zip [pikachu|eevee] (default pikachu)
Both games' patches use the same folder; Atmosphere picks the file by the game's build ID, so the two zips can share an SD card."""
import os
import sys
import zipfile

BUILD_IDS = {
    "pikachu": "C208DB6A4EF4361F28B8402BE0F7CD9A",
    "eevee": "5831EC64D6B696FD69E69505821B97B1",
}
FOLDER = "the_better_lets_go"

patch, out = sys.argv[1], sys.argv[2]
game = sys.argv[3] if len(sys.argv) > 3 else "pikachu"
name = f"atmosphere/exefs_patches/{FOLDER}/{BUILD_IDS[game]}{'0' * 32}.ips"
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(patch, name)
print(out, name)
