#!/usr/bin/env python3
"""Container workflow (deb/rpm via Distrobox) in the shared AppInstall interface."""
import json
from pathlib import Path
import sys
try:
    from qt_compat import QtCore, Signal, Slot
    QThread = QtCore.QThread
    Qt = QtCore.Qt
    QTimer = QtCore.QTimer
    from qt_compat import QtGui
    QIcon = QtGui.QIcon
    from qt_compat import QtWidgets
    QApplication = QtWidgets.QApplication
    QDialog = QtWidgets.QDialog
    QVBoxLayout = QtWidgets.QVBoxLayout
    QHBoxLayout = QtWidgets.QHBoxLayout
    QLabel = QtWidgets.QLabel
    QPushButton = QtWidgets.QPushButton
    QPlainTextEdit = QtWidgets.QPlainTextEdit
    QMessageBox = QtWidgets.QMessageBox
    QInputDialog = QtWidgets.QInputDialog
    QProgressBar = QtWidgets.QProgressBar
    QFrame = QtWidgets.QFrame
except ImportError as error:
    print('PySide6 or PyQt6 is required for the package workflow window: '+str(error), file=sys.stderr)
    sys.exit(3)
from container_backend import Engine, inspect_package, PROGRESS
import ui_style
import result_ui


def classify(message):
    """Map a raw failure line to a user-facing problem category."""
    text=message.lower()
    if text.startswith('missing required host tools:'): return 'Missing backend tools'
    if 'permission' in text or 'denied' in text: return 'Permission problem'
    if 'network' in text or 'curl' in text or 'http' in text or 'download' in text: return 'Network or repository problem'
    if 'no space' in text or 'disk' in text or 'full' in text: return 'Not enough storage'
    if 'container' in text or 'distrobox' in text or 'podman' in text: return 'Container setup problem'
    return 'Package or compatibility problem'


def failure_context(args, info):
    """Display package-validation failures separately from install/repair failures."""
    if info is not None:
        return info.get('name', 'Package'), None
    if args and args[0] and not args[0].startswith('--'):
        return Path(args[0]).name, 'Package validation failed'
    return 'Container operation', None


class Job(QThread):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    def __init__(self, callback, parent=None):
        # Keep the QThread wrapper owned by the GUI until the thread finishes.
        super().__init__(parent); self.callback=callback
    def run(self):
        # Do not retain a PySide6 bound signal emitter in this worker thread's
        # context after QThread finishes. That can outlive the QObject wrapper.
        token = PROGRESS.set(self.progress.emit)
        try:
            self.done.emit(self.callback())
        except BaseException as error:
            self.failed.emit(str(error))
        finally:
            PROGRESS.reset(token)


