"""CLI entry point: ``python -m siegesense_engine --token T --data-dir D``.

Prints ``READY <port>`` on stdout once listening. Exits when stdin closes (the app died),
or on SIGINT/SIGTERM.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import sys
import threading
from pathlib import Path

from .capture.frames import VideoFileSource, default_frame_source
from .game_watcher import default_game_watcher
from .gamesettings import default_documents_dirs
from .input.source import ReplayInputSource, default_input_source
from .server import EngineServer
from .store import Store


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="siegesense_engine")
    parser.add_argument("--token", required=True)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--documents-dir", action="append", type=Path, default=None)
    parser.add_argument("--replay-input", type=Path, default=None, help="replay a JSONL input file")
    parser.add_argument("--replay-video", type=Path, default=None, help="use a video as the screen")
    return parser.parse_args(argv)


def _watch_stdin(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    def run() -> None:
        with contextlib.suppress(Exception):
            while sys.stdin.read(1024):
                pass
        loop.call_soon_threadsafe(stop.set)

    threading.Thread(target=run, daemon=True, name="stdin-watch").start()


async def _run(args: argparse.Namespace) -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):  # not on Windows
            loop.add_signal_handler(sig, stop.set)
    _watch_stdin(loop, stop)

    store = Store(args.data_dir / "siegesense.db")
    server = EngineServer(
        token=args.token,
        store=store,
        watcher=default_game_watcher(),
        documents_dirs=args.documents_dir or default_documents_dirs(),
        input_source=(
            ReplayInputSource(args.replay_input) if args.replay_input else default_input_source()
        ),
        frame_source=(
            VideoFileSource(args.replay_video) if args.replay_video else default_frame_source()
        ),
    )
    port = await server.start(args.port)
    print(f"READY {port}", flush=True)
    try:
        await stop.wait()
    finally:
        await server.stop()
        store.close()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(message)s")
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_run(_parse_args(argv)))


if __name__ == "__main__":
    main()
