# Migrazione R5b → R5b1

R5b1 è una patch compatibile con la baseline R5b.

## Profili preesistenti

I profili alpha/chroma R5b continuano a essere caricati. Quando il campo `keying_mode` non è presente, viene usato il valore predefinito `auto`.

## Template WanGP

I template esistenti continuano a funzionare senza modifiche. Per trasmettere esplicitamente il colore richiesto alla configurazione WanGP possono essere aggiunti:

```text
${BACKGROUND_HEX}
${BACKGROUND_RGB}
${BACKGROUND_RGB_LIST}
${BACKGROUND_R}
${BACKGROUND_G}
${BACKGROUND_B}
```

Il campo esatto in cui inserirli dipende dallo schema JSON esportato dalla propria versione e dal modello WanGP.

## Import del video

Quando il video proviene da una cartella job della suite, R1 legge `request.json` o `generation_manifest.json`, recupera il colore richiesto e lo confronta con il colore effettivo.

## Compatibilità

Gli export R1/R2, i ritocchi alpha, l'allineamento, la selezione intelligente, il mirror laterale e il bridge locale rimangono compatibili.
