# Migrazione R5b1 → R5b1a

R5b1a è una hotfix compatibile con R5b1. Non modifica i profili, gli export o la logica di chroma key.

## Configurazione WanGP

Nel campo **WanGP root (cartella di wgp.py)** va indicata la directory che contiene:

```text
wgp.py
models/_settings.json
```

Esempio:

```text
C:\AI\WanGP_Standalone
```

Non usare una cartella di lavoro generica come `C:\AI\WORK`: l'output del job viene già passato con `--output-dir`.

Quando `wgp.py` e `models/_settings.json` sono presenti nella stessa root, R5b1a corregge automaticamente una configurazione precedente errata.

## Settings JSON ufficiali

È possibile continuare a usare il JSON esportato da WanGP. R5b1a riconosce il formato ufficiale e sovrascrive in modo controllato:

- prompt positivo e negativo;
- risoluzione;
- numero di frame;
- seed;
- step;
- immagine iniziale (`image_start`);
- video di controllo (`video_guide`).

Il modello, il checkpoint, guidance, solver, LoRA, `force_fps` e le altre impostazioni specialistiche restano quelli del preset WanGP.

## Sequenza di test

```text
Salva configurazione
→ Health check
→ Valida
→ Dry-run
→ Genera
```

Il report del job deve contenere `resolved_working_directory` e `template_binding`.
