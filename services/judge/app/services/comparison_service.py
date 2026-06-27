import re


def normalise(text: str) -> str:
    text = text.lower()
    text = text.strip()
    text = text.rstrip(".,!?;:")
    text = re.sub(r'\s+', ' ', text)
    return text


def compare(primary: str, candidate: str) -> dict:
    norm_primary = normalise(primary)
    norm_candidate = normalise(candidate)

    match = norm_primary == norm_candidate
    score = 1.0 if match else 0.0

    return {
        "match": match,
        "score": score,
        "reason": "normalised strings match" if match else "responses differ after normalisation",
        "normalised_primary": norm_primary,
        "normalised_candidate": norm_candidate,
    }
