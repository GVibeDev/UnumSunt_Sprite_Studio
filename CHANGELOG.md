## Phase 2 · P2-Ga — Validation Hotfix: Cleanup Alpha / Onion Bridge / Character Set Composite — 2026-09-05

- Fixed the Clean-up `Show Alpha on Checkerboard` Qt signal mismatch: the checkbox no longer forwards the emitted boolean into the keyword-only preview refresh API.
- Bridged the re-housed Alignment onion controls to the canonical shared CREATE canvas while preserving the existing AlignmentCanvas workflow. `Show Previous Frame` now drives shared-canvas Previous/Off and the opacity slider is mirrored to the shared onion opacity.
- Added a real, non-destructive Character Set composite preview path on the shared CREATE canvas.
- Added `Character Set composite (R2 + visible export layers)` as an Export Studio source. Export composition honours layer enabled/export flags, assignment visibility, opacity and X/Y offsets.
- Added strict Character Set layer validation: an assigned missing/invalid manifest is blocking, and animation-sequence frame counts must exactly match the active R2 frame count. No cycling, truncation or silent repair is performed.
- Moved Character Set composite orchestration into a dedicated controller so the MainWindow architecture guard remains unchanged.
- Automated candidate gate: `compileall` PASS; `pytest` 477 passed, 0 failed, 63 skipped, 36 subtests passed; `unittest` 540 tests OK, 63 skipped. Qt/PySide6-dependent tests remain skipped in the build environment and require Windows manual validation.

# Changelog

## Phase 2 · P2-G — CREATE Control Audit & Rehousing — 2026-09-05

- Promotes the manually validated reconciled P2-E/P2-F source to the Phase 2 input baseline.
- Adds one declarative audit/placement registry for all seven CREATE routes.
- Re-parents the existing control group widgets into persistent Source / Tools / Options / Configurations / Output route pages without duplicating engine implementations.
- Splits the former dense Alignment column across current-frame, view, geometry/profile and output pages.
- Splits Extract background/chroma secondary controls into the Options page and keeps R1 Export on Output.
- Collapses obsolete legacy control columns for Import, Extract, Clean-up and Align while preserving their production surfaces.
- Hides redundant Extract route-navigation buttons and the duplicate Import open-source button.
- Keeps specialized Clean-up and Alignment canvases on Current Workspace; shared-canvas tool-engine migration remains outside P2-G.
- Adds strict mismatch detection when an audited real workspace no longer contains exactly one expected control group.

## R5c7 — Validated Windows Release Candidate / Public Release Baseline — 2026-08-17

- Promotes the validated R5c6b line to the first distribution-ready Windows baseline.
- Adds the Windows standalone + Inno Setup release path with branded EXE, installer icon, wizard graphics and explicit Windows AppUserModelID.
- Completes Krea 2 Turbo managed integration and preserves Wan Animate / WanGP external-runtime separation.
- Adds Image Gen WanGP memory-profile and reserved-RAM controls with clearer CUDA OOM diagnostics.
- Fixes Production Preset refresh/save compatibility with current PySide6.
- Hardens Clean-up source transitions so Character/project changes cannot decode against a closed video source or re-enter QListWidget mutation callbacks.
- Removes deprecated Pillow `Image.fromarray(..., mode=...)` usage.
- Hardens managed ZIP extraction against absolute paths, drive paths, `..` traversal and symlink entries.
- Pins the managed WanGP source revision and Krea 2 model revision used by the validated runtime path.
- Validates standalone build, Setup build, Core and WanGP `pip check`, frozen version resources, embedded EXE icon, Setup checksum and frozen self-check.
- Validates install/startup, AI generation workflows, project/Character switching and conservative uninstall behavior on Windows.
- Licenses the project-owned Core as **GPL-3.0-or-later** and adds `LICENSE`, `THIRD_PARTY_NOTICES.txt`, release-license collection and GPL distribution guidance.
- Adds Krea pre-generation policy acknowledgement and post-generation manual review before an output can enter the WAN reference pipeline.

## R5c6a — Krea 2 Managed Component Completion

- Aligns Krea 2 Turbo with WanGP's current `krea2_turbo` contract and the Quanto BF16 INT8 checkpoint.
- Adds a managed Krea settings template and automatic Image Gen bridge binding.
- Reuses compatible WanGP Krea Turbo checkpoints already present before any network download.
- Keeps an optional Hugging Face token process-local and never persists it.
- Adds explicit Krea Community License/AUP acceptance to Runtime Manager and Windows Setup.
- Preserves adopted/external runtimes: Setup never modifies their model trees.
- Records Krea deployment safeguards as an R5c7 release gate.

