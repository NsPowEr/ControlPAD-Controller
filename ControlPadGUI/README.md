# ControlPad — app macOS

App nativa SwiftUI (Liquid Glass, macOS 26+) per il Cooler Master ControlPad,
con le stesse quattro schede dell'app Windows ufficiale: Illuminazione,
Mappatura tasti, Macro, Profili — più una sottopagina Impostazioni con
selezione lingua a runtime.

Il protocollo USB non è riscritto qui: questa app pilota il pad lanciando
`../ControlPadEngine/bridge.py` come sottoprocesso e parlandoci in JSON su
stdin/stdout. La logica del protocollo (handshake, timing, formato macro)
resta tutta in `ControlPadEngine/`, verificata sul dispositivo reale — vedi
`../ControlPAD - CATTURA/PROTOCOL.md` per i dettagli byte per byte.

## Eseguire in sviluppo

```bash
cd ControlPadGUI
swift run
```

Serve `ControlPadEngine/` accanto a questa cartella (nel repo lo è già) e
Python 3 con `hidapi` installato — vedi `../ControlPadEngine/requirements.txt`:

```bash
pip3 install hidapi
```

## Pacchettizzare come app

```bash
./scripts/make_app_bundle.sh
open dist/ControlPad.app
```

Lo script compila in release e crea `dist/ControlPad.app` con l'eseguibile,
il bundle risorse (localizzazioni) e una copia di `ControlPadEngine/`
dentro `Contents/Resources/`, così l'app gira senza bisogno dei sorgenti a
fianco. Firma ad-hoc inclusa, solo per uso locale — non è notarizzata.

**Nota PATH**: un'app lanciata da Finder eredita il PATH minimale di
launchd, non quello della shell interattiva. `PythonBridge` risolve il
`python3` giusto chiedendolo alla shell di login dell'utente (dove
`pip3 install hidapi` è stato eseguito), non usando `env python3` diretto —
altrimenti finirebbe sul Python di sistema, senza hidapi.

## Struttura

Vedi `Sources/ControlPadGUI/`: `Bridge/` (trasporto JSON verso il motore),
`Models/` (layout tasti, effetti, funzioni speciali, preset), `Views/`
(le quattro schede + Impostazioni + componenti condivisi), `Localization.swift`
(cambio lingua a runtime — `L()` invece della risoluzione automatica di
SwiftUI, che su un eseguibile SPM non basterebbe).

## Come sono fatte le schede

**Illuminazione** — tutte e 14 le modalità, nessuna bloccata. Le sei reattive
al tocco hanno **due colori**, di fondo e di reazione; i due pallini di fianco
al nome dicono a colpo d'occhio quali sono. Ciclo colore ignora il colore
(scorre la ruota da solo) e Spegni non ne usa: l'interfaccia lo dice invece di
mostrare comandi che non fanno niente.

**Mappatura tasti** — il pad in alto con i numeri **1–24**, gli stessi
serigrafati sull'hardware, e sotto una **tastiera intera** su cui scegliere il
tasto dove ci si aspetta di trovarlo. Le funzioni interne stanno nell'altra
linguetta, in griglia e con un'icona ciascuna.

**Macro** — si **registrano battendo davvero i tasti**: pressioni, rilasci e
pause reali finiscono nella lista, poi ogni ritardo si ritocca a mano. Non c'è
limite di lunghezza (vedi sotto).

**Profili** — preset salvati lato host in
`~/Library/Application Support/ControlPad/`, non banchi separati sul
dispositivo: nessuna cattura ha mai mostrato un comando per scriverne uno
specifico. Da non confondere con i **banchi del device**, che esistono e che
un tasto può selezionare: quella scelta sta in Mappatura tasti, accanto alla
funzione "Seleziona profilo", perché è una cosa che il pad fa da solo anche
con l'app chiusa.

## Limiti noti

- **Registrazione macro**: cattura solo mentre la finestra dell'app è in primo
  piano (`NSEvent.addLocalMonitorForEvents`). È una scelta: un tap globale
  registrerebbe anche fuori dall'app, ma pretenderebbe il permesso
  Accessibilità.
- **Lunghezza macro**: verificata sul dispositivo fino a 49 eventi. Oltre
  l'app avvisa ma non blocca, perché nessuno ha ancora provato — il vecchio
  tetto di 15 eventi era un errore, nato da una sezione obsoleta di
  `PROTOCOL.md`.
- **Nome macro** oltre 12 byte, caratteri non codificabili, macro vuota: il
  bottone "Scrivi su dispositivo" si disabilita davvero finché non correggi.
- **Velocità degli effetti reattivi**: il byte è identificato (offset 36) ma i
  valori sensati per ciascun effetto non sono stati esplorati a fondo.
- **Macro e rimappatura sullo stesso tasto**: permesse ma segnalate, il
  comportamento del dispositivo in quel caso non compare in nessuna cattura.
- **Riassegnazione delle rotelle**: la scheda la permette e lo dice, ma
  nessuna cattura mostra una rotella riprogrammata — di fabbrica lo sono già,
  e questo si vede. Va verificata dopo la scrittura.

## Cosa gira senza il pad collegato

Il motore ha un banco di prova che non tocca l'hardware — sessione, keymap,
slot di illuminazione, codifica delle macro, comandi delle modalità e regola
degli ACK:

```bash
cd ../ControlPadEngine && python3 -m unittest discover -s tests
```
