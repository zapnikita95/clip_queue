"""Unit tests for taste / progress parsing."""

from backend.taste import format_progress, parse_progress_input
from backend.youtube import watch_url


def test_parse_hm():
    assert parse_progress_input("12:34") == 12 * 60 + 34
    assert parse_progress_input("1:02:03") == 3600 + 120 + 3
    assert parse_progress_input("0:45") == 45
    assert parse_progress_input("12.34") == 12 * 60 + 34
    assert parse_progress_input("12'34") == 12 * 60 + 34
    assert parse_progress_input("12'34\"") == 12 * 60 + 34


def test_parse_letters():
    assert parse_progress_input("2м3с") == 2 * 60 + 3
    assert parse_progress_input("2m3s") == 2 * 60 + 3
    assert parse_progress_input("2 м 3 с") == 2 * 60 + 3
    assert parse_progress_input("25мин") == 25 * 60
    assert parse_progress_input("25 мин") == 25 * 60
    assert parse_progress_input("90с") == 90
    assert parse_progress_input("90 сек") == 90
    assert parse_progress_input("1ч2м") == 3600 + 120
    assert parse_progress_input("1h2m3s") == 3600 + 120 + 3


def test_parse_minutes_bare():
    assert parse_progress_input("25") == 25 * 60


def test_parse_percent():
    assert parse_progress_input("50%", duration_sec=200) == 100
    assert parse_progress_input("50%") is None


def test_format():
    assert format_progress(754) == "12:34"
    assert format_progress(3723) == "1:02:03"


def test_watch_url_t():
    assert watch_url("abc") == "https://www.youtube.com/watch?v=abc"
    assert watch_url("abc", t=12) == "https://www.youtube.com/watch?v=abc&t=12"
    assert watch_url("abc", t=0) == "https://www.youtube.com/watch?v=abc"
