"""HTML pages served by the client.

Every function returns a complete HTML document as a string and has no side effects, so the
pages can be tested without a server. All dynamic values go through _esc().
"""
import html

from catalog import (AdventureMode, allModsRepo, appendixText, modModsLinks, modModsNames,
                     vanModsLinks, vanModsNames, versionNumber)

# ---------------------------------------------------------------------------------------
# Building blocks shared by every page
# ---------------------------------------------------------------------------------------
BOOTSTRAP_CSS = '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.3.1/dist/css/bootstrap.min.css" integrity="sha384-ggOyR0iXCbMQv3Xipma34MD+dH/1fQ784/j6cY/iJTQUOhcWr7x9JvoRxT2MZw1T" crossorigin="anonymous">'
GOOGLE_FONT = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Special+Elite&display=swap" rel="stylesheet">'
)
AP_LOGO = "https://archipelago.gg/static/static/branding/header-logo.svg"
KTANE_LOGO = "https://www.bombmanual.com/img/header.png"
ICON_URL = "https://ktane.timwi.de/Icons/"
APPENDICES_ICON = "https://ktane.timwi.de/HTML/img/manual.png"

# Styles of the "something went wrong / not available" pages
STATUS_CSS = """body {
    background-color: #222326;
    color: #FFFFFF;
    font-family: "Special Elite";
}

.button {
    background-color: #BA4423;
    border-radius: 2.5em;
    font-size: 36px;
    width: 100%;
    margin-top: 5px;
    margin-bottom: 10px;
}
.center-text {
    text-align: center;
}
.container {
    margin: 0px;
    max-width: 100%;
}
.status-sign {
    color: #FF0000;
    font-weight: 900;
    text-align: center;
    font-size: 156px;
    display: flex;
    justify-content: center;
    align-items: center;
}
.title-icon {
    max-height: 100px;
    margin-left: auto;
    margin-right: auto;
    width: 100%;
    object-fit: contain;
}
.username {
    font-size: 24px;
    text-align: center;
    width: 100%;
    display: block;
}"""
STATUS_CSS_NO_BUTTON = """body {
    background-color: #222326;
    color: #FFFFFF;
    font-family: "Special Elite";
}

.center-text {
    text-align: center;
}
.container {
    margin: 0px;
    max-width: 100%;
}
.status-sign {
    color: #FF0000;
    font-weight: 900;
    text-align: center;
    font-size: 156px;
    display: flex;
    justify-content: center;
    align-items: center;
}
.title-icon {
    max-height: 100px;
    margin-left: auto;
    margin-right: auto;
    width: 100%;
    object-fit: contain;
}
.username {
    font-size: 24px;
    text-align: center;
    width: 100%;
    display: block;
}"""
MAIN_PAGE_CSS = """body {
    background-color: #222326;
    color: #FFFFFF;
    font-family: "Special Elite";
}
img.responsive {
    height: 90px;
}
@media (max-width: 767px) {
    img.responsive {
        height: 50px;
    }
}

.button {
    background-color: #BA4423;
    border-radius: 2.5em;
    font-size: 36px;
    width: 100%;
    margin-top: 5px;
    margin-bottom: 10px;
}
.col-md-11 {
    width: 12.499999995%;
    flex: 0 0 12.499%;
    max-width: 12.499%;
}
.container {
    margin: 0px;
    max-width: 100%;
}
.mod-icon {
    margin: auto;
    display: block;
}
.mod-text {
    height: 50px;
    display: flex;
    justify-content: center;
    align-items: center;
    text-align: center;
}
@media (max-width: 767px) {
    .mod-text {
        justify-content: left;
        text-align: left;
    }
}
.module {
    background-color: #333334;
    color: #000000;
    margin: 3px;
    padding: 3px;
    padding-top: 6px;
}
.padding-correction {
    padding-right: 5px;
    padding-left: 5px;
}
.title-icon {
    max-height: 100px;
    margin-left: auto;
    margin-right: auto;
    width: 100%;
    object-fit: contain;
}
.unlocked {
    background-color: #666666 !important;
    color: #FFFFFF !important;
}
.username {
    font-size: 24px;
    text-align: center;
    width: 100%;
    display: block;
}"""
CONNECTION_CSS = """body {
    background-color: #222326;
    color: #FFFFFF;
    font-family: "Special Elite";
}
img {
    width: 100%;
}
input {
    font-size: 24px;
}
label {
    font-size: 24px;
    margin-bottom: .0rem;
}
span {
    width: 100%;
    display: block;
}
textarea {
    width: 100%;
}

.button {
    background-color: #BA4423;
    border-radius: 2.5em;
    font-size: 36px;
    width: 100%;
    margin-top: 5px;
    margin-bottom: 10px;
}
.container {
    margin: 0px;
    max-width: 100%;
}
.connection-section {
    background-color: #FFFFFF;
    color: #222326;
    border-radius: 2.5em;
    margin: 20px 0px 10px 0px;
}
.error {
    border-color: #FF0000;
}
.input-field-row {
    margin: 3px 0px;
}
.text-input {
    width: 100%;
}
.title {
    font-size: 48px;
    text-align: center;
}"""
CONNECTION_JS = r"""function storeCookies(urlStr, portStr, nameStr) {
    const d = new Date();
    d.setTime(d.getTime() + 1209600000); //two weeks
    coo = "url=" + urlStr + ";port=" + portStr + ";slotName=" + nameStr + ";expires=" + d.toUTCString() + ";path=/"
    //document.cookie = coo;
    document.cookie = "url=" + urlStr + ";expires=" + d.toUTCString() + ";path=/"
    document.cookie = "port=" + portStr + ";expires=" + d.toUTCString() + ";path=/"
    document.cookie = "slotName=" + nameStr + ";expires=" + d.toUTCString() + ";path=/"
}

function getCookiesList() {
    let decodedCookies = decodeURIComponent(document.cookie);
    let fullCookieList = decodedCookies.split(";");
    const cookieList = [];
    cookieList["url"] = "";
    cookieList["port"] = "";
    cookieList["slotName"] = "";
    for(let i = 0; i < fullCookieList.length; i++) {
        let coo = fullCookieList[i]
        while (coo.charAt(0) == ' ') {
            coo = coo.substring(1);
        }
        cParts = coo.split("=");
        cookieList[cParts[0]] = cParts[1];
    }
    return cookieList;
}

document.addEventListener("DOMContentLoaded", function() {
    let myCookies = getCookiesList();
    if (myCookies["url"] != "") {
        document.getElementById("txt-server-url").value = myCookies["url"];
    }
    if (myCookies["port"] != "") {
        document.getElementById("txt-server-port").value = myCookies["port"];
    }
    if (myCookies["slotName"] != "") {
        document.getElementById("txt-slot-name").value = myCookies["slotName"];
    }
    document.getElementById("connect-button").addEventListener("click", function() {
        url = document.getElementById("txt-server-url");
        port = document.getElementById("txt-server-port");
        slotName = document.getElementById("txt-slot-name");
        password = document.getElementById("txt-server-password");
        var filled = true;
        if (url.value == "") {
            url.classList.add("error");
            filled = false;
        }
        else {
            url.classList.remove("error");
        }
        if (port.value == "") {
            port.classList.add("error");
            filled = false;
        }
        else if (!/^\d+$/.test(port.value)) {
            port.classList.add("error");
            filled = false;
        }
        else {
            port.classList.remove("error");
        }
        if (slotName.value == "") {
            slotName.classList.add("error");
            filled = false;
        }
        else {
            slotName.classList.remove("error");
        }
        if (filled) {
            storeCookies(url.value, port.value, slotName.value);
            document.getElementById("frm-connection").submit();
        }
    })
});"""


