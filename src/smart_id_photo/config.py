from dataclasses import dataclass, fields
from pathlib import Path
import math
import yaml


@dataclass(frozen=True)
class Config:
    backend: str = "local"
    mode: str = "standard"
    width: int = 295
    height: int = 413
    dpi: int = 300
    max_kb: int = 50
    kb_bytes: int = 1024
    quality_floor: int = 65
    max_pixels: int = 40_000_000
    max_working_pixels: int = 24_000_000
    max_input_bytes: int = 33_554_432
    detector_max_side: int = 1200
    output_dir: str = "output"

    def __post_init__(self):
        if self.backend != "local":
            raise ValueError("Phase 1 only implements local backend; no cloud upload is available")
        if self.mode not in {"standard", "adaptive"}:
            raise ValueError("mode must be standard or adaptive")
        ranges = {"width": (32, 4096), "height": (32, 4096), "dpi": (72, 1200),
                  "max_kb": (1, 10240), "quality_floor": (1, 95),
                  "max_pixels": (100, 40_000_000), "max_working_pixels": (100, 24_000_000),
                  "max_input_bytes": (1024, 33_554_432),
                  "detector_max_side": (256, 1600)}
        for key, (lo, hi) in ranges.items():
            value = getattr(self, key)
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError(f"{key} must be an integer in [{lo}, {hi}]")
        if self.kb_bytes != 1024 or type(self.kb_bytes) is not int:
            raise ValueError("This version consistently uses 1 KB = 1024 bytes")
        if not isinstance(self.output_dir, str) or not self.output_dir.strip():
            raise ValueError("output_dir must be a path string")

    @classmethod
    def load(cls, path):
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a mapping")
        valid = {f.name for f in fields(cls)}
        unknown = set(data) - valid - {"future"}
        if unknown:
            raise ValueError(f"Unknown config keys: {sorted(unknown)}")
        return cls(**{k: v for k, v in data.items() if k != "future"})


def mm_to_pixels(mm, dpi=300):
    if not math.isfinite(mm) or mm <= 0:
        raise ValueError("Physical dimensions must be positive")
    return round(mm / 25.4 * dpi)
