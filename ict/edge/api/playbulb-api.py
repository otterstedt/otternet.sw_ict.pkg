#!/usr/bin/python
from bottle import route, run
from time import sleep
from playbulbcandle import PlayBulbCandle
from multiprocessing import Pool
from functools import partial
import sys, traceback
from contextlib import closing
import mipow
import threading
import time

class BulbPoller(object):


    def __init__(self, bulb_macs, interval=30):

        self.interval = interval
        self.bulb_macs = bulb_macs
        
        self.bulbs = []
        self.all_bulbs = []
        self.missing_macs = []

        self.bulbs = self.setupBulbs()

        self.bulbs = [bulb for bulb in self.all_bulbs if self.isBulbAvailable(bulb)]

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True                            # Daemonize thread
        thread.start()                                  # Start the execution

    def run(self):
        """ Method that runs forever """
        while True:
            # Do something
            print('Check if bulbs are available')

            self.bulbs = [bulb for bulb in self.all_bulbs if self.isBulbAvailable(bulb)]

            print(str(len(self.bulbs)) + " available bulb(s).")

            #connect bulbs not found during startup
            for missing_mac in self.missing_macs:
                connected = False
                attempt=0
                stamp = time.time()
                while not connected and time.time() - stamp < 20:
                    try:
                        bulb = mipow.mipow(missing_mac)
                        bulb.connect()
                        self.all_bulbs.append(bulb)
                        self.missing_macs.remove(missing_mac)
                        connected = True
                    except Exception as e:
                        print(str(e))
                        print("Failed to connect missing bulb: " + missing_mac + " try: " + str(attempt))
                        attempt+=1


            sleep(self.interval)

    def setupBulbs(self):

        bulbs = []


        for bulb_mac in self.bulb_macs:
            connected = False
            attempt=0
            stamp = time.time()
            while not connected and time.time() - stamp < 10:
                try: 
                    bulb = mipow.mipow(bulb_mac)
                    bulb.set_rgb(50, 100, 150)
                    bulbs.append(bulb)
                    connected = True
                    print("Connected bulb with mac: " + bulb_mac)
                except Exception as e:
                    print("Create a new bulb instance: " + str(e))
                    print("Failed to connect: " + bulb_mac + " try: " + str(attempt))
                    attempt+=1

            if not connected and bulb_mac not in self.missing_macs:
                self.missing_macs.append(bulb_mac)

        self.bulbs = self.all_bulbs = bulbs




    def getBulbs(self):
        print("Returning " + str(len(self.bulbs)) + " bulbs")
        return self.bulbs

    def isBulbAvailable(self, bulb):
        try:
            bulb.connect()
        except Exception as e:
            print("Executed connect: " + str(e))
            print("Device is already connected? Mac: " + bulb.mac)

        loop=0
        stamp = time.time()
        while time.time() - stamp < 10:
            try:
                bulb.get_state()
                return True
            except Exception as e:
                print(str(e))
                print("Bulb lost: " + str(bulb) + "try: " + str(loop) + "time: " + str(time.time() - stamp))
                loop+=1
                
        return False




def setBulbsColor(mipowbulbs, r, g, b):
    try:
        print("Setting colors for bulbs")
        print("looping bulbs")
        for mipowbulb in mipowbulbs:
            print("Got bulb: " + str(mipowbulb))
            mipowbulb.set_rgb(r, g, b)
    except Exception as e:
        traceback.print_exc()
        print("Failed to set bulb colors: " + str(e))

#modes = {1: 'fade', 2: 'jumpRgb', 3: 'fadeRgb', 4: 'candle', 255: 'off'}
def setBulbsEffect(mipowbulbs, r, g, b, a, mode, speed):
    try:
        print("Setting effect for bulbs")
        for mipowbulb in mipowbulbs:
            print("Got bulb: " + str(mipowbulb))
            mipowbulb.set_effect(r, g, b, a, mode, speed)
    except Exception as e:
        traceback.print_exc()
        print("Failed to set bulb effect: " + str(e))


signalist_macs = [u'A2:AA:4B:15:AC:E6', u'41:4A:4B:16:AC:E6', u'68:24:4B:16:AE:C6', u'28:6E:4B:12:AC:E6']
print(signalist_macs)

print("Assigning playbulb instances")
bpoller = BulbPoller(signalist_macs)




@route('/red')
def hello():
    setBulbsColor(bpoller.getBulbs(), 255, 0, 0)

@route('/green')
def hello():
    setBulbsColor(bpoller.getBulbs(), 0, 255, 0)

@route('/yellow')
def hello():
    setBulbsColor(bpoller.getBulbs(), 255, 255, 0)

@route('/color/<r>/<g>/<b>/')
@route('/color/<r>/<g>/<b>')
def hello(r=0, g=0, b=0):
    # with closing(Pool()) as p:
    #     print("async fire")
    #     res = p.apply_async(setBulbsColor, (bpoller.getBulbs(), int(r), int(g), int(b), ))
    #     print(res.get(timeout=10))
    setBulbsColor(bpoller.getBulbs(), int(r), int(g), int(b))


@route('/effect/<r>/<g>/<b>/')
@route('/effect/<r>/<g>/<b>')
def hello(r=0, g=0, b=0):
    setBulbsColor(bpoller.getBulbs(), int(r), int(g), int(b))
    setBulbsEffect(bpoller.getBulbs(), int(r), int(g), int(b), 255, 4, 50)
    

@route('/effect/off/<r>/<g>/<b>/')
@route('/effect/off/<r>/<g>/<b>')
def hello(r=0, g=0, b=0):
    setBulbsEffect(bpoller.getBulbs(), int(r), int(g), int(b), 255, 255, 50)

@route('/clear')
def hello():
    for mipowbulb in bpoller.getBulbs():
        mipowbulb.off()

run(host='localhost', port=8081, debug=True)
