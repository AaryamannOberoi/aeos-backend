"""
Hand-constructed arithmetic tests for scoring/scorer.py. No LLM calls,
no real KB data — every profile and RequirementAnalysis here is a fake
built directly from the pydantic models so the expected numbers can be
computed by hand and checked exactly.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from schemas.requirement_analysis import ImpliedAttributeNeeds, RequirementAnalysis
from schemas.technology_profile import TechnologyProfile
from scoring.scorer import compute_axis_score, rank_candidates, score_candidate


def _make_profile(profile_id: str = "fake", **overrides) -> TechnologyProfile:
    defaults = dict(
        id=profile_id,
        display_name=profile_id,
        department="backend",
        request_handling_model="async",
        typing="static",
        ecosystem_maturity="mature",
        learning_curve="low",
        operational_complexity="low",
        horizontal_scaling="native",
        source_citations=["https://example.com"],
        last_reviewed=date(2026, 1, 1),
    )
    defaults.update(overrides)
    return TechnologyProfile(**defaults)


def _make_need(requirement_id: str = "R1", **implied) -> RequirementAnalysis:
    return RequirementAnalysis(
        requirement_id=requirement_id,
        implied_attribute_needs=ImpliedAttributeNeeds(**implied),
        supporting_evidence=["NO_EVIDENCE_FOUND"],
        reasoning="fake reasoning for test purposes",
    )


def test_compute_axis_score_exact_match_scores_one():
    profile = _make_profile(horizontal_scaling="native")
    need = _make_need(horizontal_scaling="native")

    score = compute_axis_score(profile, [need], "horizontal_scaling")

    assert score == pytest.approx(1.0)


def test_compute_axis_score_mismatch_uses_weight_distance():
    # actual = via-extension (0.6), ideal = native (1.0)
    # expected = 1 - abs(0.6 - 1.0) = 0.6
    profile = _make_profile(horizontal_scaling="via-extension")
    need = _make_need(horizontal_scaling="native")

    score = compute_axis_score(profile, [need], "horizontal_scaling")

    assert score == pytest.approx(0.6)


def test_compute_axis_score_averages_across_multiple_opinions():
    # actual = mature (1.0)
    # need1 ideal = growing (0.6) -> match = 1 - abs(1.0-0.6) = 0.6
    # need2 ideal = mature (1.0)  -> match = 1.0
    # average = (0.6 + 1.0) / 2 = 0.8
    profile = _make_profile(ecosystem_maturity="mature")
    need1 = _make_need(requirement_id="R1", ecosystem_maturity="growing")
    need2 = _make_need(requirement_id="R2", ecosystem_maturity="mature")

    score = compute_axis_score(profile, [need1, need2], "ecosystem_maturity")

    assert score == pytest.approx(0.8)


def test_compute_axis_score_is_neutral_when_no_opinion_expressed():
    profile = _make_profile(typing="dynamic")
    need = _make_need(horizontal_scaling="native")  # no opinion on typing

    score = compute_axis_score(profile, [need], "typing")

    assert score == pytest.approx(1.0)


def test_score_candidate_matches_hand_computed_total_and_trace():
    # horizontal_scaling: actual native (1.0) vs ideal native (1.0) -> 1.0
    # ecosystem_maturity: actual growing (0.6) vs ideal mature (1.0) -> 0.6
    # typing: no opinion expressed -> neutral 1.0
    profile = _make_profile(
        horizontal_scaling="native",
        ecosystem_maturity="growing",
        typing="static",
    )
    need = _make_need(horizontal_scaling="native", ecosystem_maturity="mature")
    weights = {"horizontal_scaling": 0.5, "ecosystem_maturity": 0.3, "typing": 0.2}

    result = score_candidate(profile, [need], weights)

    expected_total = 0.5 * 1.0 + 0.3 * 0.6 + 0.2 * 1.0
    assert result["total"] == pytest.approx(expected_total)
    assert result["sub_scores"] == pytest.approx(
        {"horizontal_scaling": 1.0, "ecosystem_maturity": 0.6, "typing": 1.0}
    )
    assert result["formula_trace"] == (
        "0.5*1.0 (horizontal_scaling) + 0.3*0.6 (ecosystem_maturity) + 0.2*1.0 (typing)"
    )


def test_rank_candidates_sorts_descending_by_total():
    good = _make_profile(profile_id="good", horizontal_scaling="native")
    bad = _make_profile(profile_id="bad", horizontal_scaling="difficult")
    need = _make_need(horizontal_scaling="native")
    weights = {"horizontal_scaling": 1.0}

    ranked = rank_candidates([bad, good], [need], weights)

    assert [entry["profile_id"] for entry in ranked] == ["good", "bad"]
    assert ranked[0]["total"] == pytest.approx(1.0)
    # bad: actual difficult (0.2) vs ideal native (1.0) -> 1 - abs(0.2-1.0) = 0.2
    assert ranked[1]["total"] == pytest.approx(0.2)
