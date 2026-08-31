# Migrazione R4b → R5a

R5a aggiunge un nuovo workspace senza modificare i formati degli export precedenti.

## Nuove directory dati

Il Generation Job Manager crea una cartella utente indipendente per i job:

```text
UnumSuntSpriteStudio/generation_jobs/
```

La cartella contiene soltanto richieste, output, stati e log della generazione.

## Compatibilità

- profili chroma R4a: preservati;
- profili allineamento R4a/R4b: preservati;
- mirror export R4b: preservato;
- manifest R1/R2: aggiornano solo il campo `application_version` a `R5a`;
- nessun runtime AI viene installato in questa milestone.
