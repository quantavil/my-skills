#!/usr/bin/env python3
"""Read-only APK/IPA/AAB inventory. Nothing is extracted and nothing is executed.

Output is a summary by design. A real APK holds thousands of members, and
dumping every name costs tens of thousands of tokens to say very little.
Use --members to write the full name list to its own file when a specific
question actually needs it.

Standard library only.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import re
import stat
import sys
import zipfile
from xml.parsers.expat import ExpatError

INDICATORS = {
    'android_manifest': r'(^|/)AndroidManifest\.xml$',
    'dex': r'(^|/)classes[0-9]*\.dex$',
    'flutter_aot': r'(^|/)libapp\.so$|/App\.framework/App$',
    'flutter_engine': r'(^|/)libflutter\.so$|/Flutter\.framework/Flutter$',
    'flutter_assets': r'(^|/)flutter_assets/',
    'react_native_bundle': r'(^|/)index\.android\.bundle$|/main\.jsbundle$',
    'ios_bundle_plist': r'^Payload/[^/]+\.app/Info\.plist$',
    'aab_bundle_config': r'^BundleConfig\.pb$',
}

# Facts that matter when rebuilding the UI, not when reversing logic.
ASSET_PATTERNS = {
    'fonts': r'\.(ttf|otf|ttc)$',
    'vector_drawables': r'^res/drawable[^/]*/.*\.xml$',
    'nine_patch': r'\.9\.png$',
    'svg': r'\.svg$',
    'lottie': r'\.(json|lottie)$',
    'flutter_font_manifest': r'flutter_assets/FontManifest\.json$',
    'flutter_asset_manifest': r'flutter_assets/AssetManifest\.(json|bin)$',
}
DENSITY_RE = re.compile(r'^res/[^/]*-(ldpi|mdpi|hdpi|xhdpi|xxhdpi|xxxhdpi|anydpi|nodpi)\b')
MAX_MEMBERS = 100000
MAX_SAMPLE = 25


def _unsafe(member):
    name = member.filename
    return (name.startswith('/') or '\\' in name
            or '..' in PurePosixPath(name).parts
            or bool(re.match(r'^[A-Za-z]:', name))
            or stat.S_ISLNK(member.external_attr >> 16))


def _read_ios_plist(archive, name, unsafe, names):
    entry = archive.getinfo(name)
    if (name in unsafe or names.count(name) != 1 or entry.flag_bits & 1
            or entry.file_size > 1024 * 1024):
        return {'plist': name, 'status': 'not_read'}
    try:
        with archive.open(entry) as stream:
            data = stream.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError('Info.plist exceeds the size limit')
        plist = plistlib.loads(data)
        keys = ('CFBundleIdentifier', 'CFBundleExecutable', 'CFBundleShortVersionString',
                'CFBundleVersion', 'MinimumOSVersion', 'CFBundleSupportedPlatforms')
        metadata = {key: plist[key] for key in keys if key in plist}
        json.dumps(metadata)  # reject values that would not serialise honestly
        return {'plist': name, 'status': 'read', **metadata}
    except (ValueError, TypeError, AttributeError, ExpatError,
            plistlib.InvalidFileException) as error:
        return {'plist': name, 'status': 'invalid', 'error': str(error)}


def inventory(path, include_members=False):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError('expected one archive file; bundle directories are not supported')

    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)

    result = {
        'schema_version': 2,
        'input': str(path),
        'sha256': digest.hexdigest(),
        'size_bytes': path.stat().st_size,
        'limitations': [
            'No files extracted and no external tools executed.',
            'Framework indicators are not complete framework detection.',
            'Android binary XML is not decoded; use apkanalyzer for identity.',
            'External reverse-engineering capability is established by MCP preflight.',
            'Member metadata is not a CRC or archive integrity check.',
            'Nested archives (an .apks set, a split APK) are not inspected recursively.',
        ],
    }

    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise ValueError(f'archive has more than {MAX_MEMBERS} members; inspect separately')
        names = [m.filename for m in members]
        unsafe = sorted(m.filename for m in members if _unsafe(m))

        top_level = Counter(
            (PurePosixPath(n).parts[0] if PurePosixPath(n).parts else n) for n in names)
        extensions = Counter(PurePosixPath(n).suffix.lower() or '<none>' for n in names)
        largest = sorted(members, key=lambda m: m.file_size, reverse=True)[:MAX_SAMPLE]

        result['archive'] = {
            'member_count': len(members),
            'declared_uncompressed_bytes': sum(m.file_size for m in members),
            'top_level': dict(top_level.most_common()),
            'extensions': dict(extensions.most_common(20)),
            'largest_members': [{'name': m.filename, 'bytes': m.file_size} for m in largest],
            'unsafe_members': unsafe,
            'duplicate_members': sorted(n for n, c in Counter(names).items() if c > 1),
            'encrypted_members': sorted(m.filename for m in members if m.flag_bits & 1),
            'members_written_to': None,
        }

        matched = {key: sorted(n for n in names if re.search(pattern, n))
                   for key, pattern in INDICATORS.items()}
        result['indicators'] = {
            key: {'count': len(hits), 'sample': hits[:MAX_SAMPLE]}
            for key, hits in matched.items()
        }
        result['framework_guess'] = _guess(matched)

        result['assets'] = {
            key: {'count': sum(1 for n in names if re.search(pattern, n)),
                  'sample': [n for n in names if re.search(pattern, n)][:MAX_SAMPLE]}
            for key, pattern in ASSET_PATTERNS.items()
        }
        densities = Counter(m.group(1) for n in names if (m := DENSITY_RE.match(n)))
        result['assets']['android_densities'] = dict(densities.most_common())

        result['android_abis'] = sorted({
            m.group(1) for n in names
            if (m := re.search(r'(?:^|/)lib/([^/]+)/[^/]+\.so$', n))})

        result['ios_bundles'] = [_read_ios_plist(archive, n, unsafe, names)
                                 for n in matched['ios_bundle_plist']]

        if include_members:
            result['_members'] = names
    return result


def _guess(matched):
    """State what the indicators support, not a confident verdict."""
    notes = []
    if matched['flutter_aot']:
        notes.append('Flutter AOT present (libapp.so or App.framework)')
    if matched['react_native_bundle']:
        notes.append('React Native bundle present')
    if matched['dex'] and matched['flutter_aot']:
        notes.append('DEX alongside Flutter usually belongs to the Android wrapper, '
                     'not to application logic')
    elif matched['dex']:
        notes.append('DEX present with no Flutter indicator')
    if matched['ios_bundle_plist']:
        notes.append('iOS payload bundle present')
    if matched['aab_bundle_config']:
        notes.append('Android App Bundle: not directly installable, needs bundletool')
    if not notes:
        notes.append('No recognised framework indicator; inspect manually')
    return notes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path,
                        help='write the report to a new JSON file; refuses to overwrite')
    parser.add_argument('--members', type=Path,
                        help='write the full member name list to this file (large)')
    parser.add_argument('--force', action='store_true', help='allow overwriting --output')
    args = parser.parse_args(argv)

    try:
        report = inventory(args.archive, include_members=bool(args.members))
        if args.members:
            names = report.pop('_members')
            args.members.parent.mkdir(parents=True, exist_ok=True)
            args.members.write_text('\n'.join(names) + '\n', encoding='utf-8')
            report['archive']['members_written_to'] = str(args.members)
        rendered = json.dumps(report, indent=2, ensure_ascii=True) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            mode = 'w' if args.force else 'x'
            with args.output.open(mode, encoding='utf-8') as handle:
                handle.write(rendered)
            print(f"{args.output}  sha256 {report['sha256'][:16]}…  "
                  f"{report['archive']['member_count']} members  "
                  f"{'; '.join(report['framework_guess'])}")
        else:
            sys.stdout.write(rendered)
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        print(f'inventory: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
