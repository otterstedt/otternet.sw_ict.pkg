#!/usr/bin/python

from time import sleep
import datetime
from bottle import route, run, response, abort
from sense_hat import SenseHat
import time
import requests
import json
import calendar
import random
import subprocess
import threading
import uuid
import os.path
import socket
import sys
from gi.repository import GExiv2
from PIL import Image
import paho.mqtt.client as mqtt
import base64
from shutil import copyfile

import configparser
config = configparser.ConfigParser()
secrets = configparser.ConfigParser()
config.read('../config/ict.ini')
secrets.read('../config/.ict.ini')


#homefolder = os.path.expanduser("~");

#logfolder = homefolder + "/gps/logs";
logfolder = config['tracking']['log_path']

print("Folder exists: " + str(os.path.exists(logfolder)))
if not os.path.exists(logfolder):
    print("Creating log folder.")
    os.makedirs(logfolder)
#snapfolder = homefolder + "/gps/snaps";
snapfolder = config['tracking']['snaps_path']
if not os.path.exists(snapfolder):
    print("Creating snap folder.")
    os.makedirs(snapfolder)
errorlog = logfolder + "/error.log";
trackheader = "type,time,latitude,longitude,alt,speed,trackid";
latestpath = logfolder + "/latest-tracking.log"
nofixes = 0
trackThreshold = 20
newtrack=1
trackid = str(uuid.uuid4())
db_name = "tracks"
type="v60"
#type="vacation"

## MQTT settings
#topic = "hass/message/state/dclxvi_pi"
topic = config['mqtt']['state_topic']

#locationtopic = "hass/message/location/dclxvi_pi"
locationtopic = config['mqtt']['location_topic']

#imagetopic = "hass/message/image/dclxvi_pi/front"
imagetopic = config['mqtt']['image_topic']


#url = "mqtt.otternet.ca"
url = secrets['mqtt']['host']
ca = "/etc/ssl/certs/ca-certificates.crt"
connected = False

def on_connect(client, userdata, flags, rc):
    print("Connected flags ",str(flags),"result code ",str(rc))

    if rc == 0:

        print("Connected to broker")

        global connected                #Use global variable
        connected = True                #Signal connection

    else:
        connected = False
        print("Connection failed")

def on_disconnect(client, userdata, rc):
    print("MQTT client got disconnected")
    global connected
    connected = False

def connect():
    mqttc = mqtt.Client()
    mqttc.username_pw_set(username = secrets['mqtt']['user'], password = secrets['mqtt']['password'])
    mqttc.tls_set(ca)
    mqttc.on_connect = on_connect
    mqttc.loop_start()
    try:
        mqttc.connect(url, port=8883)
    except:
        print("MQTT Connection failed");


    return mqttc




def grabImage(host, port, output):

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, int(port)))

    fh = s.makefile()

    # Read in HTTP headers:
    line = fh.readline()
    while line.strip() != '':
        parts = line.split(':')
        if len(parts) > 1 and parts[0].lower() == 'content-type':
            # Extract boundary string from content-type
            content_type = parts[1].strip()
            boundary = content_type.split(';')[1].split('=')[1]
        line = fh.readline()

    if not boundary:
        raise Exception("Can't find content-type")

    # Seek ahead to the first chunk
    while line.strip() != boundary:
        line = fh.readline()

    # Read in chunk headers
    while line.strip() != '':
        parts = line.split(':')
        if len(parts) > 1 and parts[0].lower() == 'content-length':
            # Grab chunk length
            length = int(parts[1].strip())
        line = fh.readline()

    image = fh.read(length)

    with open(output, 'w') as out_fh:
        out_fh.write(image)

    s.close()


#send color to sensehat API
def sendRgb(red, green, blue):
    try:
        requests.get(config['endpoint']['sensehat'] + "/sensehat/color/" + str(red) + "/" + str(green) + "/" + str(blue), timeout=1);
    except Exception as e:
        print("Failed to send color to GPS/Sensehat API: " + str(e));

