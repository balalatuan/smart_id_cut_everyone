import csv
import os
from pathlib import Path
import tempfile


def atomic_write(path, data):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=".smart-id-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def export_csv(results, path):
    """Single-run report utility; not the future batch job engine."""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["status", "output", "bytes", "jpeg_quality", "duration_seconds", "reasons"])
        writer.writeheader()
        for result in results:
            row = result.to_dict()
            writer.writerow({k: ("; ".join(row[k]) if k == "reasons" else row[k]) for k in writer.fieldnames})
