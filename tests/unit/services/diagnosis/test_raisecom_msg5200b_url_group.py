"""Tests for Raisecom 5200B url-group priority supplement."""

from __future__ import annotations

from sdwan_desktop.services.diagnosis.raisecom_msg5200b_url_group import (
    evaluate_url_group_priority_for_domain,
)


def test_url_group_single_match() -> None:
    blob = """url-group acceleratePlus
youtube.com
google.com
!
"""
    v = evaluate_url_group_priority_for_domain(
        domain="youtube.com",
        raw_outputs={"show url-group all domain all": blob},
    )
    assert v is not None
    assert v.effective_group == "acceleratePlus"
    assert "acceleratePlus" in v.matched_groups


def test_url_group_multi_match_priority() -> None:
    blob = """url-group acceleratePlus
tiktok.com
!
url-group liveBroadcast
tiktok.com
!
"""
    v = evaluate_url_group_priority_for_domain(
        domain="tiktok.com",
        raw_outputs={"show url-group all domain all": blob},
    )
    assert v is not None
    assert len(v.matched_groups) == 2
    assert v.effective_group == "liveBroadcast"
