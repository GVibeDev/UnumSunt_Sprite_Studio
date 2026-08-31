# Migrazione R5b1b → R5b1c

R5b1c parte dalla baseline validata `UnumSunt_Sprite_Studio_R5b1b` e non modifica il bridge WanGP già validato, il binding `image_refs`/`video_guide`, il chroma key o gli export.

## Scopo

Rimuovere le ambiguità tra i valori inseriti nello Sprite Studio e quelli realmente eseguiti da WanGP.

## Nuovo contratto della generazione

Nel tab **0 · Genera R5b1c** i campi Width e Height liberi sono sostituiti da:

- classe di risoluzione;
- rapporto d'aspetto;
- dimensione WanGP concreta e non modificabile.

La tabella integrata include le classi 360p, 480p e 720p nei rapporti 16:9, 9:16, 1:1, 4:3 e 3:4. Se nella root WanGP esiste `resolutions.json`, le opzioni locali valide sovrascrivono o estendono la tabella. La risoluzione del preset JSON corrente viene inoltre conservata quando non è già rappresentata.

## Frame

La UI mantiene il valore richiesto ma calcola prima del job il valore eseguito secondo la forma Wan `4n+1`, scegliendo il massimo valore compatibile non superiore alla richiesta.

Esempio:

```text
24 richiesti → 21 eseguiti
49 richiesti → 49 eseguiti
```

Il bridge scrive nel JSON WanGP direttamente il valore eseguito, evitando una seconda normalizzazione silenziosa.

## FPS

R5b1c distingue:

- FPS richiesti dall'utente;
- FPS previsti;
- origine del valore: richiesta, `force_fps` numerico del preset o frame rate del control video;
- FPS effettivi del file prodotto.

Con `force_fps=control`, lo Sprite Studio legge il frame rate del motion reference e lo mostra prima della generazione.

## Manifest e diagnostica

`request.json`, `provider_settings.json`, `status.json` e `generation_manifest.json` conservano il contratto richiesto, pianificato ed effettivo. Al termine vengono registrati anche i confronti:

- risoluzione pianificata vs reale;
- frame pianificati vs reali;
- FPS previsti vs reali.

## Uso consigliato

1. mantenere i percorsi WanGP già validati;
2. scegliere classe e rapporto;
3. controllare la dimensione concreta mostrata;
4. verificare frame e FPS previsti;
5. premere **Valida**;
6. avviare il test.
