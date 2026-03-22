from __future__ import annotations

import argparse
from pathlib import Path

from .config import LabConfig, Paths
from .supervisor import Supervisor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Low VRAM Institute autonomous lab")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run-once", help="run one cycle")

    daemon = sub.add_parser("daemon", help="run forever with retries and backoff")
    daemon.add_argument("--max-cycles", type=int, default=None)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    paths = Paths.discover(args.root)
    config = LabConfig(max_cycles=getattr(args, "max_cycles", None))
    supervisor = Supervisor(paths, config)

    if args.command == "run-once":
        print(supervisor.run_once())
    elif args.command == "daemon":
        supervisor.daemon()


if __name__ == "__main__":
    main()
