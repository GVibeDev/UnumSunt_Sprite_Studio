# R5c7 — Clean-up Source Transition Hotfix 2

## Motivo
La prima Source Guard evitava il `VideoOpenError` Python, ma poteva modificare `QListWidget` sincronicamente durante `currentItemChanged`. Durante cambio Character Set / Project Group / progetto questa re-entrancy Qt può terminare il processo senza passare dall'exception hook Python.

## Correzione
- introduce uno stato esplicito `_source_transition`;
- `prepare_source_change()` mette in quiescenza il pannello Clean-up PRIMA che `VideoSource` venga chiuso o sostituito;
- tutte le mutazioni della lista frame critiche usano `QSignalBlocker`;
- `_on_frame_item_changed()` non ripopola, non svuota e non muta più la propria `QListWidget`;
- `MainWindow` chiama `prepare_source_change()` prima di `video.close()`, `video.open()` e `open_sequence_manifest()`;
- il cambio Project Group mette in quiescenza Clean-up dopo aver salvato lo snapshot del gruppo uscente.

## Ambito
Nessuna modifica a formati progetto, dati utente, runtime AI, modelli, generazione o export.

## Applicazione
Sovrascrivere questi file sulla R5c7 che contiene già la precedente Cleanup Source Guard, poi ricostruire standalone + Setup.
