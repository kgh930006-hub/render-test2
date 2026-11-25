"""Deep web search on request: Bing HTML (keyless) + page fetch.

DuckDuckGo HTML currently serves a bot challenge from this VM, so Bing is
primary and DuckDuckGo stays as fallback. Stdlib only.
"""
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self.parts.append(text)


def _fetch(url, timeout=15, max_bytes=600_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(max_bytes)
        ctype = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(ctype, "replace")


def _clean(html_fragment):
    text = re.sub(r"<[^>]+>", " ", html_fragment)
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    return re.sub(r"\s+", " ", text).strip()


def bing_search(query, max_results=5):
    import base64
    import html as htmlmod

    url = "https://www.bing.com/search?" + urllib.parse.urlencode(
        {"q": query, "count": max_results}
    )
    page = _fetch(url, timeout=20)
    results = []
    for m in re.finditer(
        r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S
    ):
        href = htmlmod.unescape(m.group(1))
        title = _clean(m.group(2))
        if "bing.com/ck/" in href:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            u = qs.get("u", [""])[0]
            if u.startswith("a1"):
                try:
                    href = base64.urlsafe_b64decode(u[2:] + "==").decode()
                except Exception:
                    continue
            else:
                continue
        if not href.startswith("http") or "bing.com" in href:
            continue
        # snippet: first <p> after this heading
        tail = page[m.end() : m.end() + 2500]
        snip_m = re.search(r"<p[^>]*>(.*?)</p>", tail, re.S)
        snippet = _clean(snip_m.group(1))[:300] if snip_m else ""
        results.append({"title": title, "url": href, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


def ddg_search(query, max_results=5):
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    html = _fetch(url, timeout=20)
    results = []
    for m in re.finditer(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S
    ):
        href, title = m.group(1), _clean(m.group(2))
        parsed = urllib.parse.urlparse(href)
        qs = urllib.parse.parse_qs(parsed.query)
        real = qs.get("uddg", [href])[0]
        if real.startswith("//"):
            real = "https:" + real
        results.append({"title": title, "url": real, "snippet": ""})
        if len(results) >= max_results:
            break
    return results


def web_search(query, max_results=5):
    try:
        results = bing_search(query, max_results)
        if results:
            return results
    except Exception:
        pass
    return ddg_search(query, max_results)


def fetch_page_text(url, max_chars=3500):
    html = _fetch(url, timeout=15)
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def deep_search(query):
    """Search + fetch top pages. Returns (context_text, sources_list)."""
    results = web_search(query)
    if not results:
        return "", []
    chunks = []
    sources = []
    for r in results:
        sources.append(r["url"])
        chunks.append(f"[{r['title']}] {r['snippet']}")
    for r in results[:2]:
        try:
            page = fetch_page_text(r["url"])
            if page:
                chunks.append(f"من {r['url']}:\n{page}")
        except Exception:
            continue
    return "\n\n".join(chunks)[:9000], sources
