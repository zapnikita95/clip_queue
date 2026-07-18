from backend import themes


def test_english_channel():
    t = themes.primary_theme("Lesson 12", "englishbad")
    assert t and t["id"] == "english"


def test_news_redakciya():
    t = themes.primary_theme("Редакция. News: 79-я неделя", "Редакция")
    assert t and t["id"] == "news"


def test_history_keyword():
    t = themes.primary_theme("История СССР за час", "Some Channel")
    assert t and t["id"] == "history"


def test_languages_vs_english():
    t = themes.primary_theme("Spanish for beginners", "Easy Languages")
    assert t and t["id"] == "languages"


def test_comedy_channel():
    t = themes.primary_theme("Выпуск", "Канал Кшиштовского")
    assert t and t["id"] == "comedy"
