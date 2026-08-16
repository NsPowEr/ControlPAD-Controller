# Animare i quattro LED del ControlPad

Guida operativa alla scrittura di effetti luminosi per i LED indicatori sopra
il pad. Copre il canale hardware, il modello di animazione, il controllo del
tempo e dello spazio, la composizione e il ricettario degli effetti.

Dove sta cosa:

| File | Cosa contiene |
|---|---|
| `ANIMAZIONI.md` | questo documento |
| `anim.py` | i diciassette effetti come rassegna da riga di comando, e come esempio d'uso delle primitive |
| `../ControlPadEngine/effetti.py` | le primitive: tempo, colore, spazio, strati |
| `../ControlPadEngine/indicatori.py` | gli stessi diciassette nella forma che serve all'app: colori dell'utente, velocità, luminosità |
| `../ControlPadEngine/controlpad.py` | il driver, che comanda tutto il pad e non solo questi LED |

Le primitive stanno nel motore e non qui accanto perché il motore è ciò che
l'app impacchetta: una seconda copia in questa cartella andrebbe corretta ogni
volta due volte. Il protocollo byte per byte è in `../ControlPAD - CATTURA/PROTOCOL.md`.
Ogni numero riportato qui è misurato sul dispositivo, non stimato.

La differenza fra `anim.py` e `indicatori.py` è una sola, e sta nel colore:
la rassegna fissa le tinte nel codice, perché serve a mostrare le tecniche;
la versione dell'app le prende dai quattro selettori con `fx.colora`, che dà a
ogni LED il *suo* colore. Sei effetti restano coi colori loro anche lì — nell'
arcobaleno, nel fuoco, nel vu_meter il colore *è* l'effetto.

### Eseguire e importare

```bash
cd Come_usare_manipolare_i_4_led

python anim.py            # rassegna: tutti e diciassette, in fila
python anim.py cometa     # uno solo, a ciclo continuo, per tararlo
python anim.py bench      # quanti aggiornamenti al secondo regge il canale
```

Uno script nuovo dentro questa cartella deve poter raggiungere il motore. Sono
le righe in testa ad `anim.py`, da ricopiare:

```python
import sys, pathlib

_MOTORE = str(pathlib.Path(__file__).resolve().parent.parent / "ControlPadEngine")
if _MOTORE not in sys.path:
    sys.path.append(_MOTORE)          # in coda, non in testa

from controlpad import ControlPad
import effetti as fx
```

In **coda** e non in testa: davanti, il motore scavalcherebbe i moduli di
questa cartella se là dentro ne esistesse uno con lo stesso nome.

`effetti.py` non importa il driver — riceve un `pad` già aperto e basta —
quindi si può usare e collaudare anche senza dispositivo collegato.

---

## 1. Cosa sono questi quattro LED

Sono i **quattro indicatori sopra la griglia dei tasti**, quelli che a riposo
stanno bianchi. Non fanno parte della matrice 5×5: hanno un comando proprio e
scrivere la tabella per-tasto tutta a nero non li tocca.

La differenza che conta per animarli è che **non passano dal profilo**. La
griglia richiede handshake, due chunk, commit e apply, e la scrittura finisce
in una configurazione che va poi selezionata; questi quattro rispondono a un
comando dal vivo che ha effetto immediato, senza scrittura in flash e senza la
pausa di assestamento di 72 ms che la via delle macro impone. È l'unica
superficie del dispositivo su cui si possa realmente far scorrere fotogrammi.

Il rovescio è che **il valore resta**, e resta anche a corrente staccata: non
c'è un colore di default a cui il pad torni. Quello che si scrive per ultimo è
quello con cui si riaccende — verificato il 13 agosto 2026 in due modi opposti,
sia con colori scritti da MasterPlus mesi prima e ritrovati intatti su un altro
computer, sia chiudendo un'animazione a metà e ritrovando **quel fotogramma**
dopo aver staccato e riattaccato il cavo.

Chi anima deve quindi chiudere: a fine effetto i colori fissi vanno riscritti
espliciti, altrimenti l'ultimo fotogramma diventa lo stato permanente del pad.
Nell'app lo fa `bridge._ripristina_fissi()`, agganciato allo stdin chiuso e a
SIGTERM; in uno script a mano è la `fissa(pad, [fx.BIANCO] * fx.N)` che si vede
in coda ad `anim.py`.

| | Quattro indicatori | Griglia 5×5 |
|---|---|---|
| Comando | dal vivo | scrittura di profilo |
| Report per aggiornamento | 2 o 3 | 5 |
| Effetto | immediato | dopo commit e apply |
| Va selezionato dopo | no | sì, con commit e apply |
| Sopravvive allo scollegamento | sì, l'ultimo valore scritto | sì, l'ultima sessione scritta |
| Adatto ad animare | **sì** | no |

