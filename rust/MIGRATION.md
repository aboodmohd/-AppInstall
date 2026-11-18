# AppInstall Rust migration

Baseline: `20dc69dfa801f1924ef5a0f76d49c01b63cf44f4` on `main`. Work is on
`migration/rust-backend`; review via draft PR. Only `catalog_browse.py` is in
scope for this pilot. Nothing imports the pilot in a normal AppInstall run.
Python still owns all live behavior; the original QML and package formats are unchanged.

## Pilot design

`rust-anything` 1.5.1 scaffolded all four exports. Its generated JSON bridge
would copy Python rows and change object identity. The pilot uses direct PyO3
bindings and returns references to the original objects in new lists. Category
policy, ordering, filtering and Featured selection run in Rust. The bridge
still uses Python for object operations and Unicode case folding. Exotic
Python subclasses with overridden string or comparison methods are not part
of the tested contract. Do not run `refresh` over these custom bindings.

## Reproduce from the repository root

```sh
crate="$PWD/rust/catalog-browse-rs"
cargo fmt --manifest-path rust/Cargo.toml --all --check
cargo clippy --manifest-path rust/Cargo.toml --locked --all-targets -- -D warnings
cargo test --manifest-path rust/Cargo.toml --locked
rust-anything gate "$crate"
rust-anything shadow "$crate"  # once per checkout; writes an ignored file
RUST_ANYTHING_MODE=shadow python3 "$crate/test_pilot.py" -v
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p 'test_catalog*.py'
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p 'test_manager_qml.py'
rust-anything bench "$crate"
```

`inputs.jsonl` supplements the generated cases. `cases.jsonl` records the
unmodified original and should not be regenerated to hide a mismatch. The
generated shadow is used only on reusable, read-only fixture inputs. A
one-shot iterator cannot be replayed by passing the same object to both
implementations; integration tests exercise iterator behavior directly.

## Evidence

- Before implementation: 4 original catalog tests and 119 offscreen QML
  tests passed. The compiled scaffold matched 0/351 recorded cases.
- After implementation: all 11 MCP gate checks passed, including 351/351
  comparisons (3 expected exceptions), formatting, Clippy and 2 Rust tests.
- Four pilot integration tests passed, including all aliases, Unicode slicing,
  object identity, malformed rows, lazy iteration, and 350 shadow comparisons
  with zero mismatches. Existing catalog (27) and offscreen QML (119) tests passed.
- The local microbenchmark, including PyO3 call costs, reported 1.42× and 1.22×
  speedups for category lookup and enumeration, but 0.52× and 0.44× for
  filtering and Featured. The tool's overall estimate was 0.79×. No live
  cutover or performance claim is warranted.

## Gates for later work

Before migrating state or installation flows, record CLI and MIME dispatch,
filesystem effects in disposable XDG homes, and upgrade/rollback in VMs.
Keep on-disk data readable by the rollback build and never double-execute
mutating package operations in shadow mode. Run packaged checks on Arch,
CachyOS, Debian 13, Ubuntu 24.04/26.04, Mint 22, and Fedora 44 before any
cutover. This pilot did not run native packaging, the full Python suite,
the distro matrix, or real desktop tests. Further units and enabling the
pilot in AppInstall require approval.
