"""Run with: python -m print_agent [--port 8765] or python -m print_agent doctor."""
import argparse
import json
from pathlib import Path

from . import __version__
from .runtime import DataDirectoryInUse, StorageCompatibilityError, diagnose, resolve_data_directory


def main():
    parser = argparse.ArgumentParser(description='3D Printer Agent — local CAD and printing preparation')
    parser.add_argument('command',nargs='?',choices=['serve','doctor','backup','backup-info','restore'],default='serve')
    parser.add_argument('--port',type=int,default=None)
    parser.add_argument('--data-dir',type=Path,default=None)
    parser.add_argument('--output',type=Path,help='New backup archive outside the source data directory')
    parser.add_argument('--archive',type=Path,help='Existing complete-workspace backup archive')
    parser.add_argument('--destination',type=Path,help='New, nonexistent directory for restored data')
    parser.add_argument('--version', action='version', version=f'3D Printer Agent {__version__}')
    parser.add_argument('--probe-slicer', action='store_true',
                        help='With doctor, run the configured Bambu Studio --help to check CLI support')
    args = parser.parse_args()
    if args.probe_slicer and args.command != 'doctor':
        parser.error('--probe-slicer is only available with doctor')
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
    import uvicorn
    from .app import create_app
    storage = resolve_data_directory(args.data_dir)
    print(f'Starting 3D Printer Agent: http://127.0.0.1:{port}\n'
          f'Data directory ({storage["source"]}): {storage["path"]}\nStop: Ctrl+C', flush=True)
    uvicorn.run(create_app(args.data_dir),host='127.0.0.1',port=port,log_level='info')


if __name__ == '__main__':
    main()
