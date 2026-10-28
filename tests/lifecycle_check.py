#!/usr/bin/env python3
"""End-to-end lifecycle check: start / stop / restart / second instance / leftovers.

Run with the interpreter that has the dependencies installed:  python tests/lifecycle_check.py
"""
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 21799


def start(*extra):
    return subprocess.Popen([sys.executable, os.path.join(ROOT, "go.py"), "--no-browser", "--port", str(PORT), *extra],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def wait_until_serving(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2).status
        except OSError:
            time.sleep(0.1)
    raise AssertionError("server did not start")


def port_is_free():
    """True when nothing listens any more and a new server could bind right away.

    Binds like the server does (SO_REUSEADDR): sockets in TIME_WAIT left by finished
    connections are harmless and must not count as "in use".
    """
    listening = subprocess.run(["ss", "-tln"], capture_output=True, text=True).stdout
    if f":{PORT} " in listening:
        return False
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", PORT))
            return True
        except OSError:
            return False


def children_of(pid):
    out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split()
    return out


failures = []


def check(name, condition):
    print(("PASS " if condition else "FAIL ") + name)
    if not condition:
        failures.append(name)


for sig in (signal.SIGINT, signal.SIGTERM):
    proc = start()
    check(f"[{sig.name}] serves /", wait_until_serving() == 200)
    check(f"[{sig.name}] no child processes while running", children_of(proc.pid) == [])

    second = start()
    second_out, _ = second.communicate(timeout=10)
    check(f"[{sig.name}] second live instance fails cleanly", second.returncode == 1 and "Cannot listen" in second_out)
    check(f"[{sig.name}] first instance unaffected by the second", wait_until_serving() == 200)

    proc.send_signal(sig)
    try:
        proc.wait(timeout=10)
        exited = True
    except subprocess.TimeoutExpired:
        proc.kill()
        exited = False
    check(f"[{sig.name}] exits promptly", exited)
    check(f"[{sig.name}] port released immediately", port_is_free())

# immediate restart after a busy session (keep-alive connection left open by a client)
proc = start()
wait_until_serving()
lingering = socket.create_connection(("127.0.0.1", PORT))
lingering.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
proc.send_signal(signal.SIGINT)
proc.wait(timeout=10)
proc2 = start()
check("restart right after exit with lingering client", wait_until_serving() == 200)
proc2.send_signal(signal.SIGINT)
proc2.wait(timeout=10)
lingering.close()

print("\nFAILURES: " + ", ".join(failures) if failures else "\nall good")
sys.exit(1 if failures else 0)
