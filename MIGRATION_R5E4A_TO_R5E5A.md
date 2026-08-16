# Migrazione R5e4a → R5e5-A

R5e5-A estende lo schema chroma con un solo nuovo campo persistente:

```json
"additional_background_colors": []
```

Ogni elemento ha forma:

```json
{
  "rgb": [90, 20, 110],
  "enabled": true,
  "tolerance": null
}
```

`tolerance: null` significa che la regola usa la tolleranza principale.

## Compatibilità profili
I profili R5e4a non contengono questo campo. Al caricamento R5e5-A usa automaticamente una lista vuota: nessuna migrazione distruttiva è richiesta.

## Compatibilità Project Groups
I Project Groups salvano già la sezione `pipeline_state.chroma`. Il nuovo campo viene quindi mantenuto senza modificare la gerarchia soggetto → animazione → direzione.

## Compatibilità Preset Produttivi
I Preset Produttivi R5e4a catturano la sezione `chroma` come configurazione. In R5e5-A il nuovo campo entra automaticamente nel preset quando viene inclusa la sezione Chroma/Alpha.

## Invariante di regressione
Quando non esistono colori aggiuntivi abilitati, `create_alpha_mask()` e la decontaminazione usano il percorso legacy. La suite verifica la corrispondenza pixel-identica.
