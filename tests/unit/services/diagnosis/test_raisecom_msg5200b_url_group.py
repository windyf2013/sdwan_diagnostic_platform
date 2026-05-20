"""Tests for Raisecom 5200B url-group priority and url match modes."""

from __future__ import annotations

from sdwan_desktop.services.diagnosis.raisecom_msg5200b_url_group import (
    domain_matches_url_group_entry,
    evaluate_url_group_priority_for_domain,
    normalize_url_match_mode,
)

_RC_SUFFIX = """url-group acceleratePlus
 url match suffix
 priority 50
 exit
url-group liveBroadcast
 url match suffix
 priority 150
 exit
"""

_RC_PRECISE = """url-group acceleratePlus
 url match precise
 exit
"""

_RC_FUZZY = """url-group acceleratePlus
 url match fuzzy
 exit
"""


def test_normalize_url_match_mode_unknown_defaults_suffix() -> None:
    assert normalize_url_match_mode("suffix") == "suffix"
    assert normalize_url_match_mode("PRECISE") == "precise"
    assert normalize_url_match_mode("fuzzy") == "fuzzy"
    assert normalize_url_match_mode("legacy") == "suffix"


def test_precise_mode_exact_only() -> None:
    assert domain_matches_url_group_entry("youtube.com", "youtube.com", "precise")
    assert not domain_matches_url_group_entry("www.youtube.com", "youtube.com", "precise")
    assert not domain_matches_url_group_entry("music.google.com", "google.com", "precise")


def test_suffix_mode_subdomain() -> None:
    assert domain_matches_url_group_entry("music.google.com", "google.com", "suffix")
    assert domain_matches_url_group_entry("www.youtube.com", "youtube.com", "suffix")
    assert not domain_matches_url_group_entry("notgoogle.com", "google.com", "suffix")


def test_fuzzy_mode_label_and_subdomain() -> None:
    assert domain_matches_url_group_entry("www.google.com", "google", "fuzzy")
    assert domain_matches_url_group_entry("music.google.com", "google.com", "fuzzy")
    assert not domain_matches_url_group_entry("youtube.com", "google", "fuzzy")


def test_url_group_single_match() -> None:
    blob = """url-group acceleratePlus
youtube.com
google.com
!
"""
    v = evaluate_url_group_priority_for_domain(
        domain="youtube.com",
        raw_outputs={"show url-group all domain all": blob},
        running_config=_RC_SUFFIX,
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
        running_config=_RC_SUFFIX,
    )
    assert v is not None
    assert len(v.matched_groups) == 2
    assert v.effective_group == "liveBroadcast"


def test_url_group_suffix_subdomain_match() -> None:
    blob = """url-group acceleratePlus
google.com
youtube.com
!
"""
    v = evaluate_url_group_priority_for_domain(
        domain="music.google.com",
        raw_outputs={"show url-group all domain all": blob},
        running_config=_RC_SUFFIX,
    )
    assert v is not None
    assert v.effective_group == "acceleratePlus"
    assert ("acceleratePlus", "google.com") in v.matched_patterns
    assert "suffix" in v.summary


def test_url_group_precise_no_subdomain() -> None:
    blob = """url-group acceleratePlus
google.com
!
"""
    assert (
        evaluate_url_group_priority_for_domain(
            domain="music.google.com",
            raw_outputs={"show url-group all domain all": blob},
            running_config=_RC_PRECISE,
        )
        is None
    )
    v = evaluate_url_group_priority_for_domain(
        domain="google.com",
        raw_outputs={"show url-group all domain all": blob},
        running_config=_RC_PRECISE,
    )
    assert v is not None
    assert "precise" in v.summary


def test_url_group_fuzzy_label_match() -> None:
    blob = """url-group acceleratePlus
google
!
"""
    v = evaluate_url_group_priority_for_domain(
        domain="www.google.com",
        raw_outputs={"show url-group all domain all": blob},
        running_config=_RC_FUZZY,
    )
    assert v is not None
    assert v.effective_group == "acceleratePlus"
    assert "fuzzy" in v.summary


def test_url_group_suffix_no_false_positive() -> None:
    blob = """url-group acceleratePlus
google.com
!
"""
    v = evaluate_url_group_priority_for_domain(
        domain="plain.example",
        raw_outputs={"show url-group all domain all": blob},
        running_config=_RC_SUFFIX,
    )
    assert v is None
