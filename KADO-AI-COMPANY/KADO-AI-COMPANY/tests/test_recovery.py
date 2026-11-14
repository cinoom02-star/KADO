import json
import sqlite3
import zipfile

import pytest

from company.recovery import backup, restore


def test_roundtrip_preserves_sqlite_wal_memory_and_artifacts_without_token(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    db = sqlite3.connect(data / 'company.sqlite3')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE memories (content TEXT)')
    db.execute('INSERT INTO memories VALUES (?)', ('Türkçe kalıcı hafıza',))
    db.commit()
    (data / 'api-token.txt').write_text('private')
    (data / 'artifacts').mkdir()
    (data / 'artifacts' / 'proof.json').write_text('{"real": true}')
    archive = tmp_path / 'saved.zip'
    result = backup(data, archive)
    assert result['files'] == 2
    target = tmp_path / 'restored'
    restore(archive, target)
    with sqlite3.connect(target / 'company.sqlite3') as restored:
        assert restored.execute('SELECT content FROM memories').fetchone()[0] == 'Türkçe kalıcı hafıza'
    assert not (target / 'api-token.txt').exists()
    assert (target / 'artifacts' / 'proof.json').read_text() == '{"real": true}'
    assert db.execute('SELECT count(*) FROM memories').fetchone()[0] == 1
    db.close()
    with pytest.raises(FileExistsError):
        restore(archive, target)
    with pytest.raises(FileExistsError):
        backup(data, archive)


@pytest.mark.parametrize('path', ['../escaped', '/absolute', 'x\\escaped', 'x:stream', 'A/../b', '.env', 'api-token.txt', 'file.', 'CON.txt', 'com1', 'x/bad?file', 'AUX/data'])
def test_restore_rejects_unsafe_paths_before_creating_destination(tmp_path, path):
    archive = tmp_path / 'bad.zip'
    manifest = {'version': 1, 'files': [{'path': path, 'bytes': 0, 'sha256': '0' * 64}]}
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('manifest.json', json.dumps(manifest))
        output.writestr('data/' + path, '')
    target = tmp_path / 'restored'
    with pytest.raises(ValueError):
        restore(archive, target)
    assert not target.exists()


def test_tampered_backup_is_rejected_and_source_is_untouched(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'memory.json').write_text('{"preference": "local"}')
    archive = tmp_path / 'saved.zip'
    backup(data, archive)
    tampered = tmp_path / 'tampered.zip'
    with zipfile.ZipFile(archive) as original, zipfile.ZipFile(tampered, 'w') as output:
        for name in original.namelist():
            output.writestr(name, 'changed' if name == 'data/memory.json' else original.read(name))
    with pytest.raises(ValueError, match='integrity'):
        restore(tampered, tmp_path / 'restored')
    assert not (tmp_path / 'restored').exists()
    assert (data / 'memory.json').read_text() == '{"preference": "local"}'


def test_backup_refuses_running_marker_nested_destination_and_symlinks(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'company-process.json').write_text('{}')
    with pytest.raises(ValueError, match='Stop KADO'):
        backup(data, tmp_path / 'saved.zip')
    (data / 'company-process.json').unlink()
    with pytest.raises(ValueError, match='outside'):
        backup(data, data / 'saved.zip')
    secret = tmp_path / 'outside.txt'
    secret.write_text('private')
    (data / 'link.txt').symlink_to(secret)
    with pytest.raises(ValueError, match='Linked'):
        backup(data, tmp_path / 'saved.zip')
    assert not (tmp_path / 'saved.zip').exists()
