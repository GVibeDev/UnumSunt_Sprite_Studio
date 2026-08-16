
## R5c3 — Automated AI Runtime Installer / Model Manager

R5c3 adds `File → Gestione runtime AI…` and an installation engine for a private Miniconda/Python 3.11/WanGP/PyTorch cu130 runtime plus selected Animate and Krea 2 checkpoints. The R5c2 CUDA/storage/path preflight remains the mandatory gate; GPU model, VRAM and RAM remain informational only. See `RUNTIME_INSTALLER_R5C3.md`.
# Unum Sunt Sprite Studio — R5c1

**Baseline validata di partenza:** `UnumSunt_Sprite_Studio_R5e13b`.

R5c1 apre il ramo di distribuzione nativa con il **Windows Standalone Core**. La pipeline funzionale R5e13b resta invariata; l'applicazione può ora essere congelata come distribuzione Windows x64 che non richiede Python sul PC destinatario.

La build canonica è `build_windows_standalone.bat`. Esegue regressione automatica, PyInstaller onedir, self-check del binario congelato, release manifest, ZIP e SHA-256. Configurazioni, job e log restano in `%APPDATA%` / `%LOCALAPPDATA%`, mai nella directory dell'EXE.

WanGP, Miniconda, PyTorch/CUDA e modelli AI **non sono ancora incorporati**: R5c1 prepara il core; preflight hardware/storage e installer runtime appartengono alle milestone successive R5c2/R5c3.

Vedi `WINDOWS_STANDALONE_R5C1.md`.

---

# Unum Sunt Sprite Studio — R5e13b

**Baseline validata di partenza:** `UnumSunt_Sprite_Studio_R5e13a`.

R5e13b introduce **Painter & Core Performance Optimization** mantenendo il risultato del clean-up compatibile con R5e13a. L'intervento è mirato agli hotspot già identificati dal profiling: brush dab, transazioni Undo e repaint della preview durante una pennellata.

## Painter ROI

Il vecchio painter costruiva una maschera sull'intero frame e copiava l'intero RGBA per ogni `mouseMoveEvent`. R5e13b aggiunge `paint_alpha_circle_inplace()`: il calcolo viene confinato al rettangolo del pennello e modifica in-place il buffer di lavoro della pennellata. La API storica `paint_alpha_circle()` resta disponibile e produce output pixel-identico al comportamento R5e13a.

## Una pennellata = una transazione Undo

Il canvas espone ora un lifecycle esplicito:

```text
brush_stroke_started
→ brush_painted × N
→ brush_stroke_finished
```

`CleanupStudio` esegue una sola snapshot iniziale, applica i dab sul buffer di lavoro e crea una sola transazione al rilascio del mouse. `overrides_changed` viene quindi emesso una volta per stroke, evitando il refresh completo di R1/R2/R3 a ogni movimento.

## Dirty-region preview

La preview del Clean-up viene aggiornata soltanto nella ROI modificata. `render_checkerboard_region()` mantiene l'origine globale della scacchiera ed è verificato pixel-identico alla porzione corrispondente di `render_checkerboard()`.

`CleanupCanvas` mantiene inoltre un `QImage` persistente appoggiato al buffer NumPy, eliminando la precedente `QImage.copy()` full-frame da ogni `paintEvent`; il repaint viene richiesto sul solo dirty rectangle.

## Benchmark algoritmico sintetico

Nel container di build, su frame RGBA 720×720 e pennello raggio 6:

- 200 dab legacy full-frame: circa **562 ms**;
- 200 dab ROI in-place: circa **8,5 ms**;
- speed-up interno osservato: circa **66×**.

Per la composizione checkerboard, 50 refresh full-frame hanno richiesto circa **1352 ms**, contro circa **3,5 ms** per la ROI 15×15 (**~385×** sul solo kernel di preview). Questi numeri misurano gli algoritmi isolati, non gli FPS end-to-end della GUI Windows.

## Profiling

`run_windows_profile.bat` resta disponibile e genera ora `performance_report_R5e13b.json`. Oltre alle metriche R5e13a sono disponibili:

- `cleanup.paint_alpha_circle_roi_inplace`;
- `cleanup.render_checkerboard_region`;
- `cleanup.brush_stroke_commit`.

## Compatibilità

- nessuna modifica intenzionale a chroma, alignment, workflow, Character Set o export;
- nessuna modifica ai formati degli asset;
- schema progetto marcato R5e13b senza nuovi campi obbligatori;
- Undo del pennello cambia granularità intenzionalmente: una pennellata fisica corrisponde ora a una singola operazione Undo/Redo.

