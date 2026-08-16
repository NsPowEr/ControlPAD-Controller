# ControlPad — il reverse engineering, e come si usa quello che ne è uscito

Controllo completo del **Cooler Master ControlPad** (`VID 0x2516` / `PID 0x007B`,
variante Cherry) senza il software ufficiale, che esiste solo per Windows.

Tutto quello che c'è qui è stato **ricavato per reverse engineering dalle
catture USB** in `captures/` e **verificato inviandolo al dispositivo vero**.
Dove qualcosa non è stato provato sull'hardware, è scritto esplicitamente.

> **Dove sta il codice.** La libreria vive in **`../ControlPadEngine/`**, che è
> anche quello che l'app macOS impacchetta dentro di sé. Questa cartella tiene
> le catture, il protocollo e gli strumenti che l'hanno decodificato: fino ad
> agosto 2026 ne teneva anche una copia dei moduli, e quella copia è rimasta
> indietro proprio sulla correzione che più contava — il `_send` che legge un
> ACK solo, cioè il difetto che per un giorno ha fatto credere non
> indirizzabili i quattro LED indicatori. Una sorgente sola, quindi.

---

## 1. Preparare il Mac

Servono Python 3 e una sola libreria.

```bash
# Python 3: se "python3 --version" risponde, è già a posto.
python3 --version

# la libreria che parla con i dispositivi HID
pip3 install hidapi
```

Se `pip3 install hidapi` fallisce lamentando la mancanza di una libreria di
sistema, installa prima quella nativa:

```bash
brew install hidapi
pip3 install hidapi
```

Poi collega il ControlPad. I comandi qui sotto si danno **da
`../ControlPadEngine/`**, dove stanno i moduli.

**Permessi**: il pad viene comandato attraverso la sua interfaccia
*vendor-specific*, non attraverso quella di tastiera, e su macOS quella non
richiede il permesso "Monitoraggio input". Se però qualcosa non funzionasse,
è la prima cosa da controllare in *Impostazioni di sistema → Privacy e
sicurezza*.

## 2. Verifica che tutto funzioni

Tre comandi, in ordine. Se arrivi in fondo, tutto il resto funzionerà.

```bash
cd ../ControlPadEngine

# 1. il Mac vede il pad?
python3 -c "import hid; print([d['path'] for d in hid.enumerate(0x2516, 0x007B)])"

# 2. accende il pad di rosso
python3 -c "from controlpad import ControlPad
with ControlPad() as p: p.set_static(255, 0, 0)"

# 3. anima i quattro LED in alto
python3 ../Come_usare_manipolare_i_4_led/anim.py

# 4. quello che si verifica senza avere il pad collegato
python3 -m unittest discover -s tests
```

Se il primo comando stampa una lista vuota, il pad non è collegato o il Mac
non lo vede: nessun motivo di proseguire finché non lo vede.

## 3. Com'è fatto il pad

24 tasti su una griglia 5×5 — l'ultima riga ne ha quattro perché lo spazio ne
occupa due posizioni — più due rotelle e quattro LED indicatori in alto.

```
   ROTELLA SX                      ROTELLA DX
                        ●  ●  ●  ●     ← 4 LED indicatori

   `     1     2     3     4
   Tab   q     w     e     r
   Caps  a     s     d     f
   Shift z     x     c     v
   Ctrl  ·     Alt   [   spazio   ]
```

I nomi nella griglia sono i **codici HID di default**: il pad emula la parte
sinistra di una tastiera QWERTY, e ogni tasto si identifica nei comandi con la
lettera che batterebbe. Il tasto in posizione (3,3) è `s`, cioè `0x16`.

### Le tre numerazioni — la trappola principale

Il dispositivo numera le stesse ventiquattro cose in **tre modi diversi**, e
confonderli è l'errore più facile e più difficile da diagnosticare:

| Numerazione | Dove si usa |
|---|---|
| **codice HID** | rimappature, assegnazione macro |
| **indice per colonne** | colori dei LED, tabella dei profili |
| **indice per righe** | ordine di caricamento della keymap |

Non fare i conti a mano: `layout.py` converte fra tutte e tre.

```python
from layout import tasto, indice_led, posizione

tasto(3, 3)        # 0x16  — il codice HID del tasto in riga 3, colonna 3
indice_led(3, 3)   # 16    — il suo LED nella tabella dei colori
posizione(0x16)    # (3, 3)
```

## 4. Cosa resta nel pad e cosa no

Questa distinzione decide l'architettura dell'app.

**Restano nel pad, per sempre** — macro, rimappature, funzioni speciali,
assegnazioni di profilo. Le scrivi una volta e vivono nel firmware: funzionano
anche staccando il pad, anche su un computer senza alcun software.

**Vanno riapplicati a ogni collegamento** — colori ed effetti. Non è un limite
di questa libreria: **non li memorizza nemmeno il software ufficiale**, che
infatti tiene un servizio sempre in esecuzione apposta per rimandarli quando
il pad si ricollega.

Quindi l'app fa una scrittura una tantum per la configurazione dei tasti, e un
piccolo processo che riapplica l'illuminazione all'avvio o al collegamento.

## 5. La libreria

### Illuminazione dei tasti — dal vivo

```python
from controlpad import ControlPad, led_index