---

## 2. Il canale, in concreto

### 2.1 I comandi

I LED occupano l'indirizzo `0x00fc` e sono **dodici byte**: quattro terzine
RGB consecutive, un byte per canale.

```
41 04                                       apre la transazione — obbligatorio
55 50 fc 00 0c  <R G B> ×4                  scrive i dodici byte
41 80                                       commit — facoltativo
```

La forma generale è `55 <operazione> <indirizzo a 16 bit LE> <lunghezza>`. Con
operazione `0x40` lo stesso intervallo si **rilegge**:

```
55 40 fc 00 0c   →   55 40 fc 00 0c <R G B> ×4
```

### 2.2 Cosa è obbligatorio e cosa no

Misurato provando le quattro combinazioni:

| Sequenza | Scrive? | ms/fotogramma | fps |
|---|---|---|---|
| `41 04` + `55 50` + `41 80` | sì | 6,00 | 167 |
| `41 04` + `55 50` | **sì** | **4,00** | **250** |
| `55 50` + `41 80` | no | — | — |
| `55 50` da solo | no | — | — |

Due letture immediate. L'apertura `41 04` è **indispensabile**: senza, il
device non arriva nemmeno ad ACKare la scrittura. Il commit `41 80` invece
**non serve** per gli indicatori, e ometterlo fa risparmiare un terzo del
tempo di fotogramma — un affare quando si trasmette animazione, dove il
fotogramma successivo sostituisce comunque il precedente. Per questo
`set_indicators(colours, commit=False)` è la modalità che `riproduci()` usa.

Il `41 04` + `55 40 28 00 05` + `41 80` che nelle catture dell'app precede il
blocco di colore **non è un prologo**: è una lettura di stato, risponde
`17 ff ff …` e si può ignorare del tutto.

### 2.3 Il drenaggio degli ACK — la trappola che costa ore

Ogni report OUT riceve un ACK sull'endpoint IN con l'opcode riecheggiato. Il
device però **intercala report non richiesti** (stato di tasti e rotelle, e
un `42 20` occasionale) fra il comando e la sua conferma.

Se si legge una volta sola per report e si prende per buono quello che arriva,
la coda resta indietro di uno, poi di due, e a quel punto **il device smette
di eseguire le scritture pur continuando ad ACKarle**. Il sintomo è sleale:
ogni comando risulta accettato e non cambia niente. Peggio, si manifesta solo
dopo qualche report, quindi un comando isolato funziona e la stessa sequenza
ripetuta no.

La regola è **leggere finché non torna l'opcode che si è inviato**, scartando
il resto. È quello che fa `ControlPad._send`. Allineare le letture ha anche
fatto salire il ritmo da 48 a 167 aggiornamenti al secondo, perché prima ogni
conferma arrivava a colpi di timeout.

### 2.4 Fedeltà e prestazioni

Il device **non applica alcuna curva propria**: rilegge esattamente i byte
scritti, verificato su valori bassi (1, 2, 3, 4), medi e alti. Sono otto bit
pieni per canale, 256 livelli reali, e qualunque correzione percettiva spetta
a noi (§ 6.3).

Latenza per fotogramma su 300 campioni, con commit:

| min | mediana | p95 | max |
|---|---|---|---|
| 5,83 ms | **6,00 ms** | 6,03 ms | 6,15 ms |

Il jitter è di ±0,15 ms, cioè trascurabile: il canale è sorprendentemente
regolare e non serve compensarne l'irregolarità, solo la sua latenza.

**Budget pratico**: 250 fps senza commit, 167 con. Qualunque animazione
sensata sta larga dentro 60 fps, che costa il 24% del canale.

---

## 3. Il modello: un effetto è una funzione del tempo

Tutto in `effetti.py` poggia su una sola convenzione:

```python
def fotogramma(t):        # t = secondi trascorsi dall'inizio, float
    ...
    return [c0, c1, c2, c3]   # quattro (R, G, B), interi 0-255
```

Nient'altro. Non una classe, non uno stato obbligatorio, non un riferimento al
dispositivo. Le conseguenze pratiche sono queste:

* **Ritmo indipendente dal contenuto.** Lo stesso effetto gira a 30 o a 120
  fps senza modifiche: il tempo è un parametro, non il numero di iterazioni.
* **Trasformabile.** Rallentare è `fotogramma(t * 0.5)`, invertire il tempo è
  `fotogramma(-t)`, ritardare è `fotogramma(t - 0.3)`.
* **Componibile.** Due effetti si sovrappongono combinando i loro risultati,
  perché entrambi sono solo liste di quattro colori (§ 8).
* **Verificabile senza hardware.** `fotogramma(1.5)` si può leggere in un test
  o stampare a schermo; il pad serve solo per il giudizio estetico finale.

