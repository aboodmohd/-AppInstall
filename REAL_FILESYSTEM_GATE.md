# Real filesystem recovery acceptance gate

**Scope:** GitHub-hosted disposable Ubuntu runner only. Not a user install
script, not a production application, and not a replacement for a real-device
clean installation / low-space test.

The workflow `.github/workflows/real-filesystem-recovery.yml` creates and
mounts a **32 MiB tmpfs** below `RUNNER_TEMP`, then invokes
`tools/real_tmpfs_gate.py`. The script refuses to run unless ALL of these
conditions hold:

- GitHub Actions environment is explicitly present
- The test filesystem is a child of `RUNNER_TEMP`, not the runner temporary
  root itself
- The supplied path is a mountpoint backed by `tmpfs`
- Its size is 8 to 64 MiB, and the mount is initially empty

All source installation tests use a fake `HOME`, `XDG_DATA_HOME` and
`XDG_CONFIG_HOME` inside the disposable mount. The test exercises:

1. Actual clean source registration, with original MIME defaults and
   unrelated application/registry data in place
2. Writing until **real ENOSPC**, then attempting a source upgrade and
   confirming the executable, modules, MIME defaults, file modes and unrelated
   data remain unchanged
3. Deleting only the test's temporary filler file and retrying registration
4. Killing a child with a **real SIGKILL after its first file rename**, then
   rerunning the source registration to validate journal-based recovery,
   executable/module restoration, MIME defaults and data preservation

GitHub Action cleanup unmounts the disposable filesystem even if the probe
fails. No user-facing AppInstall package is installed.

### Limitations

- This is a temporary memory-backed filesystem, not a physical disk, so it
  doesn't measure sudden power loss, storage-controller write caching,
  persistence across actual reboot, or an actual spare CachyOS machine.
- ENOSPC is expected during source staging. It does **not** prove that the
  system can recover every possible ENOSPC in the middle of file publication.
- The SIGKILL portion verifies a persisted journal across process restart,
  not a complete host reboot.
- The stable release remains blocked on real disposable-device and desktop
  acceptance, license/dependency review, final stable package checksum and
  explicit publication authorization.

**Do not run the fill script directly on a personal computer or mounted disk.**
