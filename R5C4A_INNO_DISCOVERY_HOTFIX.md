# R5c4a — Inno Setup Discovery & WinGet Bootstrap Hotfix

R5c4a is a focused hotfix over R5c4. It does not change the installer AI workflow.

## Fixed

- detects `ISCC.exe` from PATH, Program Files, Program Files (x86), per-user LocalAppData layouts, App Paths, and uninstall registry entries;
- supports custom Inno Setup install directories through registry `InstallLocation`;
- uses the current official WinGet identifier `JRSoftware.InnoSetup.7` first, with compatibility fallbacks;
- treats WinGet exit codes as advisory and re-runs actual `ISCC.exe` discovery after each attempt;
- avoids reinstalling Inno Setup when WinGet reports that the package is already installed;
- Setup artifact names are versioned as R5c4a.

## Unchanged

Core packaging, runtime AI preflight, runtime adoption, managed-runtime installation and model policy are unchanged from R5c4/R5c3e.