Chi ha stato — le scintille che sfumano, il fuoco che tremola — lo tiene in
una chiusura e resta una funzione del tempo vista da fuori (§ 8.4).

### 3.1 Il ciclo di riproduzione, e perché non basta `sleep`

```python
riproduci(pad, fotogramma, durata=3.5, fps=60)
```

La versione ingenua del ciclo è questa, ed è sbagliata:

```python
while time.time() - inizio < durata:
    pad.set_indicators(fotogramma(t))
    time.sleep(1 / 60)              # ← sbagliato
```

Il difetto è che a ogni giro la pausa si **aggiunge** al tempo di
trasmissione invece di comprenderlo. A 60 fps nominali il periodo dovrebbe
essere 16,7 ms, ma diventa 16,7 + 6,0 = 22,7 ms: **43 fps reali**, come
misurato sulla prima versione di `anim.py`. L'errore non è solo di ritmo, è
cumulativo — a effetti sincronizzati fra loro le fasi divergono.

La forma corretta ancora ogni fotogramma a una scadenza calcolata
**dall'istante iniziale**:

```python
scadenza = inizio + n / fps
ritardo = scadenza - time.perf_counter()
if ritardo > 0:
    time.sleep(ritardo)
```

Così un giro lento viene riassorbito dal successivo invece di slittare per
sempre. `riproduci()` restituisce `(fotogrammi, secondi, saltati)`, dove
**`saltati`** conta le scadenze già passate all'arrivo: è la misura diretta di
quanto il ritmo richiesto ecceda il canale. Se è zero, il ritmo regge.

Usare `time.perf_counter()` e non `time.time()`: il primo è monotòno e ha
risoluzione adeguata a millisecondi singoli.

---

## 4. Il tempo

### 4.1 Periodo, frequenza, fase

Tre modi di dire la stessa cosa, e conviene fissarli:

* **periodo** `T` — quanti secondi dura un giro completo;
* **frequenza** `f = 1/T` — quanti giri al secondo;
* **fase** — a che punto del giro si è, sempre normalizzata fra 0 e 1.

Tutte le forme d'onda di `effetti.py` prendono una fase e rendono 0..1. La
conversione da tempo a fase è `fase(t, periodo)`, che è `(t / periodo) % 1`.

```python
fx.fase(t, periodo=2.0)     # un giro ogni 2 secondi
fx.battuta(t, bpm=120)      # un giro ogni battito, per sincronie musicali
```

Separare fase e forma d'onda è ciò che rende un effetto riconfigurabile: la
velocità si cambia toccando il periodo, il carattere toccando la forma, e le
due cose non si intralciano.

### 4.2 Andata e ritorno

`fase()` da sola torna a zero **di scatto** a fine giro. Va benissimo per un
inseguimento circolare, dove il salto coincide col rientro dal capo opposto e
non si vede; è visibilissimo invece su una luminosità, dove appare come uno
sfarfallio a ogni giro.

Per un moto che va e torna senza discontinuità serve `pingpong()`, che piega
0..1 in 0..1..0:

```python
fx.pingpong(fx.fase(t, 2.0))    # 1 s per andare, 1 s per tornare
```

Oppure `seno()`, che fa la stessa cosa in modo curvo anziché spezzato.

---

## 5. Le forme d'onda

Sono il **profilo temporale**: dicono *come* una grandezza va da un estremo
all'altro. Tutte prendono una fase 0..1 e rendono 0..1.

| Funzione | Andamento su un giro | Carattere | Uso tipico |
|---|---|---|---|
| `seno(x)` | `▁▂▄▆█▆▄▂▁` | morbido, senza spigoli | respiro, pulsazioni, tutto ciò che deve sembrare naturale |
| `triangolo(x)` | `▁▃▅█▅▃▁` | velocità costante, due spigoli | scansioni meccaniche, pendoli rigidi |
| `dente(x)` | `▁▂▃▄▅▆▇█` poi ricade | a senso unico | inseguimenti, riempimenti, rotazioni |
| `quadra(x, ciclo)` | `████____` | solo acceso o spento | allarmi, lampeggi netti |
| `impulso(x, larghezza)` | `█▁▁▁▁▁▁▁` | un lampo per giro | eventi puntuali, battiti, notifiche |
| `rumore(x)` | irregolare, mai ripetuto | imprevedibile ma continuo | fuoco, brace, tremolii organici |

Note d'uso:

* `quadra(x, ciclo=0.1)` dà un lampo breve con una lunga pausa; `ciclo=0.9`
  fa il contrario, una luce quasi fissa con brevi stacchi. È il parametro che
  distingue un allarme urgente da uno di cortesia.
* `impulso(x, morbido=True)` smussa il lampo con un mezzo seno. Su LED così
  piccoli il lampo netto è spesso troppo duro; il morbido si legge meglio.
