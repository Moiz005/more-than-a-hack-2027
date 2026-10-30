"""Half-open state intervals; X and half changes terminate a run."""


def intervals(labels, halves):
    if len(labels) != len(halves):
        raise ValueError("labels and halves must be aligned")
    result = []
    start = None
    previous = None
    for index in range(len(labels) + 1):
        label = labels[index] if index < len(labels) else None
        half = halves[index] if index < len(halves) else None
        if label not in ("H", "A", "D", "X", None):
            raise ValueError("invalid label")
        if index < len(labels) and (half not in (0, 1, 2) or (half == 0 and label != "X")):
            raise ValueError("invalid half or ungraded label")
        key = (label, half) if label in ("H", "A", "D") else None
        if key != previous:
            if previous is not None:
                result.append((previous[0], previous[1], start, index))
            start = index if key is not None else None
            previous = key
    return result
