# R5c1 — Windows frozen self-check wait hotfix

## Problema osservato su Windows
PyInstaller completava correttamente la build `onedir`, ma lo script PowerShell poteva verificare
`standalone_selfcheck.json` prima che l'eseguibile `windowed` avesse terminato il self-check.

L'EXE R5c1 e' costruito con `console=False`. Per i processi GUI Windows, l'invocazione PowerShell
tramite call operator non costituisce un gate di attesa sufficientemente esplicito per la pipeline.

## Correzione
Il self-check viene ora avviato con `Start-Process -Wait -PassThru`. La build:

1. elimina un eventuale report precedente;
2. avvia `UnumSuntSpriteStudio.exe --self-check <path>`;
3. attende la terminazione del processo;
4. verifica l'ExitCode reale;
5. solo allora verifica l'esistenza e il contenuto del JSON.

Nessuna logica applicativa, runtime o funzione editoriale e' stata modificata.
