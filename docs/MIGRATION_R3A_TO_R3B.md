# Migrazione R3a → R3b

R3b introduce override RGBA in memoria per i frame selezionati.

Questi override:

- vengono creati nella scheda **Clean-up R3b**;
- sono usati da export R1, preview del player R3 e preparazione di R2;
- non modificano il video sorgente;
- vengono persi chiudendo l'app (nessun salvataggio persistente in questa milestone).

Quando il clean-up cambia, l'allineamento R2 viene marcato come da aggiornare.
