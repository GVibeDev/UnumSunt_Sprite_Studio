# Migrazione R5a → R5b

R5b conserva il provider Mock e aggiunge `Local WAN / WanGP Bridge` nel medesimo workspace Generate.

La configurazione locale viene salvata separatamente dai job e contiene soltanto percorsi e opzioni del bridge. Non installa né modifica il runtime.

Per usare il provider reale servono:

- un ambiente Python WanGP già funzionante;
- `wgp.py`;
- un template JSON compatibile con la configurazione WanGP installata.

Per testare l'integrazione senza WanGP si può usare `tools/mock_wangp_cli.py`, disattivando temporaneamente i controlli rigidi Python 3.11 e template.