## Test

La candidata R5e13b supera **176 test automatici**, più **8 subtest** di equivalenza. I nuovi test verificano output pixel-identico del painter rispetto all'algoritmo R5e13a, limiti della ROI, equivalenza checkerboard regionale, lifecycle stroke e assenza di commit dentro ogni dab.

## Validazione manuale consigliata

1. pennello `Cancella alpha` con stroke lunghi e rapidi;
2. pennello `Ripristina alpha`;
3. Undo/Redo: una singola azione deve annullare/ripristinare l'intera pennellata;
4. zoom 2×, 8× e 24× con griglia ON/OFF;
5. verificare che durante lo stroke la preview resti fluida e che R2/R3 vengano marcati dirty al rilascio;
6. eseguire `run_windows_profile.bat` e confrontare `performance_report_R5e13b.json` con il report R5e13a, se disponibile.

---

# Unum Sunt Sprite Studio — R5e13a

**Stato storico:** milestone validata; successivamente superata da R5e13b.

R5e13a introduce **Architecture Decomposition & Performance Instrumentation**. La milestone non aggiunge nuove funzioni produttive: separa responsabilità ormai mature da `MainWindow` e prepara misurazioni quantitative per R5e13b.

## Decomposizione strutturale

`MainWindow` passa da **2.022 righe / 95 metodi** a **1.885 righe / 79 metodi**. Il wiring dei 14 workspace resta nell'hub principale, mentre vengono estratti:

- `ChromaProfileController` per lifecycle e persistenza dei profili alpha/chroma;
- `BackgroundRulesController` per i colori sfondo aggiuntivi e il relativo stato di sampling.

La separazione è intenzionalmente conservativa: nessun tentativo di raggiungere una soglia artificiale di righe e nessuna estrazione dei Project Groups finché non emerge un confine autonomo altrettanto chiaro.

## Performance Probe opt-in

`app/performance_probe.py` raccoglie metriche soltanto quando `UNUM_SUNT_PERF=1`. Con `UNUM_SUNT_PERF_REPORT=<path>` il report JSON viene scritto alla chiusura.

Su Windows è disponibile:

```text
run_windows_profile.bat
```

Sono già strumentati painter/preview Clean-up, chroma, alignment, spritesheet slicing e ProjectStore. Il probe non ottimizza ancora gli algoritmi: serve a produrre dati comparabili prima e dopo R5e13b.

## Compatibilità

- nessuna modifica intenzionale agli output chroma/alpha;
- nessuna modifica al comportamento dei tre workflow;
- Character Set / Layer Manager invariato;
- provider WAN e Image Generator invariati;
- schema progetto marcato R5e13a senza nuovi campi obbligatori.

## Test

La candidata R5e13a supera **171 test automatici**. Sono inclusi nuovi test per lifecycle dei controller estratti, sampling/regole sfondo, Performance Probe e verifica AST che i 16 metodi estratti non appartengano più a `MainWindow`.

## Validazione manuale consigliata

1. profili chroma: salva / carica / elimina / ultimo profilo;
2. colori aggiuntivi: aggiungi / campiona / toggle / tolleranza / rimuovi / svuota;
3. confronto visivo chroma e preview con R5e12;
4. percorso Standard e Sprite Sheet Rework senza regressioni;
5. eseguire `run_windows_profile.bat`, usare intensamente il pennello e chiudere l'app;
6. verificare la presenza e leggibilità di `performance_report_R5e13a.json`.

## Fuori ambito

R5e13a **non** introduce ancora ROI del pennello, stroke transaction unica, dirty-rectangle repaint o throttling della preview. Questi interventi sono riservati a **R5e13b — Performance Optimization**.

---

# Unum Sunt Sprite Studio — R5e12

**Baseline validata di partenza:** `UnumSunt_Sprite_Studio_R5e11`.

R5e12 introduce **UI Consolidation & Contextual Command System** senza modificare la logica produttiva validata. La milestone riduce la compressione dei pannelli, rende i comandi superiori coerenti con il contesto e introduce una gerarchia visiva più leggibile tra i workspace.

## Menu applicazione tradizionale

La finestra principale dispone ora di menu dedicati:

```text
File
Modifica
Progetto
Immagine
Video
Spritesheet
Preset
Esportazione
```

I menu riusano le stesse `QAction` della toolbar e dei workspace; non duplicano la logica dei comandi. `Ctrl+S` è ora coerentemente associato al salvataggio del progetto, mentre l'export rapido R1 usa `Ctrl+Shift+E`.

