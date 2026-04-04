from __future__ import annotations

from dataclasses import asdict

from xianyu_tools.models import Candidate


def dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    seen: set[str] = set()
    deduped: list[Candidate] = []
    for candidate in candidates:
        signature = candidate.item.metadata.get("title_signature") or candidate.item.normalized_title
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(candidate)
    return deduped


def is_viable_for_xianyu(candidate: Candidate) -> bool:
    title = candidate.item.title
    disallowed_words = ("二手", "闲置", "瑕疵", "临期", "代购")
    if any(word in title for word in disallowed_words):
        return False
    if "detail_error" in candidate.item.metadata:
        return False
    if candidate.estimated_margin <= 0:
        return False
    if "missing_buy_url" in candidate.risk_flags:
        return False
    return True


def filter_candidates_for_xianyu(candidates: list[Candidate]) -> list[Candidate]:
    return [candidate for candidate in candidates if is_viable_for_xianyu(candidate)]


def summarize_candidate(candidate: Candidate) -> dict:
    data = asdict(candidate)
    data["xianyu_viable"] = is_viable_for_xianyu(candidate)
    return data
