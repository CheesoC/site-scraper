import pytest

from scraper.urls import DirAllocator, URLNormalizer, slugify


def make(**kw):
    return URLNormalizer("https://Example.com/", **kw)


def test_normalize_variants_collapse():
    n = make()
    variants = [
        "https://example.com/",
        "https://example.com/#top",
        "https://example.com/?utm_source=google&utm_medium=cpc",
        "https://EXAMPLE.com:443/?fbclid=abc",
        "https://example.com//",
    ]
    assert {n.normalize(v) for v in variants} == {"https://example.com/"}


def test_normalize_keeps_relevant_query_sorted():
    n = make()
    assert n.normalize("https://example.com/shop?b=2&a=1&utm_campaign=x") == "https://example.com/shop?a=1&b=2"


def test_normalize_drop_query_mode():
    n = make(query_mode="drop")
    assert n.normalize("https://example.com/shop?page=2") == "https://example.com/shop"


def test_normalize_paths():
    n = make()
    assert n.normalize("../a/./b/../c/", base="https://example.com/x/y/") == "https://example.com/x/a/c"
    assert n.normalize("http://example.com:80/a b") == "http://example.com/a%20b"
    assert n.normalize("/%c3%bcber-uns", base="https://example.com/") == "https://example.com/%C3%BCber-uns"


def test_normalize_rejects_non_http():
    n = make()
    for href in ["mailto:a@b.de", "tel:123", "javascript:void(0)", "ftp://example.com/x", ""]:
        assert n.normalize(href, base="https://example.com/") is None


def test_internal_hosts():
    n = make(allow_domains=["*.example.org", "shop.example.net"])
    assert n.is_internal("https://www.example.com/a")
    assert n.is_internal("https://example.com/a")
    assert n.is_internal("https://blog.example.org/")
    assert n.is_internal("https://example.org/")
    assert n.is_internal("https://shop.example.net/")
    assert not n.is_internal("https://other.com/")
    assert not n.is_internal("https://evil-example.com/")


def test_classify_links():
    n = make()
    base = "https://example.com/leistungen/"
    info = n.classify("webdesign#preise", base)
    assert info.internal and info.is_page
    assert info.url == "https://example.com/leistungen/webdesign"
    assert info.fragment == "preise"
    assert n.classify("/files/preise.pdf", base).is_page is False
    ext = n.classify("https://other.com/x", base)
    assert not ext.internal and ext.url == "https://other.com/x"
    mail = n.classify("mailto:info@example.com", base)
    assert mail.url is None and mail.href == "mailto:info@example.com"
    assert n.classify("javascript:void(0)", base) is None
    assert n.classify("   ", base) is None


def test_to_path():
    n = make()
    assert n.to_path("https://example.com/") == "/"
    assert n.to_path("https://example.com/index.html") == "/"
    assert n.to_path("https://example.com/leistungen/index.php") == "/leistungen"
    assert n.to_path("https://example.com/kontakt.html") == "/kontakt"
    assert n.to_path("https://example.com/%C3%BCber-uns") == "/über-uns"
    assert n.to_path("https://www.example.com/a") == "/a"
    assert n.to_path("https://example.com/shop?page=2") == "/shop/q-page-2"
    assert n.to_path("https://example.com/?lang=en") == "/q-lang-en"


def test_to_path_other_allowed_host():
    n = make(allow_domains=["blog.example.com"])
    assert n.to_path("https://blog.example.com/post") == "/_/blog.example.com/post"


SCHOOL = "https://cms.sachsen.schule/fsamzeisigwald/schule-mit-dem-foerderschwerpunkt-geistige-entwicklung.html"


def test_scope_defaults_to_directory_of_start_url():
    assert URLNormalizer("https://example.com/").scope == "/"
    assert URLNormalizer("https://example.com/about.html").scope == "/"
    assert URLNormalizer("https://example.com/schule").scope == "/"
    assert URLNormalizer("https://example.com/schule/").scope == "/schule/"
    n = URLNormalizer(SCHOOL)
    assert n.scope == "/fsamzeisigwald/"
    assert n.root_url == "https://cms.sachsen.schule/fsamzeisigwald/"


def test_scope_limits_internal_urls_on_start_host():
    n = URLNormalizer(SCHOOL)
    assert n.is_internal("https://cms.sachsen.schule/fsamzeisigwald/kontakt.html")
    assert n.is_internal("https://cms.sachsen.schule/fsamzeisigwald")
    assert not n.is_internal("https://cms.sachsen.schule/")
    assert not n.is_internal("https://cms.sachsen.schule/admin/datenschutz")
    assert not n.is_internal("https://cms.sachsen.schule/fsamzeisigwald-andere/x.html")
    assert not n.is_internal("https://cms.sachsen.schule/andereschule/index.html")
    info = n.classify("/andereschule/index.html", SCHOOL)
    assert info.internal is False and info.is_page is False
    # an allow pattern covering the start host does not lift the scope
    wide = URLNormalizer(SCHOOL, allow_domains=["*.sachsen.schule"])
    assert not wide.is_internal("https://cms.sachsen.schule/andereschule/index.html")
    assert wide.is_internal("https://www.sachsen.schule/")


def test_scope_becomes_site_root():
    n = URLNormalizer(SCHOOL)
    assert n.to_path("https://cms.sachsen.schule/fsamzeisigwald/index.html") == "/"
    assert n.to_path("https://cms.sachsen.schule/fsamzeisigwald") == "/"
    assert n.to_path("https://cms.sachsen.schule/fsamzeisigwald/kontakt.html") == "/kontakt"
    assert n.to_path(SCHOOL) == "/schule-mit-dem-foerderschwerpunkt-geistige-entwicklung"
    assert (
        n.to_path("https://cms.sachsen.schule/fsamzeisigwald/schule-mit-dem-foerderschwerpunkt-geistige-entwicklung/gta.html")
        == "/schule-mit-dem-foerderschwerpunkt-geistige-entwicklung/gta"
    )


def test_explicit_scope():
    whole = URLNormalizer(SCHOOL, scope_path="/")
    assert whole.scope == "/" and whole.is_internal("https://cms.sachsen.schule/andereschule/")
    assert whole.to_path(SCHOOL) == "/fsamzeisigwald/schule-mit-dem-foerderschwerpunkt-geistige-entwicklung"
    assert URLNormalizer(SCHOOL, scope_path="fsamzeisigwald").scope == "/fsamzeisigwald/"
    umlaut = URLNormalizer("https://example.com/über/start.html")
    assert umlaut.is_internal(umlaut.normalize("https://example.com/über/kontakt.html"))
    assert umlaut.to_path(umlaut.normalize("https://example.com/über/kontakt.html")) == "/kontakt"
    with pytest.raises(ValueError):
        URLNormalizer(SCHOOL, scope_path="/andereschule/")


def test_slugify():
    assert slugify("Über uns & Team") == "uber-uns-team"
    assert slugify("Straße") == "strasse"
    assert slugify("???") == "_"


def test_dir_allocator_unique_and_readable():
    alloc = DirAllocator()
    assert alloc.allocate("/") == "pages/index"
    assert alloc.allocate("/leistungen/seo") == "pages/leistungen/seo"
    assert alloc.allocate("/über-uns") == "pages/uber-uns"
    second = alloc.allocate("/Über-Uns")
    assert second.startswith("pages/uber-uns-") and second != "pages/uber-uns"
    assert alloc.allocate("/index").startswith("pages/index-")
    assert alloc.allocate("/leistungen/seo") == "pages/leistungen/seo"