* `rumore(x)` somma seni di frequenze incommensurabili: è **deterministico**
  (stesso `t`, stesso valore) ma non si ripete mai davvero. Preferibile a
  `random` quando l'effetto deve poter essere riavvolto o riprodotto uguale.

### 5.1 Combinarle

Le forme d'onda si moltiplicano e si sommano come qualunque numero. Un
lampeggio che a sua volta pulsa lentamente:

```python
v = fx.quadra(fx.fase(t, 0.25)) * fx.seno(fx.fase(t, 4.0))
```

Una portante veloce sotto un inviluppo lento è il modo più economico di dare
profondità a un effetto senza scriverne uno nuovo.

---

## 6. Il colore

### 6.1 HSV, non RGB

Per animare conviene ragionare in **tinta, saturazione, luminosità** e
convertire alla fine, perché sono queste tre le grandezze che si vogliono far
variare nel tempo:

```python
fx.hsv(h, s, v)     # h gira: 1.1 vale 0.1, quindi h può crescere all'infinito
```

Che `h` sia circolare è comodo: `fx.hsv(t * 0.2)` è un arcobaleno lento che
non ha bisogno di essere riportato in intervallo.

Le tinte utili sulla ruota: `0.0` rosso, `0.08` arancio, `0.17` giallo,
`0.33` verde, `0.5` ciano, `0.62` blu, `0.75` viola, `0.92` magenta.

### 6.2 Operazioni

| Funzione | Cosa fa | Quando |
|---|---|---|
| `scala(colore, k)` | stessa tinta, luminosità × k | dimmerare, applicare un inviluppo |
| `mescola(a, b, k)` | interpola canale per canale | transizioni fra due colori |
| `somma(a, b)` | sovrappone, satura a 255 | due luci sullo stesso LED |
| `schiarisci(a, b)` | tiene il canale più alto | unire strati senza slavare |
| `moltiplica(a, b)` | usa `b` come maschera | ritagliare una forma su un fondo |
| `gradiente(fermate, x)` | colore a frazione x di una lista | palette, mappe di livello |

`somma` e `schiarisci` sembrano intercambiabili e non lo sono: sommare rosso e
verde dà giallo pieno, schiarirli dà comunque giallo, ma sommare due rossi dà
un rosso più chiaro fino a slavare verso il bianco, mentre schiarirli lascia il
rosso. Per sovrapporre strati dello stesso colore **schiarisci** conserva la
tinta; per simulare luci fisiche che si sommano davvero, `somma` è più giusta.

### 6.3 La correzione gamma — il dettaglio che separa un effetto amatoriale

L'occhio **non risponde in modo lineare** all'energia luminosa. Una rampa
lineare di byte da 0 a 255 non appare come una salita uniforme: appare come un
balzo iniziale e poi quasi nulla, perché la sensibilità è molto più fine in
basso. Un valore di 128 non sembra affatto metà di 255 — sembra circa il 73%.

Il dispositivo, verificato, non compensa niente: scrive i byte che gli si dà.
Quindi la correzione va applicata a valle, elevando a una potenza prima di
scrivere:

```python
fx.gamma(colore, g=2.2)     # 128 → 55, cioè quello che *sembra* metà
```

oppure una volta sola per tutto l'effetto:

```python
fx.riproduci(pad, fotogramma, durata=4, gamma_=2.2)
```

Dove si nota di più: **dissolvenze e respiri**. Senza correzione una
dissolvenza sembra rimanere accesa a lungo e poi crollare di colpo alla fine;
con la correzione scende in modo regolare. Dove si nota di meno: effetti a
piena intensità che stanno quasi sempre accesi o spenti, dove la parte bassa
della curva viene attraversata in fretta.

Il valore 2,2 è il punto di partenza convenzionale. Su questi LED conviene
provare fra 1,8 e 2,5 e scegliere a occhio: è una taratura percettiva, non c'è
un numero giusto in assoluto.

### 6.4 Palette pronte

`ARCOBALENO`, `FUOCO`, `GHIACCIO`, `VU` sono liste di fermate da passare a
`gradiente()`. `FUOCO` va da nero a bianco caldo passando per rosso e arancio
— la sequenza fisica di un corpo che si scalda, ed è per questo che convince
più di una semplice rampa di rosso.

---

## 7. Lo spazio: quattro LED sono pochissimi

Qui sta la difficoltà vera. Quattro punti in fila sono una risoluzione
spaziale bassissima, e le tecniche che funzionano su una striscia da sessanta
LED cadono a pezzi. Tre conseguenze da tenere presenti.

### 7.1 La posizione va tenuta come numero reale

Se si accende il LED intero più vicino, il movimento avanza a **scatti di un
quarto di fila** e si vede benissimo. La soluzione è tenere la posizione come
`float` e ripartire la luce fra i due LED adiacenti in proporzione alla
frazione — l'equivalente spaziale dell'antialiasing:

