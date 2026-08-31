# Migrazione R5e13b → R5c1

R5c1 non modifica i workflow produttivi. Introduce la fondazione di distribuzione Windows standalone.

- baseline funzionale preservata: R5e13b;
- percorsi config/job/runtime centralizzati e sempre scrivibili in area utente;
- logging persistente per build `--windowed`;
- self-check del binario congelato;
- PyInstaller spec canonico `onedir`;
- pipeline Windows che testa, compila, self-checka, manifesta, comprime e calcola SHA-256;
- nessuna dipendenza AI incorporata in R5c1.

La compatibilità dei file profilo/progetto precedenti è mantenuta. Il version tag del progetto viene migrato a `R5c1` al successivo salvataggio secondo il comportamento già adottato dalle milestone precedenti.
