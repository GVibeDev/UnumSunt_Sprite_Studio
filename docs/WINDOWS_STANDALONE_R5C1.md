# R5c1 — Windows Standalone Core

Baseline validata di partenza: `UnumSunt_Sprite_Studio_R5e13b`.

## Obiettivo

Produrre una distribuzione Windows x64 **standalone** del core di Sprite Studio. Il PC destinatario non deve avere Python, PySide6, OpenCV, NumPy o Pillow installati.

R5c1 non installa ancora WanGP, Miniconda, PyTorch/CUDA o checkpoint AI. Questi restano runtime esterni e verranno gestiti dalle milestone R5c2/R5c3.

## Build canonica

Su Windows x64 con Python 3.13 disponibile tramite Python Launcher:

```bat
build_windows_standalone.bat
```

La pipeline:

1. crea `.build-venv` isolato;
2. installa `requirements-build.txt`;
3. esegue tutti i test automatici;
4. costruisce `UnumSuntSpriteStudio.exe` in modalità PyInstaller `onedir`;
5. avvia il binario congelato con `--self-check`;
6. verifica che dipendenze core e directory utente siano operative;
7. genera `RELEASE_MANIFEST_R5c1.json`;
8. produce ZIP standalone e checksum SHA-256.

Output:

```text
release/
  UnumSunt_Sprite_Studio_R5c1_Windows_x64_Standalone.zip
  UnumSunt_Sprite_Studio_R5c1_Windows_x64_Standalone_SHA256.txt
```

## Percorsi utente

Il programma non scrive nella cartella di installazione. Conserva compatibilità con i percorsi usati dalle build R5e:

- `%APPDATA%\UnumSuntSpriteStudio\profiles.json`
- `%LOCALAPPDATA%\UnumSuntSpriteStudio\generation_jobs\`
- `%LOCALAPPDATA%\UnumSuntSpriteStudio\local_wangp.json`
- `%LOCALAPPDATA%\UnumSuntSpriteStudio\local_wangp_image.json`
- `%LOCALAPPDATA%\UnumSuntSpriteStudio\logs\sprite_studio.log`

Questo è necessario per una futura installazione sotto `Program Files`, dove l'applicazione non deve dipendere da directory scrivibili accanto all'EXE.

## Diagnostica standalone

Il binario accetta:

```text
UnumSuntSpriteStudio.exe --version
UnumSuntSpriteStudio.exe --self-check C:\percorso\report.json
```

Il self-check verifica il runtime core congelato e la scrivibilità delle directory utente. **Non esegue ancora il preflight CUDA**: quello appartiene a R5c2.

## Decisione packaging

R5c1 usa `onedir`, non `onefile`. Per un'app Qt/OpenCV di questa dimensione è una base più trasparente e affidabile per il successivo installer: avvio senza estrazione temporanea del bundle e componenti facilmente verificabili tramite manifest/hash.
