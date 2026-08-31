# Migrazione R5e4 → R5e4a

R5e4a mantiene integralmente i Project Groups validati in R5e4 e aggiunge un nuovo livello di configurazione riutilizzabile: i **Preset Produttivi**.

## Nuovo tab

```text
7 · Preset Produttivi R5e4a
```

## Compatibilità progetto
Il campo `version` del file progetto viene aggiornato a `R5e4a` al successivo salvataggio. Nessun gruppo R5e4 viene eliminato o trasformato.

## Metadata aggiuntivo opzionale
Una direzione può contenere:

```text
metadata.production_preset
```

che registra il nome del preset, le sezioni applicate e il timestamp.

## ProfilesStore
I Preset Produttivi utilizzano il namespace persistente `pipeline`, già previsto dall'architettura dei profili.

## Regola di migrazione fondamentale
Un Production Preset contiene **impostazioni**, non lo stato concreto di una produzione. Non vengono quindi trasferiti automaticamente:

- asset;
- job;
- export precedenti;
- video;
- frame scelti;
- cleanup manuale;
- offset/ancore specifici dei singoli frame.
