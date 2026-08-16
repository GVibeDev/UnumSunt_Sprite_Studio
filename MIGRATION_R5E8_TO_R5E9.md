# Migrazione R5e8 → R5e9

R5e9 aggiunge la generazione immagini locale come sottosistema indipendente.

## Compatibilità

I progetti R5e8 vengono aggiornati in memoria allo schema R5e9. I nuovi campi sono opzionali e vengono inizializzati vuoti:

```text
pipeline_state.image_generation
assets.generated_image
assets.image_generation_manifest
```

Nessuna conversione dei dati R5e8 è distruttiva.

## Runtime

Il runtime video esistente non viene modificato. R5e9 crea una configurazione distinta:

```text
local_wangp_image.json
```

che può ereditare Python, `wgp.py` e root WanGP dal bridge video, mantenendo però un preset/settings JSON immagine indipendente.

## Provider

La base provider diventa:

```text
MediaGeneratorProvider
├── VideoGeneratorProvider
└── ImageGeneratorProvider
```

Le implementazioni video esistenti continuano a soddisfare lo stesso contratto operativo.
