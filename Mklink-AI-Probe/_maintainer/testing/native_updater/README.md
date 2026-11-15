# Native signed update acceptance

This maintainer-only harness exercises Tauri updater 2.10.1, matching V0.5.0,
against disposable native installations. It uses a mock application handle
with an older version to select the update, then runs the real download,
Minisign verification and native replacement code. It does not prove an
end-to-end update initiated by the historical desktop client.

`native_release_acceptance.py` launches the packaged native WebView before and
after replacement and controls it through the packaged MCP server. Linux DEB
installation uses the CI runner's existing passwordless sudo. Interactive
privilege prompts, Gatekeeper quarantine and USB hardware remain separate
acceptance requirements.

Only public signatures enter the workflow. The signing key stays on the
maintainer's machine. HTTP is allowed only for this test's loopback server;
the product's HTTPS endpoints and version are unchanged. The test binary's
Linux bundle marker selects AppImage or DEB using the same marker as Tauri's
bundler. This does not patch any distributed binary.

Dispatch `desktop-unix.yml` on the qualification branch with `target=all`,
`qualification_run=<successful immutable v0.5.0 build run>` and `signatures`
containing the filename-to-public-signature JSON map. This skips rebuilding
and calls `desktop-unix-qualification.yml`. Building or running this workflow
does not publish assets or update indexes.