## R5c6 — Repair / Update / Uninstall

- Added maintenance lifecycle CLI for status, managed-runtime repair and selective cleanup.
- Running Setup over the same AppId acts as Core update/repair while preserving user data outside the install tree.
- Setup remembers runtime/model paths and adoption/fallback choices, but never persists legal/TOS acceptance.
- Uninstaller offers independent opt-in removal of managed runtime, managed checkpoints and application data.
- External/adopted runtimes are protected from repair or deletion.
- Managed model cleanup is constrained to `model_root/wangp_ckpts`; unrelated files in the selected model disk are untouched.
- Krea 2 Setup completion remains outside this milestone.

## R5c4a — Inno Setup Discovery & WinGet Bootstrap Hotfix

- Fixed Inno Setup compiler discovery for per-user/custom Windows installations.
- Added registry discovery (`App Paths`, uninstall `InstallLocation`) and LocalAppData candidates.
- WinGet now tries the current `JRSoftware.InnoSetup.7` package first and re-probes `ISCC.exe` even after non-zero WinGet statuses such as “already installed/no update”.
- Added bootstrap contract regression tests.

## R5c4 — Windows Setup Bootstrapper
- added a real Inno Setup Windows installer build pipeline
- added Core / Complete / Custom install modes
- Setup orchestrates preflight, existing-runtime adoption, managed runtime install and final health check
- added CLI runtime discovery and automatic external runtime adoption
- Setup preserves external runtimes/models and never requires Python on target machines
- Krea 2 gated install remains scheduled for R5c5


## R5c3e — Build Gate Scope Correction & Existing Runtime Adoption
- GPU/PyTorch compatibility is now a hard gate only for real AI runtime bindings, never for mock/development fixtures used by Core regression tests.
- Added conservative discovery and manual adoption of existing WanGP installations without moving or renaming folders.
- Runtime install state v2 records managed/external ownership plus explicit Python/WanGP/settings paths.
- External runtimes are protected from managed repair/update/model-removal actions.

## R5c3c — Managed Animate Settings Template Hotfix
- bundled canonical Wan2.2 Animate settings template with `model_type=animate`
- managed runtime sync now replaces stale/generic video settings templates
- Runtime Health Check validates the managed Animate template contract
- Local WanGP health check rejects generic settings for a standard managed WanGP layout
- no runtime/model redownload required for migration from R5c3b
## R5c3 — Automated AI Runtime Installer / Model Manager
- added private Miniconda + Python 3.11.14 runtime bootstrap
- added PyTorch 2.10/cu130 and WanGP requirements installation
- added resumable Wan Animate checkpoint acquisition with frozen SHA-256
- added gated Krea 2 acquisition with transient Hugging Face token and explicit license acknowledgement
- added Runtime Manager UI, repair/update, health check and model removal
- added CLI runtime install/health operations for future Windows bootstrapper integration
- CUDA Toolkit/nvcc is detected as optional/non-blocking; `torch.cuda` is the base runtime health gate

## R5c2 — CUDA / Storage / Paths Preflight

- added a non-destructive local-AI preflight engine and UI dialog
- CUDA compatibility is checked from the NVIDIA driver capability exposed by `nvidia-smi`
- no GPU model, VRAM or RAM minimum is enforced in this milestone
- validates Windows paths, writability and required free space by drive
- component size plan moved to `assets/runtime/runtime_install_plan.json`
- added CLI JSON preflight for the future installer/runtime manager
- detects existing WanGP configuration without modifying it


### R5c1c startup stylesheet hotfix
- fixed `ExportStudio._update_background_swatch()` startup `NameError` caused by unescaped QSS braces in a Python f-string
- added static regression coverage for malformed dynamic stylesheet patterns

## R5c1c — Theme Preferences & Status Readability
- three persistent tab gradient themes: Red, Green and Blue
- inverse per-tab background gradient to improve contrast with the existing text gradient
- File > Preferences foundation with tab-theme selection
- toolbar theme switch Red → Green → Blue
- explicit white text for status bar and dark status/info labels

## R5c1b — Build Runtime Bootstrap
- locked the official Windows build runtime to Python 3.13 x64 without requiring it to be preinstalled
- validates and automatically recreates `.build-venv` when it uses the wrong Python version or is corrupted
- detects existing Python 3.13 through the legacy launcher, Python Install Manager, or explicit runtime alias
- adds interactive Python 3.13 installation through Python Install Manager
- can bootstrap Python Install Manager through WinGet when missing
- leaves Python 3.14 and all unrelated system runtimes untouched
- adds non-interactive switches for CI/release workflows

