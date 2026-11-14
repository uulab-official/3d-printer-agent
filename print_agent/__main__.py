"""Run with: python -m print_agent [--port 8765] or python -m print_agent doctor."""
import argparse
import json
from pathlib import Path

from . import __version__
from .runtime import diagnose, resolve_data_directory


def main():
    parser = argparse.ArgumentParser(description='3D Printer Agent — local CAD and printing preparation')
    parser.add_argument('command',nargs='?',choices=['serve','doctor'],default='serve')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--data-dir',type=Path,default=None)
    parser.add_argument('--version', action='version', version=f'3D Printer Agent {__version__}')
    parser.add_argument('--probe-slicer', action='store_true',
                        help='With doctor, run the configured Bambu Studio --help to check CLI support')
    args = parser.parse_args()
    if args.probe_slicer and args.command != 'doctor':
        parser.error('--probe-slicer is only available with doctor')
    if args.command == 'doctor':
        report = diagnose(args.data_dir, probe_slicer=args.probe_slicer)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        if not report['ready']:
            raise SystemExit(1)
        return
    if not 1024 <= args.port <= 65535:
        parser.error('--port must be between 1024 and 65535')
    import uvicorn
    from .app import create_app
    storage = resolve_data_directory(args.data_dir)
    print(f'Starting 3D Printer Agent: http://127.0.0.1:{args.port}\n'
          f'Data directory ({storage["source"]}): {storage["path"]}\nStop: Ctrl+C', flush=True)
    uvicorn.run(create_app(args.data_dir),host='127.0.0.1',port=args.port,log_level='info')


if __name__ == '__main__':
    main()
