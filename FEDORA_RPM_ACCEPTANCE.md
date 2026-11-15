# Fedora 44 native RPM — Candidate Acceptance

**Status: DEVELOPMENT ONLY.** Published v1.5.0 and its tag/assets stay
unchanged. Fedora support needs a new version and separate owner approval.

The candidate native noarch RPM uses the same PKGBUILD file inventory as
the Arch and Debian packages. Its QML and Python modules live in
`/usr/lib/appinstall/`, with a launcher symlink at `/usr/bin/appinstall`.
Fedora 44 (x86_64) uses native `python3-pyside6`, `qt6-qtdeclarative`
and DNF dependencies. Other Fedora versions, RHEL and openSUSE are not
claimed to be supported.

## Required gates

- [ ] Nonroot Fedora 44 RPM build, valid metadata and source-file provenance
- [ ] Native Fedora DNF install/reinstall/removal in disposable CI
- [ ] Real Qt Quick offscreen smoke, terminal CLI, desktop entry and MIME files
- [ ] Managed user data and unrelated MIME defaults preserved on removal
- [ ] Installer matches only the RPM for the same latest stable tag, verifies
      SHA256SUMS and reads the RPM headers before installing
- [ ] Reject wrong/duplicate asset, malicious URL, tampered checksum, bad
      RPM headers and unsupported Fedora versions
- [ ] Existing Arch and Debian package/installer workflows still pass
- [ ] Real Fedora 44 desktop acceptance (or limitations documented)
- [ ] New release version and explicit owner merge/publication authorization

Installing AppInstall's own RPM is distinct from using the app to install
third-party DEB/RPM application files in Distrobox. Distrobox is not a
security sandbox. No host packages or user data were modified in preparing
this branch.
