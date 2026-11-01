import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('containers',Path(__file__).resolve().parents[1]/'container_backend.py')
c=importlib.util.module_from_spec(spec); spec.loader.exec_module(c)

def tar(files):
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w:gz') as output:
        for name,data in files.items():
            entry=tarfile.TarInfo(name); entry.size=len(data); output.addfile(entry,io.BytesIO(data))
    return buf.getvalue()

def deb(arch='amd64',files=None):
    fields=f'Package: example\nVersion: 1.0\nArchitecture: {arch}\nDescription: Example app\nDepends: libc6\nMaintainer: Example\n'.encode()
    result=b'!<arch>\n'
    for name,data in [('debian-binary',b'2.0\n'),('control.tar.gz',tar({'./control':fields})),('data.tar.gz',tar(files or {'./usr/share/applications/example.desktop':b'[Desktop Entry]'}))]:
        header=f'{name+"/":<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(data):<10}`\n'.encode()
        result+=header+data+(b'\n' if len(data)%2 else b'')
    return result

def rpm():
    def header(fields):
        content=b''; index=b''
        for key,value in fields.items():
            index+=struct.pack('>IIII',key,6,len(content),1); content+=value.encode()+b'\0'
        return b'\x8e\xad\xe8\x01'+b'\0'*4+struct.pack('>II',len(fields),len(content))+index+content
    signature=header({}); signature+=b'\0'*((-len(signature))%8)
    return b'\xed\xab\xee\xdb'+b'\0'*92+signature+header({1000:'example',1001:'1',1002:'2',1022:'x86_64',1004:'Example',1005:'Description',1015:'Maintainer',1049:'libc'})

class ContainerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'XDG_DATA_HOME':str(self.root/'data'),'XDG_STATE_HOME':str(self.root/'state')}); self.env.start()
        self.arch=patch.object(c.platform,'machine',return_value='x86_64'); self.arch.start()
    def tearDown(self):
        self.arch.stop(); self.env.stop(); self.tmp.cleanup()
    def inspect(self,data,name='file with spaces; $.deb'):
        path=self.root/name; path.write_bytes(data); return c.inspect_package(path)
    def engine(self):
        with patch.object(c.os,'geteuid',return_value=1000):
            engine=c.Engine(); self.addCleanup(engine.close); return engine
    def test_deb_metadata_and_spaces(self):
        payload=deb(); info=self.inspect(payload); self.assertEqual(info['name'],'example'); self.assertEqual(info['dependencies'],'libc6')
        self.assertEqual(Path(info['file']).read_bytes(),payload); self.assertIn('spaces',info['source'])
    def test_deb_icon(self):
        info=self.inspect(deb(files={'./usr/share/pixmaps/example.png':b'icon'})); self.assertEqual(Path(info['icon']).read_bytes(),b'icon')
    def test_rpm_metadata(self):
        with patch.object(c,'archive',return_value=b'./usr/share/applications/example.desktop\n'):
            info=self.inspect(rpm(),'example.rpm')
        self.assertEqual(info['version'],'1-2'); self.assertEqual(info['maintainer'],'Maintainer')
    def test_invalid(self):
        for payload in (b'',b'!<arch>\ninvalid',deb()[:-50]):
            with self.assertRaises((ValueError,RuntimeError,StopIteration)): self.inspect(payload)
    def test_invalid_rpm(self):
        with self.assertRaises(ValueError): self.inspect(b'invalid','example.rpm')
    def test_architecture(self):
        with self.assertRaisesRegex(ValueError,'architecture'): self.inspect(deb('arm64'))
    def test_services_rejected(self):
        with self.assertRaisesRegex(ValueError,'System packages'):
            self.inspect(deb(files={'./usr/lib/systemd/system/example.service':b'service'}))
    def test_commented_repository_not_enabled(self):
        c.validate_apt_sources('# http://snapshot.debian.org/archive/example\nURIs: http://deb.debian.org/debian')
        with self.assertRaises(RuntimeError):
            c.validate_apt_sources('URIs: https://untrusted.example/repo')
    def test_theme_icon_metadata(self):
        info=self.inspect(deb(files={'./usr/share/applications/example.desktop':b'[Desktop Entry]\nName=Example\nIcon=accessories-character-map\n'}))
        self.assertEqual(info['icon_name'],'accessories-character-map')
    def test_private_home_and_readonly_staging(self):
        engine=self.engine(); info=self.inspect(deb())
        from subprocess import CompletedProcess
        with patch.object(c.shutil,'which',return_value='/usr/bin/tool'),patch.object(c,'command',side_effect=[b'true',b'']) as command,patch.object(c.subprocess,'run',return_value=CompletedProcess([],1)),patch.object(engine,'enter',return_value=b''):
            engine.ensure(info)
        create=command.call_args_list[1].args[0]
        self.assertIn('--home',create)
        self.assertTrue(create[create.index('--volume')+1].endswith(':ro'))
    def test_hidden_helper_launchers_are_excluded(self):
        engine=self.engine(); info=self.inspect(deb())
        visible='/usr/share/applications/visible.desktop'
        hidden='/usr/share/applications/helper.desktop'
        deleted='/usr/share/applications/deleted.desktop'
        def read(info,args):
            flag = 'NoDisplay=true\n' if args[1]==hidden else ('Hidden=true\n' if args[1]==deleted else '')
            return ('[Desktop Entry]\nType=Application\nName=Example\nExec=example\n'+flag).encode()
        with patch.object(engine,'enter',side_effect=read):
            self.assertEqual(engine.visible_entries(info,[hidden,visible,deleted]),[visible])
    def test_export_failure_records_repair_status(self):
        engine=self.engine(); info=self.inspect(deb())
        engine.registry['deb:example']=dict(info,status='installed',exports=[])
        with patch.object(engine,'_export',side_effect=RuntimeError('collision')),self.assertRaises(RuntimeError):
            engine.export(info,'/usr/share/applications/example.desktop')
        self.assertEqual(engine.registry['deb:example']['status'],'needs-repair')
    def test_non_http_repositories_are_not_silently_trusted(self):
        for source in ('deb file:/tmp/repo stable main','URIs: /tmp/local-repo','URIs: http://deb.debian.org/debian\n file:/tmp/repo'):
            with self.assertRaises(RuntimeError):c.validate_apt_sources(source)
    def test_selection(self):
        self.assertEqual(c.SPECS['deb'][0],'debian-apps'); self.assertEqual(c.SPECS['rpm'][0],'fedora-apps')
    def test_root_rejected(self):
        with patch.object(c.os,'geteuid',return_value=0),self.assertRaises(RuntimeError): c.Engine()
    def test_install_and_duplicate(self):
        engine=self.engine(); info=self.inspect(deb())
        def enter(info,args):
            if args[0]=='dpkg-query': return b'/usr/share/applications/example.desktop\n'
            return b''
        with patch.object(engine,'enter',side_effect=enter),patch.object(engine,'export',return_value=[{'path':'example.desktop','sha256':'hash'}]):
            engine.install(info,lambda items:items[0]); engine.install(info,lambda items:items[0])
        self.assertEqual(len(engine.registry),1); self.assertEqual(engine.registry['deb:example']['status'],'installed')
    def test_failure_and_interruption(self):
        for error in (RuntimeError('failure'),KeyboardInterrupt()):
            engine=self.engine(); info=self.inspect(deb())
            with patch.object(engine,'enter',side_effect=error),self.assertRaises(type(error)):
                engine.install(info,lambda items:None)
            self.assertEqual(json.loads(engine.file.read_text())['deb:example']['status'],'needs-repair')
            engine.close()
    def test_changed_file(self):
        engine=self.engine(); info=self.inspect(deb()); Path(info['file']).write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'changed'): engine.install(info,lambda _:None)
    def test_export_and_conflict(self):
        engine=self.engine(); info=self.inspect(deb()); apps=self.root/'data/applications'; apps.mkdir()
        target=apps/'debian-apps-example.desktop'
        def export(*args): target.write_text('[Desktop Entry]\nName=Example\n'); return b''
        with patch.object(engine,'enter',side_effect=export):
            exports=engine.export(info,'/usr/share/applications/example.desktop')
        self.assertEqual(exports[0]['path'],str(target))
        with self.assertRaisesRegex(RuntimeError,'unrelated'): engine.export(info,'/usr/share/applications/example.desktop')
    def test_uninstall_only_owned(self):
        engine=self.engine(); info=self.inspect(deb()); owned=self.root/'owned.desktop'; owned.write_bytes(b'owned')
        other=self.root/'other.desktop'; other.write_bytes(b'changed')
        import hashlib
        engine.registry['deb:example']=dict(info,exports=[dict(path=str(owned),sha256=hashlib.sha256(b'owned').hexdigest()),dict(path=str(other),sha256='old-hash')])
        with patch.object(engine,'enter',return_value=b''): engine.uninstall('deb:example')
        self.assertFalse(owned.exists()); self.assertTrue(other.exists()); self.assertFalse(engine.registry)
    def test_export_failure_rolls_back_launcher(self):
        engine=self.engine(); info=self.inspect(deb()); apps=self.root/'data/applications'; apps.mkdir()
        target=apps/'debian-apps-example.desktop'
        def fail(*args):
            target.write_text('partial export')
            raise RuntimeError('export failed')
        with patch.object(engine,'enter',side_effect=fail),self.assertRaises(RuntimeError):
            engine.export(info,'/usr/share/applications/example.desktop')
        self.assertFalse(target.exists())
    def test_interrupted_registry_recovery(self):
        engine=self.engine(); info=self.inspect(deb())
        engine.registry['deb:example']=dict(info,status='installing'); engine.save(); engine.close()
        recovered=self.engine()
        self.assertEqual(recovered.registry['deb:example']['status'],'needs-repair')

    def test_transaction_uses_container_only(self):
        engine=self.engine(); info=self.inspect(deb())
        with patch.object(engine,'ensure'),patch.object(engine,'enter',return_value=b'Package transaction') as enter:
            engine.transaction(info)
        self.assertIn('--simulate',enter.call_args.args[1]); self.assertEqual(enter.call_args.args[1][-1],info['file'])