## R5c1a — Branding Integration
- integrated application branding assets under `assets/branding/`
- added app icon loading for source and frozen runs
- added startup splash screen with dynamic version/build/author/dependencies/license overlay
- configured PyInstaller to embed the Windows `.ico` and package branding assets
# R5c1 — Windows Standalone Core

- fondazione standalone Windows x64 con PyInstaller onedir;
- percorsi config/local-data centralizzati e compatibili con R5e;
- logging persistente in LocalAppData;
- `--self-check` del runtime congelato;
- build pipeline automatica con test, manifest, ZIP e SHA-256;
- runtime AI intenzionalmente esterno fino a R5c2/R5c3.

# Changelog — Unum Sunt Sprite Studio

## R5e13b — Painter & Core Performance Optimization

Baseline: **R5e13a validata**.

### Painter
- aggiunto painter ROI in-place per i dab del Clean-up;
- mantenuta API `paint_alpha_circle()` compatibile e pixel-identica a R5e13a;
- eliminata la maschera full-frame per ogni movimento del mouse.

### Stroke transaction
- lifecycle esplicito begin / dab / end;
- una snapshot iniziale e una sola transazione Undo per pennellata;
- `overrides_changed` emesso una volta al rilascio invece che a ogni dab;
- dipendenze R2/R3 e preview globali aggiornate una volta per stroke.

### Preview
- checkerboard regionale ancorato alle coordinate globali;
- `CleanupCanvas` con QImage persistente sul buffer NumPy;
- aggiornamento ROI e dirty-rectangle repaint;
- rimossa la `QImage.copy()` full-frame da ogni paint event.

### Profiling
- nuove metriche ROI/stroke;
- `run_windows_profile.bat` produce `performance_report_R5e13b.json`;
- benchmark sintetico 720×720: ~66× sul kernel dab ROI e ~385× sul checkerboard ROI rispetto ai rispettivi percorsi full-frame.

### Compatibilità
- nessuna nuova feature produttiva;
- nessun nuovo campo progetto obbligatorio;
- granularità Undo del pennello intenzionalmente modificata a 1 stroke = 1 transazione.

### Test
- **176 passed + 8 subtests**.


## R5e13a — Architecture Decomposition & Performance Instrumentation

Baseline storica di partenza: **R5e12 validata**.

### Decomposizione
- estratto `ChromaProfileController`;
- estratto `BackgroundRulesController`;
- `MainWindow`: 95 → 79 metodi, 2.022 → 1.885 righe;
- conservato nell'hub il wiring dei 14 workspace.

### Profiling
- aggiunto `PerformanceProbe` opt-in;
- report JSON opzionale via variabili d'ambiente;
- aggiunto `run_windows_profile.bat`;
- strumentati painter, preview, chroma, alignment, spritesheet e ProjectStore.

### Compatibilità
- nessuna nuova feature produttiva;
- nessuna ottimizzazione algoritmica anticipata;
- schema progetto R5e13a senza nuovi campi obbligatori.

### Test
- **171 passed**.

## R5e12 — UI Consolidation & Contextual Command System

Baseline: **R5e11 validata**.

### Aggiunto
- menu tradizionale File / Modifica / Progetto / Immagine / Video / Spritesheet / Preset / Esportazione;
- toolbar contestuale con visibilità per workspace;
- Command Policy centralizzata e testabile;
- etichette principali abbreviate con tooltip completi;
- gradiente cromatico dark→light per le tab;
- scorrimento/elisione delle tab su finestre strette.

### Genera
- pannelli `Generazione`, `Runtime WAN`, `Profili`;
- pannelli `Job / Output`, `Cronologia`;
- scroll verticale responsivo;
- `QFormLayout` con crescita dei campi e wrap delle righe lunghe;
- splitter riequilibrato a favore dei controlli di generazione.

### Comandi
- `Ctrl+S` salva il progetto;
- `Ctrl+Shift+E` esporta R1;
- shortcut R1 disabilitate fuori da Estrazione;
- azioni menu e toolbar condividono la stessa implementazione.

### Compatibilità
- logica R5e11 invariata;
- Guided Workflows R5e10 preservati;
- nessuna ottimizzazione prestazionale anticipata.

### Test
- **167 passed**.

## R5e11 — Character Set / Layer Manager

Baseline: **R5e10 validata**.

