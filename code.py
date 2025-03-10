# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import ssl
import board
from math import sqrt
from digitalio import DigitalInOut, Direction
from analogio import AnalogIn
import adafruit_connection_manager
import adafruit_requests
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_io.adafruit_io import IO_MQTT
import adafruit_wiznet5k.adafruit_wiznet5k_socketpool as socket



# Get Adafruit.io details from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("You need secrets.py to run this program. Please add them to the lib folder.")
    raise

# Initialize spi interface
import busio
cs = DigitalInOut(board.GP17)
spi_bus = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)

# Initialize ethernet interface with DHCP
eth = WIZNET5K(spi_bus, cs)


#Initialize a requests session
pool = adafruit_connection_manager.get_radio_socketpool(eth)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(eth)
requests = adafruit_requests.Session(pool, ssl_context)


# initiliazing feed
power_feed = secrets["aio_username"] + "/feeds/power"
led_feed = [secrets["aio_username"] + "/feeds/red", secrets["aio_username"] + "/feeds/yellow", secrets["aio_username"] + "/feeds/green"]
controller_feed = secrets["aio_username"] + "/feeds/control"

# Set power to True as we turned on the device
power = True
messages = {}
subscribe_feed_list = [power_feed, controller_feed]

# Define callback methods which are called when events occur
def connected(client, userdata, flags, rc):
    # This function will be called when the client is connected
    # successfully to the broker.
    for f in subscribe_feed_list:
        print("Connected to Adafruit IO! Listening for topic changes on %s" % f)
        # Subscribe to all changes on the feed list.
        client.subscribe(f)



def disconnected(client, userdata, rc):
    # This method is called when the client is disconnected
    print("Disconnected from Adafruit IO!")



def message(client, topic, message):
    # This method is called when a topic the client is subscribed to
    # has a new message.

    
    print(f"New message on topic {topic}: {message}")
    
    if topic == power_feed:    
        global power
        
        # Turn this device On/Off based on the interface 
        power = bool(int(message))
        
        
    elif topic == controller_feed: 
        global current_light_on_pos, led_set
        
        if int(message) == 5:      # if online controller pressed UP
            if current_light_on_pos == 2  :   # All lights are On
                print("Max_light_achieved")
            else:
                led_set[current_light_on_pos + 1].value = True  # Turn On the next light
                current_light_on_pos = current_light_on_pos + 1 # Increase pointer

                # Send Data to online interface
                mqtt_client.publish(led_feed[current_light_on_pos], 1)
                
        elif int(message) == 13:   #if online controller pressed DOWN
            if current_light_on_pos  == -1 :  # All lights are Off
                print("Min_light_achieved")

            else:
                led_set[current_light_on_pos].value = False   # Turn off the current light position

                # Send Data to online interface
                mqtt_client.publish(led_feed[current_light_on_pos], 0)
                current_light_on_pos = current_light_on_pos - 1 # Decrease pointer

    


# Setting Up MQTT client
mqtt_client = MQTT.MQTT(
    broker="io.adafruit.com",
    username=secrets["aio_username"],
    password=secrets["aio_key"],
    is_ssl=True,
    socket_pool=pool,
    ssl_context=ssl_context,
)

mqtt_client.on_connect = connected
mqtt_client.on_disconnect = disconnected
mqtt_client.on_message = message



# Connect the client to the MQTT broker.
print("Connecting to Adafruit IO...")
mqtt_client.connect()

# Notify the interface that the power has turned On
mqtt_client.publish(power_feed, 1)


#Set Joystick as analog input
Dir_Vertical = AnalogIn(board.GP26) #UP/Down
# Dir_Horizontal = AnalogIn(board.GP27) #Left/Right

#Set LED as digital ouput
led_G, led_Y, led_R = DigitalInOut(board.GP11), DigitalInOut(board.GP13), DigitalInOut(board.GP15)
led_G.direction, led_Y.direction, led_R.direction = Direction.OUTPUT, Direction.OUTPUT, Direction.OUTPUT
led_set = [led_R, led_Y, led_G]

# Test if led bulb work or not
led_G.value, led_Y.value, led_R.value= 1, 1, 1
time.sleep(1)
led_G.value, led_Y.value, led_R.value= 0, 0, 0
current_light_on_pos = -1


# power  = False
while power:
    
    mqtt_client.loop()
    
    read_Vertical = Dir_Vertical.value
    # read_Horizontal =Dir_Horizontal.value
    print("Current Position: ", current_light_on_pos)
    print("Vertical Position: ", read_Vertical)
    # Light response function
    if read_Vertical >= 60000:  # Increase number of light turned on if Joystick goes up
        if current_light_on_pos == 2  : # All lights are on
            print("Max_light_achieved")
        else:
            led_set[current_light_on_pos + 1].value = True
            current_light_on_pos = current_light_on_pos + 1

            # Send Data
            mqtt_client.publish(led_feed[current_light_on_pos], 1)

    elif read_Vertical <= 3000: # Decrease number of light turned on if Joystick goes down

        if current_light_on_pos  == -1 : # All lights are Off
            print("Min_light_achieved")

        else:
            led_set[current_light_on_pos].value = False

            mqtt_client.publish(led_feed[current_light_on_pos], 0)


            current_light_on_pos = current_light_on_pos - 1
            
    time.sleep(0.5)
    

print("Power is off")
for y in range(current_light_on_pos + 1):
    mqtt_client.publish(led_feed[y], 0)
mqtt_client.publish(controller_feed, 0)

mqtt_client.disconnect()
print("Machine Tunred off")




