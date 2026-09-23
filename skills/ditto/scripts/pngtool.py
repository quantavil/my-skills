"""PNG I/O through Pillow; RGB pixels with transparency composited on white."""
from PIL import Image, UnidentifiedImageError
import numpy as np


class PngError(ValueError):
    """Invalid or unsupported screenshot evidence."""


def read_header(path):
    try:
        with Image.open(path, formats=['PNG']) as image:
            return image.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise PngError(f'invalid PNG: {path}: {error}') from error


def open_rgb(path):
    """Load an independent RGB image, preserving 16-bit grey high-byte scaling."""
    try:
        with Image.open(path, formats=['PNG']) as image:
            if image.mode.startswith('I;16') or image.mode == 'I':
                image = Image.fromarray((np.asarray(image, dtype=np.uint16) >> 8).astype(np.uint8))
            if 'A' in image.getbands() or 'transparency' in image.info:
                image = Image.alpha_composite(Image.new('RGBA', image.size, 'white'), image.convert('RGBA'))
            return image.convert('RGB')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise PngError(f'invalid PNG: {path}: {error}') from error


def decode(path):
    image = open_rgb(path)
    return *image.size, image.tobytes()


def encode(path, width, height, rgb):
    if width <= 0 or height <= 0 or len(rgb) != width * height * 3:
        raise PngError('pixel buffer does not match the declared dimensions')
    Image.frombytes('RGB', (width, height), bytes(rgb)).save(path, format='PNG')
    return path
