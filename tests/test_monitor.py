import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import launch_monitor as m
import diagnostics_core as core
import runtime_probe as probe

class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.environment=patch.dict(os.environ,{'XDG_DATA_HOME':str(self.root/'data'),'XDG_STATE_HOME':str(self.root/'state')})
        self.environment.start()
    def tearDown(self):self.environment.stop();self.temp.cleanup()
    def spec(self,script="pass",key='test:example'):
        path=self.root/'example.desktop'
        path.write_text('[Desktop Entry]\nType=Application\nName=Example\nIcon=example\nCategories=Development;\nExec='+m.desktop_quote(sys.executable)+' -c '+m.desktop_quote(script)+' %U\n')
        return m.wrap_desktop(key,path,'test')
    def launch(self,script,**kwargs):return m.monitor(self.spec(script),notify=False,startup=.5,**kwargs)
    def test_freebuff_missing_library(self):
        result=self.launch("import sys;print('freebuff: error while loading shared libraries: libasound.so.2: cannot open shared object file',flush=True);sys.exit(127)")
        self.assertEqual(result['error']['category'],'dependency')
        self.assertEqual(result['error']['libraries'],['libasound.so.2'])
        self.assertEqual(result['exit_code'],127)
    def test_opencode_port_conflict(self):
        result=self.launch("import sys;print('Error: Managed service port 49374 on 127.0.0.1 is already in use by another process',flush=True);sys.exit(1)")
        self.assertEqual(result['error']['category'],'port');self.assertEqual(result['error']['port'],49374)
    def test_opencode_invalid_command(self):
        spec=self.spec();spec['command']='"broken';result=m.monitor(spec,notify=False)
        self.assertEqual(result['error']['category'],'launcher')
    def test_missing_executable(self):
        spec=self.spec();spec['command']='/not/a/real/application';result=m.monitor(spec,notify=False)
        self.assertEqual(result['error']['category'],'executable')
    def test_missing_desktop(self):
        spec=self.spec();Path(spec['desktop']).unlink();result=m.monitor(spec,notify=False)
        self.assertEqual(result['error']['category'],'launcher')
    def test_container_start_failure(self):
        spec=self.spec();spec.update(format='deb',container='missing',command='distrobox-enter -n missing -- example')
        with patch.object(m.shutil,'which',return_value='/usr/bin/tool'),patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],1)):
            result=m.monitor(spec,notify=False)
        self.assertEqual(result['error']['category'],'container')
    def test_immediate_crash(self):
        result=self.launch('import sys;sys.exit(42)')
        self.assertEqual(result['error']['category'],'crash');self.assertEqual(result['exit_code'],42)
    def test_clean_exit_is_not_failure(self):
        result=self.launch('pass')
        self.assertIsNone(result['error']);self.assertEqual(result['status'],'detached_or_exited_unverified')
    def test_background_child_is_not_failure(self):
        script="import subprocess,sys;subprocess.Popen([sys.executable,'-c','import time;time.sleep(.2)'])"
        result=self.launch(script)
        self.assertIsNone(result['error'])
    def test_surviving_process_not_assumed_usable(self):
        result=self.launch('import time;time.sleep(.65)')
        self.assertIsNone(result['error']);self.assertNotEqual(result['status'],'verified')
    def test_special_character_quoting_roundtrip(self):
        spec=self.spec()
        for value in ['/tmp/a b','/tmp/a "quote"','/tmp/a $dollar','/tmp/a `tick`','/tmp/a \\ slash','/tmp/a % percent','first\nsecond','a\tb']:
            self.assertEqual(m.expand_exec(m.desktop_quote(value),[],spec),[value])
    def test_appimage_environment_and_field_codes_preserved(self):
        manifest=self.root/'app.json';target=str(self.root/'a b.AppImage')
        manifest.write_text(json.dumps(dict(target=target,args=['LEGACY=ignored'],generation=str(self.root),desktop_exec='env APP_EXAMPLE="two words" AppRun --flag %U',working_directory=str(self.root))))
        path=self.root/'image.desktop';path.write_text('[Desktop Entry]\nName=Image\nExec=true\n')
        spec=m.wrap_appimage(path,manifest)
        self.assertEqual(m.expand_exec(spec['command'],['https://example.test'],spec),['env','APP_EXAMPLE=two words',target,'--flag','https://example.test'])
        self.assertEqual(spec['cwd'],str(self.root))
    def test_field_codes_and_spaces(self):
        spec=self.spec()
        spec['name']='Example App';spec['icon']='example';spec['source_desktop']='/a b/example.desktop'
        argv=m.expand_exec('env NAME="two words" "/opt/a b/app" --literal=%% %F %i %c %k',['file:///tmp/a%20b'],spec)
        self.assertEqual(argv,['env','NAME=two words','/opt/a b/app','--literal=%','/tmp/a b','--icon','example','Example App','/a b/example.desktop'])
    def test_working_directory_and_environment(self):
        script='import os;print(os.getcwd());print(os.environ["EXAMPLE_VAR"])'
        spec=self.spec(script);spec['cwd']=str(self.root);spec['command']='env EXAMPLE_VAR=hello '+spec['command']
        result=m.monitor(spec,notify=False,startup=.5)
        text=Path(result['log']).read_text();self.assertIn(str(self.root),text);self.assertIn('hello',text)
    def test_desktop_actions_and_metadata_preserved(self):
        path=self.root/'a.desktop';path.write_text('[Desktop Entry]\nType=Application\nName=Example\nIcon=example\nCategories=Development;\nExec=true %U\nPath=/missing\nTryExec=/missing\nActions=New;\n[Desktop Action New]\nName=New\nExec=true --new %u\n')
        spec=m.wrap_desktop('test:actions',path,'test')
        text=path.read_text();self.assertIn('Categories=Development;',text);self.assertIn('--action',text)
        self.assertEqual(spec['cwd'],'/missing');self.assertIn('TryExec=/missing',text);self.assertEqual(spec['actions']['New'],'true --new %u')

    def test_upgrade_skips_stale_appimage_manifest_without_deleting_launcher(self):
        apps = m.data_root().parent / 'applications'
        apps.mkdir(parents=True)
        stale = apps / 'old-image.desktop'
        missing = m.data_root() / 'missing-manifest.json'
        original = ('[Desktop Entry]\nType=Application\nName=Old Image\n'
                    'Exec=/old/image.AppImage\nX-AppInstall-Manifest='+str(missing)+'\n')
        stale.write_text(original)
        messages = m.synchronize()
        self.assertEqual(stale.read_text(), original)
        self.assertFalse(missing.exists())
        self.assertEqual(m.registry(), {})
        self.assertEqual(len(messages), 1)
        self.assertIn('Skipped stale AppInstall launcher', messages[0])
        self.assertIn('No files were removed', messages[0])

    def test_reinstall_one_record(self):
        spec=self.spec();m.wrap_desktop(spec['key'],spec['desktop'],'test')
        self.assertEqual(len(m.registry()),1);self.assertEqual(len(list(self.root.glob('*.desktop'))),1)
    def test_launcher_repair_and_unrelated_protection(self):
        spec=self.spec();path=Path(spec['desktop']);path.unlink();core.repair_launcher(spec['key']);self.assertTrue(path.exists())
        path.write_text('[Desktop Entry]\nName=Other\nExec=true\n')
        with self.assertRaises(RuntimeError):core.repair_launcher(spec['key'])
        self.assertIn('Name=Other',path.read_text())
    def test_modified_managed_launcher_is_not_overwritten(self):
        spec=self.spec();path=Path(spec['desktop'])
        changed=path.read_text().replace('Name=Example','Name=User Changed Name');path.write_text(changed)
        with self.assertRaises(RuntimeError):core.repair_launcher(spec['key'])
        self.assertEqual(path.read_text(),changed)
    def test_unknown_dependency_has_no_automatic_repair(self):
        spec=self.spec();self.assertEqual(core.library_packages(spec['key']),[])
        with self.assertRaises(RuntimeError):core.dependency_plan(spec['key'])
    def dependency_failure(self):
        spec=self.spec(key='deb:example');spec.update(format='deb',container='debian-apps');m.update_registry(spec['key'],spec)
        attempt=m.new_attempt(spec);attempt.update(status='failed',error=m.failure('dependency','missing',libraries=['libasound.so.2']))
        m.atomic_json(attempt['file'],attempt);return spec
    def test_known_dependency_plan_and_explicit_repair(self):
        import container_backend
        from unittest.mock import MagicMock
        spec=self.dependency_failure();engine=MagicMock();engine.registry={'deb:example':dict(name='example',kind='deb',container='debian-apps')}
        engine.enter.return_value=b'Install official Debian libasound2t64'
        with patch.object(container_backend,'Engine',return_value=engine),patch.object(core,'start_container'):
            plan=core.dependency_plan(spec['key'])
            self.assertEqual(plan['packages'],['libasound2t64'])
            self.assertIn('--simulate',engine.enter.call_args.args[1])
            core.install_repair(spec['key'],plan)
            args=engine.enter.call_args.args[1]
            self.assertEqual(args[:2],['sudo','apt-get']);self.assertIn('--no-remove',args);self.assertEqual(args[-1],'libasound2t64')
    def test_changed_repair_evidence_rejected(self):
        spec=self.dependency_failure()
        with self.assertRaises(RuntimeError):core.install_repair(spec['key'],dict(packages=['untrusted-package'],format='deb'))
    def test_retry_container_does_not_create_or_elevate(self):
        spec=self.spec();spec['container']='debian-apps';m.update_registry(spec['key'],spec)
        with patch.object(m,'checked',return_value='') as checked:core.start_container(spec['key'])
        calls=[call.args[0] for call in checked.call_args_list]
        self.assertEqual(calls[0],['podman','container','exists','debian-apps'])
        self.assertNotIn('sudo',calls[1]);self.assertNotIn('create',calls[1])
    def test_reexport_uses_recorded_desktop(self):
        import container_backend
        from unittest.mock import MagicMock
        spec=self.spec();spec.update(format='deb',container='debian-apps');m.update_registry(spec['key'],spec)
        engine=MagicMock();info={'desktop':'/usr/share/applications/example.desktop'};engine.registry={spec['key']:info};engine.export.return_value=[]
        with patch.object(container_backend,'Engine',return_value=engine),patch.object(core,'start_container'):
            core.reexport(spec['key'])
        engine.export.assert_called_once_with(info,info['desktop'])
    def test_privacy_and_size(self):
        path=self.root/'output.log';log=m.SafeLog(path,['opaque-secret-value'])
        log.add('password="hello world" Authorization: Bearer abc123 https://x.test/?code=secret opaque-secret-value')
        text=path.read_text();self.assertNotIn('hello world',text);self.assertNotIn('abc123',text);self.assertNotIn('opaque-secret-value',text);self.assertNotIn('code=secret',text)
        log.add('a'*(m.LOG_BYTES*2));self.assertLessEqual(path.stat().st_size,m.LOG_BYTES)
        self.assertEqual(path.stat().st_mode&0o777,0o600)
    def test_environment_secret_redaction(self):
        with patch.dict(os.environ,{'EXAMPLE_API_TOKEN':'random-sensitive-value'}):
            result=self.launch('import os;print(os.environ["EXAMPLE_API_TOKEN"])')
        self.assertNotIn('random-sensitive-value',Path(result['log']).read_text())
    def test_error_notification_delivery(self):
        spec=self.spec();attempt=m.new_attempt(spec);attempt['error']=m.failure('crash','The application exited unexpectedly.')
        with patch.object(m.shutil,'which',return_value='/usr/bin/notify-send'),patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run,patch.object(m.subprocess,'Popen') as popen:
            self.assertTrue(m.deliver_error(spec,attempt));self.assertIn('AppInstall launch failed',run.call_args.args[0]);self.assertTrue(popen.called)
    def test_history_is_ordered_by_launch_time_not_last_write(self):
        spec=self.spec();old=m.new_attempt(spec);new=m.new_attempt(spec)
        old['status']='exited_after_startup_unverified';m.atomic_json(old['file'],old)
        self.assertEqual(m.latest(spec['key'])['id'],new['id'])
    def test_rollback_restores_only_unmodified_managed_launchers(self):
        first=self.spec(key='test:first');second_path=self.root/'second.desktop'
        second_path.write_text('[Desktop Entry]\nName=Second\nExec=true\n')
        second=m.wrap_desktop('test:second',second_path,'test')
        changed=second_path.read_text().replace('Name=Second','Name=Modified');second_path.write_text(changed)
        result=m.restore_launchers()
        self.assertIn('Example',result['restored']);self.assertEqual(Path(first['desktop']).read_text(),first['original_text'])
        self.assertEqual(second_path.read_text(),changed);self.assertIn('test:second',m.registry())
    def test_documented_busy_port_is_observed_without_false_failure(self):
        spec=self.spec();spec['documented_ports']=[4096]
        with patch.object(m,'checked',return_value='State Local Address\nLISTEN 127.0.0.1:4096'),patch.object(m.shutil,'which',return_value='/usr/bin/ss'):
            notes=m.port_observations(spec)
        self.assertIn('4096',notes[0]);self.assertIn('no conflict is assumed',notes[0])
    def test_library_permission_error_is_not_a_missing_package(self):
        error=m.classify('error while loading shared libraries: libasound.so.2: Permission denied',127)
        self.assertEqual(error['category'],'permission');self.assertNotIn('libraries',error)
    def test_history_limit(self):
        spec=self.spec()
        for _ in range(m.HISTORY+3):m.new_attempt(spec)
        self.assertEqual(len(list((m.state_root()/'launches').rglob('*.json'))),m.HISTORY)
    def test_architecture_probe(self):
        file=self.root/'wrong';data=bytearray(64);data[:4]=b'\x7fELF';data[5]=1;data[18:20]=(183).to_bytes(2,'little');file.write_bytes(data);file.chmod(0o755)
        with patch.object(probe.platform,'machine',return_value='x86_64'):
            self.assertEqual(probe.inspect_runtime(dict(argv=[str(file)]))['category'],'architecture')
    def test_permission_probe(self):
        file=self.root/'not-executable';file.write_text('test');file.chmod(0o600)
        self.assertEqual(probe.inspect_runtime(dict(argv=[str(file)]))['category'],'permission')
    def test_required_environment_probe(self):
        self.assertEqual(probe.inspect_runtime(dict(argv=[sys.executable],required_env=['APPINSTALL_DEFINITELY_UNSET']))['category'],'environment')

if __name__=='__main__':unittest.main()
