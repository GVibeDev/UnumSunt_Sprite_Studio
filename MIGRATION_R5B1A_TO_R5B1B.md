# Migrazione R5b1a → R5b1b

R5b1b è una hotfix compatibile con R5b1a. Non modifica il chroma key, i profili, gli export o la root WanGP.

## Problema corretto

Il preset reale Wan 2.2 Animate usa `video_prompt_type: "PVBKI"`. La lettera `I` abilita la galleria **Reference Images**, che il loader CLI legge dal campo `image_refs`.

R5b1a collegava invece l'immagine a `image_start`. WanGP caricava correttamente il file, ma il validatore Animate non lo trovava nella galleria richiesta e terminava con:

```text
You must provide at least one Reference Image
```

## Nuovo binding semantico

R5b1b sceglie il campo immagine in base al preset:

- `video_prompt_type` contenente `I` oppure `model_type: animate` → `image_refs`;
- `image_prompt_type` contenente `S` → `image_start`;
- preset che richiedono entrambi → entrambi i campi;
- preset legacy senza selettori → fallback compatibile su `image_start`.

Il video guida continua a essere collegato tramite `video_guide`.

## Diagnostica processo

Gli errori WanGP scritti su stdout vengono ora riportati nel messaggio dell'app anche quando stderr è vuoto. Non sarà più mostrato soltanto “codice 1” quando il CLI ha già spiegato la causa.

## Configurazione utente

Non occorre cambiare i percorsi già validi. Aprire R5b1b, mantenere Python, `wgp.py`, root e preset, quindi eseguire **Valida** e **Genera**.
