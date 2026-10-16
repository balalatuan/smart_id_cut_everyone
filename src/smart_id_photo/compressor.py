from io import BytesIO
from PIL import Image, ImageCms


def encode_jpeg(image, config):
    """Find highest integer quality at fixed dimensions and above quality floor.

    Scan rather than assume monotonic JPEG size. No downscaling to meet byte limit.
    """
    resized = image.resize((config.width, config.height), Image.Resampling.LANCZOS)
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    for quality in range(95, config.quality_floor-1, -1):
        buf = BytesIO()
        # Avoid libjpeg optimized-Huffman in-memory buffer failures on high-entropy
        # large images; actual quality and byte limits are still exhaustively checked.
        resized.save(buf, "JPEG", quality=quality, subsampling=0, optimize=False,
                     dpi=(config.dpi, config.dpi), icc_profile=profile)
        data = buf.getvalue()
        if len(data) <= config.max_kb * config.kb_bytes:
            return data, quality
    raise ValueError("JPEG exceeds byte limit at quality floor and required dimensions")