def _esc(value):
    return html.escape(str(value))


def _document(title, css, body, script=""):
    script_tag = f"\n        <script>\n{script}\n        </script>" if script else ""
    return f"""
<!DOCTYPE html>
<html>
    <head>
        <title>AP KTANE - {title}</title>
        <meta charset="UTF-8">

        {BOOTSTRAP_CSS}
        {GOOGLE_FONT}
        <style>
{css}
        </style>{script_tag}
    </head>
    <body>
{body}
    </body>
</html>
"""


def _logo_row(css_class=' class="title-icon"'):
    return f"""
<div class="row">
    <div class="col-0 col-lg-2"></div>
    <div class="col-12 col-sm-6 col-lg-4 my-auto">
        <img{css_class} src="{AP_LOGO}" alt="AP logo">
    </div>
    <div class="col-12 col-sm-6 col-lg-4 my-auto">
        <img{css_class} src="{KTANE_LOGO}" alt="KTANE logo">
    </div>
    <div class="col-0 col-lg-2"></div>
</div>"""


def _heading_row(text_html):
    return f"""
<div class="row">
    <div class="col-0 col-lg-2"></div>
    <div class="col-12 col-lg-8">
        <span class="username">{text_html}</span>
    </div>
    <div class="col-0 col-lg-2"></div>
</div>"""