## Toolbar contestuale

La vecchia toolbar globale viene sostituita da **Comandi contestuali**. I pulsanti vengono mostrati soltanto nei workspace pertinenti.

Esempi:

- playback, Frame ±1, aggiunta/rimozione ed export R1: solo in `Estrazione`;
- `Apri video`: Progetto / Genera / Estrazione / Workflow;
- `Apri spritesheet`: Sprite Sheet / Workflow / Character Set;
- salvataggio progetto: disponibile come comando globale e mostrato nella toolbar nei contesti di progetto.

Le shortcut di editing video vengono anche disabilitate fuori contesto, evitando che `Del`, `A`, frecce o `Space` eseguano operazioni R1 mentre si lavora, per esempio, nel Clean-up o nei Preset.

## Tab principali più leggibili

Le 14 tab principali hanno etichette più corte e tooltip completi. Il testo usa una progressione cromatica controllata dal più scuro al più chiaro lungo la pipeline.

La barra tab usa inoltre:

- pulsanti di scorrimento quando lo spazio non basta;
- elisione dei testi lunghi;
- evidenza più netta della tab selezionata.

## Genera — layout consolidato

Il workspace Genera è stato riorganizzato per evitare la compressione verticale e orizzontale dei campi.

La colonna di configurazione è ora divisa in:

```text
Generazione
Runtime WAN
Profili
```

La parte destra è divisa in:

```text
Job / Output
Cronologia
```

Ogni pagina usa scroll verticale responsivo e i `QFormLayout` sono configurati per far crescere i campi e andare a capo quando la finestra si restringe. Il contratto WanGP, i controlli e le impostazioni salvate restano invariati.

## Compatibilità

- schema progetto aggiornato a R5e12;
- workflow R5e10 invariati;
- Character Set R5e11 invariato;
- nessuna modifica a provider, masking, cleanup, alignment o export;
- la Vista guidata continua a controllare la visibilità dei workspace.

## Test

La candidata R5e12 supera **167 test automatici**.

Sono coperti anche:

- coerenza delle 14 tab;
- policy dei comandi contestuali;
- disattivazione dei controlli video fuori da Estrazione;
- visibilità contestuale di Apri video;
- progressione cromatica monotona delle etichette.

## Validazione manuale consigliata

1. ridimensionare la finestra e verificare il workspace Genera;
2. passare tra Generazione / Runtime WAN / Profili;
3. verificare Job / Output e Cronologia;
4. cambiare workspace e controllare che la toolbar mostri solo comandi pertinenti;
5. verificare che `Del`, `A`, frecce e `Space` non attivino comandi R1 fuori da Estrazione;
6. provare File → Nuovo/Apri/Salva progetto;
7. provare Video, Immagine, Spritesheet, Preset ed Esportazione;
8. verificare la Vista guidata R5e10.

## Fuori ambito

R5e12 non ottimizza ancora il costo CPU del painter Clean-up. Il profiling e la riduzione delle copie/repaint sono destinati a **R5e13 — Performance Audit & Core Optimization**.

---

## R5e11 — Character Set / Layer Manager

**Baseline validata di partenza:** `UnumSunt_Sprite_Studio_R5e10`.

R5e11 introduce **Character Set / Layer Manager** senza modificare i tre workflow validati in R5e10. La milestone consolida la gerarchia già esistente `Soggetto → Animazione → Direzione` in una vista di produzione unificata e aggiunge un primo stack layer raster non distruttivo.

## Nuovo workspace

```text
13 · Character Set R5e11
```

Il workspace è disponibile in tutti e tre i Guided Workflows R5e10.

## Character Set

Per ogni gruppo `Soggetto`, R5e11 costruisce una matrice:

```text
Animazione × N / NE / E / SE / S / SW / W / NW
```

Ogni cella mostra:

- presenza o assenza della direzione;
- stato produttivo del relativo Project Group;
- collegamento al gruppo Direzione reale.

Il riepilogo mostra copertura delle 8 direzioni e quante direzioni sono già arrivate almeno allo stato `aligned`.

### Creazione automatica delle direzioni mancanti

Il comando **Crea direzioni mancanti** completa, per tutte le animazioni del soggetto selezionato, gli slot N/NE/E/SE/S/SW/W/NW non ancora presenti. Non tocca i gruppi già esistenti.

### Attivazione rapida

Una cella esistente della matrice può essere selezionata e resa immediatamente il Project Group attivo. La pipeline continua quindi a usare il normale meccanismo di salvataggio/caricamento R5e4–R5e10.

