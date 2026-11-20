import struct
import zlib

import httpx

from scraper.assets import AssetDownloader, image_size, sniff_type


def png(width: int, height: int) -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\x00\x00\x00" * width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


PNG = png(3, 2)


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path in ("/img/a.png", "/img/copy.png"):
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    if path == "/img/noext":
        return httpx.Response(200, content=PNG, headers={"content-type": "application/octet-stream"})
    if path == "/img/page.html":
        return httpx.Response(200, content=b"<html></html>", headers={"content-type": "text/html"})
    if path == "/img/big.png":
        return httpx.Response(200, content=PNG + b"\x00" * 5000, headers={"content-type": "image/png"})
    return httpx.Response(404)


async def test_download_dedupe_and_failures(tmp_path):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        downloader = AssetDownloader(tmp_path, client, max_bytes=2000, allow_private=False)
        a = await downloader.get("https://example.com/img/a.png")
        copy = await downloader.get("https://example.com/img/copy.png")
        noext = await downloader.get("https://example.com/img/noext")
        assert a is copy is noext  # identical bytes -> one file
        assert a.original_urls == [
            "https://example.com/img/a.png",
            "https://example.com/img/copy.png",
            "https://example.com/img/noext",
        ]
        assert a.file.startswith("assets/images/") and a.file.endswith("-a.png")
        assert (tmp_path / a.file).read_bytes() == PNG
        assert (a.width, a.height) == (3, 2)

        assert await downloader.get("https://example.com/img/page.html") is None
        assert "not an image" in downloader.failures["https://example.com/img/page.html"]
        assert await downloader.get("https://example.com/img/big.png") is None
        assert "too large" in downloader.failures["https://example.com/img/big.png"]
        assert await downloader.get("https://example.com/img/missing.png") is None
        assert downloader.failures["https://example.com/img/missing.png"] == "HTTP 404"
        assert await downloader.get("http://127.0.0.1/x.png") is None
        assert "private" in downloader.failures["http://127.0.0.1/x.png"]


async def test_inline_svg(tmp_path):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"></svg>'
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        downloader = AssetDownloader(tmp_path, client, max_bytes=2000, allow_private=False)
        record = await downloader.get("inline-svg:sha256,abc", data=svg)
    assert record.file.endswith("-inline-svg.svg")
    assert record.original_urls == []
    assert (record.width, record.height) == (20, 10)


def test_sniff_and_size():
    assert sniff_type(PNG) == "image/png"
    assert sniff_type(b"<?xml version='1.0'?><svg></svg>") == "image/svg+xml"
    assert sniff_type(b"<html>") is None
    assert image_size(b"GIF89a" + struct.pack("<HH", 7, 9), "image/gif") == (7, 9)
