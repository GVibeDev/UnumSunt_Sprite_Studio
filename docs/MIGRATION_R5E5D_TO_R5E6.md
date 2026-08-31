# Migrazione R5e5-D → R5e6

R5e6 non modifica il formato operativo dei frame, del chroma, del clean-up o dell'export. Aggiunge un sottosistema di calibrazione persistente.

## Nuovo tab

```text
8 · Calibration Lab R5e6
```

## Nuovi metadata Project Group

Ogni direzione può contenere:

```text
metadata.calibration
```

I progetti precedenti restano validi: in assenza del campo viene creato uno stato Calibration Lab vuoto in memoria.

## Generation Job Snapshot

Vengono aggiunti campi opzionali:

```text
started_at_utc
completed_at_utc
duration_seconds
```

I consumer precedenti possono ignorarli.

## Profili e preset

La promozione del Calibration Lab riusa:

- `generation` profiles;
- `pipeline` Production Presets.

Non viene introdotto un formato concorrente di preset.
