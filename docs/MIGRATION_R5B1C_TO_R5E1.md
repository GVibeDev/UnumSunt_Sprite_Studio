# Migrazione R5b1c → R5e1

R5e1 non sostituisce il bridge WanGP validato in R5b1c: lo incapsula in un primo modello di **progetto persistente**.

## Cambiamenti visibili

### Nuovo ordine dei tab
Da:

```text
0 Genera
1 Estrazione
2 Clean-up
3 Allineamento
4 Selezione intelligente
```

A:

```text
0 Progetto
1 Genera
2 Estrazione
3 Clean-up
4 Allineamento
5 Selezione intelligente
```

### Nuovo file di progetto
Ogni progetto usa:

```text
unum_sunt_sprite_project.json
```

che memorizza:

- metadati del progetto;
- asset principali;
- stato dei workspace;
- lista dei job salvati;
- fondazione per i gruppi futuri.

### Stato persistente dell'app
Lo store dei profili (`profiles.json`) ora conserva anche `app_state`, oltre ai profili e agli ultimi valori usati.

## Compatibilità

- i profili `chroma` e `alignment` esistenti restano validi;
- la configurazione locale WanGP resta compatibile;
- i job R5b1c già generati restano importabili;
- non è richiesta alcuna conversione dei manifest di generazione esistenti.

## Nuovi test
Sono stati aggiunti test specifici per:

- `ProjectStore`;
- profili `generation`;
- persistenza di `app_state`.