## Layer Manager

I layer vengono definiti a livello di soggetto.

Tipi iniziali:

```text
base
outfit
equipment
accessory
effect
custom
```

Per ogni layer sono persistiti:

- nome;
- tipo;
- ordine nello stack;
- enabled;
- export_enabled;
- opacity 0.0–1.0;
- note.

I layer possono essere riordinati, modificati o eliminati.

## Asset layer per direzione

Ogni gruppo Direzione possiede uno stack indipendente `metadata.layer_stack`.

Un layer può ricevere:

- un singolo PNG/WebP;
- una sequenza di PNG/WebP proveniente da una cartella.

Per le sequenze R5e11 richiede dimensioni identiche per tutti i frame. Un mismatch blocca l'importazione anziché ridimensionare silenziosamente.

Gli asset vengono copiati nel workspace persistente:

```text
groups/<direction_group_id>/layers/<layer_id>/
```

con:

```text
layer_manifest.json
```

Il manifest conserva modalità, numero frame, dimensione, presenza alpha e percorsi dei file copiati.

Per ogni assegnazione sono inoltre disponibili:

```text
visible
offset_x
offset_y
```

## Non distruttività

R5e11 **non appiattisce i layer sui frame base** e non sostituisce le immagini già elaborate da R1/Clean-up/Alignment.

Lo stack costituisce una struttura persistente per:

- set completi di personaggi;
- outfit/equipment/effect separati;
- riuso futuro in export composito;
- successivo Rig Editor.

La milestone non introduce ancora compositing/baking nell'Export Studio: questo evita di alterare la pipeline di export già validata prima della successiva fase di riordino UI e ottimizzazione.

## Copia e duplicazione

La duplicazione di un gruppo Direzione copia anche la cartella `layers/` e rimappa i percorsi dei manifest al nuovo workspace.

`Copia dati da altra direzione` trasferisce anche lo stack layer della direzione sorgente e rimappa i path, mantenendo separati i file del gruppo destinazione.

Eliminando una definizione layer dal soggetto, R5e11 rimuove in modo coerente:

- la definizione globale;
- le assegnazioni di tutte le direzioni discendenti;
- le relative cartelle `layers/<layer_id>`.

I frame base restano intatti.

## Schema progetto

Il progetto viene migrato in memoria e salvato come:

```text
version: R5e11
```

Metadati soggetto:

```json
{
  "metadata": {
    "character_set": {
      "version": "R5e11",
      "layers": []
    }
  }
}
```

Metadati direzione:

```json
{
  "metadata": {
    "layer_stack": {
      "version": "R5e11",
      "assignments": {}
    }
  }
}
```

I progetti precedenti senza questi campi restano compatibili: lo stato Character Set viene inizializzato vuoto soltanto quando serve.

## Fuori ambito

R5e11 non implementa ancora:

- Rig 2D / bones;
- keyframe/interpolazione;
- mesh deformation;
- baking automatico dei layer nei frame sorgente;
- redesign generale della UI;
- ottimizzazione del painter Clean-up.

Questi punti restano separati per evitare regressioni prima di **R5e12 — UI Consolidation** e **R5e13 — Performance Audit & Optimization**.

## Test

La candidata R5e11 supera **163 test automatici**.

Nuove verifiche includono:

- lifecycle layer add/update/remove;
- riordino deterministico;
- normalizzazione e clamp opacità;
- matrice delle 8 direzioni;
- copertura assegnazioni layer;
- import singolo PNG/WebP;
- import sequenza con alpha;
- rifiuto di frame con dimensioni discordanti;
- persistenza Character Set;
- offset/visibilità per direzione;
- cleanup delle assegnazioni alla cancellazione;
- duplicazione gruppo con remap manifest;
- copia dati direzione con remap dei layer;
- regressione completa delle milestone precedenti.

## Validazione manuale consigliata

1. aprire un progetto con un soggetto e almeno due animazioni;
2. entrare in `13 · Character Set R5e11`;
3. verificare la matrice delle direzioni;
4. usare `Crea direzioni mancanti`;
5. aggiungere `Mantello` come `outfit` e `Arma` come `equipment`;
6. assegnare un PNG a una direzione;
7. assegnare una sequenza PNG a un'altra;
8. impostare offset e visibilità;
9. duplicare la direzione e verificare che i manifest puntino al workspace duplicato;
10. eliminare uno dei layer e verificare che scompaia da tutte le direzioni senza modificare i frame base.

