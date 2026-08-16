# Unum Sunt Sprite Studio — Installazione rapida

## A. Versione SETUP — consigliata

### 1. Avvia l’installer

- [ ] Scarica `UnumSunt_Sprite_Studio_Setup_x64.exe`.
- [ ] Fai doppio clic sul file.
- [ ] Se Windows SmartScreen mostra un avviso, verifica il file e scegli **Ulteriori informazioni → Esegui comunque**.

### 2. Scegli il tipo di installazione

Puoi installare:

**Core**
- Sprite Studio soltanto.
- Nessun runtime AI locale.
- Nessun modello AI.

**Completa**
- Sprite Studio.
- Runtime AI locale.
- WanGP.
- Wan Animate.
- Krea 2 Turbo.

**Personalizzata**
- Scegli singolarmente Core, runtime e modelli.

### 3. Scegli le cartelle AI

Se installi il runtime locale, indica:

- **Runtime AI** — Miniconda, Python 3.11, PyTorch, WanGP.
- **Modelli AI** — Animate, Krea 2 e asset condivisi.

È possibile usare dischi differenti, per esempio:

```text
C:\...\ai_runtime
G:\AI
```

### 4. Controllo automatico

Prima dell’installazione AI Sprite Studio verifica automaticamente:

```text
Windows x64
Driver / CUDA
compatibilità GPU ↔ PyTorch
spazio disponibile
validità dei percorsi
permessi di scrittura
eventuali installazioni WanGP già presenti
```

### 5. Runtime già esistente

Se viene trovato un WanGP già funzionante:

```text
Runtime esistente
→ verifica
→ adozione
→ nessun nuovo download
```

Sprite Studio non rinomina, sposta o elimina il runtime esterno.

### 6. Nuova installazione automatica

Se non esiste un runtime utilizzabile, il Setup può installare automaticamente:

```text
Miniconda privata
↓
Python 3.11
↓
PyTorch + runtime CUDA
↓
WanGP
↓
Wan Animate
↓
Krea 2 Turbo, se selezionato
```

Non è necessario installare Python manualmente e il Python globale di Windows non viene modificato.

### 7. Licenze

Durante l’installazione possono essere richieste le accettazioni relative a:

```text
Miniconda / Anaconda
Krea 2 Community License
Krea 2 Acceptable Use Policy
```

L’eventuale token Hugging Face non viene memorizzato permanentemente da Sprite Studio.

### 8. Fine installazione

Il Setup installa automaticamente il Core e crea:

```text
Menu Start
eventuale collegamento Desktop
Uninstaller Windows
```

Avvia quindi **Unum Sunt Sprite Studio**.

### 9. Verifica finale consigliata

Dentro Sprite Studio:

```text
File
→ Gestione runtime AI…
→ Health Check
```

Se il risultato è `READY`, il runtime locale è operativo.

Per Wan Animate:

```text
Genera
→ Runtime WAN
→ Health Check
→ Dry-run
→ Generazione
```

Per Krea 2:

```text
Image Gen
→ Health Check
→ Generazione
```

### 10. Primo utilizzo AI

Al primo utilizzo WanGP può ancora scaricare automaticamente alcuni asset condivisi necessari al modello, per esempio encoder, VAE, cache o strumenti come FFmpeg.

Questo è normale e non significa che l’installazione sia incompleta.

---

# B. Versione STANDALONE — portabile

## 1. Scarica e decomprimi

- [ ] Scarica lo ZIP Standalone.
- [ ] Estrai **l’intera cartella** in una posizione permanente.
- [ ] Non avviare l’EXE direttamente dall’interno dello ZIP.

Esempio:

```text
D:\Apps\UnumSuntSpriteStudio\
```

### 2. Avvia Sprite Studio

Fai doppio clic su:

```text
UnumSuntSpriteStudio.exe
```

Non sono necessari:

```text
Python
pip
virtual environment
PySide6
OpenCV
NumPy
Pillow
```

Queste dipendenze del **Core** sono già contenute nella versione Standalone.

### 3. Se non vuoi usare l’AI locale

Non devi fare altro.

Puoi utilizzare normalmente:

```text
import video/spritesheet
estrazione frame
chroma key
cleanup
alignment
editing
spritesheet
export
progetti e preset
```

### 4. Se vuoi usare WanGP / AI locale

Apri:

```text
File
→ Gestione runtime AI…
```

### 5. Controlla prima eventuali installazioni esistenti

Premi:

```text
Rileva installazioni esistenti
```

Se compare il tuo WanGP:

```text
selezionalo
→ Adotta selezionato
→ Health Check
```

Se non viene trovato automaticamente puoi usare:

```text
Adotta manualmente…
```

e indicare:

```text
Python WanGP 3.11
wgp.py
cartella WanGP
cartella modelli
```

Non devi spostare o rinominare nulla.

### 6. Se non possiedi WanGP

Nel Runtime Manager scegli i componenti desiderati:

```text
Runtime base
Wan Animate
Krea 2 Turbo
```

poi avvia:

```text
Installa selezionati
```

Sprite Studio eseguirà automaticamente:

```text
Preflight
↓
Miniconda
↓
Python 3.11
↓
PyTorch / CUDA
↓
WanGP
↓
modelli selezionati
↓
configurazione bridge
↓
Health Check
```

### 7. Verifica

Al termine:

```text
Gestione runtime AI
→ Health Check
```

deve risultare `READY`.

Poi:

```text
Genera → Runtime WAN → Dry-run
```

oppure:

```text
Image Gen → Health Check
```

### 8. Primo utilizzo

Anche nella Standalone WanGP può acquisire al primo utilizzo alcuni asset condivisi aggiuntivi.

Lascia quindi sufficiente spazio libero sul disco dei modelli.

---

# In breve

## SETUP

```text
Setup.exe
→ scegli Core / Completa / Personalizzata
→ Preflight
→ adotta runtime esistente oppure installa automaticamente
→ installa modelli selezionati
→ avvia Sprite Studio
→ Health Check
→ pronto
```

## STANDALONE

```text
ZIP
→ estrai
→ UnumSuntSpriteStudio.exe
→ Core già pronto

Se vuoi AI locale:
File → Gestione runtime AI
→ adotta runtime esistente oppure Installa selezionati
→ Health Check
→ pronto
```

## Regola fondamentale

**Il Core di Sprite Studio non richiede Python né WanGP.**

Il runtime AI è un componente separato: può essere installato, adottato, riparato, aggiornato o rimosso senza reinstallare l’applicazione.