"""
The code below is built upon the guides linked here: 
https://johannesbader.ch/blog/track-your-heartrate-on-raspberry-pi-with-ant/

and 

https://www.instructables.com/id/PWM-Regulated-Fan-Based-on-CPU-Temperature-for-Ras/?fbclid=IwAR2iLaa_UvnwZWOha3XgddMv8Ik-GqZNTlMovMkld2qDS5jerpPwBc3FBTc

The Johannes Bader link contains all the code related to recieving data from my Blutetooh heart monitor
(HRM class and imports from ant.core primarily)

The isntructables link contains all the code related to powering the fan.

My code consits of parsing recieved data from the bluetooth sensor and changing the fan speed.
"""


"""
    Code based on:
        https://github.com/mvillalba/python-ant/blob/develop/demos/ant.core/03-basicchannel.py
    in the python-ant repository and
        https://github.com/tomwardill/developerhealth
    by Tom Wardill
"""
import sys
import time
import threading
from ant.core import driver, node, event, message, log
from ant.core.constants import CHANNEL_TYPE_TWOWAY_RECEIVE, TIMEOUT_NEVER

import RPi.GPIO as GPIO

class HRM(event.EventCallback):

    def __init__(self, serial, netkey):
        self.serial = serial
        self.netkey = netkey
        self.antnode = None
        self.channel = None

    def start(self):
        print("starting node")
        self._start_antnode()
        self._setup_channel()
        self.channel.registerCallback(self)
        print("start listening for hr events")

    def stop(self):
        if self.channel:
            self.channel.close()
            self.channel.unassign()
        if self.antnode:
            self.antnode.stop()

    def __enter__(self):
        return self

    def __exit__(self, type_, value, traceback):
        self.stop()

    def _start_antnode(self):
        stick = driver.USB2Driver(self.serial)
        self.antnode = node.Node(stick)
        self.antnode.start()

    def _setup_channel(self):
        key = node.NetworkKey('N:ANT+', self.netkey)
        self.antnode.setNetworkKey(0, key)
        self.channel = self.antnode.getFreeChannel()
        self.channel.name = 'C:HRM'
        self.channel.assign('N:ANT+', CHANNEL_TYPE_TWOWAY_RECEIVE)
        self.channel.setID(120, 0, 0)
        self.channel.setSearchTimeout(TIMEOUT_NEVER)
        self.channel.setPeriod(8070)
        self.channel.setFrequency(57)
        self.channel.open()

    def process(self, msg):
        global BPM
        if isinstance(msg, message.ChannelBroadcastDataMessage):
            m = int(ord(msg.payload[-1]))
            print("!! PRODUCING: "+str(m))
            BPM = m

SERIAL = '/dev/ttyUSB0'
NETKEY = 'B9A521FBBD72C345'.decode('hex')

#setup GPIO stuff
FAN_PIN = 21
WAIT_TIME = 1
PWM_FREQ = 25

DEF_SPEED = 45

GPIO.setmode(GPIO.BCM)
GPIO.setup(FAN_PIN, GPIO.OUT, initial=GPIO.LOW)

fan=GPIO.PWM(FAN_PIN,PWM_FREQ)

print("--SETTING DEFAULT FAN SPEED!! (45%)")
fan.start(DEF_SPEED);

# Got from:
# https://stackoverflow.com/questions/5998245/get-current-time-in-milliseconds-in-python
current_milli_time = lambda: int(round(time.time() * 1000))

#most current BPM
BPM = None

#stop bpmConsumer flag
STOP = False

"""
bpmCounter and bpmDigester are written by me (Jose Guaro)
"""
def bpmConsumer():
    global BPM
    global STOP
    while not STOP:
        if not (BPM is None):
            print(".....!GOT DATA "+str(BPM)+"!....")
            bpmDigester(BPM)
            BPM = None
            time.sleep(3)            
        else:
            print(".....waiting on data, sleeping for 1 sec....")
            time.sleep(1)        

def bpmDigester(bpm):
    global fan
    global STILL_WAITING

    print("heart rate is "+str(bpm))
    
    FACTOR = .5625
    fanSpeed = bpm * FACTOR
    print("  ----SPEED CALC: "+str(fanSpeed))
    
    if fanSpeed < DEF_SPEED:
        fanSpeed = DEF_SPEED
        print("  *TOO LOW: DEFAULTING")
    elif fanSpeed > 100:
        print("  *TOO HIGH: MAxing at 100")
        fanSpeed = 100
    
    print("   -> FINAL SPEED: "+str(fanSpeed))
    fan.ChangeDutyCycle(fanSpeed)

#start bpmConsumer on a seperate thread
ct = threading.Thread(target=bpmConsumer)
ct.start()

with HRM(serial=SERIAL, netkey=NETKEY) as hrm:
    hrm.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print("interrupted! Cleaning....")
            STOP = True
            print("stopped consumer!")
            ct.join()
            print("consumer actually stopped!")

            GPIO.cleanup()
            hrm.stop()
            sys.exit(0)
