# Migrazione R2a → R3a

R3a non modifica il formato degli export R1 o R2.

La nuova scheda **Selezione intelligente R3** lavora direttamente sul video
aperto e sulle impostazioni chroma correnti.

Quando cambiano le impostazioni chroma, l'analisi precedente viene marcata come
obsoleta e la cache del player viene invalidata. È necessario rieseguire
l'analisi per evitare di confrontare sagome ottenute con parametri differenti.

La selezione proposta da R3 non sostituisce automaticamente quella R1:
l'utente deve premere **Applica spuntati alla selezione R1**.
