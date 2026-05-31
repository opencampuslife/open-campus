#!/usr/bin/env python3
"""
add_transparency.py
Convert any PNG (RGB or RGBA) to RGBA PNG, making near-white pixels
(R≥240 AND G≥240 AND B≥240) fully transparent (A=0).
Pure stdlib: struct + zlib only, no PIL.
"""

import struct, zlib, sys, os

def _paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a) if p >= a else a - p
    pb = abs(p - b) if p >= b else b - p
    pc = abs(p - c) if p >= c else c - p
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)

def read_png_pixels(filepath):
    """Read PNG, return (w, h, rows: list[list[tuple]]) in RGBA 8-bit format."""
    with open(filepath, 'rb') as f:
        data = f.read()

    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f"Not a PNG: {filepath}")

    # Find IHDR
    ihdr_idx = data.find(b'IHDR')
    if ihdr_idx < 0:
        raise ValueError(f"No IHDR in {filepath}")
    w = struct.unpack('>I', data[ihdr_idx+4:ihdr_idx+8])[0]
    h = struct.unpack('>I', data[ihdr_idx+8:ihdr_idx+12])[0]
    bit_depth = data[ihdr_idx+12]
    color_type = data[ihdr_idx+13]

    if bit_depth != 8:
        raise ValueError(f"Unsupported bit_depth={bit_depth}: {filepath}")
    if color_type not in (2, 6):
        raise ValueError(f"Unsupported color_type={color_type}: {filepath}")

    # Collect IDAT
    pos = 8
    idat = b''
    while pos < len(data):
        if pos + 8 > len(data):
            break
        length = struct.unpack('>I', data[pos:pos+4])[0]
        ctype = data[pos+4:pos+8]
        if ctype == b'IDAT':
            idat += data[pos+8:pos+8+length]
        pos += 12 + length
        if ctype == b'IEND':
            break

    raw = zlib.decompress(idat)

    # bytes per pixel
    if color_type == 2:   # RGB
        bpp = 3
    else:                 # RGBA
        bpp = 4

    stride = w * bpp
    rows = []
    prev = bytearray(stride)

    for y in range(h):
        start = y * (stride + 1)
        ftype = raw[start]
        row = bytearray(raw[start+1 : start+1+stride])

        if ftype == 1:   # Sub
            for i in range(stride):
                left = row[i-bpp] if i >= bpp else 0
                row[i] = (row[i] + left) & 0xff
        elif ftype == 2:   # Up
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 0xff
        elif ftype == 3:   # Average
            for i in range(stride):
                left = row[i-bpp] if i >= bpp else 0
                row[i] = (row[i] + ((left + prev[i]) >> 1)) & 0xff
        elif ftype == 4:   # Paeth
            for i in range(stride):
                left = row[i-bpp] if i >= bpp else 0
                above = prev[i]
                ul = prev[i-bpp] if i >= bpp else 0
                row[i] = (row[i] + _paeth(left, above, ul)) & 0xff

        prev = row

        # Convert to RGBA tuples
        if color_type == 2:  # RGB → RGBA
            rgba_row = []
            for i in range(0, stride, 3):
                r, g, b = row[i], row[i+1], row[i+2]
                rgba_row.append((r, g, b, 255))
            rows.append(rgba_row)
        else:  # RGBA
            rows.append([tuple(row[i:i+4]) for i in range(0, stride, 4)])

    return w, h, rows


def write_rgba_png(rows, w, h, filepath):
    """Encode RGBA rows as a PNG file."""
    def chunk(ctype, data):
        crc = zlib.crc32(ctype + data) & 0xffffffff
        return struct.pack('>I', len(data)) + ctype + data + struct.pack('>I', crc)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    ihdr = chunk(b'IHDR', b'IHDR' + ihdr_data)

    raw_rows = b''.join(b'\x00' + b''.join(bytes(p) for p in row) for row in rows)
    idat = chunk(b'IDAT', zlib.compress(raw_rows, 6))
    iend = chunk(b'IEND', b'')

    with open(filepath, 'wb') as f:
        f.write(sig + ihdr + idat + iend)
    print(f"Written: {filepath} ({os.path.getsize(filepath):,} bytes)")


def make_transparent(rows, w, h, threshold=240):
    """
    Set alpha=0 for pixels where R≥threshold AND G≥threshold AND B≥threshold.
    Returns new rows (deep copy).
    """
    result = []
    for row in rows:
        new_row = []
        for r, g, b, a in row:
            if r >= threshold and g >= threshold and b >= threshold:
                new_row.append((r, g, b, 0))
            else:
                new_row.append((r, g, b, a))
        result.append(new_row)
    return result


def process(input_path, output_path, threshold=240):
    print(f"Processing: {input_path}")
    w, h, rows = read_png_pixels(input_path)
    print(f"  Decoded: {w}x{h}, {len(rows)} rows")
    rows_t = make_transparent(rows, w, h, threshold)
    # Count transparent pixels in border
    border_alphas = []
    for y in range(h):
        row = rows_t[y]
        if y == 0 or y == h - 1:
            border_alphas.extend(p[3] for p in row)
        else:
            border_alphas.append(row[0][3])
            border_alphas.append(row[-1][3])
    opaque = sum(1 for a in border_alphas if a == 255)
    trans = sum(1 for a in border_alphas if a == 0)
    print(f"  Border: opaque={opaque} transparent={trans} total={len(border_alphas)}")
    write_rgba_png(rows_t, w, h, output_path)


if __name__ == '__main__':
    if len(sys.argv) == 3:
        process(sys.argv[1], sys.argv[2])
    else:
        print(f"Usage: {__file__} <input.png> <output.png>")
        sys.exit(1)