import asyncio
import json
import re
import subprocess
import sys

from websockets.asyncio.client import connect


def test_cli_prints_ready(tmp_path):
    proc = subprocess.Popen(
        [sys.executable, "-m", "siegesense_engine", "--token", "t", "--data-dir", str(tmp_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        line = proc.stdout.readline().strip()
        match = re.fullmatch(r"READY (\d+)", line)
        assert match, line

        async def hello():
            async with connect(f"ws://127.0.0.1:{match.group(1)}") as ws:
                await ws.send(
                    json.dumps({"type": "hello", "id": "1", "ts": 0, "payload": {"token": "t"}})
                )
                return json.loads(await asyncio.wait_for(ws.recv(), 3))

        assert asyncio.run(hello())["payload"]["ok"] is True
        assert (tmp_path / "siegesense.db").exists()
    finally:
        proc.stdin.close()  # parent "dies" -> engine should exit by itself
        assert proc.wait(timeout=5) == 0
