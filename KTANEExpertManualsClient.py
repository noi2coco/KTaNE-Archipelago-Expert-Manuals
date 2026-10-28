"""KTANE Expert Manuals client for Archipelago.

Everything runs in a single process:

* the main thread runs the local HTTP server (one thread per request),
* one background thread runs the asyncio loop that owns the Archipelago websocket,
* the manuals are downloaded by a small pool of daemon threads (see manuals.py).

All of it is started by main() and torn down by the same function, so Ctrl+C / SIGTERM
leave nothing behind and the port is released immediately.
"""
import argparse
import asyncio
import http.server
import json
import os
import signal
import sys
import threading
import urllib.parse
import uuid
import webbrowser

import websockets
import websockets.exceptions

import pages
from catalog import (AdventureMode, allModsRepo, apVersion, modModsLinks, modModsNames,
                     vanModsLinks, vanModsNames)
from manuals import ManualStore, ssl_context

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 21713

OPEN_TIMEOUT = 8          # seconds to open the websocket (per scheme tried)
HANDSHAKE_TIMEOUT = 8     # seconds to get RoomInfo / the answer to our Connect
CONNECT_WAIT = 40         # upper bound for the whole "Connect" button press
MAX_POST_SIZE = 64 * 1024

STARTING_MODULES = ("TheButton", "Keypad", "Wires")

# Item ids are 71301001-71301011 (vanilla) and 71301016-71301043 (modded)
RECEIVABLE_VANILLA_NAMES = ["Complicated Wires", "Maze", "Memory", "Morse Code", "Password", "Simon Says", "Who's on First", "Wire Sequence", "Capacitor", "Knob", "Vent Gas"]
RECEIVABLE_VANILLA_LINKS = ["ComplicatedWires", "Maze", "Memory", "MorseCode", "Password", "SimonSays", "WhosonFirst", "WireSequence", "Capacitor", "Knob", "VentGas"]


# ---------------------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------------------
def to_jsonable(obj):
    """NamedTuples are not serialised as objects by json, and the AP server wants them as such."""
    if isinstance(obj, tuple) and hasattr(obj, "_fields"):
        data = obj._asdict()
        data["class"] = obj.__class__.__name__
        return data
    if isinstance(obj, (tuple, list, set, frozenset)):
        return [to_jsonable(o) for o in obj]
    if isinstance(obj, dict):
        return {key: to_jsonable(value) for key, value in obj.items()}
    return obj


def encode_packets(packets):
    return json.dumps(to_jsonable(packets), ensure_ascii=False, separators=(",", ":"))


def default_info():
    return {
        "name": "",
        "slotNumber": -1,
        "cdUrl": "",
        "cdPort": "",
        "cdName": "",
        "cdPass": "",  # never filled: passwords are not kept
        "sdRuleSeed": -1,
        "sdRandomRuleSeed": False,
        "sdHardlockModules": True,
        "sdAdventureMode": AdventureMode.VanillaVanguard.value,
        "sdLanguage": "en",
        "connected": False,
        "unlockedModules": list(STARTING_MODULES),
        "connectionResult": None,
        "connectionError": ["", ""],
    }


def slot_data_settings(slot_data):
    """Translate the slot_data sent by the server into our own settings."""
    sd = slot_data or {}

    def get(key, default):
        value = sd.get(key)
        return default if value is None else value

    languages = list(allModsRepo.keys())
    language_index = get("manuals_language", 0)
    return {
        "sdRuleSeed": get("rule_seed", 1),
        "sdRandomRuleSeed": get("random_rule_seed", 0) == 1,
        "sdHardlockModules": get("hardlock_modules", 1) == 1,
        "sdAdventureMode": get("adventure_mode", AdventureMode.VanillaVanguard.value),
        "sdLanguage": languages[language_index] if isinstance(language_index, int) and 0 <= language_index < len(languages) else "en",
    }


