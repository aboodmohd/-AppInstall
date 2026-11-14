"""Batch drag-and-drop install tests.

Covers the package MIME classification (validated against the MimeType list
in appinstall.desktop), the Qt-free BatchQueue state machine, and the
BatchQueueDialog running the real per-file review process one file at a
time — with a stubbed appinstall CLI, offscreen Qt, and no network access.
"""
import importlib.util
import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location('manager', ROOT / 'manager.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)
from qt_compat import QtWidgets


def desktop_mime_list():
    text = (ROOT / 'appinstall.desktop').read_text()
    for line in text.splitlines():
        if line.startswith('MimeType='):
            return [entry for entry in line[len('MimeType='):].split(';')
                    if entry]
    return []


class PackageMimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_every_mapped_mime_is_declared_in_the_desktop_entry(self):
        declared = set(desktop_mime_list())
        self.assertTrue(declared, 'appinstall.desktop MimeType= not found')
        self.assertLessEqual(set(manager.PACKAGE_MIMES.values()), declared)

    def test_declared_package_mimes_have_an_extension_mapping(self):
        # Every declared MIME must either map to a drop extension or be an
        # alternative registration of an already-mapped format (x-deb is the
        # deb package alias; iso9660-appimage and quickdrop-appimage are
        # AppImage containers sharing the .AppImage extension). A new
        # genuinely distinct format added to the desktop file fails here
        # until PACKAGE_MIMES learns its extension.
        declared = set(desktop_mime_list())
        aliases = {'application/x-deb', 'application/x-iso9660-appimage',
                   'application/x-quickdrop-appimage'}
        missing = declared - set(manager.PACKAGE_MIMES.values()) - aliases
        self.assertEqual(
            missing, set(),
            'desktop MIME types with no drop mapping: '+repr(missing))

    def test_classify_supported_extensions_case_insensitive(self):
        for name in ('pkg.deb', 'pkg.DEB', 'pkg.rpm', 'Game.AppImage',
                     'Game.appimage', 'app.flatpak', 'app.flatpakref',
                     'app.flatpakrepo'):
            target = self.root / name
            target.write_bytes(b'x')
            self.assertIsNotNone(manager.classify_package(target), name)

    def test_classify_rejects_unknown_types(self):
        text = self.root / 'notes.txt'
        text.write_text('hello')
        self.assertIsNone(manager.classify_package(text))
        self.assertIsNone(manager.classify_package(self.root / 'absent.deb'))

    def test_classify_rejects_directories(self):
        directory = self.root / 'bundle.deb'
        directory.mkdir()
        self.assertIsNone(manager.classify_package(directory))


class BatchQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def pkg(self, name):
        target = self.root / name
        target.write_bytes(b'x')
        return str(target)

    def test_unsupported_files_land_as_unsupported_rows(self):
        queue = manager.BatchQueue([self.pkg('x.deb'), self.pkg('x.txt')])
        self.assertEqual([item.state for item in queue.items],
                         [manager.BatchItem.QUEUED,
                          manager.BatchItem.UNSUPPORTED])

    def test_lifecycle_transitions(self):
        queue = manager.BatchQueue([self.pkg('a.deb')])
        index = queue.runnable()
        self.assertEqual(index, 0)
        queue.started(index)
        self.assertEqual(queue.items[0].state, manager.BatchItem.RUNNING)
        self.assertTrue(queue.busy())
        queue.finished(index, 0)
        self.assertEqual(queue.items[0].state, manager.BatchItem.INSTALLED)
        self.assertFalse(queue.pending())

    def test_nonzero_exit_is_failed_with_code(self):
        queue = manager.BatchQueue([self.pkg('a.rpm')])
        queue.started(queue.runnable())
        queue.finished(0, 3)
        self.assertEqual(queue.items[0].state, manager.BatchItem.FAILED)
        self.assertEqual(queue.items[0].exit_code, 3)

    def test_runnable_skips_cancelled_and_unsupported(self):
        queue = manager.BatchQueue([self.pkg('a.txt'), self.pkg('b.deb'),
                                    self.pkg('c.deb')])
        queue.cancel(1)
        self.assertEqual(queue.runnable(), 2)

    def test_cancel_running_ignores_late_exit_result(self):
        queue = manager.BatchQueue([self.pkg('a.deb')])
        queue.started(queue.runnable())
        queue.cancel(0)
        queue.finished(0, 0)  # process exits after the cancel
        self.assertEqual(queue.items[0].state, manager.BatchItem.CANCELLED)
        self.assertIsNone(queue.items[0].exit_code)

    def test_cancel_is_noop_on_terminal_states(self):
        queue = manager.BatchQueue([self.pkg('a.deb')])
        queue.started(0)
        queue.finished(0, 0)
        queue.cancel(0)
        self.assertEqual(queue.items[0].state, manager.BatchItem.INSTALLED)
        queue.finished(0, 0)  # late duplicate result also ignored
        self.assertEqual(queue.items[0].state, manager.BatchItem.INSTALLED)
        unsupported = manager.BatchQueue([self.pkg('a.txt')])
        unsupported.cancel(0)
        self.assertEqual(unsupported.items[0].state,
                         manager.BatchItem.UNSUPPORTED)

    def test_runnable_none_when_exhausted(self):
        queue = manager.BatchQueue([self.pkg('a.txt')])
        self.assertIsNone(queue.runnable())


class DialogBase(unittest.TestCase):
    """Offscreen dialog harness with a stubbed appinstall CLI."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {
            'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_STATE_HOME': str(self.root / 'state'),
        })
        self.environment.start()
        from qt_compat import QtWidgets
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        self.stub = self.root / 'stub-appinstall'
        self.write_stub('exit 0')

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def write_stub(self, body):
        self.stub.write_text('#!/bin/sh\n' + body + '\n')
        self.stub.chmod(self.stub.stat().st_mode | stat.S_IXUSR)
        return self.stub

    def touch(self, name):
        target = self.root / name
        target.write_bytes(b'\x7fELF-stub-package')
        return str(target)

    def make_dialog(self, paths, stub_body='exit 0'):
        self.write_stub(stub_body)
        dialog = manager.BatchQueueDialog(
            manager.BatchQueue(paths), None)
        dialog.show()
        return dialog

    def wait_for(self, condition, timeout=6, message='condition not reached'):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return
            time.sleep(.02)
        self.fail(message)

    def statuses(self, dialog):
        return [status.text() for status, cancel in dialog.rows.values()]


class BatchDialogTests(DialogBase):
    def patch_command(self):
        return patch.object(manager, '_appinstall_command',
                            return_value=str(self.stub))

    def test_each_file_gets_its_own_result(self):
        paths = [self.touch('a.AppImage'), self.touch('b.AppImage'),
                 self.touch('c.AppImage')]
        with self.patch_command():
            dialog = self.make_dialog(paths)
            self.wait_for(lambda: all(
                item.state == manager.BatchItem.INSTALLED
                for item in dialog.queue.items),
                message='queue did not finish')
        self.assertEqual(self.statuses(dialog),
                         ['Installed', 'Installed', 'Installed'])

    def test_failed_review_shows_exit_code(self):
        paths = [self.touch('a.AppImage'), self.touch('b.AppImage')]
        with self.patch_command():
            dialog = self.make_dialog(paths, stub_body='exit 3')
            self.wait_for(lambda: all(
                item.state in (manager.BatchItem.INSTALLED,
                               manager.BatchItem.FAILED)
                for item in dialog.queue.items),
                message='queue did not finish')
        self.assertEqual(self.statuses(dialog),
                         ['Failed (exit 3)', 'Failed (exit 3)'])

    def test_unsupported_file_gets_a_result_row_without_cancel(self):
        paths = [self.touch('keep.AppImage'), self.touch('notes.txt')]
        with self.patch_command():
            dialog = self.make_dialog(paths)
            self.wait_for(lambda: not dialog.queue.pending(),
                          message='queue did not finish')
        status, cancel = dialog.rows[1]
        self.assertEqual(status.text(), 'Unsupported type')
        self.assertFalse(cancel.isVisibleTo(dialog.rows[1][0].parentWidget()))
        self.assertEqual(dialog.rows[0][0].text(), 'Installed')

    def test_cancel_running_item_rest_keeps_going(self):
        paths = [self.touch('slow.AppImage'), self.touch('b.AppImage'),
                 self.touch('c.AppImage')]
        with self.patch_command():
            dialog = self.make_dialog(
                paths, stub_body='test "$APPINSTALL_BATCH" = 1 || exit 3; '
                                 'case "$2" in *slow*) exit 75;; esac; exit 0')
            self.wait_for(lambda: dialog.queue.items[0].state ==
                          manager.BatchItem.RUNNING,
                          message='first item never started')
            self.assertFalse(dialog.rows[0][1].isEnabled())
            self.wait_for(lambda: (
                dialog.queue.items[0].state == manager.BatchItem.CANCELLED and
                dialog.queue.items[1].state == manager.BatchItem.INSTALLED and
                dialog.queue.items[2].state == manager.BatchItem.INSTALLED),
                message='queue did not continue after cancel', timeout=12)
        self.assertEqual(self.statuses(dialog),
                         ['Cancelled', 'Installed', 'Installed'])

    def test_cancel_queued_item_skips_it(self):
        paths = [self.touch('slow.AppImage'), self.touch('b.AppImage'),
                 self.touch('queued.AppImage')]
        with self.patch_command():
            dialog = self.make_dialog(
                paths, stub_body='sleep 2; exit 0')
            self.wait_for(lambda: dialog.queue.items[0].state ==
                          manager.BatchItem.RUNNING,
                          message='first item never started')
            dialog._cancel(2)
            self.assertEqual(dialog.queue.items[2].state,
                             manager.BatchItem.CANCELLED)
            self.wait_for(lambda: (
                dialog.queue.items[1].state == manager.BatchItem.INSTALLED and
                not dialog.queue.pending()),
                message='queue did not finish around the cancel', timeout=12)
        self.assertEqual(self.statuses(dialog),
                         ['Installed', 'Installed', 'Cancelled'])

    def test_cancel_button_is_terminal_after_completion(self):
        paths = [self.touch('a.AppImage')]
        with self.patch_command():
            dialog = self.make_dialog(paths)
            self.wait_for(lambda: not dialog.queue.pending(),
                          message='item never finished')
        status, cancel = dialog.rows[0]
        self.assertEqual(status.text(), 'Installed')
        self.assertFalse(cancel.isEnabled())

    # ── Close-path regressions ──────────────────────────────────────────

    def test_close_waits_for_active_review(self):
        paths = [self.touch('active.AppImage')]
        with self.patch_command():
            dialog = self.make_dialog(paths, stub_body='sleep .2; exit 75')
            with patch.object(manager.QMessageBox, 'information') as notice:
                dialog.reject()
                notice.assert_called_once()
            self.assertTrue(dialog.isVisible())
            self.wait_for(lambda: not dialog.queue.pending())
            dialog.reject()
        self.assertFalse(dialog.isVisible())
        self.assertEqual(self.statuses(dialog), ['Cancelled'])

    def test_close_with_nothing_running_just_closes(self):
        """Closing after a review completed must not error or re-run."""
        paths = [self.touch('done.AppImage')]
        with self.patch_command():
            dialog = self.make_dialog(paths, stub_body='exit 0')
            self.wait_for(lambda: not dialog.queue.pending(),
                          message='item never finished')
            dialog.reject()
            self.wait_for(lambda: dialog.result() ==
                          QtWidgets.QDialog.DialogCode.Rejected,
                          message='dialog did not close')
        self.assertEqual(dialog.rows[0][0].text(), 'Installed')


class ManagerBatchCloseTests(DialogBase):
    """Close-path at ManagerWindow level: batch_dialog must be cleared."""

    def setUp(self):
        super().setUp()
        self.window = manager.ManagerWindow()
        self.wait_for(lambda: self.window.loader is not None and
                      not self.window.loader.isRunning())

    def tearDown(self):
        if self.window.batch_dialog is not None:
            self.window.batch_dialog.close()
        self.window.close()
        self.app.processEvents()
        super().tearDown()

    def patch_command(self):
        return patch.object(manager, '_appinstall_command',
                            return_value=str(self.stub))

    def test_close_clears_manager_batch_dialog(self):
        paths = [self.touch('active.AppImage')]
        with self.patch_command():
            dialog = self.window.open_batch(paths)
            self.wait_for(lambda: dialog.queue.items[0].state ==
                          manager.BatchItem.RUNNING,
                          message='review never started')
            self.assertIs(self.window.batch_dialog, dialog)
            with patch.object(manager.QMessageBox, 'information'):
                self.assertFalse(self.window.close())
            self.wait_for(lambda: not dialog.queue.pending())
            dialog.reject()
            self.wait_for(lambda: self.window.batch_dialog is None,
                          message='manager did not clear batch dialog')
        self.assertTrue(dialog.isHidden() or dialog.result() ==
                        QtWidgets.QDialog.DialogCode.Rejected)



class ManagerDropTests(DialogBase):
    def setUp(self):
        super().setUp()
        self.window = manager.ManagerWindow()
        self.wait_for(lambda: self.window.loader is not None and
                      not self.window.loader.isRunning())

    def tearDown(self):
        if self.window.batch_dialog is not None:
            self.window.batch_dialog.close()
        self.window.close()
        self.app.processEvents()
        super().tearDown()

    def patch_command(self):
        return patch.object(manager, '_appinstall_command',
                            return_value=str(self.stub))

    def mime_with(self, *paths):
        from qt_compat import QtCore
        data = QtCore.QMimeData()
        data.setUrls([QtCore.QUrl.fromLocalFile(path) for path in paths])
        return data

    def test_acceptable_only_for_supported_packages(self):
        supported = self.touch('game.AppImage')
        unsupported = self.touch('notes.txt')
        self.assertTrue(manager.ManagerWindow._acceptable(
            self.mime_with(supported)))
        self.assertFalse(manager.ManagerWindow._acceptable(
            self.mime_with(unsupported)))
        # A mixed drop is acceptable as a whole: the unsupported file still
        # gets its own result row inside the queue dialog.
        self.assertTrue(manager.ManagerWindow._acceptable(
            self.mime_with(supported, unsupported)))
        self.assertFalse(manager.ManagerWindow._acceptable(self.mime_with()))
        empty = self.mime_with()
        self.assertFalse(manager.ManagerWindow._acceptable(empty))

    def test_open_batch_creates_dialog_and_runs_queue(self):
        supported = self.touch('game.AppImage')
        with self.patch_command():
            dialog = self.window.open_batch([supported])
            self.assertIs(self.window.batch_dialog, dialog)
            self.wait_for(lambda: not dialog.queue.pending(),
                          message='batch never finished')
        self.assertEqual(self.statuses(dialog), ['Installed'])

    def test_open_batch_reuses_visible_dialog(self):
        first = self.touch('slow.AppImage')
        second = self.touch('next.AppImage')
        with self.patch_command():
            dialog = self.window.open_batch([first])
            self.wait_for(lambda: dialog.queue.items[0].state ==
                          manager.BatchItem.RUNNING,
                          message='first batch never started')
            again = self.window.open_batch([second])
            self.assertIs(again, dialog)
            self.assertEqual(len(dialog.queue.items), 2)
            self.wait_for(lambda: not dialog.queue.pending(),
                          message='second batch never finished')
        self.assertEqual(self.statuses(dialog), ['Installed', 'Installed'])

    def test_unsupported_only_drop_still_shows_rows(self):
        unsupported = self.touch('readme.txt')
        dialog = self.window.open_batch([unsupported])
        status, cancel = dialog.rows[0]
        self.assertEqual(status.text(), 'Unsupported type')
        self.assertFalse(dialog.queue.pending())


if __name__ == '__main__':
    unittest.main()
