# Migrazione R5e12 → R5e13a

R5e13a è una milestone di **decomposizione architetturale e strumentazione prestazionale**. Non introduce nuove funzioni produttive e non modifica intenzionalmente il risultato di chroma key, clean-up, allineamento, workflow, Character Set o export.

## Decomposizione di MainWindow

La baseline R5e12 conteneva una `MainWindow` da 2.022 righe e 95 metodi. R5e13a estrae due responsabilità ormai autonome:

- `ChromaProfileController`: cattura/applicazione, ultimo profilo, elenco, salvataggio, caricamento ed eliminazione dei profili alpha/chroma;
- `BackgroundRulesController`: elenco, aggiunta, sampling, attivazione, tolleranza, rimozione e reset dei colori sfondo aggiuntivi.

Dopo l'estrazione `MainWindow` contiene 1.885 righe e 79 metodi. Il wiring fra i 14 workspace resta intenzionalmente nella finestra principale.

## Performance Probe

È stato aggiunto `app/performance_probe.py`, disattivato per default.

Per abilitarlo su Windows:

```bat
run_windows_profile.bat
```

oppure impostare manualmente:

```bat
set UNUM_SUNT_PERF=1
set UNUM_SUNT_PERF_REPORT=C:\temp\sprite_studio_perf.json
python main.py
```

Il probe raccoglie count, tempo totale, media, massimo e p95 degli hotspot strumentati. Il report viene scritto solo quando `UNUM_SUNT_PERF_REPORT` è esplicitamente definito.

## Hotspot strumentati

- `cleanup.paint_alpha_circle`
- `cleanup.paint_brush_event`
- `cleanup.refresh_current_preview`
- `ui.main_window.refresh_previews`
- `chroma.create_alpha_mask_with_diagnostics`
- `chroma.apply_chroma_key_with_diagnostics`
- `chroma.render_checkerboard`
- `alignment.resize_rgba_alpha_aware`
- `alignment.render_aligned_frame`
- `alignment.create_spritesheet`
- `spritesheet.auto_detect_regular_grid`
- `spritesheet.slice_regular_sheet`
- `spritesheet.detect_atlas_regions`
- `project_store.load`
- `project_store.save`

## Compatibilità

Lo schema progetto viene marcato R5e13a ma non vengono introdotti nuovi campi obbligatori. I progetti precedenti continuano a essere migrati mediante il normale `ProjectStore`.

R5e13a non contiene ancora l'ottimizzazione ROI del pennello né il raggruppamento di un'intera pennellata in una sola transazione Undo: questi interventi appartengono a R5e13b e verranno guidati dai dati raccolti dal profiler.
