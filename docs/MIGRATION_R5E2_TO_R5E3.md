# Migrazione R5e2 → R5e3

R5e3 aggiunge una vera fase finale di **produzione/export** senza rimuovere i flussi precedenti.

## Cambiamenti visibili

### Nuovo tab finale
Da:

```text
0 Progetto
1 Genera
2 Estrazione R1
3 Clean-up R3b
4 Allineamento R5e2
5 Selezione intelligente R3
```

A:

```text
0 Progetto
1 Genera
2 Estrazione R1
3 Clean-up R3b
4 Allineamento R5e2
5 Selezione intelligente R3
6 Export Studio R5e3
```

### Nuova logica di export finale
L'Export Studio non sostituisce:

- export R1;
- export R2.

Li completa, aggiungendo un livello finale orientato alla produzione degli asset già pronti all'uso.

## Stato persistente
Lo stato `export` ora comprende due sotto-blocchi:

- `r1`
- `studio`

Il blocco `studio` conserva l'intera configurazione dell'Export Studio.

## Compatibilità
- i progetti R5e1 / R5e2 restano apribili;
- in assenza del blocco `export.studio`, l'Export Studio usa i propri default;
- i manifest precedenti R1 e R2 non vengono convertiti né invalidati.