```python
fx.punto(1.25, colore)      # LED 1 al 75%, LED 2 al 25%
```

A posizione 1,25 l'occhio percepisce una luce *fra* il secondo e il terzo LED,
e il movimento scorre. Senza questo passaggio non esiste animazione fluida su
quattro LED: è la singola tecnica che conta di più in tutto il documento.

`punto()` conserva l'energia — la somma delle intensità resta costante mentre
il punto si sposta, verificato su tutta la corsa — quindi non si vede pulsare
mentre passa da un LED all'altro.

### 7.2 Velocità: esiste un tetto percettivo, molto più basso del canale

Con quattro posizioni, un movimento oltre **circa 3 giri al secondo** smette
di leggersi come movimento e diventa sfarfallio: il cervello non ha abbastanza
punti per ricostruire la traiettoria. Il limite non è il canale, che regge 250
fps, è la risoluzione spaziale.

Regola pratica: da 0,5 a 2 giri al secondo si legge bene, 3 è il massimo utile,
oltre conviene passare a un effetto che non si basi sul movimento (un
lampeggio, una pulsazione).

### 7.3 Direzione, origine, verso

Il punto che interessava di più: **da che parte parte**.

L'ordine fisico è verificato accendendo un LED alla volta:
**indice 0 = LED più a sinistra, indice 3 = più a destra.**

```
  indice     0     1     2     3
            ┌─┐   ┌─┐   ┌─┐   ┌─┐
            └─┘   └─┘   └─┘   └─┘
          sinistra ──────────► destra
```

`percorso()` incapsula le tre manopole che governano il moto:

```python
fx.percorso(t, giri_al_secondo=1.0, verso=fx.DESTRA, origine=None, circolare=True)
```

| Parametro | Effetto |
|---|---|
| `giri_al_secondo` | velocità. 1.0 = una fila intera al secondo |
| `verso` | `fx.DESTRA` parte da sinistra e cresce; `fx.SINISTRA` parte da destra e cala |
| `origine` | indice di partenza, **sempre** fisico: 0 a sinistra, 3 a destra, qualunque sia il verso. `None` = il capo naturale del verso |
| `circolare` | `True` la fila è un anello, `False` i capi sono estremi veri |

Nota su `verso=SINISTRA`: non si limita a invertire il segno, sposta anche il
punto di partenza a destra. È quello che si vuole quasi sempre — «parti da
destra e vieni verso di me» — invece di partire da sinistra andando a ritroso
e comparire subito dall'altro capo.

`origine` resta comunque un indice fisico e non segue il verso, così
`origine=1` è il secondo LED da sinistra sia andando a destra sia andando a
sinistra. Le due cose sono indipendenti apposta: `verso` sceglie la direzione,
`origine` il punto di partenza, e lasciare `origine=None` fa scegliere al
verso il capo da cui conviene partire.

**Quattro modi diversi di invertire un effetto**, e non sono la stessa cosa:

| Come | Cosa cambia | Esempio |
|---|---|---|
| `verso=SINISTRA` | direzione e partenza del moto | inseguimento che arriva da destra |
| `inverti(colori)` | specchia il fotogramma finito | riflette qualunque effetto, anche non direzionale |
| `origine=3` | solo il punto di partenza | stessa direzione, altro capo |
| `fotogramma(-t)` | il tempo scorre all'indietro | riavvolge *tutto*, anche colori e inviluppi |

Il terzo e il quarto si confondono facilmente. `origine` cambia dove comincia,
`-t` fa andare a ritroso l'intera animazione: su un arcobaleno che deriva di
tinta, `origine` non tocca i colori mentre `-t` inverte anche quelli.

### 7.4 Circolare o lineare

`distanza(pos, i, circolare)` decide se la fila è un **anello** o un
**segmento**, e la scelta cambia il carattere dell'effetto:

* **circolare** — il LED 3 confina col LED 0. Un inseguimento continuo lo
  richiede, altrimenti a ogni giro c'è un salto visibile mentre la testa
  rientra dal capo opposto.
* **lineare** — i due capi sono estremi veri. È quello che vuole un pendolo,
  che deve *fermarsi* e tornare indietro, o un riempimento, che deve arrivare
  in fondo e stare.

Sbagliarla è l'errore più comune dopo la posizione intera: un pendolo
circolare non torna mai indietro, e un inseguimento lineare si inceppa ai capi.

### 7.5 Scie e barre

```python
fx.scia(pos, lunghezza=1.5, verso=fx.DESTRA, circolare=True, forma=None)
fx.barra(livello, parziale=True)
```

`scia()` mette la coda **dietro rispetto al verso di marcia** — davanti alla
testa l'intensità è nulla. Una coda simmetrica sembra un alone, non un
movimento: è la direzione della coda a dire all'occhio dove si sta andando.