class Workflow(QDialog):
    def __init__(self,args,shot=None):
        super().__init__()
        # Destroy the dialog before QApplication teardown, not during Python
        # module cleanup (where stale PySide6 wrappers can segfault).
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.args=args; self.engine=None; self.info=None; self.job=None; self.jobs=[]
        self.shot=shot; self.retry_callback=None
        self.setWindowTitle('AppInstall'); self.setWindowIcon(QIcon.fromTheme('appinstall')); self.setMinimumWidth(640); self.resize(660,540)
        layout=QVBoxLayout(self); layout.setContentsMargins(26,24,24,20); layout.setSpacing(12)
        header=QHBoxLayout(); header.setSpacing(16)
        self.icon=QLabel(); self.icon.setFixedSize(72,72); self.icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        header.addWidget(self.icon)
        head=QVBoxLayout(); head.setSpacing(4)
        self.title=QLabel('Reading package…'); self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setStyleSheet('font-size: 20px; font-weight: 700;')
        head.addWidget(self.title)
        self.subtitle=QLabel('Checking the package before any change')
        self.subtitle.setTextFormat(Qt.TextFormat.PlainText)
        self.subtitle.setStyleSheet('color: palette(window-text);')
        head.addWidget(self.subtitle)
        header.addLayout(head,1); layout.addLayout(header)
        self.description=QLabel(); self.description.setWordWrap(True); self.description.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.description)
        status=QHBoxLayout(); status.setSpacing(12)
        self.stage_label=QLabel('')

        self.stage_label.setTextFormat(Qt.TextFormat.PlainText)
        self.stage_label.setStyleSheet('color: palette(window-text); font-weight: 600;')
        status.addWidget(self.stage_label,1)
        self.bar=QProgressBar(); self.bar.setRange(0,0); self.bar.setTextVisible(False)
        self.bar.setFixedWidth(200); status.addWidget(self.bar,0); self.bar.hide()
        layout.addLayout(status)
        self.logs=QPlainTextEdit(); self.logs.setReadOnly(True); self.logs.setMaximumBlockCount(5000)
        layout.addWidget(self.logs,1)
        line=QFrame(); line.setFrameShape(QFrame.Shape.HLine); layout.addWidget(line)
        buttons=QHBoxLayout(); buttons.setSpacing(10)
        diagnostics=QPushButton('Application &Diagnostics'); diagnostics.setObjectName('ghost')
        diagnostics.clicked.connect(lambda:__import__('subprocess').Popen([sys.executable,str(Path(__file__).with_name('diagnostics_ui.py'))]))
        buttons.addWidget(diagnostics); buttons.addStretch(1)
        self.close_button=QPushButton('&Close'); self.close_button.setObjectName('ghost')
        self.close_button.clicked.connect(self.reject); buttons.addWidget(self.close_button)
        self.action=QPushButton('&Continue'); self.action.setObjectName('primary')
        self.action.setDefault(True); self.action.setEnabled(False)
        self.action.clicked.connect(self.proceed); buttons.addWidget(self.action)
        layout.addLayout(buttons)
        self.setStyleSheet(ui_style.primary_button_stylesheet(self)+ui_style.ghost_button_stylesheet(self))
        self.stage='preview'
        self.work(self.read,self.preview,'Validating package')
    def closeEvent(self,event):
        if any(job.isRunning() for job in self.jobs): event.ignore()
        else: event.accept()
    def reject(self):
        if not any(job.isRunning() for job in self.jobs): super().reject()
    def work(self,callback,success,label=''):
        if self.job and self.job.isRunning(): return  # duplicate-click guard
        self.action.setEnabled(False); self.close_button.setEnabled(False)
        self.stage_label.setText(label); self.bar.show()
        self.retry_callback=callback if callback==self.read else None
        self.job=Job(callback, self); self.jobs.append(self.job)
        self.job.progress.connect(self.logs.appendPlainText); self.job.done.connect(success); self.job.failed.connect(self.failure)
        self.job.finished.connect(self._job_finished)
        self.job.start()
    @Slot()
    def _job_finished(self):
        # QThread.finished is delivered to this GUI-thread QObject. Release
        # callbacks (some capture this Workflow), drop completed workers and
        # defer their QObject deletion while the Qt event loop still runs.
        job=self.sender()
        if job is None: return
        job.callback=None
        if job in self.jobs: self.jobs.remove(job)
        if self.job is job: self.job=None
        self.bar.hide(); self.stage_label.setText(''); self.close_button.setEnabled(True)
        job.deleteLater()
    def failure(self,message):
        self.logs.appendPlainText(message)
        self.description.setText('Operation failed. Review the problem summary below.')
        name, headline = failure_context(self.args, self.info)
        result_ui.FailureDialog(name, classify(message), '', technical=message,
                                logs=self.logs.toPlainText(), retry=self.retry_callback,
                                headline=headline).exec()
        self.description.setText('Operation failed. Review details below.'); self.action.setEnabled(False)
    def read(self):
        if self.args[0]=='--info':
            return inspect_package(self.args[1])
        if self.args[0].startswith('--'):
            self.engine=Engine(); return self.engine.registry[self.args[1]]
        return inspect_package(self.args[0])
    def preview(self,info):
        self.info=info
        self.title.setText(info.get('application_name',info['name'])+' '+info['version'])
        self.subtitle.setText(('Debian package' if info['kind']=='deb' else 'RPM package')+' inside a '+
                              ('Debian' if info['kind']=='deb' else 'Fedora')+' container')
        self.icon.setPixmap((QIcon(info['icon']) if info.get('icon') else QIcon.fromTheme(info.get('icon_name') or 'package-x-generic')).pixmap(64,64))
        self.description.setText('Runs inside a '+('Debian' if info['kind']=='deb' else 'Fedora')+' container. Distrobox integrates with your home and desktop; it is not a security sandbox. Drivers, kernel modules and system services are unsupported.')
        self.logs.setPlainText(info['description']+'\n\nArchitecture: '+info['architecture']+'\nMaintainer: '+info.get('maintainer','')+'\nDependencies: '+info.get('dependencies',''))
        if self.args[0]=='--info':
            self.logs.appendPlainText(json.dumps(info,indent=2)); return
        if self.args[0]=='--remove': self.stage='remove'; self.action.setText('&Uninstall')
        elif self.args[0]=='--launch': self.stage='launch'; self.action.setText('&Open')
        else: self.action.setText('Prepare container and review transaction')
        self.action.setEnabled(True)
    def capture(self):
        if not self.shot: return
        self.grab().save(self.shot); QApplication.quit(); self.shot=None
    def proceed(self):
        if self.stage=='preview':
            if QMessageBox.question(self,'AppInstall','Prepare or reuse the persistent container using its official image and repositories? First setup may download a large image and Distrobox integration dependencies.') != QMessageBox.StandardButton.Yes: return
            def prepare():
                self.engine=Engine(); return self.engine.transaction(self.info)
            self.description.setText('Checking requirements and preparing the container…')
            self.work(prepare,self.transaction,'Checking requirements / preparing installation')
        elif self.stage=='transaction':
            self.description.setText('Installing package and dependencies in the container…')
            self.work(lambda:self.engine.install(self.info,lambda entries:self.selected),self.installed,'Installing application')
        elif self.stage=='remove':
            if QMessageBox.question(self,'Uninstall','Remove '+self.info['name']+' from its container and remove its managed menu entry? Application data will be kept.')==QMessageBox.StandardButton.Yes:
                self.work(lambda:self.engine.uninstall(self.args[1]),lambda _:self.finished_message('Uninstalled.'),'Removing application')
        elif self.stage=='launch':
            self.engine.launch(self.args[1]); self.finished_message('Launch requested. Application visibility is not automatically verified.'); QTimer.singleShot(3000,self.verify_launch)
        elif self.stage=='open':
            self.engine.launch(self.engine.key(self.info)); self.finished_message('Launch requested. Confirm the application window appears.'); QTimer.singleShot(3000,self.verify_launch)
    def transaction(self,text):
        self.logs.setPlainText(text)
        self.selected=None
        self.stage='transaction'; self.description.setText('Review the package transaction above. Install scripts run only after Install.'); self.action.setText('&Install'); self.action.setEnabled(True)
        self.action.clicked.disconnect(); self.action.clicked.connect(self.install_transaction)
    def install_transaction(self):
        self.description.setText('Installing in the container… Live progress appears below.')
        def choose(entries):
            return entries[0] if len(entries)==1 else None
        self.work(lambda:self.engine.install(self.info,choose),self.installed,'Installing application')
    def installed(self,record):
        if not record: return
        self.info=record
        if len(record.get('candidates',[]))>1 and not record.get('exports'):
            selected,ok=QInputDialog.getItem(self,'Choose application','Select the primary application to add to your menu:',record['candidates'],0,False)
            if ok:
                def export():
                    exports=self.engine.export(record,selected)
                    record.update(desktop=selected,exports=exports)
                    self.engine.registry[self.engine.key(record)]=record; self.engine.save()
                    return record
                self.work(export,self.installed,'Creating desktop launcher'); return
        self.action.clicked.disconnect(); self.action.clicked.connect(self.proceed)
        self.description.setText('Installed. '+('Find it in your application menu.' if record.get('exports') else 'No primary graphical launcher exported.'))
        self.stage='open'; self.action.setText('&Open'); self.action.setEnabled(bool(record.get('exports')))
        self.logs.appendPlainText('Installation recorded. GUI launch has not been verified.')
        if self.shot: QTimer.singleShot(350,self.capture)
        else:
            # Never capture the Qt Workflow in a nested modal button's
            # Python callback. The QObject may be torn down while that
            # signal/lambda is retained by PySide6 until interpreter exit.
            # Capture the plain-Python backend and immutable key instead.
            engine=self.engine
            app_key=engine.key(record) if record.get('exports') else None
            open_app=(lambda: engine.launch(app_key)) if app_key is not None else None
            result_ui.SuccessDialog(record.get('application_name',record['name'])+' '+record['version'],
                                    'Installed in its '+('Debian' if record['kind']=='deb' else 'Fedora')+' container.',
                                    open_app).exec()
    def verify_launch(self):
        verified=QMessageBox.question(self,'Verify launch','Did the application window open correctly?')==QMessageBox.StandardButton.Yes
        self.info['launch_verified']=verified
        self.engine.registry[self.engine.key(self.info)]=self.info; self.engine.save()
        self.description.setText('Launch verified by you.' if verified else 'Launch not verified. Check container compatibility and application requirements.')

    def finished_message(self,text):
        self.description.setText(text); self.action.setEnabled(False)

if __name__=='__main__':
    args=sys.argv[1:]
    if '--screenshot' in args:
        index=args.index('--screenshot'); shot=args[index+1] if index+1<len(args) else None
        args=args[:index]+args[index+2:]
    else: shot=None
    app=QApplication(sys.argv[:1]); ui_style.maybe_dark(app)
    app.setWindowIcon(QIcon.fromTheme('appinstall'))
    window=Workflow(args,shot); window.show()
    if shot:
        QTimer.singleShot(600, lambda: (window.grab().save(shot), QApplication.quit()))
    sys.exit(app.exec())
