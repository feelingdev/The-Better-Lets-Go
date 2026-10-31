"""Zip a built patch so it unzips straight onto the root of an SD card.
Args: patch_ips out_zip"""
import os
import sys
import zipfile

BUILD_ID = "C208DB6A4EF4361F28B8402BE0F7CD9A"
FOLDER = "the_better_lets_go"

patch, out = sys.argv[1], sys.argv[2]
name = f"atmosphere/exefs_patches/{FOLDER}/{BUILD_ID}{'0' * 32}.ips"
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(patch, name)
print(out, name)
