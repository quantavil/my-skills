# Registry Contributions, Identity, and Releases

## Read the current contribution contract

Before preparing a registry submission, read the target repository's current
CONTRIBUTING.md, schema, validation scripts, and similar entries. For the DMS
registry, inspect `AvengeMedia/dms-plugin-registry`; do not treat this reference as
a frozen copy of its rules.

Search the whole registry for functional overlap, including combined plugins.
Inspect overlapping plugin implementations when descriptions are ambiguous.
Compare concrete features and behavior. Several modes in one interface is not a
differentiator when an existing plugin already combines those modes. IPC is not
unique merely because your plugin exposes it. State whether contributing upstream
was attempted; never invent an issue, PR, rejection, or maintainer response.

Registry entry IDs must match plugin.json and its namespace. Follow current file
naming rules (the reviewed registry used lowercase `username-plugin.json` paths
while allowing camelCase manifest IDs). Verify capabilities, dependencies,
minimum DMS version, public repository access, and screenshot URLs. A sound theme
package may supply assets even though the manifest lists executable dependencies.
Claim only observed compositor/distribution compatibility. Compositor-neutral
code does not prove it was tested on every compositor.

Run the registry's own validators in its checkout, including link checks. Describe
meaningful AI assistance accurately without inventing authorship percentages.
Update the PR description with overlap and verification evidence; after review
fixes, verify pushes before marking a draft ready when authorized.

## Identifier migration

Choose an ID early. If renaming an installed plugin, audit manifest, PluginSettings,
IPC target, I18n.trFor literals, registry entry, installation directory/symlink,
bar configuration, saved preference keys, overlay namespaces, docs, and tests.
QML type names and documented IPC response strings may intentionally stay stable.
Back up configuration; stop the shell for external settings migrations when needed.
Detect old/new namespace conflicts and resolve them deliberately instead of
silently overwriting data. Restart, check the live plugin, and confirm preferences
and bar placement survive.

## Tags and GitHub releases

Check the current guide before claiming a release is required. A registry PR and
a GitHub release are separate actions. Publish only with task authorization.
Check local and remote tags and existing releases before choosing a version. Match
manifest version, tag, release notes, and tested commit. Verify the public release
and peeled tag commit afterward. Prefer a new version for subsequent changes;
do not move published release tags or rewrite released history routinely. An old
unreleased tag can still have consumers: any replacement needs deliberate scope
and an exact expected remote value, not an unconditional force push.

Keep installation instructions, license, useful tests, and a public screenshot.
Remove stale drafts, temporary output, and duplicate docs after checking their
callers. Git history resets and unrelated deletion are not implied by packaging.
