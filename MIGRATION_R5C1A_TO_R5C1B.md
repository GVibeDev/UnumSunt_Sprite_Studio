# Migration R5c1a → R5c1b

R5c1b non cambia i workflow produttivi dell'app. Modifica la pipeline di build Windows per renderla indipendente dalla versione Python principale installata sul PC di sviluppo.

- Python build ufficiale bloccato a 3.13 x64.
- rilevamento e validazione automatica di `.build-venv`;
- venv errato/corrotto ricreato automaticamente;
- rilevamento Python 3.13 già installato;
- prompt per installazione automatica se assente;
- Python Install Manager preferito per il bootstrap;
- bootstrap del manager tramite WinGet quando necessario;
- nessuna modifica al Python 3.14 o ad altri runtime già installati.
