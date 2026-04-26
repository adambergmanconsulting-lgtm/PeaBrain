"""
Fetch a public http(s) URL and return plain text for the PeaBrain demo.
Blocks private / loopback / link-local addresses (SSRF) and validates on redirects.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import unquote, urljoin, urlparse

import httpx

# Content we decode as text in the demo
_TEXT_CT = re.compile(
    r"^(text/|application/(json|xml|javascript|xhtml)|application/xhtml\+xml)",
    re.IGNORECASE,
)
_HTML_CT = re.compile(
    r"^(text/html|application/xhtml|application/xhtml\+xml)",
    re.IGNORECASE,
)


def _addr_is_allowed(addr: str) -> bool:
    try:
        a = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved:
        return False
    if a.version == 4 and str(a).startswith("0."):
        return False
    if a == ipaddress.IPv4Address("0.0.0.0") or a == ipaddress.IPv4Address("255.255.255.255"):
        return False
    if a in (ipaddress.IPv6Address("::1"),):
        return False
    return True


def _dns_is_safe(host: str) -> bool:
    h = (host or "").strip("[]")
    if h.lower() in ("localhost", "0.0.0.0"):
        return False
    try:
        a = ipaddress.ip_address(h)
        return _addr_is_allowed(str(a))
    except ValueError:
        pass
    try:
        for res in socket.getaddrinfo(h, None, type=socket.SOCK_STREAM):
            sa = res[4]
            if not sa:
                continue
            if not _addr_is_allowed(str(sa[0])):
                return False
    except OSError:
        return False
    return True


def validate_http_url_for_fetch(url: str) -> str:
    s = (url or "").strip()
    if not s or len(s) > 8_000:
        raise ValueError("bad url")
    p = urlparse(s)
    if p.scheme not in ("http", "https"):
        raise ValueError("only http and https are allowed")
    h0 = p.hostname
    if not h0:
        raise ValueError("invalid host")
    h = h0.strip("[]")
    try:
        a = ipaddress.ip_address(h)
    except ValueError:
        if not _dns_is_safe(h):
            raise ValueError("host resolves to a disallowed address")
        return s
    if not _addr_is_allowed(str(a)):
        raise ValueError("address not allowed for fetch")
    return s


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    t = re.sub(r"(?is)<(script|style|template)\b[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"(?is)<!--.*?-->", " ", t)
    t = re.sub(
        r"<(br|p|div|tr|h[1-6]|li)\b[^>]*>",
        "\n",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = unquote(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


async def fetch_url_to_text(
    url: str,
    *,
    max_bytes: int = 1_000_000,
    max_text_chars: int = 32_000,
    max_redirects: int = 5,
) -> tuple[str, str]:
    try:
        u = validate_http_url_for_fetch(url)
    except ValueError as e:
        return "", f"rejected: {e}"

    headers = {
        "User-Agent": "PeaBrain-NadirDemo/1.0 (URL context fetch)",
        "Accept": "text/html, text/plain, application/json, */*;q=0.1",
    }
    current = u
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers=headers,
            follow_redirects=False,
        ) as client:
            for _ in range(max_redirects + 1):
                validate_http_url_for_fetch(current)
                r = await client.get(current)
                if 300 <= r.status_code < 400:
                    loc = (r.headers.get("location") or "").strip()
                    if not loc:
                        return "", "redirect with no location"
                    current = str(urljoin(str(r.request.url), loc))[:8_000]
                    continue
                r.raise_for_status()
                if len(r.content) > max_bytes:
                    return "", f"page larger than {max_bytes} bytes"
                ct = (r.headers.get("content-type") or "").split(";", 1)[0].strip()
                is_html = "html" in (ct or "").lower() or "xml" in (ct or "").lower()
                if not _TEXT_CT.match(ct) and not is_html:
                    return (
                        "",
                        f"unsupported content-type: {ct or 'unknown'} (try a web page or plain text URL)",
                    )
                raw = r.text
                if is_html or _HTML_CT.search(ct) or (not ct and "<html" in (raw or "")[:500].lower()):
                    out = _html_to_text(raw)
                else:
                    out = raw
                if len(out) > max_text_chars:
                    out = out[: max_text_chars] + "\n\n[...truncated for demo]"
                return out, ""
            return "", "too many redirects"
    except httpx.HTTPStatusError as e:
        tail = (e.response.text or "")[:400]
        return "", f"HTTP {e.response.status_code}: {tail}"
    except httpx.RequestError as e:
        return "", f"request failed: {e}"
    except OSError as e:
        return "", str(e)
