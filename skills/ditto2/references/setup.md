# DroidBot setup

When DroidBot is missing, install it automatically as part of an authorized
Ditto2 exploration task, subject to the host's package/build policy. Reuse prior
installation authorization; do not ask again for the same approved setup.
This host's `AGENTS.md` records approval for the pinned DroidBot wheel build
below. On other hosts, follow their build policy. Dependencies must use prebuilt
wheels. Do not build Android helper APKs or unrelated dependencies.

Use Python 3.13 and uv. Prefer an existing wheel from this exact upstream revision.
Otherwise download the pinned source, verify it, build only DroidBot's Python
wheel, then install it in an isolated uv tool environment:

```bash
set -eu
ditto_source_id=cc4cc93cc53941ccc188c59ef45ab173e2347113
ditto_setup_dir="${XDG_CACHE_HOME:-$HOME/.cache}/ditto2/$ditto_source_id"
mkdir -p "$ditto_setup_dir"
curl --fail --location "https://github.com/honeynet/droidbot/archive/$ditto_source_id.tar.gz" --output "$ditto_setup_dir/source.tar.gz"
printf '%s  %s\n' '8f824fdca1193bcaba11d92722570be3dfd06994bccd0417470dd879acf884f3' "$ditto_setup_dir/source.tar.gz" | sha256sum --check
tar -xzf "$ditto_setup_dir/source.tar.gz" -C "$ditto_setup_dir"
uv build --wheel --out-dir "$ditto_setup_dir/wheels" "$ditto_setup_dir/droidbot-$ditto_source_id"
uv tool install --python 3.13 --no-build --with 'setuptools<81' --with standard-telnetlib "$ditto_setup_dir/wheels/droidbot-1.0.2b4-py3-none-any.whl"
"$HOME/.local/bin/droidbot" -h
```

Verify `droidbot -h` from the MCP's environment. If the shell finds it but the
MCP does not, ensure the uv tool bin directory is on that client's PATH and
restart its server. Do not reinstall repeatedly for a PATH problem.

The MCP discovers adb through PATH, then tries `ANDROID_HOME`,
`ANDROID_SDK_ROOT`, and `~/Android/Sdk` in order. It passes the selected adb
directory to DroidBot's child PATH. Reuse a compatible device already available
on the host; check its `AGENTS.md` for device constraints.

For targeted navigation (such as reaching tabs that unguided DFS misses), DroidBot supports
custom scripts via `-script`. Ditto2's `explore_apk` accepts an optional `script_path`,
checks the required top-level JSON sections, preserves it as `script.json` inside
the exploration export directory, and passes it to DroidBot for full grammar
validation and guided transitions.

Run a bounded live exploration after installation. A help command proves CLI
startup only; a nonempty, validated navigation graph establishes runtime output.
Keep logs and report failures without claiming coverage. Update the host's
AGENTS.md after package or environment changes.
