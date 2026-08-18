import json
import os
import secrets
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TOKEN = os.environ["SANDBOX_RESET_TOKEN"]
DB_HOST = os.getenv("ODOO_DB_HOST", "odoo-db")
DB_USER = os.getenv("ODOO_DB_USER", "odoo")
DB_NAME = os.getenv("ODOO_DATABASE", "changeshield")
SNAPSHOT = Path(os.getenv("ODOO_SNAPSHOT_PATH", "/snapshot/changeshield.dump"))
LOCK = threading.Lock()


def env():
    return {**os.environ, "PGPASSWORD": os.environ["ODOO_DB_PASSWORD"]}


def run(*args, input_bytes=None):
    return subprocess.run(args, input=input_bytes, env=env(), check=True, capture_output=True, timeout=120)


def snapshot():
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    result = run("pg_dump", "-h", DB_HOST, "-U", DB_USER, "-Fc", DB_NAME)
    temporary = SNAPSHOT.with_suffix(".tmp")
    temporary.write_bytes(result.stdout)
    temporary.replace(SNAPSHOT)


def restore():
    if not SNAPSHOT.exists():
        raise RuntimeError("Sandbox snapshot has not been captured")
    run("psql", "-h", DB_HOST, "-U", DB_USER, "-d", "postgres", "-c", f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{DB_NAME}' AND pid <> pg_backend_pid();")
    run("dropdb", "-h", DB_HOST, "-U", DB_USER, "--if-exists", DB_NAME)
    run("createdb", "-h", DB_HOST, "-U", DB_USER, DB_NAME)
    run("pg_restore", "-h", DB_HOST, "-U", DB_USER, "-d", DB_NAME, str(SNAPSHOT))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.respond(200, {"status": "ready", "snapshot": SNAPSHOT.exists()})
        else:
            self.respond(404, {"error": "not found"})

    def do_POST(self):
        supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
        if not secrets.compare_digest(supplied, TOKEN):
            self.respond(403, {"error": "forbidden"}); return
        if self.path not in {"/snapshot", "/restore"}:
            self.respond(404, {"error": "not found"}); return
        if not LOCK.acquire(blocking=False):
            self.respond(409, {"error": "reset already running"}); return
        try:
            snapshot() if self.path == "/snapshot" else restore()
            self.respond(200, {"status": "captured" if self.path == "/snapshot" else "restored"})
        except (RuntimeError, subprocess.SubprocessError) as exc:
            self.respond(500, {"error": str(exc)[:500]})
        finally:
            LOCK.release()

    def respond(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()

