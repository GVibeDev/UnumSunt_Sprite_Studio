# Migrazione R5e6 → R5e7

R5e7 aggiunge Prompt Builder & Prompt Profiles senza modificare il bridge WanGP o i dati esistenti.

## ProfilesStore

Nuovo tipo supportato:

```text
prompt
```

I vecchi `profiles.json` vengono caricati normalmente; la sezione prompt viene inizializzata vuota e vengono aggiunti gli Starter R5e7.

## Generation Profile

Sono aggiunti due campi opzionali:

```text
prompt_profile_name
prompt_builder_state
```

Se assenti, il comportamento resta identico a R5e6.

## Request di generazione

I due metadata vengono salvati in `metadata` della request, senza alterare il contratto WanGP.

## Production Presets

La sanitizzazione generation già esistente conserva i nuovi metadata, ma continua a rimuovere `reference_image` e `motion_video`.

## Compatibilità progetto

La versione progetto viene aggiornata a R5e7 durante la normale migrazione in memoria. Nessun asset o Project Group viene modificato automaticamente.
