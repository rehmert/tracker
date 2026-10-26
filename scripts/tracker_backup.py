#!/usr/bin/env python3
"""Run from project root: python -m scripts.tracker_backup [create|verify|list]."""
import argparse
from pathlib import Path
from app.backup import create_backup, list_backups, prune_backups, verify_backup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['create', 'verify', 'list'])
    parser.add_argument('archive', nargs='?')
    args = parser.parse_args()
    if args.action == 'create':
        archive = create_backup()
        print(f'Created and verified {archive}')
        print(f'Pruned {len(prune_backups())} old backups')
    elif args.action == 'verify':
        if not args.archive:
            parser.error('verify requires archive path')
        manifest = verify_backup(Path(args.archive))
        print(f'Verified {len(manifest["files"])} files')
    else:
        for item in list_backups():
            print(f'{item["modified"].isoformat()} {item["size"]:>12} {item["name"]}')


if __name__ == '__main__':
    main()
