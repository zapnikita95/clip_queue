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


def test_spoyk_essay_not_cinema():
    """Essay mentioning КиноПоиск/фильм in description must not become cinema."""
    title = "КАК У НАС УКРАЛИ ЖИЗНЬ — ты готов к этому разговору"
    desc = (
        "Жизнь в России за последние годы превратилась в постоянное выживание. "
        "Выгорание от новостного потока, цензура (резня аниме на «КиноПоиске»), "
        "философский посыл фильма «Пролетая над гнездом кукушки». "
        "Актуальные новости игр, кино, делюсь мнением."
    )
    found = themes.detect_themes(title, "SPOYK", description=desc)
    ids = [t["id"] for t in found]
    assert "cinema" not in ids
    # Still classify real film reviews
    review = themes.primary_theme("Обзор фильма Дюна 2", "Кинопоиск")
    assert review and review["id"] == "cinema"


def test_cinema_title_still_works():
    t = themes.primary_theme("Лучшие сериалы 2024", "Some Channel")
    assert t and t["id"] == "cinema"
