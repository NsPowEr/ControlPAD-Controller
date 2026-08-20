# Cooler Master ControlPad — protocollo USB

Ricavato per reverse engineering dalle catture in `captures/`, verificato
inviando i comandi al dispositivo e osservando il risultato fisico.

Modello: **Controlpad (Cherry)**, `VID 0x2516` / `PID 0x007B`.
Nota: l'issue OpenRGB #2448 riguarda il PID `0x012D` (variante Gateron) e non
è mai stata implementata; quanto segue è indipendente da quel lavoro.

## Canale di comunicazione

| Proprietà | Valore |
|---|---|
| Interfaccia | `MI_01` — usage page `0xFF00` (vendor-defined) |
| Endpoint | `0x04` OUT, `0x83` IN, interrupt |
| Dimensione report | 64 byte |
| Report ID | nessuno (unnumbered) |

Con hidapi va anteposto un byte `0x00` di report ID, quindi ogni `write()`
passa 65 byte. Le altre interfacce (`MI_00`, `MI_02`) sono la tastiera
standard e i controlli multimediali: non accettano questi comandi.

Ogni report OUT riceve un ACK sull'endpoint IN con l'header riecheggiato e il
resto azzerato (`56 83 ...` → `56 83 00 00 ...`). Il device emette anche
report non richiesti che iniziano per `ff aa`, presumibilmente stato di tasti
e rotelle: vanno ignorati, non sono errori.

## Comandi

| Opcode | Funzione |
|---|---|
| `56 81` | handshake / apertura sessione |
| `56 83` | scrittura colore |
| `41 80` | commit |
| `51 28 00 00 ff` | apply (`ff` applica, `00` rilascia) |
| `56 15`, `56 21` | blob profilo/keymap — **non ancora decodificato** |

L'handshake esiste in due varianti e **seleziona la modalità**:

```
56 81 00 00 01 00 00 00 01 00 00 00 55 55 55 55   colore statico
56 81 00 00 01 00 00 00 02 00 00 00 bb bb bb bb   tabella per-tasto
```

Usare l'handshake statico per una scrittura per-tasto non fallisce in modo
esplicito: si accendono solo i tasti trasportati dal primo chunk, il che rende
il sintomo facile da interpretare male.

### Colore statico

Un solo report, RGBA a offset 16 — il quarto byte è la luminosità e a zero
spegne il LED indipendentemente da RGB:

```
56 83 00 00 01 00 00 00 00 01 00 c1 00 00 00 00 | RR GG BB AA
```

### Tabella per-tasto

Distinta dallo statico dal byte 8 (`0x80` invece di `0x00`) e dal byte 11
(`0x00` invece di `0xc1`). Il buffer dati è di 112 byte spezzato su due
report; il secondo ha un header più corto e un LED può stare a cavallo dei
due chunk:

```
chunk 0:  56 83 00 00 01 00 00 00 80 01 00 00 | dati[0:52]
chunk 1:  56 83 01 00                         | dati[52:112]
```

Dentro il buffer i colori sono **terzine RGB da 3 byte**, senza luminosità —
a differenza del comando statico. I primi 12 byte sono un prefisso fisso
(`ff 00 00 00 00 00 ff ff 00 00 00 00`): azzerarlo costa i tasti trasportati
dal secondo chunk.

I tasti della griglia partono dalla terzina 4 e proseguono **per colonne**,
dall'alto in basso e poi verso destra:

```
indice = 4 + colonna * 5 + riga        (entrambi 0-based, origine in alto a sinistra)
offset = indice * 3
```

I 4 LED sopra il pad **non** fanno parte della tabella: qualunque cosa si
scriva qui non li tocca, perché hanno un indirizzo proprio — vedi "LED
indicatori di profilo".

## Sequenza completa

```
handshake  →  chunk 0  →  chunk 1  →  commit  →  apply
```

## Macro e rimappatura

Le macro **non** passano dal blob di profilo `56 21`: hanno comandi propri. Il
confronto del blob fra la baseline e una cattura con macro mostra differenze
solo nelle regioni di colore.

