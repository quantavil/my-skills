#!/usr/bin/env python3
"""Read-only APK/IPA/AAB ZIP inventory; Python standard library only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import stat
import sys
import zipfile
from xml.parsers.expat import ExpatError

TOOLS = ('adb', 'apkanalyzer', 'jadx', 'apktool', 'apkid', 'maestro', 'flutter',
         'dart', 'r2', 'r2flutter', 'flutterdec', 'frida-ps', 'mitmdump', 'igf',
         'ipsw', 'xcrun', 'plutil', 'otool', 'dwarfdump')


def inventory(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError('Expected one archive file; bundle directories are not supported.')
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    result = {
        'schema_version': 1, 'input': str(path), 'sha256': digest.hexdigest(),
        'size_bytes': path.stat().st_size,
        'tools_on_path': {tool: shutil.which(tool) for tool in TOOLS},
        'limitations': [
            'No files extracted and no external tools executed.',
            'Framework indicators are not complete framework detection.',
            'Android binary XML is not decoded; use apkanalyzer for identity.',
            'PATH presence does not prove tool version, device access, or compatibility.',
            'Member metadata is not a full CRC or archive integrity check.'
        ]
    }
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 100000:
            raise ValueError('Archive has more than 100000 members; inspect separately.')
        names = [member.filename for member in members]
        unsafe = []
        for member in members:
            name = member.filename
            parts = PurePosixPath(name).parts
            if (name.startswith('/') or '\\' in name or '..' in parts
                    or re.match(r'^[A-Za-z]:', name)
                    or stat.S_ISLNK(member.external_attr >> 16)):
                unsafe.append(name)
        result['archive'] = {
            'member_count': len(members),
            'declared_uncompressed_bytes': sum(m.file_size for m in members),
            'unsafe_members': sorted(unsafe),
            'duplicate_members': sorted(n for n, count in Counter(names).items() if count > 1),
            'encrypted_members': sorted(m.filename for m in members if m.flag_bits & 1),
            'members': names,
        }
        patterns = {
            'android_manifest': r'(^|/)AndroidManifest\.xml$',
            'dex': r'(^|/)classes[0-9]*\.dex$',
            'flutter_aot': r'(^|/)libapp\.so$|/App\.framework/App$',
            'flutter_engine': r'(^|/)libflutter\.so$|/Flutter\.framework/Flutter$',
            'flutter_assets': r'(^|/)flutter_assets/',
            'react_native_bundle': r'(^|/)index\.android\.bundle$|/main\.jsbundle$',
            'ios_bundle_plist': r'^Payload/[^/]+\.app/Info\.plist$',
        }
        result['indicators'] = {
            key: sorted(n for n in names if re.search(pattern, n))
            for key, pattern in patterns.items()
        }
        result['android_abis'] = sorted({
            match.group(1) for name in names
            if (match := re.search(r'(?:^|/)lib/([^/]+)/[^/]+\.so$', name))
        })
        result['ios_bundles'] = []
        for name in result['indicators']['ios_bundle_plist']:
            entry = archive.getinfo(name)
            if (name in unsafe or names.count(name) != 1 or entry.flag_bits & 1
                    or entry.file_size > 1024 * 1024):
                result['ios_bundles'].append({'plist': name, 'status': 'not_read'})
                continue
            try:
                with archive.open(entry) as stream:
                    data = stream.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024:
                    raise ValueError('Info.plist exceeds size limit')
                plist = plistlib.loads(data)
                keys = ('CFBundleIdentifier', 'CFBundleExecutable',
                        'CFBundleShortVersionString', 'CFBundleVersion',
                        'MinimumOSVersion', 'CFBundleSupportedPlatforms')
                metadata = {key: plist[key] for key in keys if key in plist}
                # Reject unexpected non-JSON values rather than emit misleading metadata.
                json.dumps(metadata)
                result['ios_bundles'].append({'plist': name, 'status': 'read', **metadata})
            except (ValueError, TypeError, AttributeError, ExpatError, plistlib.InvalidFileException) as error:
                result['ios_bundles'].append({'plist': name, 'status': 'invalid',
                                              'error': str(error)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, help='New JSON file; refuses overwrite')
    args = parser.parse_args()
    try:
        report = inventory(args.archive)
        rendered = json.dumps(report, indent=2, ensure_ascii=True) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x', encoding='utf-8') as output:
                output.write(rendered)
        else:
            sys.stdout.write(rendered)
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        print(f'inventory: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
