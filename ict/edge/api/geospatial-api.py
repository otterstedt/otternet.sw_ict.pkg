#!/usr/bin/python

import sys
import os
from time import sleep
from bottle import route, run, response, abort
from sense_hat import SenseHat
import time
import requests
import json
import calendar
import random
import subprocess
import threading
from usb.core import find as finddev

from dateutil.parser import parse

from gps3.agps3threaded import AGPS3mechanism


class SenseHatPoller(object):


    def __init__(self, interval=1):

        self.interval = interval

        self.x = None;
        self.y = None;
        self.z = None;

        connected_hat = False
        while not connected_hat:
            try: 
                self.sensehat = SenseHat()
                connected_hat = True
            except Exception as e:
                print(str(e))

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True                            # Daemonize thread
        thread.start()                                  # Start the execution

    def run(self):

        loop = 0;

        while loop < 100:
            try:
                acceleration = sense.get_accelerometer_raw()
                x = acceleration['x']
                y = acceleration['y']
                z = acceleration['z']
                loop += 1;
            except Exception as e:
                pass;
        self.x = x;
        self.y = y;
        self.z = z;

    def getHat(self):
        return self.sensehat

    def getReference(self):
        if self.x:
            return { "x": self.x, "y": self.y, "z": self.z };
        else:
            return None;

class gpsPoller(object):


    def __init__(self, interval=1):

        print("Starting gpsd poller")
        sleep(5)
        self.agps = AGPS3mechanism()  # Instantiate AGPS3 Mechanisms
        self.agps.stream_data(port=2947)  # From localhost (), or other hosts, by example, (host='gps.ddns.net')
        self.agps.run_thread()  # Throttle time to sleep after an empty lookup, default '()' 0.2 two tenths of a second

        self.interval = interval
        self.laststamp = None
        self.active = False


        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True                            # Daemonize thread
        thread.start()                                  # Start the execution

    #only works if root
    def resetGps(self):
        print("Resetting GPS Dongle.")
        try:
            dev = finddev(idVendor=0x067b, idProduct=0x2303)
            dev.reset()
        except Exception as e:
            print("GPS reset failed: " + str(e.message))

    def run(self):
        """ Method that runs forever """
        failures = 0;

        while True:
            try:
                if failures > 120:
                    print("Exit Geospatial API due to missing GPS data")
                    #os.kill(os.getpid(), signal.SIGINT)
                    os._exit(1)
                    #this will trigger a service restart if configured as systemd service with restart
                  

                current = self.agps.data_stream.time
                print("current: '" + str(current) + "' last: " + str(self.laststamp));
                if (current != "n/a") and current != self.laststamp:
                    self.active = True;
                    failures = 0
                else:
                    self.active = False;
                    failures += 1;

                print("is active: " + str(self.active));

                self.laststamp = current;
            except SystemExit as se:
                print("System exit")
                sys.exit(1)
            except Exception as e:
                print("Loop had exception")
                self.active = False;
                failures += 1;

            time.sleep(self.interval)

    def isGpsActive(self):
        return self.active;

    def getAgps(self):
        return self.agps;



spoller = SenseHatPoller();
sense = spoller.getHat();

gpspoller = gpsPoller(1.001);

@route('/gps/current')
@route('/gps/current/')
def gps():
    start_time = time.time()

    response.content_type = 'application/json'

    if gpspoller.isGpsActive():
        agps_thread = gpspoller.getAgps();
        timegps = agps_thread.data_stream.time
        print("GPS time: " + str(timegps));
        date = parse(timegps)
        latitude = agps_thread.data_stream.lat
        longitude = agps_thread.data_stream.lon
        altitude = agps_thread.data_stream.alt
        speed = agps_thread.data_stream.speed
        course = agps_thread.data_stream.track
        climb = agps_thread.data_stream.climb
        satellites = agps_thread.data_stream.satellites

        orientation = sense.get_orientation()
        pitch = orientation['pitch']
        roll = orientation['roll']
        yaw = orientation['yaw']

        acceleration = sense.get_accelerometer_raw()
        x = acceleration['x']
        y = acceleration['y']
        z = acceleration['z']

        t = sense.get_temperature()
        p = sense.get_pressure()
        h = sense.get_humidity()

        t = round(t, 1)
        p = round(p, 1)
        h = round(h, 1)

        timens = int(((calendar.timegm(date.utctimetuple()) * 1000000)  + date.microsecond) * 1000)
        #timens = timens + 619315200000000000; 

        execution = time.time() - start_time;

        return { "execution": execution, "isotime": timegps, "satellites": satellites, "climb": climb, "course": course, "temp": t, "pressure": p, "humidity": h, "time": timens, "lat": latitude, "lon": longitude, "alt": altitude, "speed": speed, "pitch": pitch, "roll": roll, "yaw": yaw, "x":  x, "y": y, "z": z, "content": True}
    else:
        execution = time.time() - start_time;
        response.status = 503
        return { "execution": execution, "content": False}

@route('/sensehat/current')
@route('/sensehat/current/')
def sensehat():

    response.content_type = 'application/json'
    

    orientation = sense.get_orientation()
    pitch = orientation['pitch']
    roll = orientation['roll']
    yaw = orientation['yaw']

    acceleration = sense.get_accelerometer_raw()
    x = acceleration['x']
    y = acceleration['y']
    z = acceleration['z']

    return {"pitch": pitch, "roll": roll, "yaw": yaw, "x":  x, "y": y, "z": z, "content": True}

@route('/sensehat/text/<message>/')
@route('/sensehat/text/<message>')
def sensehatcolor(message=""):
    sense.show_message(text_string=message)
    response.content_type = 'application/json'
    return {}

@route('/sensehat/color/<r>/<g>/<b>')
@route('/sensehat/color/<r>/<g>/<b>/')
def sensehatcolor(r=0, g=0, b=0):
    sense.show_message(text_string="", back_colour=[int(r), int(g), int(b)])
    response.content_type = 'application/json'
    return {}

@route('/sensehat/reference')
@route('/sensehat/reference/')
def sensehatcolor(r=0, g=0, b=0):
    response.content_type = 'application/json'
    reference = spoller.getReference();

    if not reference:
        response.status = 503
        return {}
    else:
        return reference;





run(host='0.0.0.0', port=8082, debug=True)

        