Sono salvate nel **firmware**: premendo il tasto è il device stesso a emettere
i codici sull'endpoint tastiera `0x81`, senza software attivo sull'host. Una
volta scritta, quindi, la configurazione funziona su qualunque sistema.

### Identificazione dei tasti

Ogni tasto ha un **codice HID di default** che lo identifica nei comandi, ed è
disposto come la porzione sinistra di una tastiera QWERTY. Ordine di upload
(`51 20` / `51 80`), per **righe**, indici 0-23:

| Riga | Codici HID |
|---|---|
| 1 | `35` \` · `1e` 1 · `1f` 2 · `20` 3 · `21` 4 |
| 2 | `2b` Tab · `14` q · `1a` w · `08` e · `15` r |
| 3 | `39` Caps · `04` a · `16` s · `07` d · `09` f |
| 4 | `e1` LShift · `1d` z · `1b` x · `06` c · `19` v |
| 5 | `e0` LCtrl · `c0` · `e2` LAlt · `2c` Space (tasto largo) |

L'ultima riga ha 4 tasti perché lo Space occupa due posizioni: 5+5+5+5+4 = 24.

Il comando `51 94` fornisce la tabella di traduzione fra codice HID e indice
**per colonne** — la stessa numerazione usata dai LED e dai report di
pressione (`43 01 00 00 <indice> <stato>`, `c0` premuto / `40` rilasciato).

### Formato di una macro

```
53 00 <n_eventi> 00 | evento × n
```

Ogni evento è di 4 byte: `[codice_HID, tipo, delay_lo, delay_hi]`, con il
ritardo in millisecondi su 16 bit little-endian e tipo `3c` = pressione,
`5c` = rilascio. L'ultimo evento `00 fc fe ff` è il terminatore.

Esempio reale — una macro che digita `A`:

```
e1 3c 96 04    LeftShift  premuto     delay 1174 ms
04 3c 08 01    'a'        premuto     delay  264 ms
04 5c 28 00    'a'        rilasciato  delay   40 ms
e1 5c 00 00    LeftShift  rilasciato  delay    0 ms
00 fc fe ff    terminatore
```

I ritardi sono quelli registrati durante la creazione della macro nell'app.

### Assegnazione a un tasto

```
51 18 <slot> 00 <codice_HID_tasto> 3c     lega lo slot al tasto
51 19 <slot> 00 41 00                     proprietà della macro
53 00 <n> 00 <eventi>                     corpo della macro
```

Il tasto è identificato dal suo **codice HID di default**, non dall'indice.
Prima delle assegnazioni l'app azzera tutti e 24 gli slot con
`51 18 <i> 00 ff 3f` per `i` da 0 a 23.

Gli slot sono allocati in modo **sequenziale e crescente** man mano che si
assegnano macro (4-5, poi 7, poi 8-9-10-11 nelle catture successive): non sono
legati alla posizione del tasto. Il byte di `51 19` vale `41` per la macro che
digita `A` e `5a` per quella che digita `Z`, cioè l'ASCII della lettera —
verosimilmente l'etichetta della macro, da confermare con una macro dal nome
non banale.

L'app riscrive **l'intero stato** a ogni applicazione, non solo la modifica:
ogni cattura contiene tutte le assegnazioni correnti.

### Rimappatura semplice

Non usa le macro ma la tabella keymap, un'entrata per tasto seguita dal suo
indice:

```
51 20 <codice_default> 00 <codice_assegnato> 00
51 80 <indice> 00
```

Con `ff` come codice assegnato il tasto mantiene il comportamento di default.
Rimappare il tasto in alto a sinistra su F5 cambia un solo byte:

```
51 20 35 00 ff 00   →   51 20 35 00 3e 00
```

### I 14 slot di illuminazione

Il profilo non contiene un'illuminazione sola: ne contiene **14 configurazioni
indipendenti**, più l'indice di quella attiva. La tabella `56 15` che l'app
invia prima del blob dati ha esattamente 14 voci, una per slot:

```
56 15 <slot> 00 <tipo> 00 <offset a 16 bit> <marcatore a 32 bit>
```

| Slot | Nome nell'app | Tipo | Offset | Dim. | Marcatore |
|---|---|---|---|---|---|
| `00` | Statico | 1 | 4 | 6 | `55555555` |
| `01` | Onda arcobaleno | 1 | 10 | 12 | `55555555` |
| `02` | Mirino | 2 | 22 | 12 | `00000000` |
| `03` | Dissolvenza reattiva | 2 | 34 | 29 | `00000000` |
| `04` | Personalizzata | 1 | 63 | 11 | `bbbbbbbb` |
| `05` | Stelle | 2 | 74 | 13 | `00000000` |
| `06` | Neve | 2 | 87 | 8 | `00000000` |
| `07` | Ciclo colore | 1 | 95 | 6 | `55555555` |
| `08` | Lampeggio | 1 | 101 | 9 | `55555555` |
| `09` | Pugno reattivo | 2 | 110 | 9 | `00000000` |
| `0a` | Spettro circolare | 1 | 119 | 7 | `55555555` |
| `0b` | Tornado reattivo | 1 | 126 | 10 | `55555555` |
| `0c` | Ondulazione di acqua | 2 | 136 | 5 | `00000000` |
| `0d` | Spegni | 1 | 141 | — | `aaaaaaaa` |

Il **tipo 2** raccoglie gli effetti reattivi al tocco, che infatti occupano più
spazio: la Dissolvenza reattiva ne richiede 29 byte contro i 6 dello Statico.

Gli effetti si dividono in due famiglie, che corrispondono alla colonna tipo.
**Entrambe sono decodificate**; l'attribuzione dei nomi regge su tre riscontri
indipendenti, spiegati in `ControlPadEngine/effects.py`: l'ordine delle
selezioni nella cattura `16_tutti_gli_effetti.pcapng` segue esattamente la
lista dell'app, la spartizione otto/sei coincide con la colonna tipo qui
sopra, e i marcatori unici `bbbbbbbb` e `aaaaaaaa` cadono davanti a
Personalizza e Spegni, che nella lista stanno in quinta e quattordicesima
posizione.

**Tipo 1** — otto modalità, un colore solo:

```
56 83 00 00 | 01 00 00 00 | 00 <id> 00 c1 | <vel> 00 00 00 | R G B A | <parametri>
```

| id | Modalità | | id | Modalità |
|---|---|---|---|---|
| `01` | Statico | | `31` | Ciclo colore |
| `32` | Onda arcobaleno | | `34` | Spettro circolare |
| `30` | Lampeggio | | `83` | Tornado reattivo |
| `00` | Spegni (byte 8 = `10`) | | — | Personalizza: tabella per-tasto |

**Tipo 2** — sei modalità, tutte reattive al tocco, **due colori**:

```
56 83 00 00 | <len> 00 <len> 00 | 03 00 00 00 | … | R G B A (offset 24) |
… | <vel> (offset 36) | R G B A (offset 40) | …
```

`<len>` è la lunghezza del payload in parole da 4 byte (`0b`–`0d`), non un
numero di slot. Le sei modalità — Mirino, Dissolvenza reattiva, Stelle, Neve,
Pugno reattivo, Ondulazione di acqua — si distinguono per la combinazione dei
byte agli offset 32, 33, 46 e 47; i template registrati stanno in `effects.py`
e vengono rigiocati sostituendo solo colori e velocità.

Il **secondo colore** è la ragione per cui queste modalità hanno due selettori
nell'app: sono effetti che rispondono alla pressione, quindi hanno un colore di
fondo e uno di reazione. Che l'offset 36 sia la velocità si vede nella cattura,
dove passa da `0c` a `02` e ritorna senza che cambi nient'altro.

Il quarto byte di ogni colore è la luminosità: nelle catture scorre da sola
mentre si trascina il cursore, con RGB fermo.

**Selezionare un effetto non scrive il profilo**: l'app manda solo il comando
dal vivo. Non esiste quindi un campo "slot attivo" da salvare, e infatti
l'illuminazione non sopravvive allo scollegamento — nemmeno impostata
dall'app. Cooler Master aggira la cosa con un servizio residente che
riapplica tutto quando il pad si ricollega; una GUI su macOS può fare lo
stesso, mentre macro e rimappature stanno in flash e non vanno riscritte.

Il **marcatore** è lo stesso valore che compare nell'handshake `56 81`, e
serve a selezionare lo slot su cui si sta scrivendo. Questo spiega perché la
tabella di colori per singolo tasto pretendeva l'handshake con `bbbbbbbb`
invece di `55555555`: non è una modalità a parte, è lo slot *Personalizzata*.

Scrivere il colore senza tenere conto dello slot attivo non produce alcun
effetto visibile: la modifica finisce in una delle 14 configurazioni, e se il
pad ne sta mostrando un'altra non cambia nulla. Gli offset qui sopra vanno
ancora confermati contro il blob dati.

### Funzioni speciali e rotelle

Il campo azione di `51 20` è a **16 bit**: sotto `0x0100` è un codice tasto HID,
da `0x0100` in su è una funzione interna del dispositivo.

Oltre alle 24 entrate dei tasti, la tabella ne contiene 4 senza indice `51 80`
associato: sono le **due rotelle**, una coppia per verso.

Tabella completa, ricavata assegnando tutte le funzioni in una sola sessione:

| Codice | Funzione | | Codice | Funzione |
|---|---|---|---|---|
| `00ff` | nessuna rimappatura | | `0181` | Effect cycle + |
| `00f0` | Play / Pausa | | `0182` | Effect cycle − |
| `00f1` | Stop | | `0190` | Speed down − |
| `00f2` | Traccia precedente | | `0191` | Speed up + |
| `00f3` | Traccia successiva | | `0192` | LED brighter + |
| `00f4` | Muto | | `0193` | LED darker − |
| `00f5` | Volume − | | `0110` | Seleziona profilo |
| `00f6` | Volume + | | | |

Le due rotelle compaiono come pseudo-tasti: `c6`/`c7` la sinistra, `f5`/`f6`
la destra. Accettano gli stessi codici dei tasti, quindi si riassegnano con lo
stesso comando.

Rileggendo tutte le catture e filtrando i soli `51 20` su quei quattro codici,
le rotelle risultano **già assegnate di fabbrica**, coerentemente in ognuna:

| Pseudo-tasto | Azione osservata | |
|---|---|---|
| `c6` | `0192` | LED più luminoso |
| `c7` | `0193` | LED più scuro |
| `f5` | `00f5` | Volume − |
| `f6` | `00f6` | Volume + |

Quindi la loro presenza nella keymap non è dedotta: è osservata, con lo stesso
comando dei tasti. Resta da provare la **riassegnazione**, che nessuna cattura
mostra.

Nessun codice di *scorrimento rotella del mouse* compare in nessuna cattura:
tutte le azioni `≥ 0x0100` viste sono quelle già in tabella. Sotto `0x0100` il
campo azione è un usage HID di tastiera, che non ha modo di esprimere uno
scroll. Se quella funzione esiste nel software ufficiale, va catturata da
Windows assegnandola davvero.

### Tasti che selezionano un profilo

Il codice `0x0110` dice soltanto "questo tasto cambia profilo": **quale**
profilo sta in una tabella a parte.

```
51 90 00 00 <24 byte, uno per tasto, indice per colonne>
```

Ogni voce contiene il numero di profilo (da 0) che quel tasto attiva; il
valore predefinito è l'identità, che equivale a nessuna assegnazione. È la
stessa numerazione per colonne usata dai LED, non quella per righe della
tabella keymap.

Restano da identificare i codici di *profilo avanti* e *profilo
indietro*: vedi "Profilo + e profilo −: codici ancora ignoti".

### LED indicatori di profilo

I 4 LED sopra il pad non fanno parte della tabella per-tasto — scriverla a
nero non li spegne — perché hanno un indirizzo proprio, `0x00fc`, dodici byte
in quattro terzine RGB. La forma generale è
`55 <operazione> <indirizzo a 16 bit LE> <lunghezza>`:

```
41 04                                      apre la transazione — obbligatorio
55 50 fc 00 0c  <R G B> × 4                scrive i dodici byte
41 80                                      commit — facoltativo

