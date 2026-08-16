# Migrazione R5e5-C → R5e5-D

R5e5-D aggiunge la propagazione multi-frame del Clean-up e sostituisce lo storico puramente per-frame con uno storico a **transazioni**.

## Cambiamenti principali

### UI
Nel pannello Clean-up la sezione passa da:

```text
Selezioni · R5e5-C
```

A:

```text
Selezioni e propagazione · R5e5-D
```

Con due azioni separate:

- `Cancella selezione (frame corrente)`
- `Propaga ai frame selezionati`

### Storico
Prima:
- undo/redo locale orientato al singolo frame.

Ora:
- undo/redo transazionale per l'intero Clean-up;
- una propagazione che tocca più frame si annulla/ripete in un colpo solo.

## Compatibilità
- i vecchi progetti R5e5-C restano apribili;
- gli override RGBA già esistenti restano validi;
- in assenza di propagazione, il comportamento operativo resta equivalente o più robusto.
