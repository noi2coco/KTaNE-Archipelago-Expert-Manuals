"""Connection-flow tests against a fake Archipelago server (no network needed).

Run:  python -m unittest discover -s tests -v
"""
import asyncio
import http.client
import io
import json
import os
import socket
import sys
import threading
import time
import unittest
import urllib.parse
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets.asyncio.server as ws_server  # noqa: E402

import go  # noqa: E402
import manuals  # noqa: E402

ITEM_MAZE = 71301002        # vanilla "Maze"
ITEM_SWITCHES = 71301016    # modded "Switches"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def fake_urlopen(url, context=None, timeout=None):
    return FakeResponse(b"<html>manual for " + url.encode() + b"</html>")


class FakeArchipelago:
    """behaviour: "ok" | "refuse" | "silent" | "no-roominfo" | "drop" """

    def __init__(self, behaviour="ok", slot_data=None):
        self.behaviour = behaviour
        self.slot_data = slot_data
        self.connections = 0
        self.received = []
        self._loop = asyncio.new_event_loop()
        self._started = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._started.wait(5)

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._start())
        self._started.set()
        self._loop.run_forever()

    async def _start(self):
        self.server = await ws_server.serve(self._handler, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def _handler(self, ws):
        self.connections += 1
        if self.behaviour == "silent":
            await ws.wait_closed()
            return
        if self.behaviour == "no-roominfo":
            await ws.send(json.dumps([{"cmd": "Nope"}]))
            await ws.wait_closed()
            return
        await ws.send(json.dumps([{"cmd": "RoomInfo"}]))
        async for raw in ws:
            for packet in json.loads(raw):
                self.received.append(packet)
                if packet["cmd"] != "Connect":
                    continue
                if self.behaviour == "refuse":
                    await ws.send(json.dumps([{"cmd": "ConnectionRefused", "errors": ["InvalidSlot <b>x</b>"]}]))
                else:
                    await ws.send(json.dumps([
                        {"cmd": "Connected", "slot": 3, "players": [{"slot": 3, "alias": "Al<i>ice"}], "slot_data": self.slot_data},
                        {"cmd": "ReceivedItems", "items": [{"item": ITEM_MAZE}, {"item": ITEM_SWITCHES}, {"item": 1}]},
                    ]))
                    if self.behaviour == "drop":
                        await asyncio.sleep(0.3)
                        await ws.close()
                        return

    def stop(self):
        async def close():
            self.server.close()
            await self.server.wait_closed()
        asyncio.run_coroutine_threadsafe(close(), self._loop).result(5)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(5)


class ClientTestCase(unittest.TestCase):
    def setUp(self):
        patchers = [mock.patch.object(manuals.urllib.request, "urlopen", fake_urlopen)]
        for name, value in (("OPEN_TIMEOUT", 2), ("HANDSHAKE_TIMEOUT", 1), ("CONNECT_WAIT", 6)):
            patchers.append(mock.patch.object(go, name, value))
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.runtime = go.Runtime()
        self.manuals = manuals.ManualStore(workers=3)
        self.app = go.App(self.runtime, self.manuals)
        self.httpd = go.KtaneHTTPServer(("127.0.0.1", 0), self.app)
        self.port = self.httpd.server_address[1]
        self.http_thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.http_thread.start()
        self.servers = []

    def tearDown(self):
        self.app.shutdown()
        self.httpd.shutdown()
        self.http_thread.join(5)
        self.runtime.stop()
        self.manuals.close()
        self.httpd.server_close()
        for server in self.servers:
            server.stop()

    def fake(self, *args, **kwargs):
        server = FakeArchipelago(*args, **kwargs)
        self.servers.append(server)
        return server

    # -- http helpers -----------------------------------------------------------------
    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        data = response.read().decode("utf8")
        result = (response.status, response.getheader("Location"), data)
        conn.close()
        return result

    def post(self, **fields):
        body = urllib.parse.urlencode(fields)
        return self.request("POST", "/", body, {"Content-Type": "application/x-www-form-urlencoded"})

    def connect(self, server, **overrides):
        fields = {"post-command": "connect", "server-url": "127.0.0.1", "server-port": str(server.port), "slot-name": "Alice"}
        fields.update(overrides)
        return self.post(**fields)

    def wait_for(self, predicate, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            if predicate():
                return True
            time.sleep(0.05)
        return False

    def unlocked(self, link):
        return link in self.app.state.snapshot()["unlockedModules"]

    def get_manual(self, link):
        """Follow the 'still loading' page until the manual is there."""
        for _ in range(100):
            status, _, body = self.request("GET", "/" + link)
            if "still loading" not in body:
                return status, body
            time.sleep(0.05)
        self.fail("manual never finished loading")


class SuccessfulConnection(ClientTestCase):
    def test_connect_unlock_and_serve_manuals(self):
        server = self.fake("ok", {"rule_seed": 5, "manuals_language": 1})
        status, location, _ = self.connect(server)
        self.assertEqual((status, location), (303, "/MainPage"))

        self.assertTrue(self.wait_for(lambda: self.unlocked("Maze")))
        info = self.app.state.snapshot()
        self.assertEqual((info["slotNumber"], info["sdRuleSeed"], info["sdLanguage"]), (3, 5, "cs"))

        status, _, body = self.request("GET", "/MainPage")
        self.assertEqual(status, 200)
        self.assertIn("Al&lt;i&gt;ice", body)
        self.assertNotIn("Al<i>ice", body)

        status, body = self.get_manual("Maze")
        self.assertEqual(status, 200)
        self.assertIn("manual for https://ktane.timwi.de/HTML/", body)

        self.assertIn("not unlocked", self.request("GET", "/Memory")[2])
        self.assertEqual(self.request("GET", "/Switches")[0], 404)  # modded module, vanilla adventure

        connect_packet = server.received[0]
        self.assertEqual(connect_packet["version"]["class"], "Version")
        self.assertIsNone(connect_packet["password"])

    def test_praetorian_pact_unlocks_everything_and_loads_modded_manuals(self):
        server = self.fake("ok", {"adventure_mode": 1})
        self.assertEqual(self.connect(server)[:2], (303, "/MainPage"))
        self.assertTrue(self.wait_for(lambda: self.unlocked("Switches")))
        for link in go.vanModsLinks:
            self.assertTrue(self.unlocked(link), link)
        self.assertEqual(self.get_manual("Switches")[0], 200)
        self.assertEqual(self.get_manual("Wires")[0], 200)

    def test_connection_page_never_echoes_the_password(self):
        server = self.fake("ok")
        self.connect(server, **{"server-password": "hunter2"})
        self.assertNotIn("hunter2", self.request("GET", "/")[2])
        self.assertEqual(server.received[0]["password"], "hunter2")

    def test_disconnect_then_reconnect_starts_from_scratch(self):
        server = self.fake("ok")
        self.connect(server)
        self.assertTrue(self.wait_for(lambda: self.unlocked("Maze")))

        self.assertEqual(self.post(**{"post-command": "disconnect"})[:2], (303, "/"))
        info = self.app.state.snapshot()
        self.assertEqual((info["name"], info["unlockedModules"], info["connectionResult"]), ("", list(go.STARTING_MODULES), None))
        status, _, form = self.request("GET", "/")
        self.assertEqual(status, 200, "shows the connection form again")
        self.assertIn("127.0.0.1", form, "form keeps what the user typed")

        self.assertEqual(self.connect(server)[:2], (303, "/MainPage"))
        self.assertTrue(self.wait_for(lambda: self.unlocked("Maze")))
        self.assertEqual(self.get_manual("Wires")[0], 200)

    def test_reconnect_without_disconnect_does_not_reuse_old_result(self):
        good = self.fake("ok")
        bad = self.fake("refuse")
        self.assertEqual(self.connect(good)[1], "/MainPage")
        self.assertEqual(self.connect(bad)[1], "/Error")
        self.assertEqual(self.app.state.snapshot()["name"], "")

    def test_lost_connection_returns_to_connection_form(self):
        server = self.fake("drop")
        self.assertEqual(self.connect(server)[1], "/MainPage")
        self.assertTrue(self.wait_for(lambda: self.app.state.snapshot()["name"] == ""))
        self.assertFalse(self.app.state.snapshot()["connected"])


class FailedConnection(ClientTestCase):
    def test_refused_shows_escaped_error(self):
        server = self.fake("refuse")
        self.assertEqual(self.connect(server)[:2], (303, "/Error"))
        _, _, body = self.request("GET", "/Error")
        self.assertIn("InvalidSlot &lt;b&gt;x&lt;/b&gt;", body)
        self.assertNotIn("<b>x</b>", body)

    def test_silent_server_fails_in_bounded_time(self):
        server = self.fake("silent")
        started = time.time()
        self.assertEqual(self.connect(server)[:2], (303, "/Error"))
        self.assertLess(time.time() - started, 8)
        self.assertIn("no answer from the server", self.request("GET", "/Error")[2])

    def test_not_an_archipelago_server(self):
        server = self.fake("no-roominfo")
        self.assertEqual(self.connect(server)[1], "/Error")

    def test_closed_port(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            free = s.getsockname()[1]

        class Dummy:
            port = free

        self.assertEqual(self.connect(Dummy)[1], "/Error")

    def test_disconnect_releases_a_pending_connect(self):
        server = self.fake("silent")
        results = []
        thread = threading.Thread(target=lambda: results.append(self.connect(server)), daemon=True)
        thread.start()
        self.assertTrue(self.wait_for(lambda: server.connections == 1))
        started = time.time()
        self.post(**{"post-command": "disconnect"})
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertLess(time.time() - started, 3)

    def test_bad_forms(self):
        server = self.fake("ok")
        for fields in ({"post-command": "connect"},
                       {"post-command": "connect", "server-url": "h", "server-port": "abc", "slot-name": "s"},
                       {"post-command": "connect", "server-url": "h", "server-port": "70000", "slot-name": "s"},
                       {"post-command": "bogus"},
                       {}):
            self.assertEqual(self.post(**fields)[:2], (303, "/WrongPost"), fields)
        self.assertEqual(self.request("POST", "/", None, {})[:2], (303, "/WrongPost"), "no Content-Length")
        self.assertEqual(self.request("GET", "/WrongPost")[0], 400)
        self.assertEqual(server.connections, 0)

    def test_options_gets_an_answer(self):
        self.assertEqual(self.request("OPTIONS", "/")[0], 204)


class ManualFailures(ClientTestCase):
    def test_failed_download_reports_and_retries(self):
        failing = {"on": True}

        def flaky(url, context=None, timeout=None):
            if failing["on"] and url.endswith("Maze.html"):
                raise OSError("boom")
            return fake_urlopen(url)

        server = self.fake("ok")
        with mock.patch.object(manuals, "REQUEST_ATTEMPTS", 1), \
                mock.patch.object(manuals.urllib.request, "urlopen", flaky), \
                mock.patch.object(manuals.time, "sleep", lambda s: None):
            self.connect(server)
            self.assertTrue(self.wait_for(lambda: self.unlocked("Maze")))
            self.assertTrue(self.wait_for(lambda: not self.manuals.is_loading()))
            status, _, body = self.request("GET", "/Maze")
            self.assertEqual(status, 502)
            self.assertIn("could not be loaded", body)
            failing["on"] = False
            # every view of a failed manual queues a retry, so reloading eventually succeeds
            for _ in range(100):
                if self.request("GET", "/Maze")[0] == 200:
                    break
                time.sleep(0.05)
            else:
                self.fail("manual was never retried")


class Shutdown(unittest.TestCase):
    def test_no_threads_left_after_shutdown_while_connected(self):
        with mock.patch.object(manuals.urllib.request, "urlopen", fake_urlopen):
            before = set(threading.enumerate())
            server = FakeArchipelago("ok")
            runtime, store = go.Runtime(), manuals.ManualStore(workers=2)
            app = go.App(runtime, store)
            self.assertEqual(app.connect("127.0.0.1", str(server.port), "Alice", None), "success")
            app.shutdown()
            runtime.stop()
            store.close()
            server.stop()
            time.sleep(0.2)
            leftovers = [t for t in threading.enumerate() if t not in before and t.is_alive()]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
