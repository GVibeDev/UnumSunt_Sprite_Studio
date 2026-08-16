# R5c1b — Build Runtime Bootstrap

## Obiettivo
La build ufficiale Windows resta riproducibile su Python **3.13 x64**, ma il PC di sviluppo non deve avere Python 3.13 già installato.

Il Python principale del sistema può essere 3.14 o un'altra versione: non viene modificato né sostituito.

## Flusso
`build_windows_standalone.bat` ora:

1. verifica Windows x64;
2. controlla `.build-venv`;
3. se il venv esiste, verifica che usi Python 3.13 x64;
4. se è errato o corrotto, lo ricrea automaticamente;
5. cerca un Python 3.13 x64 già installato;
6. se manca, propone l'installazione automatica;
7. usa il Python Install Manager (`pymanager`) per installare `3.13-64`;
8. se manca Python Install Manager, può installarlo tramite WinGet;
9. crea `.build-venv` e usa esclusivamente il suo `python.exe` per dipendenze, test e PyInstaller.

## Opzioni
- default: prompt interattivo se Python 3.13 manca;
- `-InstallPython313`: autorizza il bootstrap senza prompt;
- `-NoPythonInstallPrompt`: non installa nulla e fallisce con diagnostica se Python 3.13 manca;
- `-ResetBuildVenv`: forza la ricreazione di `.build-venv`;
- `-SkipTests`: mantiene il comportamento già esistente.

## Contratto
- Build ufficiale Core: Python 3.13 x64.
- Python dell'utente finale: non richiesto.
- Runtime AI WanGP: resta separato e verrà gestito nelle milestone R5c2/R5c3.

## Riferimenti upstream
La pipeline segue il Python Install Manager ufficiale, che supporta installazione di runtime specifici (`py install <TAG>`) e raccomanda `pymanager` per gli script quando il vecchio launcher `py.exe` può creare conflitti.
