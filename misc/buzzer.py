#!/usr/bin/env python3


import time
from gpiozero import TonalBuzzer


def beep_buzzer(n):
    try:
        buzzer_pin = 12
        buzzer = TonalBuzzer(buzzer_pin)
        for _ in range(n):
            buzzer.play(440)
            time.sleep(0.1)
            buzzer.stop()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExited!")


if __name__ == "__main__":
    beep_buzzer(3)
