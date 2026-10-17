# Local Tcl runtime

This bootstrap builds the exact Tcl 8.6.16 source release used by the retained
single-axis fixture. It installs inside `.build/reproducibility/runtime`, without
changing the system Tcl or installing system packages. The default cache is
ignored by Git.

Requirements: a Unix host (macOS or Linux), Python 3.9+, a C compiler, `make`, and
`curl` for the initial source download. A working platform compiler and SDK must
already be installed. Linux execution is **NOT RUN** in the initial milestone;
the recorded native run uses macOS on arm64.

```sh
python3 tools/reproducibility/bootstrap_runtime.py
python3 tools/reproducibility/bootstrap_runtime.py --describe-json
```

The first command verifies the download's SHA-256 before extraction, builds and
installs Tcl locally, checks its exact patch version and required `hypot` math,
and writes `runtime-manifest.json`. Subsequent calls verify the archive, source
tree, full installed runtime and smoke test before reusing it. Changed files or
an unmanifested installation fail; select a fresh `--cache-dir` to rebuild.
Build commands, compiler/make versions, stdout, stderr and failures remain under
the cache's `build-records/` directory. The Tcl upstream test suite is **NOT RUN**
by this bootstrap; the milestone's integration tests exercise the actual fixture.

For an offline build, use an already downloaded archive with the exact locked
hash:

```sh
python3 tools/reproducibility/bootstrap_runtime.py --cache-dir /tmp/apollo-runtime --archive /absolute/path/tcl8.6.16-src.tar.gz
```

`runtime-lock.json` pins the archive URL, SHA-256, version and configure options.
The hash is published by the official Tcl project on its
[release download page](https://sourceforge.net/projects/tcl/files/Tcl/8.6.16/tcl8.6.16-src.tar.gz/download),
with the release described in the
[Tcl Core Team announcement](https://sourceforge.net/p/tcl/mailman/message/58851460/).
The bootstrap imports no package manager or Nix channel state.

The manifest records the host compiler, make, Python and operating system.
These tools and system libraries are **not pinned**. This setup establishes
verified source inputs and repeatable experiments; it does not establish
portable bit-identical binaries. Builds contain absolute installation paths and
must be rebuilt if the cache is moved. Keep a supplied offline archive available
at its recorded path when validating that installation.

Runtime guard tests (no compiler invocation):

```sh
python3 -m unittest discover -s docs/milestone1-evidence/tests -p test_runtime.py -v
```
