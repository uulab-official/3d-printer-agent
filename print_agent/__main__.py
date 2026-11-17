"""Run with: python -m print_agent [--port 8765] or python -m print_agent doctor."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

from . import __version__
from .runtime import DataDirectoryInUse, DataDirectoryLease, StorageCompatibilityError, diagnose, resolve_data_directory


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if os.name != 'nt':
            # Match uvicorn: a just-stopped server leaves the port in TIME_WAIT,
            # which must not look like another program owning it.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            return False
        return True


def _agent_answers(url: str) -> bool:
    """True only when this application (not another program) serves the page."""
    try:
        with urllib.request.urlopen(url + '/', timeout=2) as response:
            return b'3D Printer Agent' in response.read(65536)
    except (OSError, ValueError):
        return False


def _should_open_browser(args) -> bool:
    # Only for a person at a terminal: CI, services and test harnesses never get a window.
    return (not args.no_browser and not os.environ.get('PPA_NO_BROWSER')
            and sys.stdout is not None and sys.stdout.isatty())


def _open_when_ready(url: str, port: int, deadline_seconds: float = 60) -> None:
    def wait_then_open():
        deadline = time.monotonic() + deadline_seconds
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.25)
        else:
            return
        if _agent_answers(url):
            webbrowser.open(url)
    threading.Thread(target=wait_then_open, name='open-browser', daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description='3D Printer Agent — local CAD and printing preparation')
    parser.add_argument('command',nargs='?',choices=['serve','doctor','backup','backup-info','restore'],default='serve')
    parser.add_argument('--port',type=int,default=None)
    parser.add_argument('--data-dir',type=Path,default=None)
    parser.add_argument('--output',type=Path,help='New backup archive outside the source data directory')
    parser.add_argument('--archive',type=Path,help='Existing complete-workspace backup archive')
    parser.add_argument('--destination',type=Path,help='New, nonexistent directory for restored data')
    parser.add_argument('--version', action='version', version=f'3D Printer Agent {__version__}')
    parser.add_argument('--no-browser', action='store_true',
                        help='With serve, do not open the app in the default browser')
    parser.add_argument('--probe-slicer', action='store_true',
                        help='With doctor, run the configured Bambu Studio --help to check CLI support')
    args = parser.parse_args()
    if args.probe_slicer and args.command != 'doctor':
        parser.error('--probe-slicer is only available with doctor')
    if args.no_browser and args.command != 'serve':
        parser.error('--no-browser is only available with serve')
    allowed = {
        'serve': {'port', 'data_dir'}, 'doctor': {'data_dir', 'port'},
        'backup': {'data_dir', 'output'}, 'backup-info': {'archive'},
        'restore': {'archive', 'destination'},
    }[args.command]
    for name in ('port', 'data_dir', 'output', 'archive', 'destination'):
        if getattr(args, name) is not None and name not in allowed:
            parser.error(f'--{name.replace("_", "-")} is not available with {args.command}')
    required = {'backup': ('output',), 'backup-info': ('archive',), 'restore': ('archive', 'destination')}
    for name in required.get(args.command, ()):
        if getattr(args, name) is None:
            parser.error(f'{args.command} requires --{name}')
    if args.command in required:
        from .backup import BackupError, create_backup, inspect_backup, restore_backup
        try:
            if args.command == 'backup':
                selection = resolve_data_directory(args.data_dir)
                report = create_backup(Path(selection['path']), args.output)
                report['storage'] = selection
            elif args.command == 'backup-info':
                report = inspect_backup(args.archive)
            else:
                report = restore_backup(args.archive, args.destination)
        except (BackupError, DataDirectoryInUse, StorageCompatibilityError, OSError) as exc:
            detail = ('백업 파일과 폴더의 경로·권한·여유 공간을 확인하세요. 기존 자료를 덮어쓰지 않았습니다.'
                      if isinstance(exc, OSError) else str(exc))
            print(json.dumps({'status': 'error', 'code': 'backup_failed', 'detail': detail}, ensure_ascii=False, indent=2))
            raise SystemExit(1) from None
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if args.command == 'doctor':
        report = diagnose(args.data_dir, probe_slicer=args.probe_slicer)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        if not report['ready']:
            raise SystemExit(1)
        return
    port = args.port if args.port is not None else 8765
    if not 1024 <= port <= 65535:
        parser.error('--port must be between 1024 and 65535')
    url = f'http://127.0.0.1:{port}'
    if not _port_free(port):
        if _agent_answers(url):
            print(f'3D Printer Agent가 이미 실행 중입니다: {url}\n'
                  '브라우저에서 이 주소를 여세요. 새 서버는 시작하지 않았습니다.', flush=True)
            if _should_open_browser(args):
                webbrowser.open(url)
            return
        print(f'포트 {port}을(를) 다른 프로그램이 사용 중입니다. '
              f'다른 포트로 시작하세요: printer-agent --port {port + 1}', file=sys.stderr, flush=True)
        raise SystemExit(1)
    storage = resolve_data_directory(args.data_dir)
    root = Path(storage['path'])
    if root.is_dir():
        # Fail before starting the server, with the app's own message instead of a traceback.
        try:
            with DataDirectoryLease(root):
                pass
        except DataDirectoryInUse as exc:
            print(str(exc), file=sys.stderr, flush=True)
            raise SystemExit(1) from None
    import uvicorn
    from .app import create_app
    print(f'Starting 3D Printer Agent: {url}\n'
          f'Data directory ({storage["source"]}): {storage["path"]}\nStop: Ctrl+C', flush=True)
    if _should_open_browser(args):
        _open_when_ready(url, port)
    uvicorn.run(create_app(args.data_dir),host='127.0.0.1',port=port,log_level='info')


if __name__ == '__main__':
    main()
