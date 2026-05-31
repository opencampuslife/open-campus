#!/usr/bin/env python3
"""
make_border_transparent.py
Apply two-phase border transparency to any PNG (RGB or RGBA):
  Phase 1: Near-white pixels (R≥240 AND G≥240 AND B≥240) → alpha=0
  Phase 2: Remaining border pixels with alpha≥1 → alpha=0
Output is always RGBA PNG.

Usage: python3 make_border_transparent.py <input.png> <output.png>
"""

import struct, zlib, os, sys

def _paeth(a, b, c):
    p = a + b - c
    pa = abs(p-a) if p >= a else a-p
    pb = abs(p-b) if p >= b else b-p
    pc = abs(p-c) if p >= c else c-p
    return a if pa<=pb and pa<=pc else (b if pb<=pc else c)


def read_png_rows(filepath):
    """Read PNG → (w, h, rows: list[list[(R,G,B,A)]])."""
    with open(filepath, 'rb') as f:
        data = f.read()

    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f"Not PNG: {filepath}")

    # Find width/height from raw bytes
    ihdr_idx = data.find(b'IHDR')
    w = struct.unpack('>I', data[ihdr_idx+4 : ihdr_idx+8])[0]
    h = struct.unpack('>I', data[ihdr_idx+8 : ihdr_idx+12])[0]

    # Parse IDAT
    pos = 8
    idat = b''
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        ctype = data[pos+4:pos+8]
        if ctype == b'IDAT':  idat += data[pos+8:pos+8+length]
        elif ctype == b'IEND': break
        pos += 12 + length

    raw = zlib.decompress(idat)

    # Auto-detect bpp from raw size
    expected_rgba = h * (1 + w*4)
    expected_rgb  = h * (1 + w*3)
    ratio = len(raw) / expected_rgba
    if ratio >= 0.95:
        bpp = 4; color_type = 6
    else:
        bpp = 3; color_type = 2

    stride = w * bpp
    rows = []
    prev = bytearray(stride)

    for y in range(h):
        start = y * (stride + 1)
        ftype = raw[start]
        row = bytearray(raw[start+1 : start+1+stride])

        if ftype == 0:  pass
        elif ftype == 1:
            decoded = bytearray(stride)
            for i in range(stride):
                left = decoded[i-bpp] if i >= bpp else 0
                decoded[i] = (row[i] + left) & 0xff
            row = decoded
        elif ftype == 2:
            for i in range(stride): row[i] = (row[i] + prev[i]) & 0xff
        elif ftype == 3:
            decoded = bytearray(stride)
            for i in range(stride):
                left = decoded[i-bpp] if i >= bpp else 0
                decoded[i] = (row[i] + ((left + prev[i]) >> 1)) & 0xff
            row = decoded
        elif ftype == 4:
            decoded = bytearray(stride)
            for i in range(stride):
                left = decoded[i-bpp] if i >= bpp else 0
                ul   = prev[i-bpp]    if i >= bpp else 0
                decoded[i] = (row[i] + _paeth(left, prev[i], ul)) & 0xff
            row = decoded

        prev = bytearray(row)

        if color_type == 6:   # RGBA → keep
            rows.append([tuple(row[i:i+4]) for i in range(0, stride, 4)])
        else:                 # RGB → RGBA
            rows.append([(row[i], row[i+1], row[i+2], 255) for i in range(0, stride, 3)])

    return w, h, rows


def write_rgba_png(rows, w, h, path):
    def chunk(ctype, data):
        crc = zlib.crc32(ctype + data) & 0xffffffff
        return struct.pack('>I', len(data)) + ctype + data + struct.pack('>I', crc)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    raw_rows = b''.join(b'\x00' + b''.join(bytes(p) for p in row) for row in rows)
    png_bytes = (sig
                 + chunk(b'IHDR', b'IHDR' + ihdr_data)
                 + chunk(b'IDAT', zlib.compress(raw_rows, 6))
                 + chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png_bytes)
    print(f"  Written: {os.path.getsize(path):,} bytes")


def make_border_transparent(input_path, output_path, threshold=240):
    """Two-phase: near-white → alpha=0, then border alpha>=1 → alpha=0."""
    print(f"Input:  {input_path}")
    w, h, rows = read_png_rows(input_path)
    print(f"  Decoded: {w}x{h}")

    # ── Phase 1: near-white → transparent ───────────────────────────────────
    for ri in range(h):
        rows[ri] = [
            (r, g, b, 0) if (r >= threshold and g >= threshold and b >= threshold) else (r, g, b, a)
            for r, g, b, a in rows[ri]
        ]

    # Border stats after Phase 1
    border = []
    for x in range(w):
        border.append(rows[0][x][3])
        border.append(rows[h-1][x][3])
    for y in range(1, h-1):
        border.extend([rows[y][0][3], rows[y][w-1][3]])
    opaque1 = sum(1 for a in border if a == 255)
    trans1  = sum(1 for a in border if a == 0)
    semi1   = sum(1 for a in border if 0 < a < 255)
    non_zero1 = [a for a in border if a > 0]
    min_a1 = min(non_zero1) if non_zero1 else 0
    print(f"  Phase 1 (near-white): opaque=255:{opaque1}  semi:{semi1}  trans=0:{trans1}  min_alpha={min_a1}")

    # ── Phase 2: aggressive border clear ─────────────────────────────────────
    if opaque1 > 0:
        # Clear ALL remaining border pixels with alpha ≥ 1 (not just ≥ min+1)
        thresh = 1   # clear anything that has any opacity
        print(f"  Phase 2: clearing remaining border pixels with alpha >= {thresh}")
        for x in range(w):
            r, g, b, a = rows[0][x]
            if a >= thresh: rows[0][x] = (r, g, b, 0)
            r, g, b, a = rows[h-1][x]
            if a >= thresh: rows[h-1][x] = (r, g, b, 0)
        for y in range(1, h-1):
            r, g, b, a = rows[y][0]
            if a >= thresh: rows[y][0] = (r, g, b, 0)
            r, g, b, a = rows[y][w-1]
            if a >= thresh: rows[y][w-1] = (r, g, b, 0)

    # Final stats
    border2 = []
    for x in range(w):
        border2.append(rows[0][x][3])
        border2.append(rows[h-1][x][3])
    for y in range(1, h-1):
        border2.extend([rows[y][0][3], rows[y][w-1][3]])
    opaque2 = sum(1 for a in border2 if a == 255)
    trans2  = sum(1 for a in border2 if a == 0)
    semi2   = sum(1 for a in border2 if 0 < a < 255)
    print(f"  After:           opaque=255:{opaque2}  semi:{semi2}  trans=0:{trans2}")

    write_rgba_png(rows, w, h, output_path)


if __name__ == '__main__':
    if len(sys.argv) == 3:
        make_border_transparent(sys.argv[1], sys.argv[2])
    else:
        print(f"Usage: {sys.argv[0]} <input.png> <output.png>")
        sys.exit(1)