#!/usr/bin/env python3
"""Minimal dependency-free PNG decode/encode for screenshot parity work.

Handles the colour types adb/simctl screenshots actually produce (8-bit
grey, RGB, palette, grey+alpha, RGBA) plus 16-bit inputs, which are
downsampled to 8-bit. Anything else raises rather than guessing.

Decoded images are (width, height, pixels) where pixels is a flat
bytearray of RGB triples, three bytes per pixel, row-major.
"""
import struct
import zlib

PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class PngError(ValueError):
    """Raised for anything this decoder will not read honestly."""


def _chunks(data):
    if data[:8] != PNG_MAGIC:
        raise PngError('not a PNG file')
    offset = 8
    while offset + 8 <= len(data):
        (length,) = struct.unpack('>I', data[offset:offset + 4])
        kind = data[offset + 4:offset + 8]
        start = offset + 8
        end = start + length
        if end + 4 > len(data):
            raise PngError('truncated PNG chunk')
        yield kind, data[start:end]
        offset = end + 4


def read_header(path):
    """Return (width, height) without decoding pixels."""
    with open(path, 'rb') as handle:
        header = handle.read(26)
    if len(header) < 26 or header[:8] != PNG_MAGIC or header[12:16] != b'IHDR':
        raise PngError(f'not a PNG image: {path}')
    width, height = struct.unpack('>II', header[16:24])
    if width == 0 or height == 0:
        raise PngError(f'empty PNG dimensions: {path}')
    return width, height


def _unfilter(raw, width, height, channels, depth):
    stride = (width * channels * depth + 7) // 8
    out = bytearray(stride * height)
    step = max(1, (channels * depth) // 8)
    pos = 0
    prev = bytearray(stride)
    for row in range(height):
        if pos >= len(raw):
            raise PngError('truncated PNG image data')
        filter_type = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        if len(line) != stride:
            raise PngError('truncated PNG scanline')
        pos += stride
        if filter_type == 1:
            for i in range(step, stride):
                line[i] = (line[i] + line[i - step]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - step] if i >= step else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                left = line[i - step] if i >= step else 0
                up = prev[i]
                upleft = prev[i - step] if i >= step else 0
                p = left + up - upleft
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - upleft)
                if pa <= pb and pa <= pc:
                    pred = left
                elif pb <= pc:
                    pred = up
                else:
                    pred = upleft
                line[i] = (line[i] + pred) & 0xFF
        elif filter_type != 0:
            raise PngError(f'unsupported PNG filter type {filter_type}')
        out[row * stride:(row + 1) * stride] = line
        prev = line
    return bytes(out), stride


def _expand_bits(line, width, depth):
    """Expand sub-byte greyscale/palette samples to one byte per sample."""
    out = bytearray(width)
    per_byte = 8 // depth
    mask = (1 << depth) - 1
    for i in range(width):
        byte = line[i // per_byte]
        shift = 8 - depth * (i % per_byte + 1)
        out[i] = (byte >> shift) & mask
    return out


def decode(path):
    """Decode a PNG to (width, height, rgb_bytes)."""
    with open(path, 'rb') as handle:
        data = handle.read()
    width = height = depth = colour = None
    palette = b''
    idat = bytearray()
    for kind, payload in _chunks(data):
        if kind == b'IHDR':
            width, height, depth, colour, comp, filt, interlace = struct.unpack(
                '>IIBBBBB', payload[:13])
            if comp != 0 or filt != 0:
                raise PngError('unsupported PNG compression or filter method')
            if interlace != 0:
                raise PngError('interlaced PNG is not supported; re-capture without interlacing')
            if colour not in _CHANNELS:
                raise PngError(f'unsupported PNG colour type {colour}')
            if depth not in (1, 2, 4, 8, 16):
                raise PngError(f'unsupported PNG bit depth {depth}')
            if colour != 3 and depth < 8:
                raise PngError(f'unsupported bit depth {depth} for colour type {colour}')
        elif kind == b'PLTE':
            palette = payload
        elif kind == b'IDAT':
            idat += payload
        elif kind == b'IEND':
            break
    if width is None:
        raise PngError('PNG has no IHDR chunk')
    if not idat:
        raise PngError('PNG has no image data')
    if width == 0 or height == 0:
        raise PngError('empty PNG dimensions')

    raw = zlib.decompress(bytes(idat))
    channels = _CHANNELS[colour]
    planes, stride = _unfilter(raw, width, height, channels, depth)

    rgb = bytearray(width * height * 3)
    sample_bytes = 2 if depth == 16 else 1
    for row in range(height):
        line = planes[row * stride:(row + 1) * stride]
        if depth < 8:
            samples = _expand_bits(line, width * channels, depth)
        elif depth == 16:
            samples = line[::2]  # take the high byte; 16-bit screenshots are rare
        else:
            samples = line
        base = row * width * 3
        for col in range(width):
            o = base + col * 3
            s = col * channels
            if colour == 0 or colour == 4:
                grey = samples[s]
                rgb[o] = rgb[o + 1] = rgb[o + 2] = grey
            elif colour == 2 or colour == 6:
                rgb[o] = samples[s]
                rgb[o + 1] = samples[s + 1]
                rgb[o + 2] = samples[s + 2]
            else:  # palette
                index = samples[s]
                p = index * 3
                if p + 2 >= len(palette):
                    raise PngError('palette index out of range')
                rgb[o] = palette[p]
                rgb[o + 1] = palette[p + 1]
                rgb[o + 2] = palette[p + 2]
    del sample_bytes
    return width, height, bytes(rgb)


def encode(path, width, height, rgb):
    """Write a flat RGB byte buffer as an 8-bit RGB PNG."""
    if len(rgb) != width * height * 3:
        raise PngError('pixel buffer does not match the declared dimensions')
    raw = bytearray()
    for row in range(height):
        raw.append(0)
        raw += rgb[row * width * 3:(row + 1) * width * 3]
    out = bytearray(PNG_MAGIC)
    for kind, payload in (
        (b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)),
        (b'IDAT', zlib.compress(bytes(raw), 6)),
        (b'IEND', b''),
    ):
        out += struct.pack('>I', len(payload)) + kind + payload
        out += struct.pack('>I', zlib.crc32(kind + payload) & 0xFFFFFFFF)
    with open(path, 'wb') as handle:
        handle.write(bytes(out))
    return path
