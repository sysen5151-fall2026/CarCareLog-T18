"""Start the CarCareLog classroom demo with isolated local storage."""

import argparse
import errno
import os
from pathlib import Path
import runpy
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accounts", action="store_true", help="enable local sign-up and separate owner histories")
    parser.add_argument("--ai", action="store_true", help="draft receipts with qwen3.5:4b in local Ollama")
    parser.add_argument("--port", type=int, default=8000, help="local HTTP port (default: 8000)")
    parser.add_argument("--data-dir", type=Path, default=Path.home() / ".carcarelog-classroom",
                        help="classroom storage folder (default: ~/.carcarelog-classroom)")
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error("CarCareLog needs Python 3.10 or later.")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535.")

    folder = args.data_dir.expanduser().resolve()
    backend = Path(__file__).resolve().parent / "CarCareLog" / "backend"
    os.environ["CARCARE_PORT"] = str(args.port)
    os.environ["CARCARE_DB"] = str(folder / "single-owner.sqlite3")
    os.environ["CARCARE_SITE_DIR"] = str(folder / "accounts")
    os.environ["CARCARE_OLLAMA_MODEL"] = "qwen3.5:4b" if args.ai else ""
    sys.path.insert(0, str(backend))
    script = backend / ("owner_site.py" if args.accounts else "app.py")

    try:
        folder.mkdir(parents=True, exist_ok=True)
        print(f"Classroom data: {folder}", flush=True)
        print(f"Open http://127.0.0.1:{args.port} in your browser. Press Ctrl+C to stop.", flush=True)
        runpy.run_path(str(script), run_name="__main__")
    except KeyboardInterrupt:
        pass
    except OSError as error:
        if error.errno == errno.EADDRINUSE or getattr(error, "winerror", None) == 10048:
            parser.exit(1, f"Port {args.port} is already in use. Try a different --port.\n")
        parser.exit(1, f"CarCareLog could not start: {error}\n")


if __name__ == "__main__":
    main()
