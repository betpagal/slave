import time
import os
import sys
import board
import busio
import random
from digitalio import DigitalInOut
import neopixel
import supervisor
from wheel import wheel

class stair_slave:
     neopixel_pin = board.NEOPIXEL
     broker = 'raspi-stairs' #'10.0.2.49'
     port = 1883

     # NeoPixel strip (of 16 LEDs) connected on D4
     NUMPIXELS = 2
     neopixels = neopixel.NeoPixel(neopixel_pin, NUMPIXELS, brightness=0.1, auto_write=False)
     i = 128
     
     while True:
          i = (i + 1) % 256
          # make the neopixels swirl around
          for p in range(NUMPIXELS):
               idx = int((p * 256 / NUMPIXELS) + i)
               neopixels[p] = wheel(idx & 255)
          neopixels.show()
          time.sleep(1.5)

     # except Exception as e:
     #      # when all else fails
     #      print("-----")
     #      print("Error: ", sys.print_exception(e))
     #      print("Bailing out...reloading")
     #      print("-----")
     #      supervisor.reload()