with ControlPad() as pad:
    pad.set_static(255, 0, 0)                  # tutto il pad di rosso

    pad.set_effect(0x31, 0, 0, 255, speed=8)   # un effetto animato

    pad.set_grid({(0, 0): (255, 0, 0),         # (colonna, riga) da 0
                  (2, 2): (0, 255, 0)})        # gli altri si spengono

    pad.set_leds({led_index(2, 2): (255, 90, 0)})   # per indice di LED
```

Gli effetti animati li calcola il firmware: **un comando e basta**, non serve
alcun processo che invii fotogrammi.

### I 4 LED indicatori — gruppo separato

Hanno un comando tutto loro e **non fanno parte** della tabella dei tasti:
scrivere quella non li tocca. Nativamente indicano il profilo attivo, ma sono
liberamente pilotabili.

```python
with ControlPad() as pad:
    pad.set_indicators([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)])
```

Sono aggiornabili **167 volte al secondo** col commit `41 80` e **250** senza —
che per questi LED è facoltativo, a differenza del `41 04` che apre la
transazione — e niente di tutto ciò scrive in memoria permanente, quindi si
animano liberamente senza usurare nulla. Il rovescio della stessa medaglia è
che allo scollegamento tornano bianchi.

Il ritmo vero si ottiene però solo drenando la coda degli ACK, cioè leggendo
finché non torna l'opcode inviato: fermarsi al primo report che arriva sfasa le
letture e porta il pad ad ACKare senza più eseguire — è quello che per un
giorno li ha fatti credere non indirizzabili. Vedi
`Come_usare_manipolare_i_4_led/ANIMAZIONI.md` per i diciassette effetti finiti,
le primitive e le misure.

### Configurazione permanente

Una sola funzione scrive tutto insieme.

```python
from session import scrivi, FUNZIONI
from macro import events_for, events_for_combo, LCTRL, LALT, DEL
from layout import tasto, indice_colonne

