"""Web pages and searches in Chrome."""
import re
import urllib.parse

from tools.common import spawn

# ---------- browser ----------

def open_url(runner, url, note=""):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return spawn(runner, ["flatpak", "run", "com.google.Chrome", url], f"opened {url}{note}")


# She only opens the page; without this note the model describes results it never saw
UNSEEN = ". You cannot see the page or the results: do not describe them or offer to summarize them"


# Site search pages, checked with curl (each returns the search results page).
# Other sites use a Google search limited to that site, which always works.
SEARCH_URLS = {
    "google": "https://www.google.com/search?q={}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={}",
    "youtube": "https://www.youtube.com/results?search_query={}",
    "deviantart": "https://www.deviantart.com/search?q={}",
    "github": "https://github.com/search?q={}",
    "pinterest": "https://www.pinterest.com/search/pins/?q={}",
    "archwiki": "https://wiki.archlinux.org/index.php?search={}",
    "aur": "https://aur.archlinux.org/packages?K={}",
    "duckduckgo": "https://duckduckgo.com/?q={}",
}
SITE_ALIASES = {"wiki": "wikipedia", "yt": "youtube", "deviant art": "deviantart", "devient art": "deviantart",
                "da": "deviantart", "arch wiki": "archwiki", "ddg": "duckduckgo", "web": "google", "": "google"}


def web_search(runner, query, site=""):
    """Search the web, or one site, in a new Chrome tab."""
    key = re.sub(r"\.(com|org|net|io|in)$", "", str(site).lower().strip().removeprefix("www."))
    key = SITE_ALIASES.get(key, key.replace(" ", ""))
    q = urllib.parse.quote_plus(str(query).strip())
    if key in SEARCH_URLS:
        url = SEARCH_URLS[key].format(q)
    else:  # unknown site: Google, limited to that site
        domain = key if "." in key else f"{key}.com"
        url = SEARCH_URLS["google"].format(q + urllib.parse.quote_plus(f" site:{domain}"))
    return open_url(runner, url, UNSEEN)


def open_or_switch(runner, chrome, url):
    """A plain site address (no path, no search): switch to an open tab of that exact host.
    Anything else (a search, a page) opens a new tab."""
    m = re.match(r"^(?:https?://)?([^/?#]+)/?$", url.strip())
    if m:
        host = m.group(1).lower().removeprefix("www.")
        same = [t for t in (chrome.find([host]) or [])
                if re.sub(r"^https?://(www\.)?", "", t["url"]).split("/")[0].lower() == host]
        if same:
            return chrome.switch_tab(str(same[0]["id"]))
    return open_url(runner, url)
