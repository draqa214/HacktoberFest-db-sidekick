"""Run the web UI and authenticated API behind one Maritime port."""
import os
import signal
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
children = []


def stop(*_):
    for child in children:
        child.terminate()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
    raise SystemExit(0)


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
env = dict(os.environ)
env.setdefault("PORT", "8080")
# Maritime micro-VMs may start without a localhost hosts entry.
hosts = Path("/etc/hosts")
if hosts.exists() and "localhost" not in hosts.read_text():
    with hosts.open("a") as file:
        file.write("\n127.0.0.1 localhost\n")
try:
    children.append(subprocess.Popen(["python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=root / "backend", env=env))
    children.append(subprocess.Popen(["node", "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", "3000"], cwd=root / "frontend", env=env))
    children.append(subprocess.Popen(["caddy", "run", "--config", str(root / "deploy/Caddyfile"), "--adapter", "caddyfile"], env=env))
    while all(child.poll() is None for child in children):
        time.sleep(1)
finally:
    stop()
