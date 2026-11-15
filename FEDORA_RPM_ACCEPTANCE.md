# Fedora 44 native RPM — Candidate Acceptance

**Status: Fedora 44 CI acceptance passed on PR #71; live desktop acceptance
is still pending.** Fedora support is included in the v1.6.0 release
candidate. Published v1.5.0 remains immutable; the v1.6.0 tag and
artifacts require separate approval.

The candidate native noarch RPM uses the same PKGBUILD file inventory as
the Arch and Debian packages. Its QML and Python modules live in
`/usr/lib/appinstall/`, with a launcher symlink at `/usr/bin/appinstall`.
Fedora 44 (x86_64) uses native `python3-pyside6`, `qt6-qtdeclarative`
and DNF dependencies. Other Fedora versions, RHEL and openSUSE are not
claimed to be supported.

## Required gates

- [x] Nonroot Fedora 44 RPM build, valid metadata and source-file provenance
- [x] Native Fedora DNF install/reinstall/removal in disposable CI
- [x] Real Qt Quick offscreen smoke, terminal CLI, desktop entry and MIME files
- [x] Managed user data and unrelated MIME defaults preserved on removal
- [x] Installer matches only the RPM for the same latest stable tag, verifies
      SHA256SUMS and reads the RPM headers before installing
- [x] Reject wrong/duplicate asset, malicious URL, checksum mismatch,
      RPM headers not matching the selected package, and unsupported Fedora
      versions in unit tests and the CI verification path
- [x] Existing Arch and Debian package/installer workflows still pass
- [ ] Real Fedora 44 desktop acceptance (or limitations documented)
- [ ] New v1.6.0 release final-build/asset verification and separate
      explicit owner authorization for publication

Installing AppInstall's own RPM is distinct from using the app to install
third-party DEB/RPM application files in Distrobox. Distrobox is not a
security sandbox. No host packages or user data were modified in preparing
this branch.
