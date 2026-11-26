#!/usr/bin/env python3
"""Transactional AppImage integration and menu launch support."""
import configparser
import errno
import json
import os
import re
import struct
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))


class PreviewUnavailable(RuntimeError):
    """The image cannot be inspected without executing it; refused passively."""


def desktop(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(path)
    return dict(parser['Desktop Entry'])


def quote(value):
    value = str(value).replace('\\', '\\\\\\\\')
    for char in ('"', '`', '$'):
        value = value.replace(char, '\\\\' + char)
    return '"' + value.replace('%', '%%') + '"'


def arguments(value):
    # Desktop Exec is never passed to a shell. Keep app options and file/URL fields.
    tokens = shlex.split(value)[1:]
    return [token for token in tokens if token not in ('%f', '%F', '%u', '%U', '%i', '%c', '%k')]


def app_name(value):
    return re.sub(r'\s*\(v?\d+(?:\.\d+)+(?:[^)]*)\)\s*$', '', value).strip()


def desktop_text(value):
    """One trusted desktop-entry line from potentially untrusted AppImage metadata.

    ConfigParser permits indented multiline values; copying those into a new
    desktop file can otherwise inject arbitrary keys such as Exec or Actions.
    """
    return ''.join(' ' if ord(char) < 32 or ord(char) == 127 else char
                   for char in str(value))


def safe_desktop_files(root):
    """Select metadata within the unpacked AppDir; ignore escaping symlinks."""
    base = root.resolve()
    def validated(candidates):
        result = []
        for entry in candidates:
            try:
                resolved = entry.resolve(strict=True)
                if resolved.is_relative_to(base) and resolved.is_file():
                    result.append(entry)
            except (OSError, RuntimeError):
                continue
        return result

    # A malicious top-level symlink must not prevent fallback to legitimate
    # metadata stored deeper in the image.
    return (validated(sorted(root.glob('*.desktop'))) or
            validated(sorted(root.rglob('*.desktop'))))


def categories(value):
    main = {'AudioVideo', 'Audio', 'Video', 'Development', 'Education', 'Game',
            'Graphics', 'Network', 'Office', 'Science', 'Settings', 'System', 'Utility'}
    items = [item for item in value.split(';') if re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*', item)]
    # Entertainment is not a freedesktop menu category; use the media category.
    items = ['AudioVideo' if item == 'Entertainment' else item for item in items]
    if not any(item in main for item in items):
        items.insert(0, 'Utility')
    return ';'.join(dict.fromkeys(items)) + ';'


def run(manifest, files):
    info = json.loads(Path(manifest).read_text())
    env = dict(os.environ, APPIMAGELAUNCHER_DISABLE='1')
    target = info['target']
    argv = [target] + info['args'] + files
    if info.get('fallback'):
        root = info['fallback']
        env.update(APPDIR=root, APPIMAGE=target)
        argv[0] = str(Path(root)/'AppRun')
        os.chdir(root)
    os.execvpe(argv[0], argv, env)


def squashfs_offset(path, limit=32 << 20):
    """Find a valid SquashFS header without executing the AppImage runtime.

    The ELF runtime can contain unrelated 'hsqs' or 'sqsh' byte sequences
    before the actual embedded filesystem. Validate the complete superblock
    instead of returning the first magic-byte match.
    """
    header_size = 96

    def valid(header, remaining):
        if len(header) < header_size:
            return False
        if header[:4] == b'hsqs':
            endian = '<'
        elif header[:4] == b'sqsh':
            endian = '>'
        else:
            return False
        inodes = struct.unpack_from(endian + 'I', header, 4)[0]
        block_size = struct.unpack_from(endian + 'I', header, 12)[0]
        compression = struct.unpack_from(endian + 'H', header, 20)[0]
        block_log = struct.unpack_from(endian + 'H', header, 22)[0]
        major, minor = struct.unpack_from(endian + 'HH', header, 28)
        bytes_used = struct.unpack_from(endian + 'Q', header, 40)[0]
        inode_table = struct.unpack_from(endian + 'Q', header, 64)[0]
        directory_table = struct.unpack_from(endian + 'Q', header, 72)[0]
        return (
            inodes > 0 and major == 4 and minor == 0 and
            1 <= compression <= 6 and
            4096 <= block_size <= 1048576 and
            block_size & (block_size - 1) == 0 and
            block_log == block_size.bit_length() - 1 and
            header_size <= bytes_used <= remaining and
            header_size <= inode_table <= bytes_used and
            header_size <= directory_table <= bytes_used
        )

    with open(path, 'rb') as file:
        size = os.fstat(file.fileno()).st_size
        scanned = 0
        overlap = b''
        while scanned < min(limit, size):
            chunk = file.read(min(65536, limit - scanned))
            if not chunk:
                break
            data = overlap + chunk
            base = scanned - len(overlap)
            for magic in (b'hsqs', b'sqsh'):
                start = 0
                while (index := data.find(magic, start)) != -1:
                    offset = base + index
                    if (offset + header_size <= size and
                            valid(data[index:index + header_size], size - offset)):
                        return offset
                    start = index + 1
            # Retain superblock candidates that cross chunk boundaries.
            overlap = data[-(header_size - 1):]
            scanned += len(chunk)
    return None


def preview_contents(executable, scratch):
    """Passive only: unpack via unsquashfs without running any code from the image.

    Raises PreviewUnavailable when the image cannot be inspected without
    executing its embedded runtime; callers decide how to proceed."""
    if not shutil.which('unsquashfs'):
        raise PreviewUnavailable('unsquashfs is not installed; the image can be reviewed passively only with squashfs-tools.')
    offset = squashfs_offset(executable)
    if offset is None:
        raise PreviewUnavailable('No squashfs payload was found in this AppImage.')
    root = scratch/'squashfs-root'
    result = subprocess.run(
        ['unsquashfs', '-no-progress', '-no-xattrs', '-d', str(root), '-o', str(offset), str(executable)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    if result.returncode or not root.is_dir():
        raise RuntimeError('Passive AppImage preview failed: '+result.stdout.decode(errors='replace')[-1500:])
    return root


def install(source, destination, fallback=False):
    source, destination = Path(source), Path(destination)
    data = Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))
    apps = data/'applications'
    state = data/'appinstall'
    destination.mkdir(parents=True, exist_ok=True)
    apps.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    if source.stat().st_size > shutil.disk_usage(destination).free:
        raise OSError(errno.ENOSPC, 'Not enough free space for the AppImage', str(destination))
    # Stage one copy on the destination filesystem, not a second full copy in /tmp.
    generation = Path(tempfile.mkdtemp(prefix='.appinstall-', dir=destination))
    ident = uuid.uuid4().hex
    entry = apps/f'appinstall-{ident}.desktop'
    manifest = state/f'{ident}.json'
    try:
        target = generation/source.name
        shutil.copyfile(source, target)
        target.chmod(0o755)
        scratch = generation/'.preview'
        scratch.mkdir()
        if fallback and not shutil.which('unsquashfs'):
            raise RuntimeError('Extracted launches require unsquashfs (squashfs-tools).')
        try:
            root = preview_contents(target, scratch)
        except (RuntimeError, subprocess.TimeoutExpired) as limitation:
            root = None
            print('Detailed preview unavailable: '+str(limitation), file=sys.stderr)
        entries = safe_desktop_files(root) if root else []
        original = next((p for p in entries if desktop(p).get('Type') == 'Application'), None)
        meta = desktop(original) if original else {}
        name = app_name(desktop_text(meta.get('Name', source.stem)))
        icon = 'package-x-generic'
        iconname = meta.get('Icon', '')
        if root is None:
            candidates = []
        elif iconname:
            candidates = [root/'.DirIcon'] + list(root.rglob(Path(iconname).name + '.*'))
        else:
            candidates = [root/'.DirIcon']
        for candidate in candidates:
            try:
                resolved = candidate.resolve(strict=True)
                if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
                    continue
                suffix = resolved.suffix.lower()
                if suffix not in ('.png', '.svg', '.xpm'):
                    continue
                installed_icon = generation/('icon' + suffix)
                shutil.copyfile(resolved, installed_icon)
                icon = str(installed_icon)
                # Self-registering apps often restore Icon=<themed name>.
                # Publish the icon there as well as keeping our absolute path.
                if re.fullmatch(r'[A-Za-z0-9_.-]+', iconname):
                    themed = data/'icons/hicolor'/('scalable' if suffix == '.svg' else '256x256')/'apps'
                    themed.mkdir(parents=True, exist_ok=True)
                    themed_icon = themed/(iconname+suffix)
                    # The themed namespace is shared with other apps.
                    # Never overwrite a pre-existing user icon or follow
                    # its symlink; our desktop launcher already uses the
                    # generation-owned absolute icon path.
                    if not themed_icon.exists() and not themed_icon.is_symlink():
                        shutil.copyfile(installed_icon, themed_icon)
                break
            except OSError:
                continue
        extracted = ''
        if fallback:
            if root is None:
                raise RuntimeError('Extracted launches require the image contents; unsquashfs could not read this AppImage.')
            extracted = str(generation/'appdir')
            shutil.move(str(root), extracted)
            if not (Path(extracted)/'AppRun').exists():
                raise RuntimeError('Extracted AppImage has no AppRun launcher.')
        shutil.rmtree(scratch)
        info = dict(target=str(target), desktop_exec=meta.get('Exec','AppRun'), working_directory=meta.get('Path',''), desktop_args=shlex.split(meta.get('Exec','AppRun'))[1:], args=arguments(meta.get('Exec','AppRun')), fallback=extracted, generation=str(generation))
        helper = Path(__file__).resolve()
        comment = desktop_text(meta.get('Comment', 'AppImage application' if root else 'AppImage application. Detailed preview unavailable; the image was not executed.'))
        lines = ['[Desktop Entry]', 'Type=Application', 'Name='+name,
                 'Comment='+comment,
                 'Icon='+icon, 'Terminal=false', 'Categories='+categories(meta.get('Categories', '')),
                 'Exec='+quote(sys.executable)+' '+quote(helper)+' --run '+quote(manifest)+' %U',
                 'X-AppInstall-Exec='+str(target), 'X-AppInstall-Manifest='+str(manifest)]
        startup_wm_class = meta.get('StartupWMClass', '')
        if startup_wm_class:
            lines.append('StartupWMClass='+desktop_text(startup_wm_class))
        lines.append('TryExec='+str(target))
        text = '\n'.join(lines)+'\n'
        # Only validated, fully staged artifacts are made visible.
        staged_manifest = manifest.with_suffix('.new')
        staged_manifest.write_text(json.dumps(info))
        staged_entry = entry.with_suffix('.new')
        staged_entry.write_text(text)
        staged_manifest.replace(manifest)
        try:
            staged_entry.replace(entry)
        except Exception:
            manifest.unlink(missing_ok=True)
            raise
    except Exception:
        shutil.rmtree(generation, ignore_errors=True)
        manifest.with_suffix('.new').unlink(missing_ok=True)
        entry.with_suffix('.new').unlink(missing_ok=True)
        raise
    import launch_monitor
    launch_monitor.wrap_appimage(entry, manifest)
    return entry

if __name__ == '__main__':
    try:
        if sys.argv[1] == '--run':
            import launch_monitor
            key='appimage:'+Path(sys.argv[2]).stem
            spec=launch_monitor.registry().get(key)
            if spec:launch_monitor.monitor(spec,sys.argv[3:])
            else:run(sys.argv[2], sys.argv[3:])
        else:
            print(install(sys.argv[1], sys.argv[2], '--extract' in sys.argv[3:]))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
