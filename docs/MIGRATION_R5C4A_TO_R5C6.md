# Migration R5c4a → R5c6

R5c6 is an in-place maintenance upgrade over the validated R5c4a Windows installer baseline.

No runtime or model migration is required. Keep all existing folders unchanged and run the R5c6 Setup over the existing installation.

New behavior:

- same product `AppId`, preserving the existing installation identity;
- previous runtime/model paths restored by the Setup wizard;
- managed runtime repair can preserve downloaded checkpoint files;
- uninstall can independently keep/remove managed runtime, models and app data;
- external/adopted runtimes remain protected from repair/delete;
- new maintenance JSON CLI for Setup/uninstaller orchestration.

Recommended Windows validation:

1. install R5c6 over an existing R5c4a installation;
2. verify the application starts and existing profiles/settings remain available;
3. verify existing adopted or managed runtime remains usable;
4. run Setup a second time as a Core repair/update;
5. uninstall while choosing **No** for runtime/models/data, reinstall, and verify reuse;
6. in a disposable test installation, uninstall while explicitly removing managed components and verify only owned paths are deleted.
