# Migrazione R5e5-A → R5e5-B

R5e5-B aggiunge il secondo blocco della roadmap **Advanced Masking & Cleanup Propagation**: **Structural Mask Refinement**.

La baseline validata di partenza è `UnumSunt_Sprite_Studio_R5e5-A`.

## Nuovi campi Chroma/Alpha

```json
{
  "outer_border_mask_px": 0,
  "subject_edge_mask_expand_px": 0
}
```

Entrambi hanno default `0`, quindi un progetto o profilo precedente continua a usare il percorso R5e5-A.

## Bordo esterno forzato

`outer_border_mask_px = N` forza come background una cornice di N pixel sui quattro lati del frame. In `edge_connected` la stessa fascia viene anche usata come seed per le componenti di background collegate.

Il valore effettivo viene limitato a:

```text
min(width, height) // 4
```

## Rilevamento sagoma centrale

Il rilevatore analizza le componenti foreground e privilegia la componente maggiore che interseca una ROI centrale pari circa al 50% della larghezza × 70% dell'altezza. Se non esiste una componente centrale valida, usa come fallback la componente foreground maggiore non collegata ai bordi.

Sono rifiutate componenti troppo piccole o eccessivamente grandi, evitando erosioni distruttive alla cieca.

## Espansione background verso la sagoma

`subject_edge_mask_expand_px = N` erode il foreground della sola sagoma centrale rilevata con kernel ellittico di raggio N. Se la sagoma non è affidabile, l'operazione non viene applicata.

## Preview diagnostiche

R1 aggiunge:

- `Sagoma rilevata`
- `Sfondo candidato`

oltre alle preview già esistenti.

## Compatibilità

Con entrambi i nuovi parametri a zero, `create_alpha_mask()` esegue il percorso R5e5-A senza modifiche. La suite include un confronto pixel-identico.

I nuovi campi sono inclusi automaticamente in:

- profili Chroma/Alpha;
- Project Groups;
- Preset Produttivi;
- stato applicativo;
- manifest export.
