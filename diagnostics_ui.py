#!/usr/bin/env python3
"""Application Diagnostics and launch-error windows within AppInstall."""
import json
from pathlib import Path
import subprocess
import sys
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (QApplication,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
                              QPlainTextEdit,QTableWidget,QTableWidgetItem,QMessageBox,QFileDialog,QInputDialog)
import launch_monitor as monitor
import diagnostics_core as core


class Task(QThread):
    done=Signal(object);failed=Signal(str)
    def __init__(self,callback):super().__init__();self.callback=callback
    def run(self):
        try:self.done.emit(self.callback())
        except Exception as error:self.failed.emit(monitor.redact(str(error)))


class LogWindow(QDialog):
    def __init__(self,path,parent=None):
        super().__init__(parent);self.setWindowTitle('AppInstall — Diagnostic Logs');self.resize(760,500)
        layout=QVBoxLayout(self);text=QPlainTextEdit();text.setReadOnly(True)
        try:content=Path(path).read_bytes()[-monitor.LOG_BYTES:].decode(errors='replace')
        except OSError:content='The log file is not available.'
        text.setPlainText(content);layout.addWidget(text)
        copy=QPushButton('Copy Logs');copy.clicked.connect(lambda:QApplication.clipboard().setText(content));layout.addWidget(copy)
        close=QPushButton('Close');close.clicked.connect(self.accept);layout.addWidget(close)


class FailureWindow(QDialog):
    def __init__(self,attempt):
        super().__init__();self.attempt=attempt;self.setWindowTitle('AppInstall — Launch Failed');self.resize(640,420)
        try:spec=monitor.registry().get(attempt['key'],dict(name=attempt['name']))
        except (OSError,ValueError):spec=dict(name=attempt['name'])
        text=monitor.error_text(spec,attempt['error'])
        self.details=text+'\n\n'+attempt.get('technical','')+'\n\nLog: '+attempt['log']
        layout=QVBoxLayout(self)
        title=QLabel(attempt['name']+' could not start');title.setTextFormat(Qt.PlainText);font=title.font();font.setPointSize(17);font.setBold(True);title.setFont(font);layout.addWidget(title)
        body=QPlainTextEdit();body.setReadOnly(True);body.setPlainText(self.details);layout.addWidget(body)
        row=QHBoxLayout()
        for name,callback in [('View Logs',self.logs),('Copy Error Details',lambda:QApplication.clipboard().setText(self.details)),('Application Diagnostics',self.diagnostics)]:
            button=QPushButton(name);button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row)
        close=QPushButton('Close');close.clicked.connect(self.accept);layout.addWidget(close)
    def logs(self):LogWindow(self.attempt['log'],self).exec()
    def diagnostics(self):
        self.manager=Diagnostics();self.manager.show()