def sendText(text):
    try:
        requests.get(config['endpoint']['sensehat'] + "/sensehat/text/" + text, timeout=30);
    except Exception as e:
        print("Unable to send text to GPS/Sensehat API: " + str(e));

def showGreen():
    sendRgb(0,255,0);

def showRed():
    sendRgb(255,0,0);

def showYellow():
    sendRgb(255,255,0);

def showBlank():
    sendRgb(0,0,0);

def showFlash():
    sendRgb(255, 255, 255);
    sleep(0.1);
    sendRgb(0, 0, 0);

def waitForGpsDevice():
    while not os.path.islink("/dev/gps"):
        print("No GPS connected");
        showRed();
        sleep(5);


def writeFile(file, content):
    with open(file, "a+") as myfile:
        myfile.write(str(content) + "\n");

def overwriteFile(file, content):
    with open(file, "w+") as myfile:
        myfile.write(str(content) + "\n");

def writeHeader(date):
    logfile = date + "-tracking.log"
    sendText("New track v2");
    writeFile(logfolder + "/" + logfile, trackheader);

def postDB(dbname, payload):
    try:
        requests.post("http://localhost:8086/write?db=" + dbname, data=payload, timeout=2)
    except Exception as e:
        print("Request failed: " + str(e));


sendRgb(50, 50, 50);

mqttc = connect()

