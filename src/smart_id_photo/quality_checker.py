def classify(geometry, reasons, manual):
    # No automated PASS before independent accuracy validation. A user rectangle
    # is not independent proof of complete hair or institutional compliance either.
    notes = list(dict.fromkeys(geometry.warnings + reasons))
    notes.append("Manual crop requires visual confirmation" if manual else
                 "Unvalidated hair boundary: automated PASS disabled in Phase 1")
    return "REVIEW", notes