def item_to_module(item_id):
    """Returns (link, display name) for an Archipelago item id, or None if it is not a module."""
    if 71301000 < item_id < 71301012:
        index = item_id - 71301001
        return RECEIVABLE_VANILLA_LINKS[index], RECEIVABLE_VANILLA_NAMES[index]
    if 71301015 < item_id < 71301044:
        index = item_id - 71301016
        return modModsLinks[index], modModsNames[index]
    return None


class ConnectionFailed(Exception):
    """Could not reach / talk to an Archipelago server on any of the URLs tried."""


def describe_error(error):
    if isinstance(error, asyncio.TimeoutError):
        return "no answer from the server"
    return f"{type(error).__name__}: {error}" if str(error) else type(error).__name__


def candidate_urls(server_url, server_port):
    """Which websocket URLs to try, in order."""
    server_url = server_url.strip().rstrip("/")
    if server_url.startswith(("ws://", "wss://")):
        return [f"{server_url}:{server_port}"]
    return [f"ws://{server_url}:{server_port}", f"wss://{server_url}:{server_port}"]


# ---------------------------------------------------------------------------------------
# State shared between the HTTP threads and the asyncio loop
# ---------------------------------------------------------------------------------------
class AppState:
    """Thread-safe holder for everything the pages display."""

    def __init__(self):
        self._lock = threading.RLock()
        self._info = default_info()

    def snapshot(self):
        with self._lock:
            info = dict(self._info)
            info["unlockedModules"] = list(info["unlockedModules"])
            info["connectionError"] = list(info["connectionError"])
            return info

    def update(self, **changes):
        with self._lock:
            self._info.update(changes)

    def unlock(self, link):
        with self._lock:
            if link in self._info["unlockedModules"]:
                return False
            self._info["unlockedModules"].append(link)
            return True

    def reset_session(self):
        """Back to the not-connected state, keeping what the user typed in the form."""
        with self._lock:
            fresh = default_info()
            for key in ("cdUrl", "cdPort", "cdName"):
                fresh[key] = self._info[key]
            self._info = fresh


class Session:
    """One connection attempt. Late events of an old session are ignored."""

    def __init__(self):
        self.done = threading.Event()   # set as soon as the outcome (success / failure) is known
        self.result = None              # "success" | "failure"
        self.future = None
        self.task = None                # the asyncio task running the connection