`lunghezza` è in unità di LED e su quattro punti è un parametro delicato:

| Lunghezza | Resa |
|---|---|
| 0,8 | punto netto, movimento a scatti percepibile |
| 1,5 | **buon compromesso**, scorre e resta leggibile |
| 2,5 | scia lunga, elegante ma la testa si distingue poco |
| 3,5 | quasi tutta la fila accesa, la direzione si perde |

`forma` rimappa il decadimento: `forma=fx.entra` dà una coda che sfuma in
fretta e poi si allunga sottile, `forma=fx.esce` una coda che resta luminosa e
poi taglia netto. Il default lineare è il più neutro.

`barra()` riempie da sinistra, con `parziale=True` il LED di frontiera si
accende in proporzione — di nuovo antialiasing, ed è ciò che permette di
mostrare un livello continuo su soli quattro passi. Con `parziale=False` si
ottiene una barra a scalini, che è quello che si vuole quando i quattro LED
rappresentano **quattro cose distinte** (quattro profili, quattro stati) e non
una grandezza continua.

---

## 8. Comporre

### 8.1 Sovrapporre

```python
fx.strati(sfondo, primo_piano, fondi=fx.schiarisci)
```

Il caso tipico è un fondo continuo con sopra qualcosa di puntuale: una
pulsazione lenta sotto, e sopra un inseguimento veloce.

```python
def fotogramma(t):
    fondo = [fx.hsv(0.6, 1, 0.15)] * 4
    testa = fx.punto(fx.percorso(t, 1.2), fx.hsv(0.6))
    return fx.strati(fondo, testa)
```

### 8.2 Dissolvere fra due effetti

```python
fx.dissolvi(a(t), b(t), k)
```

Con `k` guidato da un easing si passa da un effetto all'altro senza stacco:

```python
k = fx.dolce(min(1.0, max(0.0, (t - 2.0) / 0.5)))   # transizione a t=2s, 0,5s
return fx.dissolvi(respiro_frame(t), allarme_frame(t), k)
```

È il modo pulito di cambiare stato — da «tutto a posto» ad «attenzione» —
senza che il passaggio sembri un glitch.

### 8.3 Concatenare

```python
fx.in_sequenza((entrata, 0.4), (tenuta, 1.5), (uscita, 0.6))
```

Restituisce un unico `fotogramma(t)` che percorre i tre pezzi e poi riparte.
Serve per animazioni con inizio, centro e fine — una notifica che entra, resta
e sfuma — senza scriverne a mano la macchina a stati.

### 8.4 Memoria fra fotogrammi

Alcuni effetti hanno bisogno di ricordare il fotogramma precedente. Il
decoratore lo aggiunge senza cambiare la firma:

```python
fx.con_decadimento(fotogramma, tenuta=0.85)
```

Ogni LED sfuma verso il basso invece di spegnersi di colpo. È ciò che rende
guardabili gli effetti a scatti — scintille, colpi, letture discrete — che
senza memoria risultano duri.

`tenuta` è il fattore per fotogramma, quindi **dipende dal frame rate**: 0,85
a 60 fps significa scendere a un decimo in circa 14 fotogrammi, cioè 0,23 s.
A 30 fps la stessa tenuta dà una coda doppia. Se il ritmo cambia, va ritarata.

---

## 9. Ricettario

Sei effetti costruiti da zero, ciascuno con la tecnica che illustra.

### 9.1 Inseguimento con scia — il caso base

```python
def cometa(t):
    pos = fx.percorso(t, giri_al_secondo=1.2, verso=fx.DESTRA)
    return fx.dipingi(fx.scia(pos, lunghezza=1.5), fx.hsv(0.07))
```

Da qui si ricava tutto il resto: `verso=fx.SINISTRA` lo fa arrivare da destra,
`giri_al_secondo` regola la velocità, `lunghezza` la coda, e sostituire
`dipingi` con `colora` fa dipendere la tinta dalla posizione invece che dal
tempo.

### 9.2 Pendolo — quando la fila non è un anello

```python
def pendolo(t):
    pos = fx.pingpong(fx.fase(t, 1.6)) * (fx.N - 1)
    return fx.punto(pos, fx.hsv(0.0), circolare=False)
```

Due differenze dal precedente, entrambe necessarie: `pingpong` perché il moto
deve tornare indietro, `circolare=False` perché i capi sono estremi veri.
Sostituendo `pingpong` con `seno` il pendolo rallenta agli estremi invece di
invertire di scatto — molto più naturale.

### 9.3 Respiro — dove la gamma si vede

```python
def respiro(t):
    v = fx.seno(fx.fase(t, 3.0))
    return [fx.gamma(fx.hsv(0.55, 1.0, v))] * 4
```

