from io import BytesIO
from pathlib import Path
import math
import warnings
from PIL import Image, ImageCms, ImageOps
from .schema import ImageInfo


def bounded_size(size, pixel_limit):
    """Never upscale; integer rounding must not exceed the pixel budget."""
    width, height = size
    if width * height <= pixel_limit:
        return size
    scale = math.sqrt(pixel_limit / (width * height))
    width, height = max(1, math.floor(width*scale)), max(1, math.floor(height*scale))
    # Extremely narrow images may hit the one-pixel floor on one axis.
    if width * height > pixel_limit:
        if width >= height:
            width = max(1, pixel_limit // height)
        else:
            height = max(1, pixel_limit // width)
    return width, height


def load_image_details(path, config):
    """Check source headers BEFORE decoding; resize before orientation/color copies.

    Working-image budget is not a decoder RSS ceiling. PNG needs a full raster;
    JPEG draft only supports discrete native reduction factors. No source writes.
    """
    path = Path(path)
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("Only JPG/JPEG/PNG inputs are supported")
    if path.stat().st_size > config.max_input_bytes:
        raise ValueError("Input file exceeds byte limit")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as original:
            if original.format not in {"JPEG", "PNG"}:
                raise ValueError("Actual file format must be JPEG or PNG")
            source_size, source_format = original.size, original.format
            if original.width * original.height > config.max_pixels:
                raise ValueError(
                    f"Input exceeds pixel limit: {original.width} x {original.height} "
                    f"= {original.width * original.height:,}; allowed {config.max_pixels:,}"
                )
            if getattr(original, "n_frames", 1) != 1:
                raise ValueError("Animated images are unsupported")
            # Read EXIF before JPEG draft changes the decoder dimensions.
            orientation = original.getexif().get(274, 1)
            oriented_size = source_size[::-1] if orientation in {5, 6, 7, 8} else source_size
            profile = original.info.get("icc_profile")
            target = bounded_size(source_size, config.max_working_pixels)
            if source_format == "JPEG" and target != source_size:
                original.draft(original.mode, target)
            decoder_size = original.size
            original.load()
            if original.size != target:
                original.thumbnail(target, Image.Resampling.LANCZOS, reducing_gap=None)
            ImageOps.exif_transpose(original, in_place=True)
            notes = []
            image = original
            owns_image = False
            try:
                if "A" in image.getbands() or "transparency" in image.info:
                    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
                    white = Image.new("RGB", image.size, "white")
                    try:
                        with rgba.getchannel("A") as alpha:
                            white.paste(rgba, mask=alpha)
                    finally:
                        if rgba is not original:
                            rgba.close()
                    image, owns_image = white, True
                    notes.append("Transparent input composited on white")
                if profile:
                    try:
                        converted = ImageCms.profileToProfile(
                            image, ImageCms.ImageCmsProfile(BytesIO(profile)),
                            ImageCms.createProfile("sRGB"), outputMode="RGB")
                    except Exception:
                        notes.append("ICC profile could not be interpreted; color requires review")
                        converted = image.convert("RGB")
                else:
                    if image.mode == "CMYK":
                        notes.append("Untagged CMYK converted approximately; color requires review")
                    converted = image.convert("RGB")
                if owns_image:
                    image.close()
                image, owns_image = converted, True
                info = ImageInfo(
                    source_format=source_format, source_size=source_size,
                    oriented_source_size=oriented_size, decoder_size=decoder_size,
                    working_size=image.size,
                    scale_x=image.width/oriented_size[0], scale_y=image.height/oriented_size[1],
                    downsampled=image.size != oriented_size,
                    decoder_reduced=decoder_size != source_size)
                if info.downsampled:
                    notes.append(
                        f"Large input downsampled for processing: {oriented_size[0]} x {oriented_size[1]} "
                        f"-> {image.width} x {image.height}; original preserved; "
                        "crop coordinates remain in oriented source pixels")
                return image, notes, info
            except BaseException:
                if owns_image:
                    image.close()
                raise


def load_image(path, config):
    """Backward-compatible two-value interface."""
    image, notes, _ = load_image_details(path, config)
    return image, notes