scrivi(
    macros=[
        # (slot, tasto, eventi, nome)
        (8, tasto(1, 1), events_for("Ciao mondo"), "saluto"),
        (9, tasto(1, 2), events_for_combo([LCTRL, LALT, DEL]), "ctrlaltcanc"),
    ],
    remaps={
        tasto(2, 1): 0x3E,                      # diventa F5
        tasto(2, 2): FUNZIONI["volume_su"],     # diventa una funzione
    },
    profile_keys={
        indice_colonne(4, 1): 0,                # questo tasto attiva il profilo 1
    },
)
```

Gli **slot** delle macro sono progressivi e arbitrari: usa 8, 9, 10… Non sono
legati alla posizione del tasto.

Funzioni disponibili in `FUNZIONI`:

`play_pausa` · `stop` · `traccia_prec` · `traccia_succ` · `muto` ·
`volume_giu` · `volume_su` · `effetto_avanti` · `effetto_indietro` ·
`velocita_giu` · `velocita_su` · `luce_su` · `luce_giu` · `seleziona_profilo`

Le stesse funzioni valgono per le **rotelle**, che sono pseudo-tasti:
`ROTELLA_SINISTRA` e `ROTELLA_DESTRA` in `layout.py`.

## 6. Trappole da conoscere

Ognuna di queste è costata ore, e nessuna si deduce dai byte.

**La scrittura agisce sempre sul profilo attivo.** Se l'utente cambia profilo,
la configurazione appena scritta "sparisce" — non è persa, è in un altro
profilo. Mostra sempre nella GUI quale profilo si sta modificando: è il tipo
di confusione che fa sembrare rotto un programma che funziona.

**Un tasto selettore di profilo richiede due scritture**, l'azione nella
keymap e la voce nella tabella. `scrivi()` le fa entrambe se passi
`profile_keys`; se scrivessi la tabella da solo, il tasto conserverebbe
l'azione precedente.

**Non costruire la sessione da zero.** Anche con tutti i byte corretti il pad
la ignora *in silenzio*, rispondendo ACK regolari. Va usato lo scheletro
registrato in `skeleton.py`, sostituendo le sole parti che interessano — è
quello che fa `session.py`.

**Le pause contano.** Dopo ogni corpo macro servono ~72 ms: è la scrittura in
flash. Senza, il comando viene accettato e non ha alcun effetto.

**L'illuminazione ha 14 slot, non uno.** Statico, Onda arcobaleno, Mirino,
Dissolvenza reattiva, Personalizzata, Stelle, Neve, Ciclo colore, Lampeggio,
Pugno reattivo, Spettro circolare, Tornado reattivo, Ondulazione di acqua,
Spegni. Scrivere il colore di uno slot mentre il pad ne mostra un altro non
produce nulla di visibile.

**I colori dell'app non sono mai puri.** Un rosso scelto col selettore vale
`ff 19 28`, non `ff 00 00`. Se cerchi valori esatti nelle catture non trovi
nulla — è così che questo progetto ha perso un comando che aveva già in mano.

## 7. Costruire l'app

Le quattro parti che hai in mente, e cosa serve per ciascuna:

**Rimappatura di tutti i tasti fisici** — pronta. `remaps` accetta qualunque
codice HID, per tutti e 24 i tasti e per le rotelle. Verificato fino a sei
macro simultanee, ma non c'è più alcun limite legato allo scheletro: se ne
servono ventiquattro, funzionano.

**Funzioni speciali inseribili o meno** — pronta. Il dizionario `FUNZIONI`
copre media, retroilluminazione e profili; `NESSUNA_RIMAPPATURA` (`0x00FF`)
riporta un tasto al comportamento di fabbrica.

**Gestore colori ed effetti dei tasti** — pronta. Statico, colore per singolo
tasto e **tutte e quattordici** le modalità, comprese le sei reattive al tocco
col loro secondo colore: `set_mode()` rigioca il report registrato dall'app e
ne sostituisce i soli campi che l'utente controlla.

**Gestore dei 4 LED, gruppo separato** — pronta, animazioni comprese. È già un
gruppo indipendente a livello di protocollo: due comandi diversi, nessuna
interferenza.

## 8. Cosa manca ancora

Nessuna di queste blocca lo sviluppo. Le prime due si chiudono soltanto col
pad in mano; le altre hanno i dati già dentro `captures/`, senza tornare su
Windows.

- **Riassegnazione delle rotelle**: che siano pseudo-tasti della keymap è
  osservato, non dedotto — sono già assegnate di fabbrica in ogni cattura, con
  lo stesso comando `51 20` dei tasti. Scriverci sopra qualcosa di diverso non
  l'ha ancora provato nessuno.
- **Cambio profilo da software** (`51 00 00 00 <N>`): dedotto da due catture
  concordi, mai eseguito.
- **Profilo avanti/indietro**: i codici non compaiono in nessuna cattura. La
  selezione diretta di un profilo funziona e copre lo stesso bisogno.
- **Velocità degli effetti reattivi**: il byte è identificato (offset 36), ma
  quali valori abbiano senso per ciascun effetto non è stato esplorato.
- **Nome di una macro** (`51 19`): nelle catture è un byte solo, l'ASCII della
  lettera digitata. Che il campo ne accetti di più è plausibile e mai provato.

Risolte da quando questa sezione è stata scritta: i **nomi di tutte e
quattordici le modalità** e la **seconda forma del comando** usata dalle sei
reattive al tocco — entrambe in `../ControlPadEngine/effects.py`, con il
ragionamento che regge l'attribuzione.

## 9. I file

Il codice sta nel motore, `../ControlPadEngine/`:

| File | Cosa contiene |
|---|---|
| `controlpad.py` | comandi dal vivo: colori, effetti, LED indicatori |
| `session.py` | configurazione permanente: macro, rimappature, funzioni, profili |
| `effects.py` | le quattordici modalità di illuminazione, come le manda l'app |
| `macro.py` | codifica delle macro in eventi |
| `layout.py` | disposizione fisica e conversione fra le tre numerazioni |
| `skeleton.py` | la sessione registrata dall'app, usata come base |
| `effetti.py` · `indicatori.py` | primitive e effetti finiti dei 4 LED |
| `bridge.py` | busta JSON attorno a tutto il resto, per l'app macOS |
| `tests/` | quello che si verifica senza pad: `python3 -m unittest discover -s tests` |

Qui restano le fonti e gli strumenti:

| File | Cosa contiene |
|---|---|
| `PROTOCOL.md` | il protocollo byte per byte |
| `stato.html` | il punto della situazione, verificato contro dedotto |
| `test.py` | banco di prova a fasi, utile per verificare l'hardware |
| `captures/` | le catture USB grezze — **conservale**, sono la fonte di tutto |
| `analisi/` | strumenti usati per decodificare, richiedono tshark e Windows |

`captures/` è la cosa da non perdere: contiene ancora dati non decodificati, e
su macOS non è possibile registrarne di nuovi.
