"""All PUBLIC geometry is in EXIF-oriented source pixels, including manual crops."""
from dataclasses import replace
import math


def source_rect_to_working(rect, info):
    # Round outward to preserve the requested image content.
    w, h = info.working_size
    left, top, right, bottom = rect
    return (max(0, math.floor(left*info.scale_x)),
            max(0, math.floor(top*info.scale_y)),
            min(w, math.ceil(right*info.scale_x)),
            min(h, math.ceil(bottom*info.scale_y)))


def working_rect_to_source(rect, info):
    if rect is None:
        return None
    w, h = info.oriented_source_size
    l, t, r, b = rect
    return (max(0, round(l/info.scale_x)), max(0, round(t/info.scale_y)),
            min(w, round(r/info.scale_x)), min(h, round(b/info.scale_y)))


def geometry_to_source(geometry, info):
    def point(p):
        return None if p is None else (p[0]/info.scale_x, p[1]/info.scale_y)
    head = geometry.estimated_head
    # Do not clamp inferred head bounds: out-of-image estimates are QC evidence.
    head = None if head is None else (head[0]/info.scale_x, head[1]/info.scale_y,
                                     head[2]/info.scale_x, head[3]/info.scale_y)
    faces = [(round(x/info.scale_x), round(y/info.scale_y),
              round(w/info.scale_x), round(h/info.scale_y)) for x,y,w,h in geometry.faces]
    return replace(geometry, faces=faces, face_center=point(geometry.face_center),
                   estimated_head=head, eyes=None if geometry.eyes is None else
                   [point(p) for p in geometry.eyes], chin=point(geometry.chin))
