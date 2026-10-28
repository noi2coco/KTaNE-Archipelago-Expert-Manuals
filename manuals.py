import queue
import ssl
import threading
import time
import urllib.parse
import urllib.request

import certifi

from catalog import allModsRepo

ssl_context = ssl.create_default_context(cafile=certifi.where())

REQUEST_TIMEOUT = 10  # seconds, for every single HTTP request
REQUEST_ATTEMPTS = 3
KTANE_UTILS_URL = "https://ktane.timwi.de/HTML/js/ktane-utils.js"


def patchKtaneUtils(script):
    """ktane-utils.js loads jQuery relative to itself, which does not work when it is inlined into our pages."""
    return script.replace('e.src = scriptDir + "jquery.3.7.0.min.js"', 'e.src = "https://ktane.timwi.de/HTML/js/jquery.3.7.0.min.js"')

def renderManual(moduleName, playerInfo, fetch):
    """Download one manual and rewrite it so that it works when served from localhost."""
    module = ""
    if moduleName in list(allModsRepo[playerInfo["sdLanguage"]].keys()):
        module = allModsRepo[playerInfo["sdLanguage"]][moduleName]
    else:
        module = allModsRepo["en"][moduleName]
    fullUrl = "https://ktane.timwi.de/HTML/" + module + ".html" + ("" if playerInfo["sdRuleSeed"] == 1 else "#" + str(playerInfo["sdRuleSeed"]))
    fullUrl = fullUrl.replace("%20", " ").replace("%26", "&").replace("%27", "'")

    #encoding fix
    parts = urllib.parse.urlsplit(fullUrl)
    encoded_path = urllib.parse.quote(parts.path)
    encoded_query = urllib.parse.quote(parts.query, safe="=&")
    encodedFullUrl = urllib.parse.urlunsplit((parts.scheme, parts.netloc, encoded_path, encoded_query, parts.fragment))

    htmlContent = fetch(encodedFullUrl)

    htmlContent = htmlContent.replace(
        '<link rel="stylesheet" type="text/css" href="css/font.css">',
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n<link href="https://fonts.googleapis.com/css2?family=Special+Elite&display=swap" rel="stylesheet">'
    )
    #CORS problem
    #russianFontCss = urllib.request.urlopen("https://ktane.timwi.de/HTML/css/font-cyrillic.css", context=ssl_context).read().decode("utf8")
    #russianFontCss = russianFontCss.replace("..", "https://ktane.timwi.de/HTML")
    #htmlContent = htmlContent.replace(
    #    '<link rel="stylesheet" type="text/css" href="css/font-cyrillic.css">',
    #    '<style>' + russianFontCss + "</style>"
    #)
    #htmlContent = htmlContent.replace(
    #    '<link rel="stylesheet" type="text/css" href="https://ktane.timwi.de/HTML/css/font-cyrillic.css">',
    #    '<style>' + russianFontCss + "</style>"
    #)
    htmlContent = htmlContent.replace(
        '<link rel="stylesheet" type="text/css" href="css/font-cyrillic.css">',
        '<link rel="stylesheet" type="text/css" href="https://ktane.timwi.de/HTML/css/font-cyrillic.css">'
    )
    htmlContent = htmlContent.replace(
        '<link rel="stylesheet" type="text/css" href="css/normalize.css">',
        '<link rel="stylesheet" type="text/css" href="https://ktane.timwi.de/HTML/css/normalize.css">'
    )
    htmlContent = htmlContent.replace(
        '<link rel="stylesheet" type="text/css" href="css/Modules/',
        '<link rel="stylesheet" type="text/css" href="https://ktane.timwi.de/HTML/css/Modules/'
    )
    htmlContent = htmlContent.replace(
        '<link rel="stylesheet" type="text/css" href="css/main.css">',
        '<link rel="stylesheet" type="text/css" href="https://ktane.timwi.de/HTML/css/main.css">'
    )
    ktaneUtilsPage = patchKtaneUtils(fetch(KTANE_UTILS_URL))
    htmlContent = htmlContent.replace(
        '<script src="js/ktane-utils.js"></script>',
        '<script>' + ktaneUtilsPage + '</script>'
    )
    ruleSeedPage = fetch("https://ktane.timwi.de/HTML/js/ruleseed.js")
    ruleSeedPage = ruleSeedPage.replace("this.seed = seed;", "this.seed = " + str(playerInfo["sdRuleSeed"]) + ";")
    ruleSeedPage = ruleSeedPage.replace('if (/^#(\\d+)$/.exec(window.location.hash) && (RegExp.$1 | 0) !== 1)', 'if (' + str(playerInfo["sdRuleSeed"] > 1).lower() + ')')
    ruleSeedPage = ruleSeedPage.replace('var seed = RegExp.$1 | 0;', 'var seed = ' + str(playerInfo["sdRuleSeed"]) + ";")
    if (playerInfo["sdRandomRuleSeed"]):
        ruleSeedPage = ruleSeedPage.replace("Array.from(document.getElementsByClassName('ruleseed-header')).forEach(x => { x.innerText = 'RULE SEED: ' + seed; });", "Array.from(document.getElementsByClassName('ruleseed-header')).forEach(x => { x.innerText = 'Archipelago'; });")
        ruleSeedPage = ruleSeedPage.replace("x.innerText = names[x.getAttribute('name-id')] + ' — rule seed: ' + seed;", "x.innerText = names[x.getAttribute('name-id')] + ' — Archipelago'")
    htmlContent = htmlContent.replace(
        "<script src='js/ruleseed.js'></script>",
        "<script>" + ruleSeedPage + "</script>"
    )
    htmlContent = htmlContent.replace(
        '<script src="js/ruleseed.js"></script>',
        "<script>" + ruleSeedPage + "</script>"
    )
    htmlContent = htmlContent.replace(
        '<script src="js/jquery.3.7.0.min.js"></script>',
        '<script src="https://ktane.timwi.de/HTML/js/jquery.3.7.0.min.js"></script>'
    )
    htmlContent = htmlContent.replace(
        "<script src='js/jquery.3.7.0.min.js'></script>",
        "<script src='https://ktane.timwi.de/HTML/js/jquery.3.7.0.min.js'></script>"
    )
    htmlContent = htmlContent.replace(
        '<script src="js/Utilities/svg-utils.js"></script>',
        '<script src="https://ktane.timwi.de/HTML/js/Utilities/svg-utils.js"></script>'
    )
    htmlContent = htmlContent.replace(
        "<script src='js/Utilities/svg-utils.js'></script>",
        "<script src='https://ktane.timwi.de/HTML/js/Utilities/svg-utils.js'></script>"
    )
    htmlContent = htmlContent.replace(
        "<script src='js/Modules/X-Ray.js'></script>",
        "<script src='https://ktane.timwi.de/HTML/js/Modules/X-Ray.js'></script>"
    )
    htmlContent = htmlContent.replace(
        '<script src="js/Modules/Zoo.js"></script>',
        '<script src="https://ktane.timwi.de/HTML/js/Modules/Zoo.js"></script>'
    )
    htmlContent = htmlContent.replace(
        'img/Comp',
        'https://ktane.timwi.de/HTML/img/Comp'
    )
    htmlContent = htmlContent.replace(
        'img/Keypad/',
        'https://ktane.timwi.de/HTML/img/Keypad/'
    )
    htmlContent = htmlContent.replace(
        'img/Who',
        'https://ktane.timwi.de/HTML/img/Who'
    )
    htmlContent = htmlContent.replace(
        'img/Morse',
        'https://ktane.timwi.de/HTML/img/Morse'
    )
    htmlContent = htmlContent.replace(
        'img/Color',
        'https://ktane.timwi.de/HTML/img/Color'
    )
    htmlContent = htmlContent.replace(
        'img/Friendship',
        'https://ktane.timwi.de/HTML/img/Friendship'
    )
    htmlContent = htmlContent.replace(
        'img/Zoo',
        'https://ktane.timwi.de/HTML/img/Zoo'
    )
    htmlContent = htmlContent.replace(
        "console.log('seed = ' + rnd.seed);",
        ""
    )
    if (playerInfo["sdRandomRuleSeed"]):
        htmlContent = htmlContent.replace(
            "console.log(`[Password rule seed] Seed: ${rnd.seed}",
            "console.log(`[Password rule seed] Seed: Archipelago"
        )
        htmlContent = htmlContent.replace(
            "console.log(`[Morse Code rule seed] Seed: ${rnd.seed}",
            "console.log(`[Morse Code rule seed] Seed: Archipelago"
        )
        htmlContent = htmlContent.replace(
            "console.log(`[Morse-A-Maze rule seed] Seed: ${rnd.seed}",
            "console.log(`[Morse-A-Maze rule seed] Seed: Archipelago"
        )
    return htmlContent


