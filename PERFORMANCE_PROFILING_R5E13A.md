# Performance Profiling — R5e13a

Il profiler di R5e13a è **opt-in** e non modifica il comportamento normale dell'app.

## Avvio rapido Windows

Eseguire:

```bat
run_windows_profile.bat
```

Alla chiusura dell'app viene generato `performance_report_R5e13a.json` nella cartella del progetto.

## Test consigliato prima di R5e13b

1. Aprire un progetto reale e un frame con alpha/clean-up.
2. Usare il pennello per almeno 10–15 secondi con tratti lunghi e brevi.
3. Cambiare più volte frame.
4. Aggiornare le preview chroma.
5. Aprire uno spritesheet e scomporlo.
6. Eseguire un allineamento/export rappresentativo.
7. Salvare il progetto e chiudere normalmente l'app.

Il report JSON consente di distinguere costo per evento, frequenza e picchi. R5e13b dovrà intervenire soltanto sugli hotspot dimostrati dai dati, mantenendo la regressione funzionale invariata.
