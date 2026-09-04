from difflib import SequenceMatcher


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.casefold().strip(), right.casefold().strip()).ratio()
