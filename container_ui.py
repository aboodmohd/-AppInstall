#!/usr/bin/env python3
"""Container workflow in the existing AppInstall interface."""
import json
from pathlib import Path
import sys
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QPlainTextEdit,QMessageBox,QInputDialog)
from container_backend import Engine, inspect_package, PROGRESS

class Job(QThread):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    def __init__(self, callback):
        super().__init__(); self.callback=callback
    def run(self):
        try:
            PROGRESS.set(self.progress.emit)
            self.done.emit(self.callback())
        except BaseException as error: self.failed.emit(str(error))

class Workflow(QDialog):
    def __init__(self,args):
        super().__init__(); self.args=args; self.engine=None; self.info=None; self.job=None; self.jobs=[]
        self.setWindowTitle('AppInstall'); self.resize(650,520)
        layout=QVBoxLayout(self); layout.setContentsMargins(24,24,24,24)
        header=QHBoxLayout(); self.icon=QLabel(); header.addWidget(self.icon)
        self.title=QLabel('Reading package…'); self.title.setTextFormat(Qt.PlainText); header.addWidget(self.title,1); layout.addLayout(header)
        self.description=QLabel(); self.description.setWordWrap(True); self.description.setTextFormat(Qt.PlainText); layout.addWidget(self.description)
        self.logs=QPlainTextEdit(); self.logs.setReadOnly(True); self.logs.setMaximumBlockCount(5000); layout.addWidget(self.logs)
        self.action=QPushButton('Continue'); self.action.setEnabled(False); self.action.clicked.connect(self.proceed); layout.addWidget(self.action)
        self.close_button=QPushButton('Close'); self.close_button.clicked.connect(self.reject); layout.addWidget(self.close_button)
        self.stage='preview'
        self.work(self.read,self.preview)
    def closeEvent(self,event):
        if self.job and self.job.isRunning(): event.ignore()
        else: event.accept()
    def reject(self):
        if not self.job or not self.job.isRunning(): super().reject()
    def work(self,callback,success):
        self.action.setEnabled(False); self.close_button.setEnabled(False)
        self.job=Job(callback); self.jobs.append(self.job); self.job.progress.connect(self.logs.appendPlainText); self.job.done.connect(success); self.job.failed.connect(self.failure)
        self.job.finished.connect(lambda:self.close_button.setEnabled(True)); self.job.start()
    def failure(self,message):
        self.logs.appendPlainText(message); self.description.setText('Operation failed. Review details below.'); self.action.setEnabled(False)
    def read(self):
        if self.args[0].startswith('--'):
            self.engine=Engine(); return self.engine.registry[self.args[1]]
        return inspect_package(self.args[0])
    def preview(self,info):
        self.info=info
        self.title.setText(info.get('application_name',info['name'])+' '+info['version'])
        self.icon.setPixmap((QIcon(info['icon']) if info.get('icon') else QIcon.fromTheme(info.get('icon_name') or 'package-x-generic')).pixmap(64,64))
        self.description.setText('Runs inside a '+('Debian' if info['kind']=='deb' else 'Fedora')+' container. Distrobox integrates with your home and desktop; it is not a security sandbox. Drivers, kernel modules and system services are unsupported.')
        self.logs.setPlainText(info['description']+'\n\nArchitecture: '+info['architecture']+'\nMaintainer: '+info.get('maintainer','')+'\nDependencies: '+info.get('dependencies',''))
        if self.args[0]=='--info':
            self.logs.appendPlainText(json.dumps(info,indent=2)); return
        if self.args[0]=='--remove': self.stage='remove'; self.action.setText('Uninstall')
        elif self.args[0]=='--launch': self.stage='launch'; self.action.setText('Open')
        else: self.action.setText('Prepare container and review transaction')
        self.action.setEnabled(True)
    def proceed(self):
        if self.stage=='preview':
            if QMessageBox.question(self,'AppInstall','Prepare or reuse the persistent container using its official image and repositories? First setup may download a large image and Distrobox integration dependencies.') != QMessageBox.Yes: return
            def prepare():
                self.engine=Engine(); return self.engine.transaction(self.info)
            self.description.setText('Preparing container and resolving dependencies…')
            self.work(prepare,self.transaction)
        elif self.stage=='transaction':
            self.description.setText('Installing package and dependencies in the container…')
            self.work(lambda:self.engine.install(self.info,lambda entries:self.selected),self.installed)
        elif self.stage=='remove':
            if QMessageBox.question(self,'Uninstall','Remove '+self.info['name']+' from its container and remove its managed menu entry? Application data will be kept.')==QMessageBox.Yes:
                self.work(lambda:self.engine.uninstall(self.args[1]),lambda _:self.finished_message('Uninstalled.'))
        elif self.stage=='launch':
            self.engine.launch(self.args[1]); self.finished_message('Launch requested. Application visibility is not automatically verified.'); QTimer.singleShot(3000,self.verify_launch)
        elif self.stage=='open':
            self.engine.launch(self.engine.key(self.info)); self.finished_message('Launch requested. Confirm the application window appears.'); QTimer.singleShot(3000,self.verify_launch)
    def transaction(self,text):
        self.logs.setPlainText(text)
        # Discover launchers in the package archive, before installing scripts.
        self.selected=None
        self.stage='transaction'; self.description.setText('Review the package transaction above. Install scripts run only after Install.'); self.action.setText('Install'); self.action.setEnabled(True)
        # Installed package launchers are chosen after installation through a second worker.
        self.action.clicked.disconnect(); self.action.clicked.connect(self.install_transaction)
    def install_transaction(self):
        self.description.setText('Installing in the container… Live progress appears below.')
        def choose(entries):
            # Worker returns candidates using a separate signal-driven selection below.
            return entries[0] if len(entries)==1 else None
        self.work(lambda:self.engine.install(self.info,choose),self.installed)
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
                self.work(export,self.installed); return
        self.action.clicked.disconnect(); self.action.clicked.connect(self.proceed)
        self.description.setText('Installed. '+('Find it in your application menu.' if record.get('exports') else 'No primary graphical launcher exported.'))
        self.stage='open'; self.action.setText('Open'); self.action.setEnabled(bool(record.get('exports')))
        self.logs.appendPlainText('Installation recorded. GUI launch has not been verified.')
    def verify_launch(self):
        verified=QMessageBox.question(self,'Verify launch','Did the application window open correctly?')==QMessageBox.Yes
        self.info['launch_verified']=verified
        self.engine.registry[self.engine.key(self.info)]=self.info; self.engine.save()
        self.description.setText('Launch verified by you.' if verified else 'Launch not verified. Check container compatibility and application requirements.')

    def finished_message(self,text):
        self.description.setText(text); self.action.setEnabled(False)

if __name__=='__main__':
    app=QApplication(sys.argv)
    window=Workflow(sys.argv[1:]); window.show(); sys.exit(app.exec())
