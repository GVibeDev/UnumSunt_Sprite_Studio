# R5c6a — Image Memory Profile Hotfix TEST

Stato: **candidato di test**, non nuova baseline validata.

Base richiesta: `UnumSunt_Sprite_Studio_R5c6a`.

## Modifica

La patch aggiunge controlli dedicati alla memoria per il provider locale Image Gen / Krea 2:

- `Memory profile`: Auto oppure profili WanGP/mmgp 1–5;
- `Reserved RAM max`: Auto oppure valore 0.01–1.00;
- conversione controllata in argomenti CLI `--profile` e `--perc-reserved-mem-max`;
- rimozione automatica di eventuali duplicati degli stessi argomenti presenti in `extra_arguments`;
- persistenza in `local_wangp_image.json`;
- messaggio OOM più operativo senza alterare WanGP, modelli o runtime esterni.

## Applicazione

Estrarre questo ZIP **nella root del repository R5c6a** e consentire la sovrascrittura dei file esistenti.

La patch non modifica:

- runtime WanGP;
- checkpoint Krea 2;
- template Krea 2;
- configurazione video Wan Animate;
- installer;
- progetti utente.

## Primo test consigliato

In `11 · Image Gen` → `WanGP Image Runtime`:

1. `Memory profile = 5 — VeryLowRAM / LowVRAM`;
2. `Reserved RAM max = 0.20`;
3. salvare il runtime;
4. riprovare la stessa generazione che produceva CUDA OOM.

Se stabile ma troppo lenta, provare profilo 4 mantenendo inizialmente `0.20`.

## Test automatici eseguiti

- suite completa: **291 test OK**;
- test specifici hotfix: **4/4 OK**;
- regressione Krea 2 + hotfix: **15/15 OK**.

La validazione reale richiede ancora una generazione Krea 2 sulla macchina dell'autore.
