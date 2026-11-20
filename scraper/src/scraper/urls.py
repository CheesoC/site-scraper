"""URLNormalizer: canonical URLs, site paths and archive directories."""

from __future__ import annotations

import hashlib
import ipaddress
import posixpath
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "gclid", "gclsrc", "dclid", "fbclid", "msclkid", "yclid", "igshid", "twclid", "ttclid", "li_fat_id",
    "mc_cid", "mc_eid", "_ga", "_gl", "_hsenc", "_hsmi", "__hstc", "__hssc", "__hsfp", "hsctatracking",
    "ref", "ref_src", "spm", "scid", "s_kwcid", "trk", "wt_mc", "pk_campaign", "pk_kwd", "pk_source",
    "pk_medium", "piwik_campaign", "piwik_kwd", "matomo_campaign", "srsltid", "si",
}
TRACKING_PREFIXES = ("utm_", "hsa_", "mtm_", "pk_", "vero_", "oly_")
SESSION_PARAMS = {"phpsessid", "jsessionid", "sid", "sessionid", "cfid", "cftoken"}

INDEX_FILE_RE = re.compile(r"/index\.(?:html?|php|aspx?|jsp)$", re.IGNORECASE)
HTML_EXT_RE = re.compile(r"\.(?:html?|php|aspx?|jsp)$", re.IGNORECASE)

NON_PAGE_EXTENSIONS = {
    # documents / downloads
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "rtf", "txt", "csv",
    "zip", "rar", "7z", "gz", "tgz", "tar", "dmg", "exe", "msi", "apk", "ics", "vcf",
    # media
    "jpg", "jpeg", "png", "gif", "webp", "avif", "svg", "ico", "bmp", "tif", "tiff",
    "mp4", "webm", "mov", "avi", "mkv", "mp3", "wav", "ogg", "m4a", "flac",
    # code / data
    "css", "js", "mjs", "json", "xml", "rss", "atom", "woff", "woff2", "ttf", "otf", "eot", "map",
}

SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:", "callto:", "skype:", "whatsapp:", "fax:", "geo:")


def _is_tracking(name: str) -> bool:
    lowered = name.lower()
    return lowered in TRACKING_PARAMS or lowered in SESSION_PARAMS or lowered.startswith(TRACKING_PREFIXES)


def slugify(value: str, max_len: int = 60) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.replace("ß", "ss")
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value).strip("-_")
    value = re.sub(r"-{2,}", "-", value)
    return value[:max_len].strip("-") or "_"


def short_hash(value: str, length: int = 6) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def is_private_host(host: str) -> bool:
    if not host:
        return True
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified


@dataclass(frozen=True)
class LinkInfo:
    """Result of classifying an href found on a page."""

    href: str  # absolute URL (or original value for mailto:, tel:, ...)
    url: str | None  # normalized absolute URL if http(s), else None
    internal: bool
    is_page: bool  # internal and probably an HTML page (not a download)
    fragment: str