class Diagnostics(QDialog):
    def __init__(self):
        super().__init__();self.setWindowTitle('AppInstall — Application Diagnostics');self.resize(1000,650)
        self.records=[];self.jobs=[];self.busy=False
        layout=QVBoxLayout(self)
        heading=QLabel('Application Diagnostics');font=heading.font();font.setPointSize(20);heading.setFont(font);layout.addWidget(heading)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['Application','Format','Container','Last launch','Last detected error'])
        self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection);self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.details);layout.addWidget(self.table)
        self.text=QPlainTextEdit();self.text.setReadOnly(True);self.text.setMaximumHeight(170);layout.addWidget(self.text)
        self.buttons={};row=QHBoxLayout()
        for label,callback in [('Open',self.launch),('View Logs',self.logs),('Repair Launcher',self.repair),('Re-export',self.reexport),('Retry Container',self.container),('Repair Dependency',self.dependency),('Port Owner',self.port),('Uninstall',self.uninstall)]:
            button=QPushButton(label);button.clicked.connect(callback);self.buttons[label]=button;row.addWidget(button)
        layout.addLayout(row)
        footer=QHBoxLayout()
        for label,callback in [('Install File',self.install_file),('Refresh',self.refresh),('Close',self.accept)]:
            button=QPushButton(label);button.clicked.connect(callback);footer.addWidget(button)
        layout.addLayout(footer)
        self.refresh();self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(3000)
    def selected(self):
        selected=self.table.selectionModel().selectedRows()
        row=selected[0].row() if selected else self.table.currentRow()
        return self.records[row] if 0<=row<len(self.records) else None
    def refresh(self):
        if self.busy:return
        selected=self.selected();key=selected['key'] if selected else None
        self.records=core.applications();self.table.blockSignals(True);self.table.setRowCount(len(self.records))
        row=0
        for index,record in enumerate(self.records):
            last=record.get('last') or {};error=(record.get('last_error') or {}).get('error') or {}
            values=[record['name'],record['format'].upper(),record.get('container','—'),last.get('started','Never'),error.get('detail','None detected')]
            for column,value in enumerate(values):self.table.setItem(index,column,QTableWidgetItem(str(value)))
            if record['key']==key:row=index
        if self.records:self.table.selectRow(row)
        self.table.resizeColumnsToContents();self.table.blockSignals(False);self.details()
    def details(self):
        record=self.selected()
        for button in self.buttons.values():button.setEnabled(bool(record) and not self.busy)
        if not record:self.text.setPlainText('No AppInstall-managed applications have been registered yet. Install a file or refresh after migration.');return
        last=record.get('last') or {};error=last.get('error') or {}
        self.text.setPlainText(record['name']+'\nManaged launcher: '+record['desktop']+'\nLast status: '+last.get('status','Never launched')+'\n'+error.get('detail','No detected launch error. Running or detached does not prove the application is usable.')+'\n'+('Logs: '+last['log'] if last.get('log') else 'No launch logs yet.'))
        self.buttons['Uninstall'].setEnabled(record['format'] in ('deb','rpm','appimage','flatpak') and not self.busy)
        self.buttons['View Logs'].setEnabled(bool(last.get('log')) and not self.busy)
        for label in ('Re-export','Retry Container'):self.buttons[label].setEnabled(bool(record.get('container')) and not self.busy)
        self.buttons['Repair Dependency'].setEnabled(bool(core.library_packages(record['key'])) and not self.busy)
        self.buttons['Port Owner'].setEnabled(bool(error.get('port')) and not self.busy)
    def run_task(self,callback,done=None):
        self.busy=True;self.details();job=Task(callback);self.jobs.append(job)
        def success(value):
            self.busy=False
            if done:done(value)
            elif value:QMessageBox.information(self,'AppInstall',str(value))
            self.refresh()
        def failure(message):self.busy=False;QMessageBox.warning(self,'AppInstall',message);self.refresh()
        job.done.connect(success);job.failed.connect(failure);job.start()
    def confirm(self,message):return QMessageBox.question(self,'AppInstall',message)==QMessageBox.Yes
    def launch(self):
        if self.selected():core.open_application(self.selected()['key'])
    def logs(self):
        record=self.selected()
        if record and record.get('last'):
            attempts=record.get('history',[record['last']])
            selected=attempts[0]
            if len(attempts)>1:
                choices=[item['started']+' — '+item['status'] for item in attempts]
                choice,ok=QInputDialog.getItem(self,'Launch Logs','Choose a launch attempt:',choices,0,False)
                if not ok:return
                selected=attempts[choices.index(choice)]
            LogWindow(selected['log'],self).exec()
    def repair(self):
        record=self.selected()
        if record and self.confirm('Recreate this managed launcher? A launcher changed outside AppInstall will be preserved.'):
            self.run_task(lambda:core.repair_launcher(record['key']))
    def reexport(self):
        record=self.selected()
        if record and self.confirm('Re-export this application using Distrobox? Unrelated or modified launchers will be preserved.'):
            self.run_task(lambda:core.reexport(record['key']))
    def container(self):
        record=self.selected()
        if record and self.confirm('Retry starting the existing '+record['container']+' container? No container will be created or deleted.'):
            self.run_task(lambda:core.start_container(record['key']))
    def dependency(self):
        record=self.selected()
        if not record:return
        key=record['key']
        def review(plan):
            dialog=QDialog(self);dialog.setWindowTitle('Review Dependency Repair');dialog.resize(700,500)
            layout=QVBoxLayout(dialog);label=QLabel('Install '+', '.join(plan['packages'])+' inside '+record['container']+'?');label.setTextFormat(Qt.PlainText);layout.addWidget(label)
            text=QPlainTextEdit();text.setReadOnly(True);text.setPlainText(plan['text']);layout.addWidget(text)
            yes=QPushButton('Install Approved Repair');yes.clicked.connect(dialog.accept);layout.addWidget(yes)
            no=QPushButton('Cancel');no.clicked.connect(dialog.reject);layout.addWidget(no)
            if dialog.exec()==QDialog.Accepted:self.run_task(lambda:core.install_repair(key,plan))
        self.run_task(lambda:core.dependency_plan(key),review)
    def port(self):
        record=self.selected()
        if record:self.run_task(lambda:core.port_owner(record['key']))
    def uninstall(self):
        record=self.selected()
        if record and self.confirm('Uninstall '+record['name']+' and its managed launcher? Personal application data and logs will be kept.'):
            self.run_task(lambda:core.uninstall(record['key']))
    def install_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Install Application',str(Path.home()/'Downloads'),'Applications (*.AppImage *.appimage *.flatpak *.flatpakref *.flatpakrepo *.deb *.rpm)')
        if path:
            local=Path(__file__).with_name('appinstall');command=str(local) if local.exists() else str(Path.home()/'.local/bin/appinstall')
            subprocess.Popen([command,path])
    def closeEvent(self,event):
        if self.busy:event.ignore()
        else:event.accept()
    def reject(self):
        if not self.busy:super().reject()


if __name__=='__main__':
    app=QApplication(sys.argv)
    if len(sys.argv)>2 and sys.argv[1]=='--error':
        window=FailureWindow(json.loads(Path(sys.argv[2]).read_text()))
    else:window=Diagnostics()
    window.show();sys.exit(app.exec())
