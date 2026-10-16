import math


def optimize_crop(size, geometry, config):
    """Aspect-constrained in-image crop. Never pad or generate missing content."""
    W, H = size
    if not geometry.estimated_head:
        return None, ["Head cannot be located; manual rectangle required"]
    left, top, right, bottom = geometry.estimated_head
    head_h = bottom-top
    occupancy = .70 if config.mode == "standard" else .57
    height = head_h / occupancy
    width = height * config.width / config.height
    width = max(width, (right-left)*1.12)
    height = width * config.height / config.width
    scale = min(1., W/width, H/height)
    width, height = width*scale, height*scale
    # Upper margin + shoulder space. Shift inside source without synthesizing pixels.
    x = min(max(0., (left+right)/2-width/2), W-width)
    y = min(max(0., top-.08*height), H-height)
    rect = (round(x), round(y), min(W, round(x+width)), min(H, round(y+height)))
    reasons = []
    if left < 0 or top < 0 or right > W or bottom > H:
        reasons.append("Estimated head extends outside source; missing hair cannot be restored")
    if left < rect[0] or top < rect[1] or right > rect[2] or bottom > rect[3]:
        reasons.append("Constrained crop cannot contain estimated head")
    return rect, reasons


def validate_manual(rect, size, config):
    if len(rect) != 4 or any(not math.isfinite(float(v)) for v in rect):
        raise ValueError("Crop needs four finite coordinates")
    x0, y0, x1, y1 = (round(float(v)) for v in rect)
    if not 0 <= x0 < x1 <= size[0] or not 0 <= y0 < y1 <= size[1]:
        raise ValueError("Crop must stay within the oriented source image")
    target = config.width / config.height
    ratio = (x1-x0)/(y1-y0)
    if abs(ratio/target-1) > .02:
        raise ValueError("Crop aspect ratio must match output within 2%; avoid face distortion")
    return (x0, y0, x1, y1)