def _click_submits(button_id, form_id):
    return f"""    document.getElementById("{button_id}").addEventListener("click", function() {{
        document.getElementById("{form_id}").submit();
    }});"""


def _on_load_script(*statements):
    inner = "\n".join(statements)
    return f"""document.addEventListener("DOMContentLoaded", function() {{
{inner}
}});"""


def _disconnect_button(label):
    return f"""
<div class="row">
    <div class="col-0 col-sm-2 col-md-4"></div>
    <div class="col-12 col-sm-8 col-md-4">
        <form method="POST" id="frm-disconnect">
            <input type="hidden" name="post-command" value="disconnect">
            <input id="disconnect-button" class="button" type="button" value="{label}">
        </form>
    </div>
    <div class="col-0 col-sm-2 col-md-4"></div>
</div>"""


def _main_page_button(label):
    return f"""
<div class="row">
    <div class="col-0 col-lg-2"></div>
    <div class="col-12 col-lg-8 center-text">
        <form method="POST" id="frm-main-page">
            <input type="hidden" name="post-command" value="main-page">
            <input id="main-page-button" class="button" type="button" value="{label}">
        </form>
    </div>
    <div class="col-0 col-lg-2"></div>
</div>"""


# ---------------------------------------------------------------------------------------
# Small status pages (404, not connected, error, ...)
# ---------------------------------------------------------------------------------------
def _status_page(title, heading_html, sign, lines_html, button=None):
    """button: None, ("main-page", label) or ("disconnect", label)."""
    rows = "".join(f"""
<div class="row">
    <div class="col-12 center-text">
        {line}
    </div>
</div>""" for line in lines_html)
    if button is None:
        css, script, button_html = STATUS_CSS_NO_BUTTON, "", ""
    elif button[0] == "main-page":
        css, button_html = STATUS_CSS, _main_page_button(button[1])
        script = _on_load_script(_click_submits("main-page-button", "frm-main-page"))
    else:
        css, button_html = STATUS_CSS, _disconnect_button(button[1])
        script = _on_load_script(_click_submits("disconnect-button", "frm-disconnect"))
    body = f"""<div class="container">{_logo_row()}{_heading_row(heading_html)}
<div class="row">
    <div class="col-12">
        <span class="status-sign">{sign}</span>
    </div>
</div>{rows}{button_html}
</div>"""
    return _document(title, css, body, script)


def notUnlockedPage(playerInfo, module):
    return _status_page("Not Unlocked Modules", _esc(playerInfo["name"]), "🔒",
                        [f"The module {_esc(module)} is not unlocked yet."])


def notFoundPage():
    return _status_page("Not Found", "404 - Not Found", "🔍", ["This page wasn't found."],
                        ("main-page", "Return to safety"))


def notConnectedPage():
    return _status_page("Not Connected", "404 - Not Connected", "👤", ["You are not connected to the Archipelago server."],
                        ("main-page", "Return to connection page"))


def badPostPage():
    return _status_page("Not Found", "Bad HTML Post", "✉️",
                        ["The HTML post that was used to transfer data to the server contained invalid data."],
                        ("main-page", "Return to safety"))


