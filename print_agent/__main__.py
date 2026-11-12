"""Run with: python -m print_agent [--port 8765] or python -m print_agent doctor."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='3D Printer Agent — local CAD and printing preparation')
    parser.add_argument('command',nargs='?',choices=['serve','doctor'],default='serve')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--data-dir',type=Path,default=None)
    args = parser.parse_args()
    if args.command == 'doctor':
        import cadquery
        from . import __version__
        from .planner import provider_config
        from .slicer import detect_environment
        print(json.dumps({'version':__version__,'cadquery':cadquery.__version__,
                          'slicer':detect_environment(),'provider':provider_config()},ensure_ascii=False,indent=2))
        return
    if not 1024 <= args.port <= 65535:
        parser.error('--port must be between 1024 and 65535')
    import uvicorn
    from .app import create_app
    print(f'3D Printer Agent: http://127.0.0.1:{args.port}\nStop: Ctrl+C')
    uvicorn.run(create_app(args.data_dir),host='127.0.0.1',port=args.port,log_level='info')


if __name__ == '__main__':
    main()