Provarlo con e senza `gamma` è il modo più rapido di capire perché serve: la
versione non corretta sembra restare accesa e poi crollare, quella corretta
scende in modo regolare.

### 9.4 Livello continuo su quattro punti

```python
def vu(t):
    livello = 4 * fx.seno(fx.fase(t, 2.5))
    return fx.colora(fx.barra(livello), fx.VU)
```

`barra` con riempimento parziale dà la risoluzione continua, `colora` mappa la
tinta sulla **posizione** e non sul tempo, così l'ultimo LED resta rosso
qualunque sia il livello — che è l'informazione che un indicatore deve dare.

### 9.5 Effetto organico

```python
def brace(t):
    return [fx.gradiente(fx.FUOCO, 0.35 + 0.55 * fx.rumore(t * 0.6 + i * 3.1))
            for i in range(fx.N)]
```

Lo sfasamento `i * 3.1` è ciò che rende i quattro LED **indipendenti**: senza,
tremolerebbero all'unisono e sembrerebbe un guasto, non una fiamma. Il numero
va scelto irrazionale rispetto al periodo, altrimenti si risincronizzano.

### 9.6 Notifica con inizio e fine

```python
lampo   = lambda t: [fx.hsv(0.5, 0.3, fx.impulso(t / 0.18))] * 4
riposo  = lambda t: [fx.NERO] * 4
respiro = lambda t: [fx.hsv(0.5, 1, 0.25 * fx.seno(fx.fase(t, 2.0)))] * 4

notifica = fx.in_sequenza((lampo, 0.18), (riposo, 0.10),
                          (lampo, 0.18), (riposo, 0.25), (respiro, 2.0))
```

Due lampi, una pausa, poi uno stato di attesa discreto. La struttura tipica di
una notifica che deve farsi notare e poi non disturbare più.

---

## 10. Manipolare un effetto esistente

Tabella di consultazione: cosa toccare per ottenere un dato cambiamento.

| Voglio | Manopola | Nota |
|---|---|---|
| Più veloce | `giri_al_secondo` ↑ oppure `periodo` ↓ | oltre 3 giri/s diventa sfarfallio |
| Più lento | il contrario | sotto 0,2 giri/s sembra fermo |
| Parte da destra | `verso=fx.SINISTRA` | sposta anche la partenza, non solo il segno |
| Parte da un altro LED | `origine=2` | 0 è sempre il LED di sinistra |
| Specchiato | `fx.inverti(colori)` | agisce sul risultato, vale per qualunque effetto |
| A ritroso | `fotogramma(-t)` | riavvolge anche colori e inviluppi |
| Coda più lunga | `lunghezza` ↑ | oltre 2,5 la direzione si legge male |
| Movimento più fluido | `fx.punto()` invece dell'indice intero | il singolo intervento che conta di più |
| Dissolvenze regolari | `gamma_=2.2` in `riproduci` | tarare a occhio fra 1,8 e 2,5 |
| Meno acceso | `fx.scala(colore, 0.4)` sul risultato | dimmerazione globale a costo zero |
| Colore fisso invece di variabile | `fx.dipingi(intensita, colore)` | separa forma e tinta |
| Tinta dipendente dalla posizione | `fx.colora(intensita, palette)` | per indicatori di livello |
| Transizione morbida agli estremi | `seno` invece di `triangolo` | rallenta dove inverte |
| Meno regolare, più vivo | moltiplicare per `rumore(t)` | tenerlo sopra 0,6 per non spegnere |
| Coda temporale | `fx.con_decadimento(f, 0.85)` | ritarare se cambia il frame rate |
| Sincronizzato a musica | `fx.battuta(t, bpm)` | al posto di `fase` |

---

## 11. Trappole

Raccolte per sintomo, perché è così che si presentano.

**Il comando è ACKato e non succede niente.** La coda IN non viene drenata:
va letto fino all'ACK con l'opcode giusto (§ 2.3). È il guasto più insidioso
del progetto perché ogni indicatore software dice che è andato tutto bene.

**L'animazione gira più lenta di quanto chiesto.** `sleep` di durata fissa
invece di scadenze ancorate all'inizio (§ 3.1). Controllare `saltati` nel
valore di ritorno di `riproduci`.

**Il movimento è a scatti.** Posizione arrotondata all'indice invece che
ripartita fra i vicini (§ 7.1).

**Il movimento sfarfalla invece di scorrere.** Troppo veloce per quattro
punti: sotto i 3 giri al secondo (§ 7.2).

**Le dissolvenze sembrano restare accese e poi crollare.** Manca la
correzione gamma (§ 6.3).

**Il pendolo non torna indietro.** `circolare=True` dove serviva lineare
(§ 7.4).

**L'inseguimento ha un salto a ogni giro.** Il contrario: `circolare=False`
dove serviva l'anello.

