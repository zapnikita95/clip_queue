"""Content bucket: music clips / shorts / normal video."""
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


def test_shorts_by_duration_and_hash():
    assert yt.content_bucket("Funny bit", "Some Channel", 45) == "shorts"
    assert yt.content_bucket("Clip #shorts", "Some Channel", 120) == "shorts"


def test_normal_longform_stays_video():
    assert yt.content_bucket("Редакция. News: 79-я неделя", "Редакция", 2568) == "video"
    assert yt.content_bucket("Большой разбор", "Кинопоиск", 1800) == "video"


def test_music_beats_shorts():
    # 50s VEVO clip → music, not shorts
    assert yt.content_bucket("Song", "FooVEVO", 50) == "music"
