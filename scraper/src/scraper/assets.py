"""AssetDownloader: stores images locally (original format, deduplicated by SHA-256)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from .urls import is_private_host, slugify

log = logging.getLogger(__name__)

CONTENT_TYPE_EXT = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/pjpeg": "jpg", "image/png": "png", "image/gif": "gif",
    "image/webp": "webp", "image/avif": "avif", "image/svg+xml": "svg", "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico", "image/bmp": "bmp", "image/tiff": "tif", "image/heic": "heic",
}
IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp", "avif", "svg", "ico", "bmp", "tif", "tiff", "heic"}


@dataclass
class AssetRecord:
    id: str
    file: str  # archive-relative
    sha256: str
    bytes: int
    content_type: str | None
    width: int | None = None
    height: int | None = None
    original_urls: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "file": self.file,
            "originalUrls": self.original_urls,
            "contentType": self.content_type,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "width": self.width,
            "height": self.height,
            "pages": self.pages,
        }


class AssetDownloader:
    def __init__(self, output_dir: Path, client: httpx.AsyncClient, max_bytes: int, allow_private: bool, concurrency: int = 8):
        self.output_dir = output_dir
        self.client = client
        self.max_bytes = max_bytes
        self.allow_private = allow_private
        self.semaphore = asyncio.Semaphore(concurrency)
        self.by_url: dict[str, AssetRecord] = {}
        self.by_sha: dict[str, AssetRecord] = {}
        self.failures: dict[str, str] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    async def get(self, url: str, data: bytes | None = None) -> AssetRecord | None:
        """Download (once) and return the record for `url`, or None on failure."""
        if url in self.by_url:
            return self.by_url[url]
        if url in self.failures:
            return None
        task = self._tasks.get(url)
        if task is None:
            task = asyncio.create_task(self._load(url, data))
            self._tasks[url] = task
        return await task

    async def _load(self, url: str, data: bytes | None) -> AssetRecord | None:
        try:
            if data is not None:
                content_type = "image/svg+xml" if url.startswith("inline-svg:") else sniff_type(data)
                record = self._store(url, data, content_type)
            else:
                async with self.semaphore:
                    payload, content_type = await self._download(url)
                record = self._store(url, payload, content_type)
        except Exception as exc:
            self.failures[url] = str(exc) or type(exc).__name__
            log.info("asset failed %s: %s", url, exc)
            return None
        self.by_url[url] = record
        return record

    async def _download(self, url: str) -> tuple[bytes, str | None]:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise ValueError(f"unsupported URL scheme '{parts.scheme}'")
        if not self.allow_private and is_private_host(parts.hostname or ""):
            raise ValueError("private or local address not allowed")
        async with self.client.stream("GET", url) as response:
            if response.status_code >= 400:
                raise ValueError(f"HTTP {response.status_code}")
            declared = int(response.headers.get("content-length") or 0)
            if declared > self.max_bytes:
                raise ValueError(f"too large ({declared} bytes)")
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > self.max_bytes:
                    raise ValueError(f"too large (> {self.max_bytes} bytes)")
                chunks.append(chunk)
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower() or None
        payload = b"".join(chunks)
        sniffed = sniff_type(payload)
        if content_type in (None, "application/octet-stream", "binary/octet-stream", "text/plain", "text/xml", "application/xml"):
            content_type = sniffed or content_type
        if not (content_type or "").startswith("image/"):
            if sniffed:
                content_type = sniffed
            else:
                raise ValueError(f"not an image ({content_type})")
        if not payload:
            raise ValueError("empty response")
        return payload, content_type

    def _store(self, url: str, payload: bytes, content_type: str | None) -> AssetRecord:
        sha = hashlib.sha256(payload).hexdigest()
        existing = self.by_sha.get(sha)
        if existing is not None:
            if url not in existing.original_urls and not url.startswith(("data:", "inline-svg:")):
                existing.original_urls.append(url)
            return existing
        ext = CONTENT_TYPE_EXT.get(content_type or "")
        name = "image"
        if not url.startswith(("data:", "inline-svg:")):
            last = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
            if "." in last:
                stem, url_ext = last.rsplit(".", 1)
                name = stem or name
                if not ext and url_ext.lower() in IMAGE_EXTS:
                    ext = url_ext.lower()
            elif last:
                name = last
        else:
            name = "inline-svg" if url.startswith("inline-svg:") else "embedded"
        ext = ext or "bin"
        filename = f"{sha[:8]}-{slugify(name, 40)}.{ext}"
        rel = f"assets/images/{filename}"
        target = self.output_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        width, height = image_size(payload, content_type)
        record = AssetRecord(
            id=sha[:16],
            file=rel,
            sha256=sha,
            bytes=len(payload),
            content_type=content_type,
            width=width,
            height=height,
            original_urls=[] if url.startswith(("data:", "inline-svg:")) else [url],
        )
        self.by_sha[sha] = record
        return record


def sniff_type(data: bytes) -> str | None:
    head = data[:64]
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:12] in (b"ftypavif", b"ftypavis"):
        return "image/avif"
    if head[:4] == b"\x00\x00\x01\x00":
        return "image/x-icon"
    if head[:2] == b"BM":
        return "image/bmp"
    text = data[:1024].lstrip().lower()
    if text.startswith(b"<svg") or (text.startswith(b"<?xml") and b"<svg" in data[:4096].lower()):
        return "image/svg+xml"
    return None


def image_size(data: bytes, content_type: str | None) -> tuple[int | None, int | None]:
    try:
        if data.startswith(b"\x89PNG") and len(data) >= 24:
            width, height = struct.unpack(">II", data[16:24])
            return width, height
        if data[:6] in (b"GIF87a", b"GIF89a"):
            width, height = struct.unpack("<HH", data[6:10])
            return width, height
        if data[:3] == b"\xff\xd8\xff":
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    height, width = struct.unpack(">HH", data[i + 5:i + 9])
                    return width, height
                length = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + length
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            chunk = data[12:16]
            if chunk == b"VP8X":
                width = 1 + int.from_bytes(data[24:27], "little")
                height = 1 + int.from_bytes(data[27:30], "little")
                return width, height
            if chunk == b"VP8 ":
                width, height = struct.unpack("<HH", data[26:30])
                return width & 0x3FFF, height & 0x3FFF
            if chunk == b"VP8L":
                bits = int.from_bytes(data[21:25], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if content_type == "image/svg+xml":
            head = data[:2048].decode("utf-8", "ignore")
            tag = re.search(r"<svg[^>]*>", head, re.S)
            if tag:
                w = re.search(r'\swidth="(\d+)(?:px)?"', tag.group(0))
                h = re.search(r'\sheight="(\d+)(?:px)?"', tag.group(0))
                if w and h:
                    return int(w.group(1)), int(h.group(1))
                vb = re.search(r'viewBox="[\d.\s-]+?\s([\d.]+)\s([\d.]+)"', tag.group(0))
                if vb:
                    return int(float(vb.group(1))), int(float(vb.group(2)))
    except (struct.error, IndexError, ValueError):
        pass
    return None, None