55 40 fc 00 0c   →   55 40 fc 00 0c <R G B> × 4      rilegge
```

Provando le quattro combinazioni: senza `41 04` la scrittura non viene nemmeno
ACKata; il `41 80` invece non serve, e ometterlo porta il fotogramma da 6,00 a
4,00 ms — 250 aggiornamenti al secondo. Il device non applica curve proprie:
rilegge esattamente i byte scritti, otto bit pieni per canale.

È un comando **dal vivo**: effetto immediato, nessuna pausa di assestamento, e
nessun profilo da selezionare dopo — è l'unica superficie del pad su cui si
possa far scorrere fotogrammi.

Il valore però **sopravvive allo scollegamento**, commit `41 80` o no. Due
riscontri, il 13 agosto 2026: i colori rosso-verde-blu-giallo scritti da
MasterPlus mesi prima si ritrovavano a ogni accensione su qualunque computer,
con qualunque programma chiuso; e chiudendo l'app durante un'animazione il pad
si riaccendeva **sull'ultimo fotogramma**, staccando e riattaccando il cavo. Da
qui la conseguenza pratica per chi anima: l'ultimo fotogramma scritto è quello
con cui il pad resta, quindi a fine animazione i colori fissi vanno riscritti
espliciti — lo fa `bridge._ripristina_fissi()`, agganciato sia allo stdin chiuso
sia a SIGTERM. Il solo caso non copribile è il cavo strappato mentre
l'animazione gira: quando lo si scopre il device non è più raggiungibile, e si
rimedia al collegamento successivo.

> **Perché sembravano non indirizzabili.** L'11 agosto 2026 quattro strade
> diverse — comando corto, sequenza lunga della cattura 12, impostazione
> `55 50 28 00 05 17 ffffffff` con cambio profilo e apply, prime quattro
> terzine della tabella per-tasto — risultavano tutte accettate con ACK
> regolare e i LED restavano bianchi. La causa non era l'hardware ma **la coda
> degli ACK non drenata**: il device intercala report non richiesti (`ff aa`
> stato di tasti e rotelle, un `42 20` occasionale) fra un comando e la sua
> conferma, e leggendo una volta sola per report le letture slittano di uno,
> poi di due, finché il pad *continua ad ACKare e smette di eseguire*. Il
> sintomo è sleale in due modi: ogni indicatore software dice che è andato
> tutto bene, e un comando isolato funziona mentre la stessa sequenza ripetuta
> no. La regola è leggere finché non torna l'opcode inviato — è quello che fa
> `ControlPad._send`, e allinearla ha anche portato il ritmo da 48 a 167
> fotogrammi al secondo, perché prima ogni conferma arrivava per timeout.
>
> Da correggere anche la riga precedente di questo paragrafo: i **45
> aggiornamenti al secondo** erano una misura di velocità d'invio, non una
> conferma che i LED cambino. Vale la regola generale del progetto — un numero
> misurato dall'host non dimostra niente sul pad finché non lo si guarda.

Il registro `0x28` che compare nelle stesse catture **non** riguarda questi
LED: `55 50 28 00 05 17 ff ff ff ff` è stato dell'illuminazione, e nella
cattura 11 vale `17 09 04 ff ff` dopo aver girato effetto e velocità.
Riscriverci lo stesso `ffffffff` non prova nulla in nessuna direzione.

La guida operativa all'animazione — primitive, tempo, spazio, composizione,
misure — è in `Come_usare_manipolare_i_4_led/ANIMAZIONI.md`; il codice sta in
`ControlPadEngine/effetti.py` (primitive) e `indicatori.py` (i diciassette
effetti dell'app).

Nota su come cercarli nelle catture: i colori dell'app non sono mai valori
puri. Un rosso scelto col selettore vale `ff 19 28`, non `ff 00 00`, e cercare
`ff0000` non trova nulla — motivo per cui questo comando era sfuggito a una
prima analisi della cattura che lo conteneva già.

### Inquadramento di sessione

La scrittura completa osservata dall'app:

```
41 01                          apertura sessione
41 80 × 2
(41 80 + 51 18 <i> 00 ff 3f) × 24     azzeramento slot macro
(51 18 + 51 19 + 53 00 + 41 80) × n   una per ogni macro assegnata
(51 20 + 51 80) × 24                  tabella keymap
51 94 × 2                             tabella codice HID → indice
41 80 · 52 00 · 41 04 · 55 50 · 41 80
56 15 × 14 · 56 21 × 11               profilo illuminazione
41 80 · 51 28 · 41 01 · 50 55 · 41 00 chiusura e apply
```

## Stato del lavoro

Aggiornata al 16 agosto 2026. Prima era rimasta indietro rispetto a
`stato.html` e `README.md`, che documentavano già come risolte due voci qui
elencate come aperte: leggerla come attuale è costato un limite artificiale di
15 eventi nell'app macOS, tolto dopo il confronto. La regola che ne è uscita è
che di un fatto ci sia **un posto solo** dove è scritto.

Implementato e verificato sul dispositivo: colore statico, colore per singolo
tasto su tutta la griglia, tutte e quattordici le modalità di illuminazione, i
quattro LED indicatori (animazioni comprese), la rimappatura semplice, e
**macro di lunghezza arbitraria** — 49 eventi su 4 report, spezzati da
`macro_packets()` col byte di continuazione.
Include inoltre la sanitizzazione dei nomi macro (UTF-8 con troncamento a 12 byte) e la normalizzazione della velocità su scala 1-10 per tutti e 14 gli effetti.

Tre vincoli scoperti sperimentalmente, nessuno deducibile dai byte:

* Dopo ogni corpo macro (`53 00`) serve una pausa di circa **72 ms**, che è il
  tempo di scrittura in flash. Senza, il comando viene accettato con ACK
  regolare ma non ha alcun effetto — un fallimento silenzioso.
* Costruire la sessione da zero non funziona anche a byte corretti: serve
  l'inquadramento completo dell'app, blob di profilo finale incluso. Il
  metodo che funziona è partire da una cattura e sostituire solo le parti che
  interessano — è quello che fa `ControlPadEngine/session.py`.
* Ogni report va letto **finché non torna il suo opcode**. Il device intercala
  report non richiesti fra un comando e la sua conferma, e chi ne legge uno
  solo slitta di uno, poi di due, finché il pad continua ad ACKare e smette di
  eseguire. Vale per i comandi dal vivo e per la scrittura di sessione: sono
  centocinquanta report, ed è lì che la deriva pesa di più.

### La sessione registrata non è una configurazione da tenere

`skeleton.py` è la traccia di una sessione vera, quindi porta con sé le scelte
di chi l'ha registrata: **dieci** delle ventotto voci `51 20` hanno un'azione
diversa da `00ff`, fra cui quattro tasti a `0000` perché ci stavano sopra le
macro di quella cattura. Riprodurla senza toccarle significa scrivere sul pad
rimappature che nessuno ha chiesto — `2` che batte `3`, `f` che manda Invio,
e `x` `c` `v` `Alt` muti.

Chi genera una sessione deve quindi decidere **ogni** voce: `00ff` per i tasti
che l'utente non ha toccato, e le assegnazioni di fabbrica per le quattro voci
di rotella, che `00ff` non sono. Lo fa `session._con_rimappatura`.

Rileggere le catture **non richiede più Windows**: `analisi/pcapng.py` legge i
`.pcapng` di USBPcap in Python puro, senza tshark. Registrarne di *nuove* sì,
perché macOS non ha uno sniffer USB equivalente — ma le catture esistenti
contengono ancora dati non sfruttati.

### Cambio di banco (`selezione_singola_di_un_profilo_alla_volta_da_1_a_24_per_tornare.pcapng`)

* Commutazione da software: `51 00 00 00 <banco>`, `<banco>` da `0x00`
  (profilo 1) a `0x17` (profilo 24).
* Interrogazione: `52 00 00 00`, a cui il pad risponde `52 00 00 00 <banco>`
  col banco attivo nel byte 4.

### Quello che il pad dice da solo

Il device manda report non richiesti sull'interfaccia vendor, e sono l'unico
modo che l'app ha di sapere cosa succede quando il pad viene toccato a mano.
Tutti e tre verificati in `cattura funzioni interne - e +.pcapng`, filtrando
il solo indirizzo USB del pad:

```
52 00 00 00 <banco>            il banco di profilo attivo è cambiato
52 28 00 00 <slot>             la modalità di illuminazione è cambiata
43 01 00 00 <indice> c0 | 40   un tasto è stato premuto (c0) o rilasciato (40)
```

L'`<indice>` del terzo è l'**indice per colonne** — quello di
`layout.indice_colonne`, lo stesso che numera i LED e la tabella `51 94` — non
il codice HID. Verificato su sei pressioni della cattura: il tasto `x` (HID
`0x1b`, riga 4 colonna 3) si annuncia come `0x0d`, cioè `2*5+3`; `Caps`
(`0x39`, riga 3 colonna 1) come `0x02`; `c` (`0x06`, riga 4 colonna 4) come
`0x12`. Si risale al tasto con `layout.tasto_da_indice_colonne`.

Il terzo è di gran lunga il più frequente — arriva a ogni pressione, anche dei
tasti che battono solo il loro carattere — ed è quello che riempie il buffer
del sistema se non lo si legge. È il motivo per cui il thread di ascolto del
bridge non può permettersi una pausa dopo ogni lettura: vedi
`bridge._poll_connection`.

### Rilettura della keymap

`52 20 <tasto> 00` → `52 20 <tasto> 00 <azione lo> <azione hi>`.

È una lettura dal vivo, fuori da qualunque sessione: il software ufficiale la
usa per ricaricare la configurazione, e nelle catture precede ogni scrittura,
ventotto voci per volta. Serve anche a distinguere un'azione che il firmware
ha accolto da una che ha scartato — è su questo che si regge il setaccio di
`ControlPadEngine/sonda_funzioni.py`.

### Profilo + e profilo −: codici ancora ignoti

Non esistono. Non nel senso che il device non li abbia, ma nel senso che
**nessuna delle diciannove catture del progetto li contiene**. Filtrando tutti
i `51 20` di tutti i file sulle azioni `≥ 0x0100`, l'insieme completo è:

| Cattura | Azioni `≥ 0x0100` viste |
|---|---|
| `11 funzioni.pcapng` | `0110` `0181` `0182` `0190` `0191` `0192` `0193` |
| `cattura funzioni interne - e +.pcapng` | `0181` `0182` `0190` `0191` `0192` `0193` |
| tutte le altre | solo i valori di fabbrica `0181` `0192` `0193` |

`cattura funzioni interne - e +.pcapng` è stata registrata apposta per le
funzioni interne, e mostra sette assegnazioni successive — `x`→`0182`,
`c`→`0181`, `Caps`→`0190`, `a`→`0191` — seguite dalle pressioni di prova. In
quelle pressioni il pad risponde `52 28 00 00 03` al tasto di effetto, quindi
la cattura *conferma* effetto ± e velocità ±. Di profilo ± non c'è traccia:
quelle voci non sono state assegnate.

Quindi `0x0111` e `0x0112` sarebbero un'ipotesi per contiguità con `0x0110`,
non un dato. Per risolverla senza tornare a Windows c'è
`ControlPadEngine/sonda_funzioni.py`, che scrive i candidati sul pad vero e li
rilegge, e poi guarda se premendo il tasto arriva un `52 00 00 00 <banco>`
diverso da prima. Finché quella prova non è stata fatta, profilo ± resta fuori
da `session.FUNZIONI` e da `SpecialFunctions.swift`.

### Cosa è per banco e cosa no

Il dispositivo ha ventiquattro banchi di profilo, ma **non tutto è bancato**, e
la differenza non si vede dai byte. Misurata sul device:

| Cosa | Comando | Per banco? |
|---|---|---|
| Keymap / rimappature | `51 20` · `52 20` | **sì** |
| Modalità di illuminazione | `51 28` · `52 28` | **sì** |
| I 4 LED indicatori | `55 50 <addr> 0c` · `55 40 <addr> 0c` | **sì**, uno slot per banco |

Per la keymap: scritta una rimappatura col pad sul banco 5, `52 20 35 00` la
rilegge `003e` solo dal banco 5; dai banchi 2 e 7 torna `0035`, il valore di
fabbrica. Per la modalità: commutando banco, `52 28 00 00` restituisce quella
del banco nuovo (banco 2 → `04`, banco 5 → `00`).

Anche i LED indicatori sono per banco, ma con un indirizzo diverso per
ciascuno: vedi "I 4 LED indicatori sono per banco".

Ne discendono due obblighi per chi scrive la configurazione:

* **La sessione va nel banco attivo**, e non porta con sé il banco in cui
  dovrebbe finire: chi vuole scrivere il profilo *N* deve prima commutare il
  pad su *N* con `51 00`. Lo fa `bridge.handle` per il comando `write_session`,
  che accetta un campo `profile`. Senza, modificare un profilo qualunque
  scriveva sempre nello stesso banco — uno funzionava, gli altri ventitré no.
* **I quattro LED vanno scritti nello slot del banco giusto**, che è quello
  che il pad ha attivo in quel momento: lo slot sbagliato non dà errore — il
  device conferma e non si accende niente.

### Commutare banco richiede i commit

`51 00 00 00 <banco>` da solo viene **ACKato e non eseguito**: chiesto il banco
9 mentre il pad era sull'8, `52 00 00 00` continuava a rispondere 8. Va
avvolto fra due `41 80`, come fa il software ufficiale in
`selezione_singola_di_un_profilo_alla_volta_da_1_a_24_per_tornare.pcapng`.
Quella cattura manda anche `42 10 00 00 01 00 00 01` due volte dopo il
comando; provato, non serve.

### Il registro 51 28 fa doppio servizio

Ci si scrive la modalità da attivare (`51 28 00 00 <slot>`, slot 0–13), ma
anche il comando di applicazione, che è `51 28 00 00 ff` — 120 volte nelle
catture. Rileggendo con `52 28 00 00` subito dopo un'applicazione torna quindi
**255**, che non è una modalità: significa "ho appena applicato". Chi usa
`52 28` per sapere l'effetto attivo deve scartare quel valore.

### I 4 LED indicatori sono per banco — uno slot ciascuno

Non un registro solo, come si era creduto per mesi: **ventiquattro slot da
dodici byte**, quattro terzine RGB per ciascun banco di profilo, a passo 12 a
partire da `0x00f0`.

```
indirizzo(banco) = 0x00f0 + banco * 12
```

| banco | indirizzo | | banco | indirizzo |
|---|---|---|---|---|
| 0 | `0x00f0` | | 12 | `0x0180` |
| **1** | **`0x00fc`** | | 23 | `0x0204` |

Il software ufficiale li rilegge **tutti e ventiquattro** ogni volta che il
banco attivo cambia — la spazzata è in `profilo + e -.pcapng`, `55 40 <addr>
0c` per `addr` da `0x00f0` a `0x0204`.

`0x00fc`, l'unico indirizzo usato in questo progetto fino ad ora, è il
**secondo** della serie: lo slot del **banco 1**, cioè del profilo che l'app
chiama P2. Ogni scrittura degli indicatori finiva lì qualunque banco fosse
attivo, quindi i quattro LED rispondevano su P2 e da nessun'altra parte.

Il guasto era invisibile a ogni verifica fatta finora, e vale la pena dire
perché: la rilettura `55 40 fc 00 0c` usava lo **stesso indirizzo fisso** della
scrittura, quindi tornava sempre coerente. Scrivendo rosso col pad sul banco 3
e rileggendo dal banco 7 il rosso c'era davvero — ma era lo slot del banco 1
in entrambi i casi, e sembrava la prova che i LED fossero globali. Una lettura
concorde non dimostra niente se legge il posto sbagliato insieme a chi scrive.

Il commit `41 80` basta a fissarli; `51 28 00 00 ff` no, e per giunta lascia
255 nel registro della modalità — vedi la sezione su `51 28`.

### Cosa non è ancora stato eseguito

Codici di profilo avanti/indietro (vedi sopra) · riassegnazione delle rotelle ·
macro oltre 49 eventi · un tasto che porti insieme macro e rimappatura.
