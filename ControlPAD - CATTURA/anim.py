"""Animate the four indicator LEDs, and measure how fast they can be driven.

They take a live command rather than a profile write, so there is no flash
wear and none of the 72 ms settling the macro path needs: the only limit is
how quickly reports can be pushed over USB.
"""

import colorsys
import time

from controlpad import ControlPad

FRAME = 1 / 60


def hue(h, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, 1.0, v)
    return int(r * 255), int(g * 255), int(b * 255)


def rincorsa(pad, giri=6, passo=0.09):
    """Un LED acceso che scorre, con una scia che si spegne dietro di lui."""
    for n in range(giri * 4):
        frame = []
        for i in range(4):
            distanza = (n - i) % 4
            frame.append(hue(n / 16, 1.0 if distanza == 0 else
                             0.25 if distanza == 1 else 0.05))
        pad.set_indicators(frame)
        time.sleep(passo)


def arcobaleno(pad, durata=6.0, sfasamento=0.12):
    """Sfumatura continua, ogni LED sfasato rispetto al precedente."""
    inizio = time.time()
    n = 0
    while time.time() - inizio < durata:
        t = (time.time() - inizio) * 0.35
        pad.set_indicators([hue(t + i * sfasamento) for i in range(4)])
        n += 1
        time.sleep(FRAME)
    return n, time.time() - inizio


def respiro(pad, cicli=3, colore=(0.55, 1.0)):
    """Dissolvenza morbida su tutti e quattro insieme."""
    h, _ = colore
    for c in range(cicli):
        for passo in range(60):
            v = (1 - abs(passo - 30) / 30) ** 2
            pad.set_indicators([hue(h, v)] * 4)
            time.sleep(FRAME)


def velocita_massima(pad, campioni=120):
    """Quanti aggiornamenti al secondo regge, senza attese artificiali."""
    inizio = time.time()
    for n in range(campioni):
        pad.set_indicators([hue(n / 40 + i * 0.1) for i in range(4)])
    trascorso = time.time() - inizio
    return campioni / trascorso, trascorso


if __name__ == "__main__":
    with ControlPad() as pad:
        print("1/4  rincorsa")
        rincorsa(pad)

        print("2/4  arcobaleno")
        n, sec = arcobaleno(pad)
        print(f"     {n} fotogrammi in {sec:.1f} s -> {n / sec:.0f} al secondo")

        print("3/4  respiro")
        respiro(pad)

        print("4/4  velocita massima, senza attese")
        fps, sec = velocita_massima(pad)
        print(f"     {fps:.0f} aggiornamenti al secondo "
              f"({1000 / fps:.1f} ms per fotogramma)")

        pad.set_indicators([(255, 255, 255)] * 4)
        print("ripristinati bianchi")
