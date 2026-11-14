"""Offline, data-only recovery. Never imports or changes legacy KADO stores."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
import zipfile

MAX_BYTES = 2_000_000_000
MAX_FILES = 10000
EXCLUDED = {'api-token.txt', 'company-process.json', 'logs', 'backups', '__pycache__',
            'credentials.json', 'secrets.json', 'token.json', 'sessions', 'auth_info'}
WINDOWS_DEVICES = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)),
                   *(f'lpt{i}' for i in range(1, 10))}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def check_database(path: Path) -> None:
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite integrity check failed')


def backup(data_dir: Path, destination: Path) -> dict:
    data_dir, destination = data_dir.resolve(), destination.absolute()
    if not data_dir.is_dir():
        raise ValueError('Data directory does not exist')
    if (data_dir / 'company-process.json').exists():
        raise ValueError('Stop KADO first; process ownership record is still present')
    if destination.resolve().is_relative_to(data_dir):
        raise ValueError('Backup destination must be outside the data directory')
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                'scope': 'company data only; legacy KADO, credentials and logs excluded', 'files': []}
    with tempfile.TemporaryDirectory(dir=destination.parent) as scratch:
        archive_path = Path(scratch) / 'backup.zip'
        total = 0
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for directory, dirs, names in os.walk(data_dir, followlinks=False):
                dirs[:] = sorted(d for d in dirs if d.casefold() not in EXCLUDED and not d.startswith('.')
                                 and not (Path(directory) / d).is_symlink())
                for name in sorted(names):
                    path = Path(directory) / name
                    if name.casefold() in EXCLUDED or name.startswith('.') or name.endswith(('-wal', '-shm')):
                        continue
                    if path.is_symlink() or not path.is_file():
                        raise ValueError('Linked or special files are not supported')
                    relative = path.relative_to(data_dir).as_posix()
                    source = path
                    if name.endswith(('.sqlite3', '.sqlite', '.db')):
                        snapshot = Path(scratch) / 'snapshot.sqlite3'
                        snapshot.unlink(missing_ok=True)
                        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
                            with sqlite3.connect(snapshot) as target:
                                db.backup(target)
                        check_database(snapshot)
                        source = snapshot
                    size = source.stat().st_size
                    total += size
                    if total > MAX_BYTES or len(manifest['files']) >= MAX_FILES:
                        raise ValueError('Backup size/file limit exceeded')
                    raw = source.read_bytes()
                    if len(raw) != size:
                        raise ValueError('Data changed during backup; stop all writers')
                    archive.writestr('data/' + relative, raw)
                    manifest['files'].append({'path': relative, 'bytes': size, 'sha256': digest(raw)})
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
        # Exclusive creation protects an existing backup, including a racing writer.
        created = False
        try:
            with destination.open('xb') as output, archive_path.open('rb') as source:
                created = True
                os.chmod(destination, 0o600)
                shutil.copyfileobj(source, output)
        except Exception:
            if created:
                destination.unlink(missing_ok=True)
            raise
    return {'path': str(destination), 'files': len(manifest['files']), 'bytes': total}


def restore(archive_path: Path, destination: Path) -> dict:
    """Verify everything first, then restore into a NEW directory. Never overwrite."""
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Restore requires a new directory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or len(names) > MAX_FILES + 1:
            raise ValueError('Duplicate entries or file limit exceeded')
        if sum(info.file_size for info in infos) > MAX_BYTES:
            raise ValueError('Archive size limit exceeded')
        manifest_info = archive.getinfo('manifest.json')
        if manifest_info.file_size > 5_000_000:
            raise ValueError('Manifest too large')
        manifest = json.loads(archive.read(manifest_info))
        if manifest.get('version') != 1 or not isinstance(manifest.get('files'), list):
            raise ValueError('Unsupported manifest')
        expected = {'manifest.json'}
        paths = set()
        for item in manifest['files']:
            value = item['path']
            rel = PurePosixPath(value)
            if (not value or rel.is_absolute() or '\\' in value or ':' in value or
                    any(part in {'', '.', '..'} or part.endswith(('.', ' ')) for part in value.split('/')) or
                    any(part.casefold() in EXCLUDED or part.startswith('.') or
                        part.split('.')[0].casefold() in WINDOWS_DEVICES or
                        any(ord(char) < 32 or char in '<>"|?*' for char in part)
                        for part in rel.parts)):
                raise ValueError('Unsafe archive path')
            # Case folding also protects Windows from colliding paths.
            if value.casefold() in paths:
                raise ValueError('Duplicate destination path')
            paths.add(value.casefold())
            expected.add('data/' + value)
            raw = archive.read('data/' + value)
            if len(raw) != item['bytes'] or digest(raw) != item['sha256']:
                raise ValueError('Backup integrity mismatch')
        if set(names) != expected:
            raise ValueError('Unexpected archive entries')
        with tempfile.TemporaryDirectory(dir=destination.parent) as scratch:
            staging = Path(scratch) / 'restored'
            staging.mkdir(mode=0o700)
            for item in manifest['files']:
                target = staging / item['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read('data/' + item['path']))
                target.chmod(0o600)
                if target.suffix in {'.sqlite3', '.sqlite', '.db'}:
                    check_database(target)
            # Exclusive mkdir protects even an empty directory created by a
            # concurrent caller, consistently on Windows and POSIX.
            destination.mkdir(mode=0o700)
            try:
                for child in staging.iterdir():
                    child.rename(destination / child.name)
            except Exception:
                shutil.rmtree(destination)
                raise
    return {'path': str(destination), 'files': len(manifest['files']),
            'note': 'API token excluded; configure a new token before starting restored data'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    save = commands.add_parser('backup')
    save.add_argument('--data-dir', type=Path, required=True)
    save.add_argument('--destination', type=Path, required=True)
    load = commands.add_parser('restore')
    load.add_argument('archive', type=Path)
    load.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = backup(args.data_dir, args.destination) if args.command == 'backup' else restore(args.archive, args.destination)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, zipfile.BadZipFile) as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__,
                          'message': 'Recovery failed; original data was not replaced.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
