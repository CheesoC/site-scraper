from scraper.sanitize import sanitize_html


def test_removes_scripts_styles_and_event_handlers():
    html = '<div onclick="x()" class="a"><script>alert(1)</script><style>p{}</style><p style="color:red">Hi <b>du</b></p></div>'
    assert sanitize_html(html) == "<div><p>Hi <b>du</b></p></div>"


def test_unwraps_unknown_tags_and_keeps_text():
    assert sanitize_html("<my-widget><font>Text</font></my-widget>") == "Text"


def test_filters_dangerous_urls():
    html = '<a href="javascript:alert(1)">a</a><a href="/x">b</a><img src="data:image/png;base64,AAA" alt="c">'
    assert sanitize_html(html, url_resolver=lambda u: "https://example.com" + u) == (
        '<a>a</a><a href="https://example.com/x">b</a><img alt="c"/>'
    )


def test_drops_iframes_and_forms():
    assert sanitize_html('<iframe src="https://evil"></iframe><form><input></form><p>ok</p>') == "<p>ok</p>"
