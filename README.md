# ControlPad

Controllo completo del **Cooler Master ControlPad** (`VID 0x2516` / `PID 0x007B`,
variante Cherry) su macOS, dove il software ufficiale non esiste: è solo per
Windows. Il protocollo USB è stato ricavato per reverse engineering dalle
catture in `ControlPAD - CATTURA/captures/` e verificato inviando i comandi al
dispositivo vero.

## Le quattro cartelle

| Cartella | Cosa contiene |
|---|---|
| `ControlPadEngine/` | **il codice**: driver, sessione, macro, effetti, e il bridge JSON che l'app usa come sottoprocesso |
| `ControlPadGUI/` | l'app macOS in SwiftUI — quattro schede come l'app Windows, più Impostazioni |
| `ControlPAD - CATTURA/` | le catture USB, il protocollo byte per byte, gli strumenti che l'hanno decodificato |
| `Come_usare_manipolare_i_4_led/` | i quattro LED indicatori: primitive, diciassette effetti, misure |

La libreria vive in un posto solo. Fino ad agosto 2026 ne esisteva una copia
dentro `ControlPAD - CATTURA/`, ed è rimasta indietro proprio sulla correzione
che contava di più — motivo per cui adesso quella cartella non contiene moduli.

## Partire

```bash
pip3 install hidapi                       # l'unica dipendenza

cd ControlPadEngine
python3 -m unittest discover -s tests     # senza pad collegato
python3 -c "import hid; print(hid.enumerate(0x2516, 0x007B) and 'pad visto')"

cd ../ControlPadGUI
swift run                                 # l'app, in sviluppo
./scripts/make_app_bundle.sh              # l'app, impacchettata in ~/Applications
```

## Da leggere prima di toccare il protocollo

* `ControlPAD - CATTURA/PROTOCOL.md` — il protocollo, e la sezione "Stato del
  lavoro" con quello che è stato eseguito davvero e quello che è solo dedotto.
* `ControlPAD - CATTURA/README.md` — le trappole, ognuna costata ore e nessuna
  deducibile dai byte: le tre numerazioni degli stessi 24 tasti, la pausa di
  flash dopo ogni macro, la coda degli ACK da drenare, i colori dell'app che
  non sono mai valori puri.
* `Come_usare_manipolare_i_4_led/ANIMAZIONI.md` — i quattro LED sopra il pad,
  che sono l'unica superficie su cui si possano far scorrere fotogrammi.

Regola generale del progetto: **un numero misurato dall'host non dimostra
niente sul pad finché non lo si guarda.** Il device risponde ACK anche a quello
che non esegue.

## Cosa resta nel pad e cosa no

**Restano, per sempre**: macro, rimappature, funzioni speciali, assegnazioni di
profilo. Scritte una volta, vivono nel firmware e funzionano su qualunque
computer, senza software.

**Vanno riapplicati a ogni collegamento**: colori ed effetti. Non è un limite
di questo progetto — non li memorizza nemmeno il software ufficiale, che tiene
un servizio residente apposta per rimandarli. L'app fa lo stesso mentre è
aperta.

**Eccezione**: i quattro LED indicatori sopravvivono allo scollegamento, quindi
l'ultimo fotogramma scritto è quello con cui il pad si riaccende.