def errorConnectionPage(errorType, errorMessage):
    return _status_page("Not Connected", "Error in connection", "❌", [_esc(errorType), _esc(errorMessage)],
                        ("disconnect", "Return to connection"))


def manualStatusPage(module, failed, detail=""):
    """Small self-refreshing page shown while a manual is still downloading (or when it failed)."""
    module = _esc(module)
    if failed:
        title, body, refresh = "Manual unavailable", f"The manual for {module} could not be loaded: {_esc(detail)}. Reload this page to try again.", ""
    else:
        title, body, refresh = "Loading manual", f"The manual for {module} is still loading, this page will refresh automatically.", '<meta http-equiv="refresh" content="2">'
    return f"""<!DOCTYPE html>
<html>
    <head>
        <title>AP KTANE - {title}</title>
        <meta charset="UTF-8">
        {refresh}
        <style>body {{ background-color: #222326; color: #FFFFFF; font-family: monospace; text-align: center; padding-top: 20vh; font-size: 24px; }}</style>
    </head>
    <body>{body}</body>
</html>
"""


# ---------------------------------------------------------------------------------------
# Connection form
# ---------------------------------------------------------------------------------------
def _field_row(field_id, name, label, value=None, password=False):
    if password:
        input_html = f'<input type="password" id="{field_id}" name="{name}" class="text-input" autocomplete="off">'
    else:
        input_html = f'<input type="text" id="{field_id}" name="{name}" class="text-input" value="{_esc(value)}">'
    return f"""
<div class="row input-field-row">
    <div class="col-0 col-xl-1"></div>
    <div class="col-12 col-sm-4 col-xl-3 my-auto"><label for="{field_id}">{label}</label></div>
    <div class="col-12 col-sm-8 col-xl-7">
        {input_html}
    </div>
    <div class="col-0 col-xl-1"></div>
</div>"""


def connectionPage(playerInfo):
    fields = (
        _field_row("txt-server-url", "server-url", "Server URL:", playerInfo["cdUrl"])
        + _field_row("txt-server-port", "server-port", "Server Port:", playerInfo["cdPort"])
        + _field_row("txt-slot-name", "slot-name", "Slot Name:", playerInfo["cdName"])
        + _field_row("txt-server-password", "server-password", "Server Password:", password=True)
    )
    body = f"""<div class="container">{_logo_row(css_class="")}
<div class="row">
    <div class="col-0 col-lg-2"></div>
    <div class="col-12 col-lg-8">
        <form method="POST" id="frm-connection" accept-charset="UTF-8">
            <input type="hidden" name="post-command" value="connect">
            <div class="container connection-section">
                <div class="row">
                    <div class="col-12">
                        <span class="title">Connection:</span>
                    </div>
                </div>{fields}
                <div class="row">
                    <div class="col-0 col-sm-2 col-lg-4"></div>
                    <div class="col-12 col-sm-8 col-lg-4"><input id="connect-button" class="button" type="button" value="Connect"></div>
                    <div class="col-0 col-sm-2 col-lg-4"></div>
                </div>
            </div>
        </form>
    </div>
    <div class="col-0 col-lg-2"></div>
</div>
<div class="row">
    <div class="col-0 col-lg-2"></div>
    <div class="col-12 col-lg-8">Version {versionNumber}</div>
    <div class="col-0 col-lg-2"></div>
</div>
</div>"""
    return _document("Connection", CONNECTION_CSS, body, CONNECTION_JS)


# ---------------------------------------------------------------------------------------
# Main page: the grid of modules
# ---------------------------------------------------------------------------------------
ALWAYS_UNLOCKED = ("TheButton", "Keypad", "Wires", "Appendices")

# What is shown on the main page, row by row. Appendices is not a module, so it is not in the catalog.
VANILLA_GRID = [
    ["TheButton", "Keypad", "Wires"],
    ["Maze", "Memory", "SimonSays", "WhosonFirst"],
    ["ComplicatedWires", "MorseCode", "Password", "WireSequence"],
    ["Capacitor", "Knob", "VentGas", "Appendices"],
]
MODDED_ORDER = ["3DMaze", "Backgrounds", "BigCircle", "BlindAlley", "BlindMaze", "Bitmaps", "TheBulb", "CheapCheckout",
                "Chess", "ColoredSquares", "ColorMorse", "DoubleOh", "FastMath", "FizzBuzz", "FollowtheLeader", "Friendship",
                "Hexamaze", "MorseAMaze", "MouseintheMaze", "PolyhedralMaze", "Radiator", "RockPaperScissorsLizardSpock",
                "SimonScreams", "Switches", "TicTacToe", "WirePlacement", "XRay", "Zoo"]
