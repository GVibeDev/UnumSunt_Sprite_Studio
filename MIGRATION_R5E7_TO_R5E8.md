# Migrazione R5e7 → R5e8

R5e8 aggiunge una nuova sorgente di pipeline: la **sprite frame sequence** ottenuta da uno spritesheet.

## Compatibilità progetti

I progetti precedenti vengono caricati senza modifiche distruttive. Lo schema asset aggiunge:

```text
source_sequence_manifest
source_spritesheet
```

I progetti che usano video continuano a usare `source_video`.

## Sequenze importate

Ogni sequenza persistente viene materializzata come PNG RGBA nel workspace del Project Group e descritta da `spritesheet_import/import_manifest.json`. Questo evita di dover rieseguire l'auto-detection alla riapertura.

## Alpha

Per sequenze con trasparenza reale, l'alpha dello spritesheet è usato come base non distruttiva. Le immagini completamente opache restano compatibili con il chroma key R1.

## Atlas irregolari

Le componenti di dimensioni diverse vengono normalizzate su un canvas comune prima dell'import; nessun resize silenzioso avviene dentro `VideoSource`.