### Aggiunto
- workspace `13 · Character Set R5e11`;
- matrice Soggetto → Animazioni → 8 direzioni;
- creazione automatica delle direzioni mancanti;
- attivazione rapida dei direction group dalla matrice;
- layer logici subject-level con tipo, ordine, enabled, export flag, opacità e note;
- asset layer singolo PNG/WebP o sequenza;
- manifest per layer copiato nel workspace del Project Group;
- offset X/Y e visibilità per direzione;
- copertura delle assegnazioni;
- cleanup delle assegnazioni alla cancellazione;
- copy/duplicate compatibili con `layers/` e remap path.

### Compatibilità
- schema progetto R5e11;
- workflow R5e10 invariati;
- nessun baking distruttivo sui frame base;
- layer assenti nei progetti legacy = stack vuoto.

### Test
- **163 passed**.

## R5e10 — Guided Workflows / Workflow Router

Baseline: **R5e9 validata**.

### Aggiunto
- tre workflow ufficiali: Standard, Full AI-to-Sprite, Sprite Sheet Rework;
- workspace `12 · Workflow R5e10`;
- stato workflow persistente per Project Group;
- routing step-by-step ai workspace esistenti;
- rilevamento automatico del progresso;
- complete / reopen / skip manuali;
- checkpoint impostazioni persistenti;
- vista guidata opzionale dei tab;
- promozione del video intermedio a motion reference persistente;
- ripristino automatico del master image per la generazione finale;
- distinzione fra video intermedio e video finale.

### Compatibilità
- nessuna pipeline duplicata;
- provider R5e9 invariati;
- vecchi progetti caricabili senza workflow;
- Project Groups e Preset precedenti preservati.

### Test
- **150 passed**.

## R5e9 — Local Image Generation Provider

Baseline: **R5e8 validata**.

### Aggiunto
- workspace `11 · Image Generator R5e9`;
- `MediaGeneratorProvider` e `ImageGeneratorProvider`;
- Text-to-Image e Image-to-Image;
- Development Image Mock;
- Local WanGP Image Bridge;
- configurazione runtime immagine separata dal preset video;
- ereditarietà controllata del runtime WanGP video;
- normalizzazione output in `generated_image.png`;
- `image_generation_manifest.json`;
- passaggio automatico dell'immagine generata a Genera come reference WAN;
- persistenza R5e9 per Project Group;
- copia master/manifest nel workspace del gruppo.

### Compatibilità
- bridge video invariato;
- job immagine separati dalla cronologia Calibration video;
- progetti R5e8 migrati in memoria con campi opzionali vuoti.

### Test
- **140 passed**.

## R5e8 — Sprite Sheet Import / Decompose / WAN Reference Builder

Baseline: **R5e7 validata**.

### Aggiunto
- workspace `10 · Sprite Sheet R5e8`;
- import spritesheet PNG/WebP/BMP/TIFF;
- Grid slicer con dimensione frame, righe, colonne, padding, margine e ordine lettura;
- Auto-detect griglia conservativo e correggibile;
- atlas irregolari tramite alpha connected components;
- normalizzazione atlas su canvas comune;
- frame sequence source compatibile con la pipeline R1/R2/R3/R4;
- preservazione dell'alpha originale per sheet trasparenti;
- manifest persistente per Project Group;
- WAN Reference Sheet Builder;
- caricamento diretto della reference sheet nel workspace Genera;
- nuovi asset `source_sequence_manifest` e `source_spritesheet`.

### Sicurezza / compatibilità
- nessuna detection automatica viene resa irreversibile;
- frame con dimensioni miste vengono rifiutati prima di entrare nella pipeline;
- video e sprite sequence mantengono sorgenti distinte;
- i progetti precedenti vengono migrati in memoria alla versione R5e8;
- R5e7 e tutte le milestone precedenti restano coperte dalla regressione.

### Test
- **130 passed**.

## R5e7 — Prompt Builder & Prompt Profiles

Baseline: **R5e6 validata**.

### Aggiunto
- workspace `9 · Prompt Builder R5e7`;
- Action: Idle, Walk, Run, Attack, Interaction, Hurt, Death, Custom;
- Direction N/NE/E/SE/S/SW/W/NW;
- Motion Static/Subtle/Moderate/Strong;
- Camera Fixed/Fixed isometric/Fixed 3/4;
- Identity Preservation Normal/Strict/Very strict;
- Background Green/Magenta/Black/Custom RGB;
- Output Purpose Sprite extraction/Concept animation/Motion reference;
- 11 technical constraints indipendenti;
- composizione deterministica positive/negative prompt;
- editor finale sempre visibile e modificabile;
- applicazione a Genera solo tramite azione esplicita;
- caricamento del testo corrente da Genera senza ricomposizione;
- nuovo tipo `prompt` in ProfilesStore;
- starter Prompt Profiles Idle/Walk/Run/Attack/Interaction;
- protezione dalla cancellazione dei profili starter;
- metadata `prompt_profile_name` e `prompt_builder_state` nei Generation Profiles e nelle request;
- recupero metadata prompt nel Calibration Lab;
- trasferimento automatico nei Preset Produttivi generation-only.

