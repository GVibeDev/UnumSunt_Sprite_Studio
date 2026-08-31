# Migrazione R5e1 → R5e2

R5e2 amplia il punto finale dell'allineamento e dell'export. Il formato storico 96×96 resta il default, ma non è più un vincolo.

## Nuovo contratto dimensioni

```text
larghezza: 36–256 px
altezza:   36–256 px
```

Le dimensioni possono essere diverse tra loro.

## Profili precedenti

I profili R5e1 che contengono:

```json
{
  "canvas_width": 96,
  "canvas_height": 96
}
```

restano validi. I nuovi campi mancanti ricevono i default:

```json
{
  "output_size_preset": "square-96",
  "lock_aspect_ratio": false,
  "preserve_pivot_proportion": true,
  "auto_fit_on_resize": false
}
```

Valori storici inferiori a 36 o superiori a 256 vengono limitati automaticamente dai controlli UI.

## Pivot

Il nuovo comportamento predefinito conserva la posizione relativa del pivot quando cambia il formato. È possibile disattivarlo per mantenere le coordinate assolute.

## Export e manifest

Lo schema del manifest passa da:

```text
unum-sunt-sprite-studio-animation-v3
```

A:

```text
unum-sunt-sprite-studio-animation-v4
```

Il nuovo manifest aggiunge `geometry_diagnostics` e amplia `canvas` con forma, rapporto e intervallo supportato.

## Compatibilità

Non sono richieste conversioni per:

- job WanGP;
- video generati;
- frame selezionati;
- cleanup;
- chroma;
- progetti R5e1;
- manifest precedenti già esportati.
