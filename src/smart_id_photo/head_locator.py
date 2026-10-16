def estimate_head(geometry):
    if len(geometry.faces) != 1:
        geometry.warnings.append("Expected exactly one frontal face")
        return geometry
    x, y, w, h = geometry.faces[0]
    geometry.face_center = (x + w/2, y + h/2)
    # Conservative prior, not a measured hair outline. Do not clamp: out-of-frame
    # estimates are important independent evidence of possible clipping.
    geometry.estimated_head = (x - .23*w, y - .55*h, x + 1.23*w, y + 1.15*h)
    geometry.warnings.append("Hair boundary, eyes, chin and orientation are unmeasured; head box is a prior")
    return geometry
