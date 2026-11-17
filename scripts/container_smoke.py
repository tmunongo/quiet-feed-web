"""Rehearse fresh install and every legacy upgrade using disposable Docker volumes."""

import http.cookiejar
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import uuid4

from smoke_helpers import CRYPTO, seed_legacy


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else "quiet-feed:test"
    assert docker("image", "inspect", "--format", "{{.Architecture}}", image) == "arm64"
    with tempfile.TemporaryDirectory(prefix="quiet-feed-container-") as directory:
        for revision, historical in [
            (None, False),
            (0, False),
            (1, False),
            (2, False),
            (1, True),
            (2, True),
        ]:
            suffix = uuid4().hex[:10]
            name, volume = f"quiet-feed-smoke-{suffix}", f"quiet-feed-smoke-data-{suffix}"
            docker("volume", "create", volume)
            try:
                docker(
                    "create",
                    "--name",
                    name,
                    "--platform",
                    "linux/arm64",
                    "-p",
                    "127.0.0.1::3000",
                    "--mount",
                    f"source={volume},target=/app/data",
                    "-e",
                    f"BETTER_AUTH_SECRET={CRYPTO['secret']}",
                    "-e",
                    "ORIGIN=http://localhost:3000",
                    "-e",
                    "ENABLE_INTERNAL_SCHEDULER=false",
                    image,
                )
                if revision is not None:
                    path = seed_legacy(
                        Path(directory) / f"legacy-{revision}-{historical}.db", revision, historical
                    )
                    docker("cp", str(path), f"{name}:/app/data/quiet-feed.db")
                docker("start", name)
                port = docker("port", name, "3000/tcp").rsplit(":", 1)[1]
                origin = f"http://127.0.0.1:{port}"
                client = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
                )
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    try:
                        response = client.open(origin + "/healthz", timeout=2)
                        assert json.load(response)["status"] == "ok"
                        break
                    except OSError:
                        time.sleep(0.2)
                else:
                    raise RuntimeError("Container did not become healthy")
                response = client.open(origin + ("/register" if revision is None else "/login"))
                response.close()
                # Read the form token from the HTML so this also verifies template wiring.
                page = (
                    client.open(origin + ("/register" if revision is None else "/login"))
                    .read()
                    .decode()
                )
                csrf = re.search(r'name="csrf_token" value="([^"]+)"', page)[1]
                fields = {
                    "csrf_token": csrf,
                    "name": "Reader",
                    "email": "fresh@example.com" if revision is None else "reader@example.com",
                    "password": "fresh-test-password"
                    if revision is None
                    else CRYPTO["passwords"][0]["password"],
                }
                # Avoid compiling feeds on the redirect even at 23:59 UTC.
                if revision is not None:
                    docker(
                        "exec",
                        name,
                        "python",
                        "-c",
                        "import sqlite3,datetime; c=sqlite3.connect('/app/data/quiet-feed.db'); c.execute('UPDATE user_settings SET last_edition_date=?',(datetime.datetime.now(datetime.timezone.utc).date().isoformat(),)); c.commit()",
                    )
                response = client.open(
                    origin + ("/register" if revision is None else "/login"),
                    data=urllib.parse.urlencode(fields).encode(),
                )
                assert response.status == 200
                if revision is not None:
                    assert b"Existing story" in client.open(origin + "/article/progress").read()
                    count = docker(
                        "exec",
                        name,
                        "python",
                        "-c",
                        "from pathlib import Path; print(len(list(Path('/app/data/backups').glob('*.db'))))",
                    )
                    assert count == "1"
                docker("restart", name)
                port = docker("port", name, "3000/tcp").rsplit(":", 1)[1]
                origin = f"http://127.0.0.1:{port}"
                # The same database/session survives recreation and migrations are idempotent.
                for _ in range(100):
                    try:
                        assert client.open(origin + "/feeds", timeout=2).status == 200
                        break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Container did not restart")
                if revision is not None:
                    assert (
                        docker(
                            "exec",
                            name,
                            "python",
                            "-c",
                            "from pathlib import Path; print(len(list(Path('/app/data/backups').glob('*.db'))))",
                        )
                        == "1"
                    )
                print(
                    f"ARM64 container smoke passed: {'fresh install' if revision is None else f'Drizzle revision {revision}'}, login, data, restart."
                )
            except Exception:
                print(docker("logs", name), file=sys.stderr)
                raise
            finally:
                subprocess.run(["docker", "rm", "-f", name], capture_output=True)
                subprocess.run(["docker", "volume", "rm", volume], capture_output=True)


if __name__ == "__main__":
    main()
