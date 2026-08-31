# Migrazione R5e9 → R5e10

R5e10 non modifica il formato degli asset R5e9 né i contratti dei provider. Aggiunge un livello di orchestrazione persistente per Project Group.

## Schema progetto

La versione progetto passa a `R5e10`.

I direction group possono avere il nuovo campo opzionale:

```text
metadata.workflow
```

I progetti precedenti vengono caricati senza workflow e continuano a funzionare normalmente.

## Nuovo workspace

```text
12 · Workflow R5e10
```

Il workflow selezionato non duplica le pipeline: effettua routing verso i workspace già esistenti.

## Full workflow

Aggiunta una funzione di promozione del video corrente a motion reference persistente. Il file viene copiato nel workspace del gruppo e il master image R5e9 viene ripristinato come reference per la generazione finale.

## Compatibilità

- nessun modello AI incorporato;
- nessuna modifica al bridge video WanGP;
- nessuna modifica al bridge image R5e9;
- nessuna modifica ai formati R1/R2/Export;
- nessuna conversione distruttiva di progetti pre-R5e10.
