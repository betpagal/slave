import time
import sys
import digitalio
import board
import busio
import pulseio
import random
from digitalio import DigitalInOut
from analogio import AnalogIn
import neopixel
import supervisor
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_minimqtt import MQTT
from wheel import wheel

LED_RED = (255, 0, 0)
LED_YELLOW = (255, 150, 0)
LED_GREEN = (0, 255, 0)
LED_CYAN = (0, 255, 255)
LED_BLUE = (0, 0, 255)
LED_PURPLE = (180, 0, 255)

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

neopixel_pin = board.D13 #NEOPIXEL #D13 # .NEOPIXEL
ww_level = 10
cw_level = 10

ir_in = AnalogIn(board.A3)
tx_out = digitalio.DigitalInOut(board.TX)
tx_out.direction = digitalio.Direction.OUTPUT

# NeoPixel strip (of 16 LEDs) connected on D4
NUMPIXELS = 100
neopixels = neopixel.NeoPixel(neopixel_pin, NUMPIXELS, brightness=1, auto_write=False)
status_light = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.01)
cwled = pulseio.PWMOut(board.D11)
wwled = pulseio.PWMOut(board.D12)

# AirLift Feather Wing
esp32_cs = DigitalInOut(board.D10)
esp32_ready = DigitalInOut(board.D9)
esp32_reset = DigitalInOut(board.D6)

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, neopixels, debug=True) 

broker = 'io.adafruit.com'
port = 1883

# Setup a feed named 'photocell' for publishing
photocell_feed = secrets['aio_username'] + '/feeds/photocell'
# Setup feeds for subscribing to changes
cw_feed = secrets['aio_username'] + '/feeds/cw-level'
ww_feed = secrets['aio_username'] + '/feeds/ww-level'

def get_voltage(pin):
    return (pin.value / 33000)# * 3.3) #/ 65536

def mqtt_connected(client, userdata, flags, rc):
    # This function will be called when the client is connected
    # successfully to the broker.
    print('Connected')
    status_light[0] = LED_GREEN
    status_light.show()
    # Subscribe to all changes on the feeds.
    client.subscribe(ww_feed)
    client.subscribe(cw_feed)

def mqtt_disconnected(client, userdata, rc):
    # This method is called when the client is disconnected
    status_light[0] = LED_RED
    status_light.show()
    print('Disconnected')

def mqtt_message(client, topic, message):
    # This method is called when a topic the client is subscribed to
    # has a new message.
    status_light[0] = LED_PURPLE
    status_light.show()

    if '/cw-level' in topic:
        cw_level = message
        print('cw', cw_level, sep = '', end = ' ')
        cwled.duty_cycle = int(cw_level) * 650
    if '/ww-level' in topic:
        ww_level = message
        print('ww', ww_level, sep = '', end = ' ')
        wwled.duty_cycle = int(ww_level) * 650

    status_light[0] = LED_GREEN
    status_light.show()

def mqtt_subscribe(client, userdata, topic, granted_qos):
    print('Subscribed to {0} with QOS level {1}'.format(topic, granted_qos))

def mqtt_unsubscribe(client, userdata, topic, pid):
    print('Unsubscribed from {0} with PID {1}'.format(topic, pid))

# Set up a MiniMQTT Client
mqtt_client = MQTT(socket,
    broker = broker,
    port = port,
    username = secrets['aio_username'],
    password = secrets['aio_key'],
    network_manager = wifi)

def mqtt_connect_all():
    print('1', end = ' ')
    status_light[0] = LED_YELLOW
    status_light.show()
    
    print('2', end = ' ')
    tx_out.value = True

    print('3', end = ' ')
    wifi.connect()

    print('4', end = ' ')
    status_light[0] = LED_BLUE
    status_light.show()

    # Connect the client to the MQTT broker.
    print("Connecting to", broker)
    print('5', end = ' ')
    mqtt_client.connect()
    print('6', end = ' ')
    mqtt_client.publish(photocell_feed, "connection", qos=0)

# Setup the callback methods above
mqtt_client.on_connect = mqtt_connected
mqtt_client.on_disconnect = mqtt_disconnected
mqtt_client.on_message = mqtt_message
mqtt_client.on_subscribe = mqtt_subscribe
mqtt_client.on_unsubscribe = mqtt_unsubscribe

# Connect the client to the MQTT broker.
try:
    print('Connecting to Adafruit IO...'.rstrip())
    mqtt_connect_all()
    mqtt_client.publish(cw_feed, 17, qos=0)
    mqtt_client.publish(ww_feed, 19, qos=0)

    photocell_val = random.randint(0, 1023)

    i = 0
    while True:
        
        # Send a new message
        photocell_val += random.randint(-100,100)
        if photocell_val >= 923:
            photocell_val -= random.randint(0,100)
        if photocell_val <= 100:
            photocell_val += random.randint(0,100)

        # make the neopixels swirl around
        for p in range(NUMPIXELS):
            idx = int((p * 256 / NUMPIXELS) + i)
            neopixels[p] = wheel(idx & 255)
        neopixels.show()
        #print(neopixels[p], end='')

        try:
            if i % 5 == 0:
                mqtt_client.loop() # this is where the client looks for published messages
                print(get_voltage(ir_in), sep = '|', end = ' ')
                neopixels.brightness = 2 - get_voltage(ir_in)
            
            if i % 64 == 0: # just a randomy number to publish stuff
                #print(' Sending photocell value:', '{:4}'.format(photocell_val), '...', end='')
                #print(photocell_val, end = ' ')
                print('.', sep = '', end = '')
                status_light[0] = LED_PURPLE
                status_light.show()
                mqtt_client.publish(photocell_feed, photocell_val, qos=0)
                status_light[0] = LED_GREEN
                status_light.show()            
                #print('Sent!')
                
        except Exception as e:
            status_light[0] = LED_RED
            status_light.show()
            print ("error publishing:", e)
            mqtt_connect_all()
            while(not mqtt_client.is_connected()):
                print("not is_connected(2). trying connect_all()")
                mqtt_connect_all()
                time.sleep(4)
            print('recovery 2')

        i = (i+1) % 256	 # run from 0 to 255
        #print(i, end = ' ')
        time.sleep(0.0)

except Exception as e:
    # when all else fails
    print("-----")
    print("Error: ", sys.print_exception(e))
    print("Bailing out...reloading")
    print("-----")
    supervisor.reload()
