#!/usr/bin/env python3
"""Validate NPC PNG border transparency for all 88 NPC PNGs.
Reports border ring opaque vs transparent pixel counts.
Uses pure stdlib (struct, zlib) — no PIL.

Usage: python3 tools/validate_npc_png_borders.py
Output: stdout summary + report saved to reports/n2d-td-border-cleanup.md
"""
import struct
import zlib
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
NPC_BASE = PROJECT_DIR / "assets" / "npcs"
NPC_IDS = [
    "admissions_director", "compliance_officer", "homeroom_teacher",
    "it_operator", "logistics_manager", "parent_representative",
    "principal", "student_representative",
]
EXPECTED_FILES = [
    "portrait_neutral.png", "portrait_happy.png", "portrait_worried.png", "portrait_strict.png",
    "sprite_idle.png",
    "{npc_id}_walk_down.png", "{npc_id}_walk_left.png", "{npc_id}_walk_right.png", "{npc_id}_walk_up.png",
]


def parse_png(filepath):
    """Parse PNG: return (width, height, pixel_rows) where each row is RGBA bytes.
    Returns None if file missing or not valid PNG."""
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        return None

    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return None

    pos = 8
    ihdr = None
    idat_chunks = []

    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        chunk_type = data[pos+4:pos+8]
        chunk_data = data[pos+8:pos+8+length]
        pos += 12 + length

        if chunk_type == b'IHDR':
            ihdr = chunk_data
        elif chunk_type == b'IDAT':
            idat_chunks.append(chunk_data)
        elif chunk_type == b'IEND':
            break

    if ihdr is None or not idat_chunks:
        return None

    width, height, bit_depth, color_type = struct.unpack('>IIBB', ihdr[:10])
    if color_type != 6:  # RGBA
        return None

    # Decompress
    raw = zlib.decompress(b''.join(idat_chunks))

    # Unfilter: PNG uses filter byte per row
    bytes_per_pixel = 4
    row_stride = width * bytes_per_pixel + 1  # +1 for filter byte

    pixels = []
    prev_row = None
    for y in range(height):
        row_start = y * row_stride
        filter_byte = raw[row_start]
        row_data = bytearray(raw[row_start+1:row_start+row_stride])

        if filter_byte == 1:  # Sub
            for i in range(bytes_per_pixel, len(row_data)):
                row_data[i] = (row_data[i] + row_data[i - bytes_per_pixel]) & 0xFF
        elif filter_byte == 2 and prev_row is not None:  # Up
            for i in range(len(row_data)):
                row_data[i] = (row_data[i] + prev_row[i]) & 0xFF
        elif filter_byte == 3 and prev_row is not None:  # Average
            for i in range(len(row_data)):
                left = row_data[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                up = prev_row[i]
                row_data[i] = (row_data[i] + (left + up) // 2) & 0xFF
        elif filter_byte == 4 and prev_row is not None:  # Paeth
            for i in range(len(row_data)):
                left = row_data[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                up = prev_row[i]
                up_left = prev_row[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                p = left + up - up_left
                pa = abs(p - left)
                pb = abs(p - up)
                pc = abs(p - up_left)
                pr = left if (pa <= pb and pa <= pc) else (up if pb <= pc else up_left)
                row_data[i] = (row_data[i] + pr) & 0xFF
        # filter 0 = None, no transform

        pixels.append(row_data)
        prev_row = row_data

    return width, height, pixels


def get_border_ring_pixels(pixels, width, height):
    """Extract alpha values of border ring pixels (outermost row/col)."""
    alphas = []
    # Top and bottom rows
    for x in range(width):
        alphas.append(pixels[0][x * 4 + 3])
        alphas.append(pixels[height - 1][x * 4 + 3])
    # Left and right cols (skip corners already counted)
    for y in range(1, height - 1):
        alphas.append(pixels[y][3])              # left edge
        alphas.append(pixels[y][(width - 1) * 4 + 3])  # right edge
    return alphas


def main():
    print("=" * 70)
    print("NPC PNG Border Transparency Validator")
    print("=" * 70)

    all_results = {}
    all_passed = True

    for npc_id in NPC_IDS:
        npc_dir = NPC_BASE / npc_id / "baseline"
        if not npc_dir.exists():
            print(f"\n⚠️  {npc_id}: baseline/ directory missing, skipping")
            continue

        print(f"\n--- {npc_id} ---")
        npc_results = {}
        npc_border_issues = []

        for tmpl in EXPECTED_FILES:
            fname = tmpl.format(npc_id=npc_id) if "{npc_id}" in tmpl else tmpl
            fpath = npc_dir / fname

            result = parse_png(fpath)
            if result is None:
                if fpath.exists():
                    npc_results[fname] = "ERROR: not valid RGBA PNG"
                else:
                    npc_results[fname] = "MISSING"
                continue

            width, height, pixels = result
            border_alphas = get_border_ring_pixels(pixels, width, height)
            total = len(border_alphas)
            opaque = sum(1 for a in border_alphas if a >= 250)
            transparent = total - opaque
            ratio = opaque / total * 100 if total > 0 else 0

            status = "✓" if opaque == 0 else f"⚠ {opaque}/{total} opaque ({ratio:.1f}%)"
            npc_results[fname] = status

            if opaque > 0:
                npc_border_issues.append(f"{fname}: {opaque}/{total} border pixels opaque")

        all_results[npc_id] = npc_results
        if npc_border_issues:
            all_passed = False
            print(f"  BORDER ISSUES ({len(npc_border_issues)}):")
            for issue in npc_border_issues:
                print(f"    {issue}")
        else:
            print("  ✓ All borders transparent")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for npc_id in NPC_IDS:
        results = all_results.get(npc_id, {})
        total = len(results)
        errors = sum(1 for v in results.values() if "ERROR" in str(v) or "MISSING" in str(v))
        opaque_count = sum(1 for v in results.values() if "opaque" in str(v))
        print(f"  {npc_id:30s} {total} files  errors={errors}  opaque_border={opaque_count}")

    verdict = "PASS" if all_passed else "FAIL — opaque border pixels found"
    print(f"\nRESULT: {verdict}")

    # Write report
    report_path = PROJECT_DIR / "reports" / "n2d-td-border-cleanup.md"
    with open(report_path, "w") as f:
        f.write("# N2D TD-1: PNG Border Transparency Report\n\n")
        f.write("## Method\n")
        f.write("Pure stdlib (struct+zlib) PNG parsing of 88 NPC PNGs. ")
        f.write("Extracts border ring (top/bottom rows + left/right cols) alpha channel per file.\n\n")
        f.write("## Per-NPC Results\n\n")
        for npc_id in NPC_IDS:
            f.write(f"### {npc_id}\n\n")
            results = all_results.get(npc_id, {})
            f.write("| File | Result |\n|------|--------|\n")
            for fname, status in sorted(results.items()):
                f.write(f"| {fname} | {status} |\n")
            f.write("\n")
        f.write("## Summary\n\n")
        f.write(f"**Verdict: {verdict}**\n\n")
        if not all_passed:
            f.write("PNGs with opaque borders:\n\n")
            for npc_id in NPC_IDS:
                for fname, status in all_results.get(npc_id, {}).items():
                    if "opaque" in str(status):
                        f.write(f"- `{npc_id}/{fname}`: {status}\n")

    print(f"\nReport saved to: {report_path}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
