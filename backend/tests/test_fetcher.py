from app.fetcher import decode_html, html_to_page_text


HTML = """
<html>
  <head>
    <title>Кухни на заказ</title>
    <meta name="description" content="Шкафы и кухни в Москве">
    <link rel="canonical" href="https://example.com/kuhni">
  </head>
  <body>
    <script>secret()</script>
    <h1>Кухни</h1>
    <p>Делаем кухни по размерам.</p>
  </body>
</html>
"""


def test_extracts_visible_text_and_drops_script():
    text = html_to_page_text(HTML, "https://example.com/kuhni")
    assert "Кухни на заказ" in text
    assert "Шкафы и кухни" in text
    assert "H1: Кухни" in text
    assert "Делаем кухни по размерам." in text
    assert "secret" not in text
    assert "https://example.com/kuhni" in text


def test_decodes_meta_charset_when_header_missing():
    raw = (
        "<meta charset='windows-1251'><title>Кухня</title>"
    ).encode("cp1251")
    text = decode_html(raw, None)
    assert "Кухня" in text
