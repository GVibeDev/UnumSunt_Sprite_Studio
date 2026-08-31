# Migrazione R5e10 → R5e11

R5e11 mantiene integralmente i tre workflow R5e10 e aggiunge una struttura Character Set/Layer Manager sopra i Project Groups esistenti.

## Compatibilità

I progetti R5e10 sono caricati senza conversione distruttiva. Il Project Store li normalizza allo schema `R5e11` al successivo salvataggio.

Nuovi campi opzionali:

- `subject.metadata.character_set`
- `direction.metadata.layer_stack`

L'assenza di entrambi equivale a Character Set senza layer.

## Filesystem

I Project Group Direzione possono ora contenere:

```text
groups/<group_id>/layers/
```

Ogni layer importato usa una sottocartella propria e un `layer_manifest.json`.

## Nessuna modifica ai frame base

La migrazione non modifica video, sequenze importate, alpha override, alignment, export, job WAN, preset o workflow.
