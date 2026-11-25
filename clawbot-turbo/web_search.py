"""PATCH P-SEARCH v2 / TURBO: keyless parallel web search (Bing + Wikipedia).

deep_search(query, llm) -> (context_text, sources)  [signature unchanged]
v2: Bing + Arabic/English Wikipedia in parallel, first 3 pages fetched in
parallel (6s cap each), 10-minute result cache, then LLM summary with sources.
"""
import concurrent.futures
import json
import re
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
_cache = {}
CACHE_TTL = 600


def _fetch(url, timeout=8):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _strip_html(html):
    html = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&quot;|&#39;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def bing_results(query, count=6):
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "count": count})
    html = _fetch(url, timeout=10)
    out = []
    for m in re.finditer(r'<li class="b_algo".*?</li>', html, re.S):
        block = m.group(0)
        a = re.search(r'<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        link = a.group(1)
        if "bing.com" in link or "microsoft.com" in link:
            continue
        title = _strip_html(a.group(2))
        p = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
        snippet = _strip_html(p.group(1)) if p else ""
        out.append({"title": title, "url": link, "snippet": snippet})
        if len(out) >= count:
            break
    return out


def wiki_results(query, count=3):
    out = []
    for lang in ("ar", "en"):
        try:
            api = (f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&format=json"
                   f"&srlimit={count}&srsearch=" + urllib.parse.quote(query))
            req = urllib.request.Request(api, headers={"User-Agent": "ClawBotTurbo/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            for hit in data.get("query", {}).get("search", []):
                title = hit["title"]
                out.append({"title": f"Wikipedia: {title}",
                            "url": f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                            "snippet": _strip_html(hit.get("snippet", ""))})
            if out:
                break
        except Exception:
            continue
    return out


async def deep_search(query, llm):
    from agent import _ask_llm
    q = (query or "").strip()
    if not q:
        return "أرسل استعلام بحث بعد /search", []
    cached = _cache.get(q)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1], cached[2]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f_bing = ex.submit(bing_results, q, 6)
        f_wiki = ex.submit(wiki_results, q, 3)
        for f in (f_bing, f_wiki):
            try:
                results.extend(f.result(timeout=15))
            except Exception:
                pass
    if not results:
        return "لم أجد نتائج (محرك البحث لم يرد). جرّب صياغة أخرى.", []
    def _page(r):
        try:
            return _strip_html(_fetch(r["url"], timeout=6))[:2500]
        except Exception:
            return ""
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        pages = list(ex.map(_page, results[:3]))
    blocks, sources = [], []
    for i, r in enumerate(results[:6]):
        body = pages[i] if i < len(pages) else ""
        blocks.append(f"[{i+1}] {r['title']}\n{r['snippet']}\n{body}".strip())
        sources.append(r["url"])
    prompt = ("اعتمد فقط على نتائج البحث التالية للإجابة عن السؤال، واذكر أرقام المصادر [n]. "
              "إن لم تحتوِ النتائج إجابة مباشرة قل ذلك بصراحة ولخّص ما وجدته. أجب بلغة السؤال.\n\n"
              f"السؤال: {q}\n\n" + "\n\n".join(blocks))
    try:
        answer = await _ask_llm(llm, prompt)
    except Exception as e:
        answer = "تعذّر تلخيص النتائج بالنموذج (" + type(e).__name__ + "). إليك أهم المقاطع:\n" + \
                 "\n".join(f"- {r['title']}: {r['snippet'][:200]}" for r in results[:4])
    _cache[q] = (time.time(), answer, sources)
    return answer, sources