ADVENTURE_GRID = (
    [["TheButton", "Keypad", "Wires", "Appendices"]]
    + VANILLA_GRID[1:3]
    + [MODDED_ORDER[i:i + 4] for i in range(0, len(MODDED_ORDER), 4)]
)


def _check_grid(grid, expected):
    shown = [link for row in grid for link in row]
    assert len(shown) == len(set(shown)) and set(shown) == set(expected), "main page grid and catalog.py are out of sync"


_check_grid(VANILLA_GRID, vanModsLinks + ["Appendices"])
# NOTE: the original adventure page never listed these three vanilla modules, although they are unlocked
# (and their pages work) in that mode. Kept as it was; remove them from this set to show them.
NOT_LISTED_IN_ADVENTURE = {"Capacitor", "Knob", "VentGas"}
_check_grid(ADVENTURE_GRID, [link for link in vanModsLinks + modModsLinks if link not in NOT_LISTED_IN_ADVENTURE] + ["Appendices"])

_MODULE_NAMES = dict(zip(vanModsLinks + modModsLinks, vanModsNames + modModsNames), Appendices="Appendices")


def _module_card(link, unlocked):
    icon = APPENDICES_ICON if link == "Appendices" else ICON_URL + allModsRepo["en"][link] + ".png"
    state = "module unlocked" if unlocked else "module"
    return f"""
<div class="col-12 col-md-3 padding-correction">
    <a href="/{link}" target="_blank">
        <div class="container {state}">
            <div class="row">
                <div class="col-3 col-sm-2 col-md-12">
                    <img class="mod-icon responsive" src="{icon}">
                </div>
                <div class="col-9 col-sm-10 col-md-12 my-auto mod-text">
                    {_MODULE_NAMES[link]}
                </div>
            </div>
        </div>
    </a>
</div>"""


def _module_grid(grid, unlocked_modules, centered_first_row):
    rows = []
    for index, row in enumerate(grid):
        cards = "".join(_module_card(link, link in ALWAYS_UNLOCKED or link in unlocked_modules) for link in row)
        spacer = '\n<div class="col-0 col-md-11"></div>' if centered_first_row and index == 0 else ""
        rows.append(f'\n<div class="row">{spacer}{cards}{spacer}\n</div>')
    return '<div class="container">' + "".join(rows) + "\n</div>"


def mainPage(playerInfo):
    unlocked = playerInfo.get("unlockedModules", [])
    vanilla = playerInfo["sdAdventureMode"] == AdventureMode.VanillaVanguard.value
    total = len(vanModsLinks) if vanilla else len(vanModsLinks) + len(modModsLinks)
    # While modules are still missing, check for new ones every 15 seconds.
    refresh = len(unlocked) < total
    script = _on_load_script(
        _click_submits("disconnect-button", "frm-disconnect"),
        "    refreshPage();" if refresh else "",
    )
    if refresh:
        script += """

function refreshPage() {
    setTimeout(function() {
        location.reload();
    }, 15000);
}"""

    header = f"""<div class="container">{_logo_row()}{_heading_row(_esc(playerInfo["name"]))}"""
    grid_row = f"""
<div class="row">
    <div class="col-0 col-lg-2"></div>
    <div class="col-12 col-lg-8">
        {_module_grid(VANILLA_GRID if vanilla else ADVENTURE_GRID, unlocked, centered_first_row=vanilla)}
    </div>
    <div class="col-0 col-lg-2"></div>
</div>"""
    button = _disconnect_button("Disconnect")
    if vanilla:
        # Historical layout of the vanilla page: the grid and the button sit outside the first container.
        body = f"""{header}
    <div class="col-0 col-lg-2"></div>
</div>{grid_row}{button}"""
    else:
        body = f"{header}{grid_row}{button}\n</div>"
    return _document("Main Page", MAIN_PAGE_CSS, body, script)


