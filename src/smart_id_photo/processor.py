from io import BytesIO
from pathlib import Path
import time
from uuid import uuid4
from PIL import Image, ImageDraw
from .config import Config
from .schema import Geometry, Result
from .image_loader import load_image_details
from .coordinates import source_rect_to_working, working_rect_to_source, geometry_to_source
from .face_detector import FaceDetector
from .head_locator import estimate_head
from .crop_optimizer import optimize_crop, validate_manual
from .compressor import encode_jpeg
from .quality_checker import classify
from .exporter import atomic_write


class Processor:
    def __init__(self, detector=None):
        self.detector = detector or FaceDetector()

    def process(self, path, config=None, manual_crop=None):
        config = config or Config()
        started = time.perf_counter()
        geometry = Geometry()
        result = Result("FAIL", [], geometry, manual=manual_crop is not None)
        image = preview = cropped = None
        try:
            image, notes, info = load_image_details(path, config)
            result.image_info = info
            working_geometry = estimate_head(self.detector.detect(image, config))
            geometry = geometry_to_source(working_geometry, info)
            result.geometry = geometry
            if manual_crop is not None:
                source_rect = validate_manual(manual_crop, info.oriented_source_size, config)
                rect = source_rect_to_working(source_rect, info)
                if rect[2] <= rect[0] or rect[3] <= rect[1]:
                    raise ValueError("Manual crop is too small at working resolution")
                reasons = []
            else:
                rect, reasons = optimize_crop(image.size, working_geometry, config)
                source_rect = working_rect_to_source(rect, info)
            result.crop = source_rect
            directory = Path(config.output_dir)
            directory.mkdir(parents=True, exist_ok=True)
            # Independent random filename, never derived from a private input name.
            token = uuid4().hex
            preview_scale = min(1., 1200/image.width, 1200/image.height)
            preview = image.resize((max(1, round(image.width*preview_scale)),
                                    max(1, round(image.height*preview_scale))), Image.Resampling.LANCZOS)
            info.preview_size = preview.size
            sx, sy = preview.width/info.oriented_source_size[0], preview.height/info.oriented_source_size[1]
            draw = ImageDraw.Draw(preview)
            for x,y,w,h in geometry.faces:
                draw.rectangle((x*sx,y*sy,(x+w)*sx,(y+h)*sy), outline="cyan", width=3)
            if geometry.estimated_head:
                draw.rectangle(tuple(v*(sx if i%2==0 else sy) for i,v in enumerate(geometry.estimated_head)), outline="orange", width=3)
            if source_rect:
                draw.rectangle(tuple(v*(sx if i%2==0 else sy) for i,v in enumerate(source_rect)), outline="lime", width=3)
            buf = BytesIO()
            preview.save(buf, "PNG")
            preview_path = directory / f"{token}-preview.png"
            atomic_write(preview_path, buf.getvalue())
            result.preview = str(preview_path.resolve())
            if rect is None:
                result.reasons = geometry.warnings + notes + reasons
                # A decodable input without a face may still be manually corrected.
                result.status = "REVIEW"
            else:
                cropped = image.crop(rect)
                data, quality = encode_jpeg(cropped, config)
                output = directory / f"{token}.jpg"
                atomic_write(output, data)
                # Verify exported file itself (including dimensions/decodability).
                with Image.open(output) as check:
                    check.load()
                    if check.size != (config.width, config.height) or output.stat().st_size > config.max_kb*1024:
                        output.unlink()
                        raise ValueError("Export verification failed")
                result.output = str(output.resolve())
                result.bytes, result.jpeg_quality = len(data), quality
                result.status, result.reasons = classify(geometry, notes+reasons, manual_crop is not None)
        except Exception as exc:
            result.status = "FAIL"
            # Do not echo full exceptions with private path/raw data into reports.
            result.reasons = [str(exc) if isinstance(exc, ValueError) else
                              f"Input or processing error ({type(exc).__name__})"]
        finally:
            for resource in (cropped, preview, image):
                if resource is not None:
                    resource.close()
        result.duration_seconds = round(time.perf_counter()-started, 6)
        return result
