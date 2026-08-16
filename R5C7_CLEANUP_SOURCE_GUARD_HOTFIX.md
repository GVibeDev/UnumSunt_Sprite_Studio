# R5c7 — Clean-up Source Guard Hotfix

## Problema
Durante cambi di progetto/gruppo, chiusura o ripristino di una sorgente, un evento Qt del pannello Clean-up poteva tentare di ricaricare un frame dopo che `VideoSource` era già stato chiuso. Il risultato era un `VideoOpenError: Nessuna sorgente aperta.` non gestito.

## Correzione
- i frame selezionati vengono accettati solo se esiste metadata di una sorgente aperta;
- gli indici vengono filtrati sul range reale dei frame;
- il preview Clean-up verifica la sorgente prima del decode;
- una perdita transitoria della sorgente tra evento UI e decode viene intercettata come stato normale della UI;
- il pannello viene riportato a `Nessun frame` senza crash.

## Ambito
Nessuna modifica a generazione, export, runtime AI, modelli, dati utente o formato progetto.
