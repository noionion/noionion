"""Export official token usage for the locally signed-in Codex account.

No API key required. Only allowlisted aggregate counters are written to the repository.
This command never commits or pushes. Run on the computer signed in to Codex.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

from codex_usage import sanitize, validate


class AppServer:
    def __init__(self, executable, timeout=60):
        self.timeout = timeout
        self.messages = queue.Queue()
        self.sequence = 0
        self.process = subprocess.Popen(
            [executable, 'app-server', '--stdio'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.process.stdout:
            try:
                self.messages.put(json.loads(line))
            except ValueError:
                continue
        self.messages.put(None)

    def send(self, message):
        self.process.stdin.write(json.dumps(message)+'\n')
        self.process.stdin.flush()

    def call(self, method, params):
        self.sequence += 1
        identity = self.sequence
        self.send({'method': method, 'id': identity, 'params': params})
        deadline = time.monotonic()+self.timeout
        while True:
            try:
                message = self.messages.get(timeout=max(0, deadline-time.monotonic()))
            except queue.Empty:
                raise RuntimeError(f'Codex timed out while reading {method}') from None
            if message is None:
                raise RuntimeError('Codex app-server stopped; check that Codex can run and is signed in')
            if message.get('id') == identity:
                if 'error' in message:
                    # Do not echo arbitrary server payloads into public export logs.
                    code = message['error'].get('code', 'unknown')
                    raise RuntimeError(f'Codex rejected {method} (code {code}); no usage file was changed')
                return message['result']
            if 'id' in message and 'method' in message:
                self.send({'id': message['id'], 'error': {'code': -32601, 'message': 'Unsupported method'}})

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        for stream in (self.process.stdin, self.process.stdout):
            stream.close()


def read_account_usage(executable):
    client = AppServer(executable)
    try:
        client.call('initialize', {'clientInfo': {'name': 'noionion_profile', 'version': '1.0.0'},
                                   'capabilities': {'experimentalApi': True}})
        client.send({'method': 'initialized', 'params': {}})
        account = client.call('account/read', {'refreshToken': False}).get('account') or {}
        if account.get('type') != 'chatgpt':
            raise RuntimeError('Sign in to the intended ChatGPT account in Codex before exporting usage')
        return client.call('account/usage/read', {})
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', default=shutil.which('codex'), help='Path to the installed Codex CLI')
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parent.parent / 'data/codex-usage.json')
    args = parser.parse_args()
    if not args.codex:
        parser.error('Codex was not found; supply --codex with the executable path')
    response = read_account_usage(args.codex)
    fetched_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    data = validate(sanitize(response, fetched_at))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(args.output)
    print(f'Exported official account summary and {len(data["daily"] or {})} daily records to {args.output}')


if __name__ == '__main__':
    main()
