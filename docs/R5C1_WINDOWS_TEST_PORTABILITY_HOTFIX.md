# R5c1 — Windows test portability hotfix

This hotfix changes **tests only**. Product/runtime code is unchanged.

## Problem

Two R5c1 standalone tests simulated Windows APPDATA/LOCALAPPDATA paths but asserted a mixed separator representation (`\` in the supplied Windows base path and `/` before the app directory). That representation is produced by `pathlib.Path` when the tests are executed on POSIX, but a real Windows `Path` renders the final separator as `\`. Therefore the exact same product code passed in the Linux build container and failed two assertions on Windows.

## Fix

The two assertions now normalize path separators to `/` before comparing the logical Windows path. The runtime path implementation is not modified.

Expected result: the complete 180-test suite remains green both in the Linux validation environment and in the Windows build environment.