# ---------------------------------------------------------------------------------------
# Appendices (indicators, batteries, ports), shown in the language of the seed
# ---------------------------------------------------------------------------------------
def _appendix_table(header, rows, style=""):
    """rows: (image path, extra attributes of the <img>, text)"""
    body = "".join(f'\n<tr><td><img src="https://ktane.timwi.de/HTML/img/{image}"{img_style}></td><td>{text}</td></tr>' for image, img_style, text in rows)
    return f"<table{style}>\n<tr><th>{header[0]}</th><th>{header[1]}</th></tr>{body}\n</table>"


def appendicesPage(lang, ktaneUtilsScript):
    """ktaneUtilsScript: the (already patched) ktane-utils.js, it is inlined into the page."""
    t = appendixText.get(lang, appendixText["en"])
    title = "Keep Talking and Nobody Explodes"
    pages = [
        ("page page-bg-07 appendix-indicators", t[0], f"""
<h2>{t[1]}</h2>
<p>{t[2]}</p>
<img src="https://ktane.timwi.de/HTML/img/Component/IndicatorWidget.svg" style="height: 5em; display: block; margin: .6em 0 0">
<h3>{t[3]}</h3>
<ul>{"".join(f"<li>{name}</li>" for name in ("SND", "CLR", "CAR", "IND", "FRQ", "SIG", "NSA", "MSA", "TRN", "BOB", "FRK"))}</ul>""", t[4]),
        ("page page-bg-01 appendix-batteries", t[5], f"""
<h2>{t[6]}</h2>
<p>{t[7]}</p>
{_appendix_table((t[8], t[9]), [
    ("appendix-batteries/Battery-AA.svg", ' style="width: 4.09375em; height: 6.18125em"', t[10]),
    ("appendix-batteries/Battery-D.svg", ' style="width: 4.09375em; height: 5.553125em"', t[11])], ' style="margin-top: 1em"')}""", t[12]),
        ("page page-bg-02 appendix-ports", t[13], f"""
<h2>{t[14]}</h2>
<p>{t[15]}</p>
{_appendix_table((t[16], t[17]), [
    ("appendix-ports/DVI-D.svg", ' style="height:60px"', t[18]),
    ("appendix-ports/Parallel.svg", ' style="height:60px"', t[19]),
    ("appendix-ports/PS2.svg", "", t[20]),
    ("appendix-ports/RJ-45.svg", "", t[21]),
    ("appendix-ports/Serial.svg", ' style="height:60px"', t[22]),
    ("appendix-ports/Stereo RCA.svg", "", t[23])])}""", t[24]),
    ]
    sections = []
    for index, (css_class, section, content, footer) in enumerate(pages):
        page = f"""
<div class="{css_class}">
    <div class="page-header">
        <span class="page-header-doc-title">{title}</span>
        <span class="page-header-section-title">{section}</span>
    </div>
    <div class="page-content">{content}
    </div>
    <div class="page-footer relative-footer">{footer}</div>
</div>"""
        # as in the original page, only the first appendix is wrapped in a "section"
        sections.append(f'\n<div class="section">{page}\n</div>' if index == 0 else page)
    sections = "".join(sections)
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="initial-scale=1">
    <title>Appendices — {title}</title>
    {GOOGLE_FONT}
    <link rel="stylesheet" type="text/css" href="https://ktane.timwi.de/HTML/css/normalize.css">
    <link rel="stylesheet" type="text/css" href="https://ktane.timwi.de/HTML/css/main.css">
    <link rel="stylesheet" type="text/css" href="https://ktane.timwi.de/HTML/css/Modules/Ports.css">
    <script>{ktaneUtilsScript}</script>
    <style>
        td img {{ height: 80px; }}
        .dark td img {{ filter: invert(87%); }}
        .dark img {{ filter: invert(87%); }}
    </style>
</head>
<body>{sections}
</body>
</html>
"""
