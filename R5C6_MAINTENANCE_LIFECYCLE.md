# R5c6 — Repair / Update / Uninstall

R5c6 adds the maintenance lifecycle to the validated R5c4a Windows Setup line.

## Goals

- update/repair the Core by running the current Setup over the existing installation;
- preserve runtime AI, checkpoints, profiles and user projects by default;
- repair a managed WanGP runtime without reinstalling checkpoint files;
- allow explicit removal of managed runtime and/or managed model checkpoints;
- never delete adopted/external WanGP installations;
- optionally purge application settings, logs, caches and temporary generation jobs;
- keep project folders outside the application data roots untouched.

## Core update / repair contract

The installer keeps the same Inno Setup `AppId` used by R5c4a and `UsePreviousAppDir=yes`. Running a newer Setup over the existing installation therefore targets the existing product installation rather than creating a parallel product identity. Core files are replaced from the new standalone payload while `%APPDATA%` / `%LOCALAPPDATA%` state remains outside the `[Files]` payload.

Runtime/model paths and the auto-adopt/fallback choices are persisted through Inno Setup PreviousData. Legal/TOS acceptance is deliberately not persisted.

## Runtime maintenance CLI

The frozen executable exposes:

```text
--maintenance-status <report.json>
--maintenance-repair <report.json> [--accept-anaconda-tos]
--maintenance-cleanup <report.json>
    [--remove-managed-runtime]
    [--remove-managed-models]
    [--remove-user-data]
```

`--maintenance-repair` is destructive only for the managed runtime source/dependency layer; existing checkpoint files are not selected for installation or deletion.

## Ownership protection

`runtime_install_state.json` remains the authority for runtime ownership.

- `ownership=managed`: runtime and `model_root/wangp_ckpts` may be removed only after explicit user choice.
- `ownership=external`: runtime/model delete and repair actions return `protected`; no external file is changed.

Model cleanup never deletes the selected `model_root` itself. It only removes the dedicated `wangp_ckpts` subtree owned by Sprite Studio.

## Uninstall behavior

The Core uninstaller asks three independent questions, all opt-in for deletion:

1. remove managed AI runtime;
2. remove managed model checkpoints;
3. remove Sprite Studio settings/logs/cache/temporary jobs.

Choosing **No** preserves the corresponding data for a future reinstall. External/adopted runtimes are protected regardless of the answer.

User project directories are not part of maintenance cleanup and are never removed.

## Scope boundary

R5c6 intentionally does not absorb the deferred R5c5 Krea 2 Setup-completion work. Existing Runtime Manager Krea support remains unchanged; this milestone is only the maintenance lifecycle.
