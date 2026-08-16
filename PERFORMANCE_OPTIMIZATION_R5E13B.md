# Performance Optimization — R5e13b

## Hotspot affrontato

In R5e13a ogni dab del Pixel Painter comportava: copia RGBA full-frame, `ogrid` full-frame, nuova transazione Undo, aggiornamento override, emissione `overrides_changed`, ricomposizione preview e repaint.

R5e13b sostituisce il percorso con:

```text
stroke begin → snapshot once
mouse move   → ROI alpha edit + ROI checkerboard + dirty repaint
stroke end   → one override + one Undo transaction + one dependent refresh
```

## Metriche disponibili

Il Performance Probe registra, fra le altre:

- `cleanup.paint_alpha_circle`;
- `cleanup.paint_alpha_circle_roi_inplace`;
- `cleanup.paint_brush_event`;
- `cleanup.brush_stroke_commit`;
- `cleanup.render_checkerboard_region`;
- `cleanup.refresh_current_preview`;
- `ui.main_window.refresh_previews`.

## Benchmark sintetico di build

Frame 720×720, raggio 6, 200 dab: legacy ~562 ms; ROI in-place ~8,5 ms.
Checkerboard: 50 full-frame ~1352 ms; 50 ROI 15×15 ~3,5 ms.

Sono misure isolate nel container e servono come controllo tecnico, non come promessa di speed-up identico nell'intera GUI Windows. Il confronto più significativo resta il p95 del report R5e13a/R5e13b sul PC reale.
