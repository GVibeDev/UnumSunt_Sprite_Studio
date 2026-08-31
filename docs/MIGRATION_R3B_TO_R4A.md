# Migrazione R3b → R4a

R4a aggiunge un sistema di profili persistenti per due aree:

- `chroma`
- `alignment`

Il file dei profili è indipendente dai file esportati e vive in una cartella utente di configurazione.

Non esiste ancora un file progetto completo: i ritocchi frame e gli override RGBA restano di sessione, mentre i profili di impostazione restano persistenti.