## Branding Integration (R5c1a)

- App icon integrated from `assets/branding/app_icon.png` and `app_icon.ico`
- Splash screen integrated from `assets/branding/splash_screen.png`
- Dynamic splash metadata overlay for version, build, author, dependencies and license
- PyInstaller spec updated to embed the Windows application icon and bundle branding assets

## Windows Build Runtime Bootstrap (R5c1b)

The official Windows standalone build is reproducible on **Python 3.13 x64**, while the developer machine may use Python 3.14 or another version as its normal interpreter. `build_windows_standalone.bat` validates `.build-venv`, finds Python 3.13 when already installed, and can offer to install the required build runtime automatically without replacing the system's current Python. See `BUILD_RUNTIME_BOOTSTRAP_R5C1B.md`.

## R5c1c — Theme Preferences & Status Readability

R5c1c adds three persistent RGB-inspired tab themes (Red, Green, Blue), inverse tab backgrounds for contrast, the first File > Preferences dialog, a toolbar theme switch, and explicit white foreground for the status bar and dark status/info panels.

## R5c2 — CUDA / Storage / Paths Preflight

R5c2 adds the non-destructive compatibility gate used by the future local-AI installer. The preflight checks Windows x64, NVIDIA driver CUDA capability, path validity/writability and per-drive free-space requirements. GPU model, VRAM and system RAM are diagnostic only and do not block installation in R5c2.

The UI entry point is **File → Verifica runtime AI…**. The standalone executable also supports `--runtime-preflight <report.json>` with optional `--runtime-root` / `--model-root` overrides.

## R5c3e — Existing Runtime Adoption / Build Gate Scope

- Core regression/build fixtures no longer require PyTorch: the GPU/PyTorch guard is enforced only for real AI runtime bindings.
- Runtime Manager can detect/adopt existing WanGP installations without moving, renaming or re-downloading them.
- External runtimes store explicit Python/WanGP/model paths and are protected from managed repair/update/removal actions.
- See `R5C3E_EXISTING_RUNTIME_ADOPTION.md`.

## Windows Setup — R5c4

R5c4 adds `build_setup_windows.bat`, which first builds the canonical standalone Core and then compiles a real Windows installer with Inno Setup. The Setup supports Core, Complete R5c4 (Core + WanGP runtime + Wan Animate), and Custom modes. Before any heavy AI download it runs the existing preflight and can adopt a valid external WanGP installation without moving or redownloading it. See `WINDOWS_SETUP_R5C4.md`.


### R5c4a Inno Setup bootstrap hotfix

R5c4a hardens `build_setup_windows.bat`: Inno Setup can now be discovered from per-user/custom installations and the Windows registry, and WinGet “already installed/no update” statuses no longer abort the build before `ISCC.exe` is re-detected. See `R5C4A_INNO_DISCOVERY_HOTFIX.md`.


## Windows maintenance lifecycle — R5c6

R5c6 turns the validated Windows Setup line into a maintenance installer. Re-running the Setup updates/repairs the Core in place while preserving application data and AI assets by default. The runtime maintenance layer can repair a managed WanGP environment without selecting checkpoint downloads, and the uninstaller asks separately whether to remove the managed runtime, managed `wangp_ckpts`, or Sprite Studio settings/logs/cache/jobs. Adopted/external runtimes are always protected from destructive actions. See `R5C6_MAINTENANCE_LIFECYCLE.md`.

## Krea 2 managed component — R5c6a

R5c6a completes local Krea 2 Turbo integration using WanGP's current `krea2_turbo` model contract. The managed default is `Krea2Turbo_quanto_bf16_int8.safetensors` (~13.5 GB) from `DeepBeepMeep/krea-2`, while compatible checkpoints already present are reused in place. The Image Gen bridge receives a dedicated managed template (`model_type=krea2_turbo`, 8 steps, guidance 0). Krea Community License/AUP acceptance is explicit; any Hugging Face token is optional for the configured public WanGP checkpoint and is never persisted. External/adopted runtimes remain non-destructive and are not modified by Setup. See `R5C6A_KREA2_MANAGED_COMPONENT.md`.
## Windows Release Candidate hardening — R5c7

R5c7 is the pre-release hardening line built on the validated R5c6b baseline. It does not add a new production feature set: it tightens version/manifest coherence, removes Pillow deprecations, protects managed ZIP extraction against path traversal, and pins managed WanGP/Krea 2 upstream revisions for reproducible installs. Public release still requires the remaining license/compliance gates and the real Windows install/update/repair/uninstall matrix.