class Runtime:
    """Owns the asyncio loop and the thread that runs it."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="asyncio", daemon=True)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def stop(self, timeout=5):
        async def cancel_everything():
            current = asyncio.current_task()
            tasks = [t for t in asyncio.all_tasks() if t is not current]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        if self.loop.is_running():
            try:
                self.submit(cancel_everything()).result(timeout)
            except Exception as e:
                print(f"Could not stop every task cleanly: {e!r}")
            self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout)
        if not self._thread.is_alive():
            self.loop.close()


# ---------------------------------------------------------------------------------------
# Archipelago connection
# ---------------------------------------------------------------------------------------
class App:
    def __init__(self, runtime, manuals):
        self.runtime = runtime
        self.manuals = manuals
        self.state = AppState()
        self._lock = threading.RLock()
        self._session = None

    # -- called from the HTTP threads -------------------------------------------------
    def connect(self, server_url, server_port, slot_name, password):
        """Blocks (bounded) until the connection succeeded or failed. Returns "success" or "failure"."""
        self.disconnect()
        session = Session()
        with self._lock:
            self._session = session
            self.state.update(cdUrl=server_url, cdPort=server_port, cdName=slot_name)
        session.future = self.runtime.submit(self._run_session(session, server_url, server_port, slot_name, password))
        if not session.done.wait(CONNECT_WAIT):
            self._fail(session, "TimeoutError", "Connection attempt timed out")
            self._stop_session(session)
        return session.result

    def disconnect(self):
        with self._lock:
            session, self._session = self._session, None
            self.state.reset_session()
        if session is not None:
            if not session.done.is_set():
                session.result = "failure"
                session.done.set()  # release a request thread that is still waiting
            self._stop_session(session)
        self.manuals.reset()

    def _stop_session(self, session):
        """Cancel the connection task and wait (bounded) until its websocket is really closed."""
        task = session.task
        if task is None:
            if session.future is not None:
                session.future.cancel()  # not started yet
            return

        async def cancel_and_wait():
            if not task.done():
                task.cancel()
                await asyncio.wait([task], timeout=3)

        try:
            self.runtime.submit(cancel_and_wait()).result(5)
        except Exception:
            pass  # the loop is already gone: nothing left to close

    def shutdown(self):
        self.disconnect()

    # -- helpers that only act for the current session -------------------------------
    def _is_current(self, session):
        return self._session is session

    def _apply(self, session, **changes):
        with self._lock:
            if not self._is_current(session):
                return False
            self.state.update(**changes)
            return True

    def _fail(self, session, kind, message):
        with self._lock:
            if not self._is_current(session) or session.done.is_set():
                return
            self.state.update(connected=False, connectionError=[kind, message], connectionResult="failure")
            session.result = "failure"
            session.done.set()

    # -- asyncio side -----------------------------------------------------------------
    async def _run_session(self, session, server_url, server_port, slot_name, password):
        session.task = asyncio.current_task()
        try:
            await self._connect_and_serve(session, server_url, server_port, slot_name, password)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            self._fail(session, "TimeoutError", "The server did not answer in time")
        except ConnectionFailed as e:
            self._fail(session, "Connection failed", str(e))
        except Exception as e:
            self._fail(session, type(e).__name__, str(e) or repr(e))
        finally:
            self._connection_ended(session)

    def _connection_ended(self, session):
        with self._lock:
            if not self._is_current(session):
                return
            if not session.done.is_set():
                self._fail(session, "Connection closed", "The server closed the connection")
            elif session.result == "success":
                print("Connection to the server lost")
                self.state.update(connected=False, name="")

    async def _open(self, url):
        options = {"ping_interval": 30, "ping_timeout": 60, "close_timeout": 2, "open_timeout": None}
        if url.startswith("wss://"):
            options["ssl"] = ssl_context
        return await asyncio.wait_for(websockets.connect(url, **options), OPEN_TIMEOUT)

    async def _connect_and_serve(self, session, server_url, server_port, slot_name, password):
        errors = []  # (url, exception) of every scheme that did not work
        for url in candidate_urls(server_url, server_port):
            try:
                ws = await self._open(url)
            except Exception as e:
                errors.append((url, e))
                continue
            try:
                await self._serve(session, ws, slot_name, password)
                return
            except Exception as e:
                if session.done.is_set():
                    raise  # the connection worked and was lost afterwards
                errors.append((url, e))  # e.g. a TLS server answering a plain request: try the next scheme
            finally:
                await ws.close()
        if all(isinstance(e, asyncio.TimeoutError) for _, e in errors):
            raise asyncio.TimeoutError()
        raise ConnectionFailed("; ".join(f"{url}: {describe_error(e)}" for url, e in errors))

    async def _serve(self, session, ws, slot_name, password):
        loop = asyncio.get_running_loop()
        first = json.loads(await asyncio.wait_for(ws.recv(), HANDSHAKE_TIMEOUT))
        if not any(isinstance(m, dict) and m.get("cmd") == "RoomInfo" for m in first):
            raise ConnectionError("The server did not send RoomInfo, is this an Archipelago server?")

        await ws.send(encode_packets([{
            "cmd": "Connect",
            "password": password,
            "name": slot_name,
            "version": apVersion,
            "tags": ["ExpertManuals"],
            "items_handling": 0b111,
            "uuid": uuid.getnode(),
            "game": "Keep Talking and Nobody Explodes",
            "slot_data": True,
        }]))

        deadline = loop.time() + HANDSHAKE_TIMEOUT
        while True:
            if session.done.is_set() and session.result != "success":
                return  # refused
            timeout = None if session.done.is_set() else max(deadline - loop.time(), 0.01)
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout)
            except asyncio.TimeoutError:
                self._fail(session, "TimeoutError", "The server did not answer the connection request")
                return
            await self._process_message(session, raw)

    async def _process_message(self, session, raw):
        try:
            packets = json.loads(raw)
        except ValueError as e:
            print(f"Ignoring invalid message from the server: {e}")
            return
        for packet in packets:
            if not isinstance(packet, dict):
                continue
            cmd = packet.get("cmd")
            if cmd == "ConnectionRefused":
                self._fail(session, "Connection Refused", "\n".join(packet.get("errors", [])))
            elif cmd == "Connected":
                self._on_connected(session, packet)
            elif cmd == "ReceivedItems":
                self._on_received_items(session, packet)
            elif cmd == "PrintJSON":
                if packet.get("type") != "ItemSend" and packet.get("data"):
                    print("".join(part.get("text", "") for part in packet["data"]))
            elif cmd in (None, "Bounced", "RoomUpdate"):
                continue
            else:
                print(f"Received Random Message: {packet}")

    def _on_received_items(self, session, packet):
        for item in packet.get("items", []):
            module = item_to_module(item.get("item", 0))
            if module is None:
                continue
            link, name = module
            with self._lock:
                if self._is_current(session) and self.state.unlock(link):
                    print(f"Received Module {name}")

    def _on_connected(self, session, packet):
        print("CONNECTED")
        slot = packet["slot"]
        player = next((p for p in packet.get("players", []) if p["slot"] == slot), None)
        settings = slot_data_settings(packet.get("slot_data"))
        with self._lock:
            if not self._is_current(session):
                return
            self.state.update(slotNumber=slot, name=(player["alias"] if player else str(slot)) or str(slot), connected=True, **settings)
            if settings["sdAdventureMode"] == AdventureMode.PraetorianPact.value:
                for link in vanModsLinks:
                    self.state.unlock(link)
            elif not settings["sdHardlockModules"]:
                self.state.unlock("Capacitor")
                self.state.unlock("VentGas")
            snapshot = self.state.snapshot()
            modules = list(vanModsLinks)
            if settings["sdAdventureMode"] == AdventureMode.PraetorianPact.value:
                modules += modModsLinks
            self.manuals.load(snapshot, modules)  # downloads in the background
            self.state.update(connectionResult="success", connectionError=["", ""])
            session.result = "success"
            session.done.set()


# ---------------------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------------------
class KtaneHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets a second instance steal the port; on Linux it only lets
    # us rebind while old connections are in TIME_WAIT.
    allow_reuse_address = os.name != "nt"

    def __init__(self, address, app):
        self.app = app
        super().__init__(address, KtaneRequestHandler)


class KtaneRequestHandler(http.server.BaseHTTPRequestHandler):
    @property
    def app(self):
        return self.server.app

    # -- responses --------------------------------------------------------------------
    def _send_html(self, body, status=200):
        data = body.encode("utf8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _redirect(self, path):
        self.send_response(303)
        self.send_header("Location", path)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # -- GET --------------------------------------------------------------------------
    def do_GET(self):
        try:
            self._route_get(urllib.parse.urlsplit(self.path).path)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            print(f"An error occured: {e!r}\nPlease contact the developper with a screenshot of this message.")
            try:
                self._send_html("<h1>Internal error</h1>", 500)
            except Exception:
                pass

    do_HEAD = do_GET

    def _route_get(self, path):
        info = self.app.state.snapshot()
        name = path[1:]
        if path == "/":
            if info["name"] != "":
                self._redirect("/MainPage")
            else:
                self._send_html(pages.connectionPage(info))
        elif path == "/MainPage":
            if info["name"] == "":
                self._send_html(pages.notConnectedPage())
            else:
                self._send_html(pages.mainPage(info))
        elif path == "/Error" and info["connectionResult"] == "failure":
            self._send_html(pages.errorConnectionPage(*info["connectionError"]))
        elif path == "/WrongPost":
            self._send_html(pages.badPostPage(), 400)
        elif path == "/Appendices":
            try:
                script = self.app.manuals.ktane_utils()
            except Exception as e:
                self._send_html(pages.manualStatusPage("the appendices", True, e), 502)
                return
            self._send_html(pages.appendicesPage(info["sdLanguage"], script))
        elif name in vanModsLinks:
            self._send_manual(info, name, vanModsNames[vanModsLinks.index(name)])
        elif name in modModsLinks and info["sdAdventureMode"] == AdventureMode.PraetorianPact.value:
            self._send_manual(info, name, modModsNames[modModsLinks.index(name)])
        else:
            self._send_html(pages.notFoundPage(), 404)

    def _send_manual(self, info, link, display_name):
        if info["name"] == "":
            self._send_html(pages.notConnectedPage())
        elif link not in info["unlockedModules"]:
            self._send_html(pages.notUnlockedPage(info, display_name))
        else:
            status, content = self.app.manuals.status(link)
            if status == "ready":
                self._send_html(content)
            elif status == "loading":
                self._send_html(pages.manualStatusPage(display_name, False))
            else:
                if status == "failed":
                    self.app.manuals.retry(link)  # the next reload tries again
                self._send_html(pages.manualStatusPage(display_name, True, content or "not loaded"), 502)

    # -- POST -------------------------------------------------------------------------
    def do_POST(self):
        try:
            post_data = self._read_form()
            if post_data is None:
                self._redirect("/WrongPost")
                return
            command = post_data.get("post-command", [None])[0]
            if command == "connect":
                self._connect(post_data)
            elif command == "disconnect":
                self.app.disconnect()
                self._redirect("/")
            elif command == "main-page":
                self._redirect("/")
            else:
                self._redirect("/WrongPost")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            print(f"An error occured: {e!r}\nPlease contact the developper with a screenshot of this message.")
            try:
                self._send_html("<h1>Internal error</h1>", 500)
            except Exception:
                pass

    def _read_form(self):
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return None
        if not 0 <= length <= MAX_POST_SIZE:
            return None
        try:
            return urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        except UnicodeDecodeError:
            return None

    def _connect(self, post_data):
        def field(key):
            values = post_data.get(key)
            return values[0].strip() if values else None

        url, port, slot = field("server-url"), field("server-port"), field("slot-name")
        password = (post_data.get("server-password") or [None])[0]  # the password is used verbatim
        if not url or not slot or not port or not port.isdigit() or not 0 < int(port) < 65536:
            self._redirect("/WrongPost")
            return
        result = self.app.connect(url, port, slot, password)
        self._redirect("/MainPage" if result == "success" else "/Error")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, HEAD, POST, OPTIONS")
        self.end_headers()


# ---------------------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------------------
def parse_args(argv):
    parser = argparse.ArgumentParser(description="KTANE Expert Manuals Archipelago client")
    parser.add_argument("--host", default=DEFAULT_HOST, help="address to listen on (default: %(default)s, use 0.0.0.0 to share the manuals on your network)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="port to listen on (default: %(default)s)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the web browser automatically")
    return parser.parse_args(argv)


def _raise_interrupt(signum, frame):
    raise KeyboardInterrupt


def main(argv=None):
    args = parse_args(argv)
    print("KTANE Expert Manuals Client")

    runtime = Runtime()
    manuals = ManualStore()
    app = App(runtime, manuals)
    try:
        httpd = KtaneHTTPServer((args.host, args.port), app)
    except OSError as e:
        print(f"Cannot listen on {args.host}:{args.port}: {e}\nIs the client already running? Use --port to pick another port.")
        runtime.stop()
        manuals.close()
        return 1

    signal.signal(signal.SIGTERM, _raise_interrupt)
    if hasattr(signal, "SIGBREAK"):  # Windows Ctrl+Break
        signal.signal(signal.SIGBREAK, _raise_interrupt)

    browse_host = "localhost" if args.host in ("0.0.0.0", "::", "") else args.host
    url = f"http://{browse_host}:{args.port}"
    print(f"Listening on {url}  (Ctrl+C to quit)")
    if not args.no_browser:
        threading.Thread(target=webbrowser.open, args=(url,), name="browser", daemon=True).start()

    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        # Order matters: stop connections first, then the loop, then free the port.
        app.shutdown()
        runtime.stop()
        manuals.close()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
