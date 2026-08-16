# Migrazione R5e5-B → R5e5-D

R5e5-D aggiunge **Cleanup Selection Tools** senza modificare il keyer R1 validato in R5e5-B.

## Nuovi strumenti Clean-up

Nel workspace `3 · Clean-up R5e5-D` sono disponibili tre modalità:

- `Pennello`
- `Selezione rettangolare`
- `Lasso poligonale`

La selezione rettangolare usa drag mouse-down → mouse-up.

Il lasso poligonale usa click successivi per i vertici e viene chiuso con doppio click oppure `Invio`.

## Cancellazione

`Cancella selezione` oppure `Del` applica:

```text
RGBA[selected_pixels] = (0, 0, 0, 0)
```

La selezione non altera il frame finché l'utente non esegue esplicitamente la cancellazione.

## Coordinate

Tutte le geometrie vengono trasformate dal canvas zoomato alle coordinate del frame sorgente. Cambiare zoom non cambia quindi l'area sorgente selezionata.

## Undo / Redo

Le cancellazioni entrano nello storico locale già esistente del frame e sono ripristinabili con:

- `Ctrl+Z`
- `Ctrl+Y`
- `Ctrl+Shift+Z`

## Project Groups

Le selezioni sono transitorie e non vengono persistite. Il risultato della cancellazione continua invece a essere salvato tramite gli override RGBA per Project Group già validati.

Al cambio di Project Group vengono ora azzerati anche storico Undo/Redo e selezione transitoria, evitando contaminazioni tra contesti.

## Compatibilità

- nessuna modifica alla pipeline R1;
- nessuna modifica ai parametri R5e5-A/R5e5-B;
- painter esistente invariato;
- override esistenti ancora caricabili;
- propagazione della stessa selezione a più frame resta fuori ambito e sarà R5e5-D.
