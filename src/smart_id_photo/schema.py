from dataclasses import dataclass, field, asdict


@dataclass
class ImageInfo:
    source_format: str
    source_size: tuple[int, int]
    oriented_source_size: tuple[int, int]
    decoder_size: tuple[int, int]
    working_size: tuple[int, int]
    scale_x: float
    scale_y: float
    downsampled: bool
    decoder_reduced: bool
    coordinate_space: str = "exif_oriented_source"
    preview_size: tuple[int, int] | None = None


@dataclass
class Geometry:
    faces: list[tuple[int, int, int, int]] = field(default_factory=list)
    face_center: tuple[float, float] | None = None
    # Heuristic estimate; deliberately NOT a segmentation result.
    estimated_head: tuple[float, float, float, float] | None = None
    eyes: list | None = None
    chin: tuple | None = None
    orientation: float | None = None
    hair_boundary_confidence: float | None = None
    method: str = "opencv-haar-frontalface-default"
    warnings: list[str] = field(default_factory=list)


@dataclass
class Result:
    status: str
    reasons: list[str]
    geometry: Geometry
    crop: tuple[int, int, int, int] | None = None
    output: str | None = None
    preview: str | None = None
    bytes: int | None = None
    jpeg_quality: int | None = None
    duration_seconds: float = 0
    manual: bool = False
    image_info: ImageInfo | None = None
    def to_dict(self):
        return asdict(self)
