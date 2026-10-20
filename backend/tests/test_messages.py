from app.agent import step_user_message


def test_internet_step_keeps_only_the_link():
    text = step_user_message("Оцени заголовки страницы.", "https://example.com", None)
    assert "https://example.com" in text
    assert "НАЧАЛО ТЕКСТА СТРАНИЦЫ" not in text


def test_offline_step_includes_page_text():
    text = step_user_message("Оцени заголовки страницы.", "https://example.com", "Title: Кухни")
    assert "Title: Кухни" in text
    assert "НАЧАЛО ТЕКСТА СТРАНИЦЫ" in text
    assert "КОНЕЦ ТЕКСТА СТРАНИЦЫ" in text
