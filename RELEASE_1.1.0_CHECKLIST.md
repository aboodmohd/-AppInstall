# AppInstall v1.1.0 — Release Preparation Checklist

**STATUS: NOT PUBLISHED. Publication and merge require separate explicit approval.**

- Candidate branch: `release/1.1.0-prep`
- Starting main commit: `60fe4dcee72acbbf22832814cc8fa9ed9f11cf35`
- Application version: `1.1.0`
- Arch candidate package version: `1.1.0-1`
- Separate one-command installer version: `1.1.0`
- Latest published stable version: `v1.0.0`

## Release scope

The new Install from URL feature provides HTTPS downloads, progress and
cancellation, format identification, checksums, installation confirmation,
and reuse of the existing AppImage, Flatpak, DEB and RPM backends. It
preserves the original My Applications interface and the existing app state.

## Required checks before a release

- [ ] All release-preparation CI jobs pass on the final commit.
- [ ] Run `python3 -m unittest discover -s tests -v` and Bash syntax checks.
- [ ] Confirm all 35 `PKGBUILD` BLAKE2b source checksums match exact candidate files.
- [ ] Build the candidate `appinstall-1.1.0-1-any.pkg.tar.zst` in a disposable Arch environment.
- [ ] Verify packaged `url_install.py` and `url_dialog.py`, file permissions,
      MIME handlers, metadata and the MIT notice.
- [ ] Inspect the candidate via `pacman -Qip` and `pacman -Qlp`.
- [ ] Test clean install, upgrade from published v1.0.0, and rollback in
      an isolated Arch/CachyOS installation. Preserve registries, MIME
      defaults, managed app data and launcher behavior.
- [ ] Smoke-test GUI URL entry, download progress, cancellation, preview,
      and cleanup with controlled fixtures.
- [ ] Verify no DNS-rebinding or private-address regression.
- [ ] Compute SHA-256 of the **actual built artifact** and prepare a matching
      `SHA256SUMS`. Never reuse the v1.0.0 digest.
- [ ] Review `KNOWN_LIMITATIONS.md`, dependencies, licensing and release text.
- [ ] Obtain owner's explicit permission to merge the release preparation PR.
- [ ] Obtain **separate** explicit permission to create the `v1.1.0` tag
      and publish a GitHub release with the verified assets.

## Publication hold

Do not create a tag, a release (including draft), or upload release assets
until the user explicitly authorizes publication. Do not alter the user's
installed CachyOS AppInstall or existing managed applications.

Expected eventual assets — **not yet built**:
- `appinstall-1.1.0-1-any.pkg.tar.zst`
- `SHA256SUMS`
- `RELEASE_VERIFICATION.txt` (evidence for this exact artifact)

The one-command installer `install.sh` must continue installing only the
latest *published stable* package. It must not fetch this candidate.
