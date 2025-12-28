import os
import socket
import sys
import time


def wait_for_db():
    host = os.environ.get("POSTGRES_HOST", "db")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    timeout = int(os.environ.get("POSTGRES_CONNECT_TIMEOUT", "60"))

    for _ in range(timeout):
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(1)

    return False


if __name__ == "__main__":
    if not wait_for_db():
        print("Postgres not reachable after waiting.", file=sys.stderr)
        sys.exit(1)