### Compatibilità
- bridge WanGP invariato;
- R1/R5e5/Alignment/Export invariati;
- profili e progetti legacy compatibili;
- asset reference/motion restano esclusi dai Preset Produttivi.

### Test
- **115 passed**.

## R5e6 — Calibration Lab

Baseline: **R5e5-D validata**.

### Aggiunto
- workspace `8 · Calibration Lab R5e6`;
- sincronizzazione dei job generativi del Project Group attivo;
- snapshot manuale della configurazione Genera;
- rating, frame utilizzabili, verdetto e note;
- baseline A/B per gruppo;
- confronto di due run con diff dei soli parametri differenti;
- creazione di varianti a singolo parametro;
- preservazione automatica del seed nelle varianti non-seed;
- caricamento di run/varianti nel workspace Genera;
- promozione a Profilo Generazione;
- promozione a Preset Produttivo generation-only;
- persistenza `metadata.calibration` per Project Group;
- probe leggero OS/CPU/GPU NVIDIA quando disponibile;
- timing normalizzato dei Generation Job Snapshot.

### Compatibilità
- nessuna modifica al bridge WanGP;
- nessuna modifica ai contratti R1/R2/Export;
- riuso dei sistemi Profile Store e Production Presets esistenti;
- vecchi progetti compatibili con Calibration Lab vuoto.

### Test
- **106 passed**.

## R5e5-D — Cleanup Propagation & Transaction History

Baseline: **R5e5-C validata**.

### Aggiunto
- propagazione della stessa selezione a tutti i frame selezionati;
- pulsante `Propaga ai frame selezionati`;
- controllo di compatibilità dimensionale tra selezione e frame;
- blocco sicuro dell'operazione in caso di mismatch;
- storico Undo/Redo transazionale globale al Clean-up;
- una propagazione multi-frame = una singola transazione;
- supporto transazionale anche per pennello, clean-up automatico e reset;
- helper testabili per batch erase e compatibilità selezione.

### Modificato
- il tab Clean-up viene descritto come `R5e5-D`;
- `Del` continua a lavorare sul frame corrente;
- Undo/Redo non sono più solo per-frame ma per transazione;
- il cambio Project Group svuota storico e redo locali.

### Compatibilità
- painter, rettangolo e lasso restano invariati;
- override RGBA per gruppo preservati;
- nessuna propagazione parziale in caso di frame incompatibili.

### Test
- **99 passed**.

## R5e5-C — Cleanup Selection Tools

Baseline: **R5e5-B validata**.

### Aggiunto
- selezione rettangolare nel Clean-up;
- lasso poligonale deterministico;
- overlay visuale delle selezioni;
- cancellazione esplicita della selezione;
- `Del` per cancellare e `Esc` per annullare;
- chiusura lasso con doppio click o `Invio`;
- mapping delle geometrie in coordinate frame sorgente;
- shortcut `Ctrl+Z`, `Ctrl+Y`, `Ctrl+Shift+Z`;
- reset dello storico/transienti al cambio di Project Group.

### Test
- **96 passed**.

## R5c3b — Runtime Bridge Binding Hotfix
- fixed stale app-state runtime paths overriding the managed WanGP Python 3.11 environment
- added automatic bridge resynchronization from the managed runtime install state
- Runtime Manager now resynchronizes Generate and Image Gen after install/health check
- bridge binding rejects Miniconda base Python and targets `wangp_env/python.exe`
- WanGP health check now verifies PyTorch import before generation

## R5c3d — GPU Capability Guard & Runtime Compatibility Diagnostics
- Added direct GPU compute-capability verification against the architectures compiled into the managed PyTorch wheel.
- Runtime Manager Health Check now requires a compatible GPU ↔ PyTorch architecture contract for READY status.
- Managed Local WanGP health blocks real generation before process launch when the default CUDA device is unsupported by the installed wheel.
- Runtime preflight reports the same contract as READY/WARNING when a managed runtime already exists, without introducing arbitrary GPU model, VRAM or RAM minimums.
- Added diagnostics for `sm_XX`, PyTorch/CUDA versions and compiled architecture list.