class ManualStore:
    """Downloads the manuals in the background and keeps them in memory.

    Every call to load()/reset() starts a new "generation": results coming from
    an older generation (e.g. a session that was disconnected meanwhile) are discarded.
    Workers are daemon threads and every request has a timeout, so nothing can keep
    the program alive or block it forever.
    """

    def __init__(self, workers=6):
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._generation = 0
        self._info = {}
        self._ready = {}
        self._failed = {}
        self._pending = set()
        self._cache = {}
        self._closed = False
        self._threads = [threading.Thread(target=self._worker, name=f"manual-{i}", daemon=True) for i in range(workers)]
        for thread in self._threads:
            thread.start()

    # -- public API -------------------------------------------------------------------
    def load(self, playerInfo, modules):
        """Forget everything and start downloading `modules` for the given session."""
        with self._lock:
            self._generation += 1
            self._info = dict(playerInfo)
            self._ready = {}
            self._failed = {}
            self._pending = set(modules)
            self._drain_queue()
            for module in modules:
                self._queue.put((self._generation, module))

    def reset(self):
        self.load({}, [])

    def status(self, module):
        """Returns ("ready", html), ("loading", None), ("failed", error) or ("unknown", None)."""
        with self._lock:
            if module in self._ready:
                return "ready", self._ready[module]
            if module in self._pending:
                return "loading", None
            if module in self._failed:
                return "failed", self._failed[module]
            return "unknown", None

    def retry(self, module):
        """Queue a failed manual again."""
        with self._lock:
            if module not in self._failed:
                return
            del self._failed[module]
            self._pending.add(module)
            self._queue.put((self._generation, module))

    def is_loading(self):
        with self._lock:
            return bool(self._pending)

    def ktane_utils(self):
        """The patched ktane-utils.js shared by the appendices (cached). Raises on failure."""
        return patchKtaneUtils(self._fetch(KTANE_UTILS_URL, None))

    def close(self):
        with self._lock:
            self._closed = True
            self._generation += 1
            self._drain_queue()
            for _ in self._threads:
                self._queue.put(None)
        for thread in self._threads:
            thread.join(timeout=1)

    # -- internals --------------------------------------------------------------------
    def _drain_queue(self):
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass

    def _fetch(self, url, generation):
        key = url.split("#", 1)[0]
        cacheable = key.endswith(".js")  # shared scripts only, the manuals themselves are stored once, rendered
        with self._lock:
            if cacheable and key in self._cache:
                return self._cache[key]
        last_error = None
        for attempt in range(REQUEST_ATTEMPTS):
            with self._lock:
                if self._closed or (generation is not None and generation != self._generation):
                    raise RuntimeError("download cancelled")
            try:
                with urllib.request.urlopen(url, context=ssl_context, timeout=REQUEST_TIMEOUT) as response:
                    text = response.read().decode("utf8")
                if cacheable:
                    with self._lock:
                        self._cache[key] = text
                return text
            except Exception as e:
                last_error = e
                time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"{url}: {last_error}")

    def _worker(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            generation, module = item
            with self._lock:
                if generation != self._generation:
                    continue
                info = dict(self._info)
            try:
                result = renderManual(module, info, lambda url: self._fetch(url, generation))
                error = None
            except Exception as e:
                result, error = None, str(e)
            with self._lock:
                if generation != self._generation:
                    continue
                self._pending.discard(module)
                if error is None:
                    self._ready[module] = result
                    print("Loaded " + module)
                else:
                    self._failed[module] = error
                    print(f"Could not load {module}: {error}")