class URLNormalizer:
    """Normalizes URLs of one site and maps them to site paths.

    * scheme/host lower case, default ports removed
    * fragment removed, tracking/session parameters removed, remaining query sorted
    * dot segments resolved, duplicate slashes collapsed, no trailing slash (except root)

    Scope: on the start host only URLs below `scope` (a path prefix such as "/fsamzeisigwald/") are
    internal, and that prefix becomes the site root "/" in site paths. By default the scope is the
    directory of the start URL (everything up to its last "/"); "/" means the whole host.
    """

    def __init__(
        self,
        start_url: str,
        allow_domains: list[str] | None = None,
        query_mode: str = "keep",
        scope_path: str | None = None,
    ):
        if "://" not in start_url:
            start_url = "https://" + start_url
        self.start_url = self.normalize(start_url, keep_query=True) or start_url
        parts = urlsplit(self.start_url)
        self.scheme = parts.scheme
        self.host = parts.hostname or ""
        self.netloc = parts.netloc
        self.query_mode = query_mode
        bare = self.host[4:] if self.host.startswith("www.") else self.host
        self.primary_hosts = {bare, "www." + bare} if bare else {self.host}
        self.allow_patterns = [d.lower().strip() for d in (allow_domains or []) if d.strip()]
        if scope_path is None:
            raw_path = urlsplit(start_url).path or "/"
            scope_path = raw_path[: raw_path.rfind("/") + 1] or "/"
        self.scope = self._scope_prefix(scope_path)
        self._scope_unquoted = unquote(self.scope)
        if not self.in_scope(urlsplit(self.start_url).path or "/"):
            raise ValueError(f"Start-URL {self.start_url} liegt nicht im Bereich {self.scope}")

    def _scope_prefix(self, path: str) -> str:
        """Normalize a scope path to "/" or "/a/b/" (leading and trailing slash, quoted like page URLs)."""
        path = (path or "/").strip()
        if not path.startswith("/"):
            path = "/" + path
        normalized = self.normalize(f"{self.scheme}://{self.netloc}{path}")
        path = urlsplit(normalized).path if normalized else "/"
        return path if path == "/" else path.rstrip("/") + "/"

    @property
    def root_url(self) -> str:
        """URL of the scope root, e.g. https://cms.sachsen.schule/fsamzeisigwald/."""
        return f"{self.scheme}://{self.netloc}{self.scope}"

    def in_scope(self, path: str) -> bool:
        """Whether a (quoted) URL path on the start host lies inside the scope."""
        if self.scope == "/":
            return True
        return path == self.scope[:-1] or path.startswith(self.scope)

    def is_primary_host(self, host: str) -> bool:
        return host in self.primary_hosts or host == self.host

    # ------------------------------------------------------------------ urls
    def normalize(self, url: str, base: str | None = None, keep_query: bool | None = None) -> str | None:
        """Return the normalized absolute http(s) URL or None for unsupported URLs."""
        if not url:
            return None
        url = url.strip()
        if url.lower().startswith(SKIP_SCHEMES):
            return None
        if base:
            url = urljoin(base, url)
        try:
            parts = urlsplit(url)
        except ValueError:
            return None
        scheme = parts.scheme.lower()
        if scheme not in ("http", "https"):
            return None
        host = (parts.hostname or "").lower().rstrip(".")
        if not host:
            return None
        try:
            port = parts.port
        except ValueError:
            return None
        netloc = host
        if ":" in host and not host.startswith("["):
            netloc = f"[{host}]"
        if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
            netloc += f":{port}"

        path = parts.path or "/"
        path = re.sub(r"/{2,}", "/", path)
        trailing = path.endswith("/")
        path = posixpath.normpath(path)
        if path in (".", ""):
            path = "/"
        if not path.startswith("/"):
            path = "/" + path
        if trailing and path != "/":
            path += "/"
        path = quote(unquote(path), safe="/:@!$&'()*+,;=-._~")
        if path != "/":
            path = path.rstrip("/")

        mode = self.query_mode if getattr(self, "query_mode", None) else "keep"
        if keep_query is True:
            mode = "keep"
        query = ""
        if mode == "keep" and parts.query:
            pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _is_tracking(k)]
            pairs.sort()
            query = urlencode(pairs, doseq=True)
        return urlunsplit((scheme, netloc, path, query, ""))

    def is_internal(self, url: str) -> bool:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if self.is_primary_host(host):
            # the start host is restricted to the scope, even if an --allow-domain pattern would match it
            return self.in_scope(parts.path or "/")
        for pattern in self.allow_patterns:
            if pattern.startswith("*."):
                if host == pattern[2:] or host.endswith(pattern[1:]):
                    return True
            elif host == pattern:
                return True
        return False

    @staticmethod
    def looks_like_page(url: str) -> bool:
        path = urlsplit(url).path
        last = path.rsplit("/", 1)[-1]
        if "." in last:
            ext = last.rsplit(".", 1)[-1].lower()
            return ext not in NON_PAGE_EXTENSIONS
        return True

    def classify(self, href: str, base: str) -> LinkInfo | None:
        """Classify an href found on page `base`. Returns None for empty/anchor-only junk."""
        if href is None:
            return None
        raw = href.strip()
        if not raw:
            return None
        if raw.lower().startswith("javascript:"):
            return None
        if raw.lower().startswith(SKIP_SCHEMES):
            return LinkInfo(href=raw, url=None, internal=False, is_page=False, fragment="")
        absolute = urljoin(base, raw)
        fragment = urlsplit(absolute).fragment
        normalized = self.normalize(absolute)
        if normalized is None:
            return LinkInfo(href=absolute, url=None, internal=False, is_page=False, fragment="")
        internal = self.is_internal(normalized)
        return LinkInfo(
            href=absolute,
            url=normalized,
            internal=internal,
            is_page=internal and self.looks_like_page(normalized),
            fragment=fragment,
        )

    # ----------------------------------------------------------------- paths
    def to_path(self, url: str) -> str:
        """Map a normalized internal URL to a site path ("/", "/leistungen/seo", ...)."""
        parts = urlsplit(url)
        path = unquote(parts.path or "/")
        host = (parts.hostname or "").lower()
        if self.scope != "/" and self.is_primary_host(host):
            # the scope prefix becomes the site root: /fsamzeisigwald/kontakt.html -> /kontakt.html
            prefix = self._scope_unquoted
            if path == prefix[:-1]:
                path = "/"
            elif path.startswith(prefix):
                path = "/" + path[len(prefix):]
        path = INDEX_FILE_RE.sub("/", path)
        if path != "/":
            path = path.rstrip("/")
            path = HTML_EXT_RE.sub("", path)
        path = re.sub(r"\s", "-", path) or "/"
        if host and not self.is_primary_host(host):
            path = f"/_/{host}" + (path if path != "/" else "")
        if parts.query:
            suffix = "q-" + slugify(unquote(parts.query).replace("=", "-").replace("&", "-"), 50)
            if len(parts.query) > 50:
                suffix += "-" + short_hash(parts.query)
            path = (path.rstrip("/") or "") + "/" + suffix
        return path if path.startswith("/") else "/" + path


class DirAllocator:
    """Assigns readable, unique archive directories to site paths."""

    def __init__(self, prefix: str = "pages"):
        self.prefix = prefix
        self.by_path: dict[str, str] = {}
        self.taken: set[str] = set()

    def allocate(self, path: str) -> str:
        if path in self.by_path:
            return self.by_path[path]
        if path == "/":
            rel = "index"
        else:
            rel = "/".join(slugify(seg) for seg in path.strip("/").split("/") if seg)
            rel = rel or "_"
        candidate = f"{self.prefix}/{rel}"
        if candidate in self.taken:
            candidate = f"{candidate}-{short_hash(path)}"
        self.taken.add(candidate)
        self.by_path[path] = candidate
        return candidate
