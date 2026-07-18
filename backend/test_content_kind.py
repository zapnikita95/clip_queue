"""Content bucket: music clips / shortform / marathon / normal video."""
from backend import youtube as yt


def test_vevo_is_music():
    assert yt.content_bucket("Connection", "OneRepublicVEVO", 166) == "music"
    assert yt.content_bucket("Caution", "TheKillersVEVO", 269) == "music"


def test_topic_and_library_music():
    assert yt.content_bucket("Every Country's Sun", "Mogwai - Topic", 338) == "music"
    assert yt.content_bucket("Apocalypse", "Music Library Uploads", 290) == "music"


def test_official_music_video_title():
    assert (
        yt.content_bucket("Artist - Song (Official Music Video)", "Some Channel", 210)
        == "music"
    )


def test_shorts_and_shortform():
    assert yt.content_bucket("Funny bit", "Some Channel", 45) == "shorts"
    assert yt.content_bucket("Clip #shorts", "Some Channel", 120) == "shorts"
    # 2–6 min atmospheric / random — not the planning queue
    assert yt.content_bucket("Hippie Life", "lovechild909", 135) == "shortform"
    assert yt.content_bucket("Heart-Crazy On You", "SuperKevinheart", 294) == "music"


def test_marathon_junk():
    assert yt.content_bucket("10 hours of dogs", "Ambient", 10 * 3600) == "marathon"
    assert yt.content_bucket("Sleep stream", "X", 12 * 3600) == "marathon"


def test_normal_longform_stays_video():
    assert yt.content_bucket("Редакция. News: 79-я неделя", "Редакция", 2568) == "video"
    assert yt.content_bucket("Большой разбор", "Кинопоиск", 1800) == "video"
    # just over 6 min
    assert yt.content_bucket("Лекция", "Универ", 6 * 60 + 30) == "video"
    # under 10h
    assert yt.content_bucket("Длинный стрим", "Канал", 9 * 3600) == "video"


def test_music_beats_shorts():
    assert yt.content_bucket("Song", "FooVEVO", 50) == "music"
