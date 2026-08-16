# R5c1b — Windows Bootstrap Hotfix

Correzioni derivate dal test su Windows reale:

1. PowerShell parser error nella stringa con `$BuildPythonLabel:` corretto usando `${BuildPythonLabel}:`.
2. Il tag usato per Python Install Manager è ora `3.13`; l'architettura x64 viene verificata separatamente dal probe runtime.
3. La risoluzione del runtime installato usa anche `pymanager list --one --format=exe 3.13`.
4. `run_windows.bat` non impone più Python 3.13: il runner da sorgente accetta Python 3.13.x o 3.14.x x64.
5. Il lock Python 3.13 resta esclusivamente nella pipeline di build ufficiale standalone.