**La scia sembra un alone e non si capisce la direzione.** La coda va dietro
rispetto al verso di marcia, mai simmetrica (§ 7.5).

**Il tremolio sembra un guasto.** I LED sono in fase: sfasare il rumore per
indice (§ 9.5).

**Gli effetti sovrapposti slavano verso il bianco.** `somma` dove serviva
`schiarisci` (§ 6.2).

**A fine programma i LED restano sull'ultimo fotogramma, e ci restano anche
dopo aver staccato il cavo.** Non è un difetto del ciclo: il valore scritto
sopravvive alla corrente e non esiste un default a cui il pad torni. Rimettere
i colori voluti espliciti in uscita, sempre — compresi i percorsi di uscita che
non si vedono, come un segnale di terminazione (§ 1).

---

## 12. Riferimento rapido di `effetti.py`

```python
N = 4                       # LED, indice 0 a sinistra
DESTRA = +1 ; SINISTRA = -1
NERO ; BIANCO

# riproduzione
riproduci(pad, fotogramma, durata, fps=60, commit=False, gamma_=None)
                            # -> (fotogrammi, secondi, saltati)
fissa(pad, colori, secondi=0.0, commit=True)

# tempo
fase(t, periodo=1.0)        # -> 0..1, riparte di scatto
pingpong(x)                 # -> 0..1..0
battuta(t, bpm)

# forme d'onda: fase 0..1 -> 0..1
seno(x) ; triangolo(x) ; dente(x)
quadra(x, ciclo=0.5) ; impulso(x, larghezza=0.12, morbido=True) ; rumore(x)

# transizioni: 0..1 -> 0..1  (elastico sconfina apposta)
lineare(x) ; dolce(x) ; entra(x) ; esce(x) ; elastico(x) ; rimbalzo(x)

# colore
hsv(h, s=1.0, v=1.0) ; scala(colore, k) ; mescola(a, b, k)
somma(a, b) ; schiarisci(a, b) ; moltiplica(a, b)
gamma(colore, g=2.2) ; gradiente(fermate, x)
ARCOBALENO ; FUOCO ; GHIACCIO ; VU

# spazio
percorso(t, giri_al_secondo=1.0, verso=DESTRA, origine=None, circolare=True)
distanza(pos, i, circolare=True)
punto(pos, colore=BIANCO, circolare=True)          # antialiasing spaziale
scia(pos, lunghezza=1.5, verso=DESTRA, circolare=True, forma=None)
barra(livello, parziale=True)
dipingi(intensita, colore=BIANCO)                  # tinta unica
colora(intensita, palette)                         # tinta per posizione

# riordino e strati
inverti(colori) ; ruota(colori, k) ; specchia(colori)
strati(*fotogrammi, fondi=schiarisci) ; dissolvi(a, b, k)
in_sequenza(*(fotogramma, durata))
con_decadimento(fotogramma, tenuta=0.85)
casuale(probabilita, colore=None)
```

E di `indicatori.py`, che è la porta da cui passa l'app:

```python
CATALOGO                    # [(id, fabbrica, usa_colori)] × 17, ordine del menu
elenco()                    # [{"id":…, "uses_colors":…}] per il bridge
costruisci(nome, colori=None, velocita=16, luminosita=255)   # -> fotogramma(t)
fattore_velocita(velocita)  # cursore 0..32 -> moltiplicatore del tempo, 0,4..2,4
riproduci_finche(pad, fotogramma, ferma, fps=60, commit=False)
                            # come riproduci(), ma finisce quando `ferma` (un
                            # threading.Event) si alza; -> (fotogrammi, s, saltati)
```

---

## 13. Numeri, in un posto solo

| Grandezza | Valore | Come è stato ottenuto |
|---|---|---|
| Indice 0 | LED più a sinistra | acceso uno alla volta, verificato a vista |
| Byte per LED | 3 (RGB), 8 bit pieni | scritto e riletto su valori bassi, medi, alti |
| Trasformazioni del firmware | nessuna | rilettura identica alla scrittura |
| Indirizzo | `0x00fc`, 12 byte | `55 50` scrive, `55 40` rilegge |
| `41 04` | obbligatorio | senza, nessun ACK e nessuna scrittura |
| `41 80` | facoltativo | ometterlo: 6,00 → 4,00 ms |
| Fotogramma con commit | 6,00 ms → 167 fps | mediana su 300 campioni |
| Fotogramma senza commit | 4,00 ms → 250 fps | media su 60 campioni |
| Jitter | ±0,15 ms | min 5,83 / max 6,15 su 300 |
| Costo di 60 fps | 24% del canale | 6,00 ms su 16,7 ms disponibili |
| Tetto percettivo del moto | ~3 giri al secondo | quattro posizioni sono poche |
| Persistenza | l'ultimo valore scritto | ritrovato dopo scollegamento, su un altro computer e a programmi chiusi |