while True:
    print("Starting GPS tracking loop");

    waitForGpsDevice();

    try:
        response = requests.get(config['endpoint']['tracking_api'] + "/gps/current", timeout=2).json();

        if response['content']:
            print("Got response from GPS/sensors API")
            showGreen();
            pitch = response['pitch']
            roll = response['roll']
            yaw = response['yaw']
            latitude = response['lat']
            longitude = response['lon']
            altitude = response['alt']
            speed = response['speed']
            longitude = response['lon']
            timens = response['time']
            x = response['x']
            y = response['y']
            z = response['z']
            temp = response['temp']
            pressure = response['pressure']
            humidity = response['humidity']
            climb = response['climb']
            course = response['course']





            eastwest = ('W' if int(longitude) < 0 else 'E')
            northsouth = ('S' if int(latitude) < 0 else 'N')

            s = int(timens) / 1000000000.0
            date = datetime.datetime.utcfromtimestamp(s).strftime('%Y-%m-%d');
            time = datetime.datetime.utcfromtimestamp(s).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z";

            print("Got date: " + date + " and time: " + time);

            imgfolder = snapfolder + "/" + date;

            img = imgfolder + "/"  + time + ".jpg";
            img640 = imgfolder + "/640x480-" + time + ".jpg";
            img320 = imgfolder + "/320x240-" + time + ".jpg";

            if not os.path.exists(imgfolder):
                print("Creating image folder.")
                os.makedirs(imgfolder)

            print("Grabbing image from stream to: " + img);
            showFlash();
            #grabImage("localhost", 8001, img);
            copyfile(config['motion']['snapshot'], img)
            print("Completed grabbing image from stream" + img);
            showGreen();


            print("Setting exif data");
            metadata = GExiv2.Metadata();
            metadata.open_path(img);

            print("Altitude: " + str(altitude) + " Longitude: " + str(longitude) + " Latitude: " + str(latitude));
            metadata.set_gps_info(longitude, latitude, altitude)
            metadata['Exif.GPSInfo.GPSAltitudeRef'] = "0" if altitude > 0.0 else "1";
            metadata['Exif.GPSInfo.GPSLatitudeRef'] = str(northsouth);
            metadata['Exif.GPSInfo.GPSLongitudeRef'] = str(eastwest);
            metadata['Exif.Image.DateTime'] = str(time);
            metadata['Exif.Photo.DateTimeOriginal'] = str(time);
            metadata['Exif.Photo.DateTimeDigitized'] = str(time);

            metadata.save_file()
            print("Completed setting exif data");


            #print("Scaling image");
            #image = Image.open(img)


            imageBase64 = None
            imageBinary = None
            try:
                with open(img, 'rb') as imgFile:
                    imageData = imgFile.read()
                    imageBase64 = base64.b64encode(imageData)
                    imageBinary = bytearray(imageData) 
            except:
                print("Failed to open and base encode image")
                
                
            #basewidth = 640
            #wpercent = (basewidth/float(image.size[0]))
            #hsize = int((float(image.size[1])*float(wpercent)))
            #newimage = image.resize((basewidth,hsize), Image.ANTIALIAS)
            #newimage.save(img640)

            #basewidth = 320
            #wpercent = (basewidth/float(image.size[0]))
            #hsize = int((float(image.size[1])*float(wpercent)))
            #newimage = image.resize((basewidth,hsize), Image.ANTIALIAS)
            #newimage.save(img320)

            #print("Completed scaling image");

            climb = climb if climb != 'n/a' else 0
            payloadpoint = "point,type={0},purpose={1},trackid={2} altitude={3},speed={4},longitude={5},latitude={6},climb={7},course={8} {9}".format(type,
                                                                                                                                                      "private",
                                                                                                                                                      trackid,
                                                                                                                                                      altitude,
                                                                                                                                                      speed,
                                                                                                                                                      longitude,
                                                                                                                                                      latitude,
                                                                                                                                                      climb,
                                                                                                                                                      course,
                                                                                                                                                      timens);
            print(payloadpoint)
            postDB("tracks", payloadpoint);

            payloadenv = "env temp={0},pressure={1},humidity={2} {3}".format(temp,
                                                                           pressure,
                                                                           humidity,
                                                                           timens);
            postDB("tracks", payloadenv);

            payloadmovement = "movement gravity={0},acceleration={1} {2}".format(z,
                                                                                 x,
                                                                                 timens);
            postDB("tracks", payloadmovement);





            logpath = logfolder + "/" + str(date) + "-tracking.log";

            if not os.path.isfile(logpath):
                print("Creating folder: " + logfolder)
                if not os.path.exists(logfolder):
                    os.makedirs(logfolder);
                writeFile(logpath, trackheader);

            print("Writing tracking file");
            trackentry = "T," + str(time) + "," + str(latitude) + "," + str(longitude) + "," + str(altitude) + "," + str(speed) + "," + str(trackid);
            writeFile(logpath, trackentry);
            overwriteFile(latestpath, trackentry);
            print("Completed writing tracking file");

            nofixes = 0;
            showGreen();


            location = {}
            location['pitch'] = pitch
            location['roll'] = roll
            location['yaw'] = yaw
            location['latitude'] = latitude
            location['longitude'] = longitude
            location['altitude'] = altitude
            location['speed'] = speed
            location['timestamp'] = int(timens / 1000000000)
            location['timestampms'] = int(timens / 1000000)
            location['timestampns'] = timens
            location['acceleration'] = x
            location['side_gravity'] = y
            location['gravity'] = z
            location['temp'] = temp
            location['pressure'] = pressure
            location['humidity'] = humidity
            location['climb'] = climb
            location['course'] = course
            location['date'] = time
            location['trackid'] = trackid
            #location['image'] = {}
            #location['image']['content_type'] = 'image/jpeg'
            #location['image']['data'] = imageBase64
            

            if connected:
                mqttc.loop()
                mqttc.publish(topic, "ON")
                mqttc.publish(locationtopic, json.dumps(location), 0, True)
                mqttc.publish(imagetopic, imageBinary, 0, True)
                print("Sent MQTT message")
            else:
                mqttc = connect()

        else:
            nofixes +=1;
            showYellow();
            sleep(10);
            continue;
    except Exception as e:
        print("Unable to get the GPS/sensehat data" + str(e);
        sleep(5);
        continue;







