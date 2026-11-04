"""Crash-recoverable per-user source file publication.

All payloads are staged and fsynced before replacing any deployed file. Existing
files are hard-linked to adjacent backups; a journal makes interrupted updates
recoverable on the next registration. Multiple file replacements are not
globally atomic, and this does not cover third-party launcher migrations.
"""
import fcntl
import json
import os
from pathlib import Path
import tempfile
import uuid


def sync_dir(path):
    """Persist directory entry updates where supported by the filesystem."""
    fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class SourceTransaction:
    def __init__(self, state, targets):
        self.state = Path(state)
        self.allowed = {str(Path(path).absolute()) for path in targets}
        self.txdir = self.state / '.source-update'
        self.journal = self.txdir / 'journal.json'
        self.done = self.txdir / 'committed'
        self.lock = None

    def __enter__(self):
        self.state.mkdir(parents=True, exist_ok=True)
        self.lock = (self.state / '.source-update.lock').open('a')
        try:
            fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX)
            self.recover()
            return self
        except BaseException:
            self.lock.close()
            self.lock = None
            raise

    def __exit__(self, exc_type, exc, tb):
        fcntl.flock(self.lock.fileno(), fcntl.LOCK_UN)
        self.lock.close()
        self.lock = None

    def _entries(self):
        records = json.loads(self.journal.read_text())
        if not isinstance(records, list):
            raise RuntimeError('Source update journal has invalid contents.')
        for item in records:
            if not isinstance(item, dict) or item.get('target') not in self.allowed:
                raise RuntimeError('Source update journal contains an unexpected path.')
            target = Path(item['target'])
            if item['stage'] and Path(item['stage']).parent != target.parent:
                raise RuntimeError('Source update staging path is unexpected.')
            if item.get('backup') and Path(item['backup']).parent != target.parent:
                raise RuntimeError('Source update backup path is unexpected.')
        return records

    def _mark_done(self):
        with self.done.open('w') as stream:
            stream.write('complete\n')
            stream.flush()
            os.fsync(stream.fileno())
        sync_dir(self.txdir)

    def _cleanup(self, entries):
        for item in entries:
            if item['stage']:
                Path(item['stage']).unlink(missing_ok=True)
            if item.get('backup'):
                Path(item['backup']).unlink(missing_ok=True)
        self.journal.unlink(missing_ok=True)
        self.done.unlink(missing_ok=True)
        try:
            self.txdir.rmdir()
        except OSError:
            pass

    def recover(self):
        """Restore original files after a killed or interrupted source update."""
        if not self.journal.exists():
            if self.done.exists():
                self.done.unlink()
            return False
        entries = self._entries()
        if not self.done.exists():
            for item in reversed(entries):
                target = Path(item['target'])
                if item['existed']:
                    backup = Path(item['backup'])
                    if not backup.is_file():
                        raise RuntimeError(
                            'Source update recovery needs missing backup '+str(backup)+
                            '. Stop and inspect the journal; no additional writes were made.'
                        )
                    restored = target.with_name('.'+target.name+'.appinstall-restore-'+uuid.uuid4().hex)
                    try:
                        os.link(backup, restored)
                        os.replace(restored, target)
                    finally:
                        restored.unlink(missing_ok=True)
                else:
                    target.unlink(missing_ok=True)
                sync_dir(target.parent)
            self._mark_done()
        self._cleanup(entries)
        return True

    def _publish(self, stage, target):
        """Isolated seam for fault-injection tests."""
        os.replace(stage, target)

    def apply(self, changes):
        """Publish mapping Path -> (bytes, mode) or None (delete)."""
        if self.journal.exists():
            raise RuntimeError('Pending source update journal was not recovered.')
        entries = []
        committed = False
        journal_ready = False
        self.txdir.mkdir(parents=True, exist_ok=True)
        try:
            for name, payload in changes.items():
                target = Path(name).absolute()
                if str(target) not in self.allowed:
                    raise ValueError('Unexpected source update destination: '+str(target))
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_symlink() or (target.exists() and not target.is_file()):
                    raise RuntimeError('Refusing to replace non-regular file: '+str(target))
                existed = target.exists()
                item = dict(target=str(target), stage='', backup='', existed=existed,
                            delete=payload is None)
                entries.append(item)
                if payload is not None:
                    content, mode = payload
                    fd, name = tempfile.mkstemp(
                        prefix='.'+target.name+'.appinstall-stage-', dir=str(target.parent))
                    item['stage'] = name
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(content)
                        stream.flush()
                        os.fchmod(stream.fileno(), mode)
                        os.fsync(stream.fileno())
                if existed:
                    backup = target.with_name(
                        '.'+target.name+'.appinstall-backup-'+uuid.uuid4().hex)
                    os.link(target, backup, follow_symlinks=False)
                    item['backup'] = str(backup)
                sync_dir(target.parent)

            # Write and fsync the recovery instructions before publishing.
            pending = self.txdir / ('journal-'+uuid.uuid4().hex+'.tmp')
            with pending.open('w') as stream:
                json.dump(entries, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, self.journal)
            journal_ready = True
            sync_dir(self.txdir)

            for item in entries:
                target = Path(item['target'])
                if item['delete']:
                    target.unlink(missing_ok=True)
                else:
                    self._publish(item['stage'], target)
                sync_dir(target.parent)
            self._mark_done()
            committed = True
        except BaseException as error:
            if journal_ready:
                try:
                    self.recover()
                except Exception as recovery_error:
                    raise RuntimeError(
                        'Source update failed and recovery was incomplete: '+
                        str(recovery_error)+'. Preserve '+str(self.txdir)
                    ) from error
            raise
        finally:
            if not journal_ready:
                self._cleanup(entries)
            elif committed:
                # Publish succeeded. A failed cleanup can be retried next run.
                try:
                    self._cleanup(entries)
                except OSError:
                    pass
