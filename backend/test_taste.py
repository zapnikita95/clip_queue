"""Unit tests for taste / progress parsing."""

from backend.taste import format_progress, parse_progress_input


def test_parse_hm():
    assert parse_progress_input("12:34") == 12 * 60 + 34
    assert parse_progress_input("1:02:03") == 3600 + 120 + 3
    assert parse_progress_input("0:45") == 45


def test_parse_minutes():
    assert parse_progress_input("25 мин") == 25 * 60
    assert parse_progress_input("25") == 25 * 60


def test_parse_percent():
    assert parse_progress_input("50%", duration_sec=200) == 100
    assert parse_progress_input("50%") is None


def test_format():
    assert format_progress(754) == "12:34"
    assert format_progress(3723) == "1:02:03"
