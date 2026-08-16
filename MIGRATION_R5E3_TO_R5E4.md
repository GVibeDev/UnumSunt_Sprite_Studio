# Migrazione R5e3 → R5e4

R5e4 aggiunge Project Groups senza rimuovere il vecchio snapshot globale.

## Schema progetto

Nuovi campi:

```json
{
  "groups": [],
  "active_group_id": null
}
```

Ogni gruppo usa una struttura normalizzata con:

```text
id
parent_id
type
name
status
notes
created_at
updated_at
workspace
assets
pipeline_state
jobs
exports
metadata
```

## Gerarchia valida

```text
subject       parent = null
animation     parent = subject
direction     parent = animation
```

Solo `direction` può diventare gruppo attivo.

## Compatibilità progetti precedenti

I progetti R5e3 sono migrati in memoria automaticamente. Il vecchio blocco:

```text
assets
pipeline_state
jobs
```

rimane disponibile come fallback finché non viene creato un gruppo attivo.

## Clean-up

Gli override RGBA vengono salvati per gruppo in:

```text
groups/<group_id>/cleanup/rgba_overrides.npz
```

Il JSON conserva solo indice dei frame e path relativo.

## Allineamento

R5e4 conserva anche gli stati per-frame dell'allineamento, non soltanto il profilo globale.

## Job

I job vengono associati al gruppo che era attivo al momento dell'avvio, evitando che un cambio di gruppo durante l'inferenza sposti il risultato nel contesto sbagliato.

## Export

Gli export finali vengono registrati nello storico del gruppo attivo.
