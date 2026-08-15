"""Fail-closed sensitive document policy."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.sensitive_document_policy import allow_download, evaluate_url


def test_ddosecrets_is_blocked():
    policy = evaluate_url("https://ddosecrets.org/dataset/example")
    assert policy["policy_status"] == "blocked_sensitive"
    assert policy["download_allowed"] is False
    assert allow_download(policy) is False


def test_credential_path_is_blocked():
    policy = evaluate_url("https://example.com/leaked-password-dump.txt")
    assert policy["policy_status"] == "blocked_sensitive"


def test_personal_data_context_is_blocked():
    policy = evaluate_url(
        "https://example.org/file.pdf",
        classification="document_file",
        context_text="Includes patient medical record numbers",
    )
    assert policy["policy_status"] == "blocked_sensitive"


def test_sec_metadata_allowed_but_not_downloaded():
    policy = evaluate_url(
        "https://www.sec.gov/files/example.pdf",
        classification="agency_filing",
    )
    assert policy["policy_status"] == "allowed_metadata"
    assert policy["download_allowed"] is False
    assert policy["extract_personal_data"] is False
