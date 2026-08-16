# Migrazione R5e13a → R5e13b

R5e13b è una milestone di ottimizzazione mirata. Non cambia il formato dei Project Group, degli asset o degli export.

## Clean-up painter

Il dab del pennello usa ora una ROI locale e un buffer RGBA di lavoro per l'intera pennellata. L'algoritmo è coperto da test di equivalenza pixel-per-pixel rispetto a R5e13a.

## Undo/Redo

Cambiamento intenzionale: R5e13a produceva una transazione per ogni evento mouse; R5e13b produce una transazione per ogni pressione/trascinamento/rilascio. Questo riduce copie di memoria e rende Undo coerente con il gesto dell'utente.

## Preview

La scacchiera viene ricomposta solo nella zona modificata e il canvas aggiorna solo il dirty rectangle. Il QImage della preview non viene più ricopiato integralmente ad ogni paint event.

## Progetti esistenti

Nessuna migrazione dati obbligatoria. `ProjectStore` aggiorna la versione a R5e13b usando il normale percorso di migrazione.

## Profiling

Usare `run_windows_profile.bat`; il report predefinito è `performance_report_R5e13b.json`.
