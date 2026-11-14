"""Windows entry point for isolated company data recovery; legacy data stays untouched."""
from pathlib import Path
import os
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from dotenv import load_dotenv
from company.recovery import backup, restore
from company.config import _protected_windows_path


def main():
    load_dotenv(ROOT / '.env', override=False)
    if len(sys.argv) > 1 and sys.argv[1] == 'restore':
        if len(sys.argv) != 4:
            raise ValueError('Usage: recovery_cli.py restore ARCHIVE NEW_DIRECTORY')
        result = restore(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        if os.environ.get('DATABASE_URL') and not os.environ['DATABASE_URL'].startswith('sqlite:'):
            raise ValueError('External databases require their native backup tools; no backup was created')
        if os.environ.get('DATABASE_URL'):
            # An external/custom SQLite path may fall outside data_dir. Never
            # produce a misleading "complete" backup of that configuration.
            raise ValueError('Custom DATABASE_URL: use company.recovery with an explicit, verified data directory')
        configured_root = Path(os.environ.get('KADO_COMPANY_ROOT', str(ROOT)))
        if not configured_root.is_absolute():
            configured_root = ROOT / configured_root
        data = Path(os.environ.get('KADO_DATA_DIR', str(configured_root / 'data')))
        if not data.is_absolute():
            data = ROOT / data
        if _protected_windows_path(data.resolve()):
            raise ValueError('Legacy KADO directories are not Company recovery data')
        if not (data / 'company.sqlite3').is_file():
            raise ValueError('Company SQLite database not found; no complete backup can be claimed')
        output = ROOT / 'backups' / ('kado-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.zip')
        result = backup(data, output)
    print('Recovery verified:', result)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Recovery failed:', str(exc))
        raise SystemExit(1)
