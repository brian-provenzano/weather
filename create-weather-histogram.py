#!/usr/bin/python3
"""
Create Weather Histogram
-----------------------
Creates a tsv file of histogram bins based on logfile input 
(containing IP addresses) and requested bin size
-----------------------

Third party APIs (or databases) used
-----------------------
1 - GeoLite2 location database (download) and py lib/mod: 
    - https://dev.maxmind.com/geoip/geoip2/geolite2/
    - http://geolite.maxmind.com/download/geoip/database/GeoLite2-City.tar.gz
    - https://github.com/maxmind/GeoIP2-python (library/module)
2 - openweathermap.org - get weather based on location (lat/long/city/state etc)
    -API docs: https://openweathermap.org/current
    -API limits and tiers: https://openweathermap.org/price

Usage:
-----------------------
create-weather-hist.py <input-logfilename> <output-filename> <hist-buckets>

BJP - 4/12/18
"""

#--3rd party - see readme for pip install
import requests
import geoip2.database
import numpy

#--std mod/libs
import time , datetime
import json
import zipfile
import argparse
import socket, sys, os
from enum import Enum
#from subprocess import call
#from pathlib import Path

##########################################
#- Modify the options below as needed
##########################################

#-IP -> Location database
GEOIP2_DB = "files/GeoLite2-City-20180403.mmdb"
#-Weather APIs
OPENWEATHER_BASEURL = "http://api.openweathermap.org/data/2.5/forecast"
OPENWEATHER_APIKEY = "" #appid - free tier
OPENWEATHER_UNITS = "imperial" #Options: imperial, standard, metric
#These are passed to be safe on rate limits (number of calls allowed per minute by free tier is 60)
OPENWEATHER_RATE_SLEEP_SECONDS = 1 #seconds to wait between calls to be nice (docs warn on velocity)
OPENWEATHER_CONNECT_TIMEOUT = 5 # wait no longer than 5 seconds for a response (avg is less than second)

##########################################
#- END - Do not modify below here!!!
##########################################

def Main():
    """ Main()"""

    parser = argparse.ArgumentParser(prog="create-weather-histogram", \
            description=" Creates a tsv file of histogram bins of weather forecasts based " \
            "on logfile location input (containing IP addresses) and requested bin size.  " \
            "Uses various 3rd party APIs (currently openweathermap.org and GeoLite2 location.  " \
            "Please see source of this file to set options appropriately (keys, datapaths)")
    #-required args
    parser.add_argument("logfile", type=str, \
            help="Log source file containing locations to find weather forecast data for")
    parser.add_argument("outputfile", type=str, \
            help="Name of the file to output the histogram data to in tsv format")
    parser.add_argument("buckets", type=int, \
            help="Number of buckets for histogram")
    #-informational args
    parser.add_argument("-d", "--debug", action="store_true", 
            help="Debug mode - show more informational messages for debugging")
    parser.add_argument("-q", "--quiet", action="store_true", 
            help="Do not print histogram to console.  Output to file only.")
    parser.add_argument("-v", "--version", action="version", version="1.0")
    args = parser.parse_args()

    logfile = args.logfile.strip()
    outputFile = args.outputfile.strip()
    numberBuckets = args.buckets

    try:
        ipAddressList = ParseLogFile(logfile,args)
        locationsList = GetLocations(ipAddressList,args)
        weatherForecastList = GetWeatherForecast(locationsList,args)
        CreateHistogram(weatherForecastList,outputFile,numberBuckets,args)

    except ValueError as ve:
        PrintMessage(MessageType.ERROR, "System ValueError occurred!",str(ve))
    except FileNotFoundError as fe:
        PrintMessage(MessageType.ERROR, "The file not found! "
            "Check to make sure you provided the logfile and/or the log file is in your path",str(fe))
    except Exception as e:
        PrintMessage(MessageType.ERROR, "UNKNOWN Error Occurred!",str(e))


def ParseLogFile(logFile, argparse):
    """ 
    Parse the source log file for IP Addresses to use
    Returns: ipAddresses
    """
    timer = SimpleTimer()
    with open(logFile, "r") as f:
        ipList = [line.strip("\n") for line in f]
        # TODO - consider a tuple for speed
        ipAddresses = []
        failures = 0
        for linecount,item in enumerate(ipList, start=1):
            for count,field in enumerate(item.split("\t")):
                #ip address is in 23rd position (zero based)
                if (count == 23):
                    try:
                        socket.inet_aton(field)
                    except socket.error:
                        failures += 1
                        PrintMessage(MessageType.ERROR,
                            "Invalid IP Address found at line [ {0} ]!  Skipping line... "\
                            "Please double check the logfile!".format(linecount))

                    ipAddresses.append(field)

            # ipAddressCount = len(ipAddresses)
            ipAddressFailures = failures
            ipAddressAttempts = len(ipList)

    timer.stop()
    PrintSummary(ipAddresses,ipAddressAttempts,ipAddressFailures, timer.PrintSummary("getting IPs from local logfile"),
            "Log file IPs","Processing IPs From Local Log File",argparse.debug)

    return ipAddresses


def GetLocations(ipAddressList, argparse):
    """ 
    Get locations from list of IPs using geoip2 database - lat and long  
    Returns: locations, locationsCount
    """
    timer = SimpleTimer()
    locations = []
    failures = 0
    with geoip2.database.Reader(GEOIP2_DB) as reader:
        for item in ipAddressList:
            try:
                response = reader.city(item)
                loc = [response.location.latitude,response.location.longitude]
                locations.append(loc)
            except:
                print()
                PrintMessage(MessageType.ERROR,
                "IP Address [{0}] not found in database!  Skipping location...!".format(item))
                failures += 1

    locationsFailures = failures
    locationsAttempted = len(ipAddressList)

    timer.stop()
    PrintSummary(locations,locationsAttempted,locationsFailures,timer.PrintSummary("getting locations from local db"),
        "Locations Lookup DB", "Looking Up Locations In Local Location DB",argparse.debug)

    return locations


def GetWeatherForecast(locationsList,argparse):
    """ 
    Get Weather forecast for next day using openweathermap API  
    Returns: forecastList
    """
    locationsCount = len(locationsList)
    PrintMessage(MessageType.INFO,
        "Getting forecast info from service for [{0}] locations. "\
        "This will take approximately [{1}]".format(locationsCount, TimeFromFloat(locationsCount* 1.5)))

    if (locationsCount > 500):
        PrintMessage(MessageType.INFO,"NOTE: This is a large dataset!  You might want to go get a cup of coffee...")
    
    timer = SimpleTimer()
    forecastList = []
    failures = 0
    for count,item in enumerate(locationsList, start=1):
        payload = {"appid":OPENWEATHER_APIKEY,"lat":item[0],"lon":item[1],"units":OPENWEATHER_UNITS}
        try:
            response = requests.get(OPENWEATHER_BASEURL, params=payload, timeout=5)
            response.raise_for_status()
            if response.status_code == 200:
                jsonResult = response.json()
                forecastList.append(jsonResult["list"][0]["main"]["temp_max"])
                PrintProgress(locationsCount,count,timer.getElapsed())
            else:
                failures += 1
                raise requests.ConnectionError("Server did not return status 200 - returned [{0}]".format(response.status_code))
        
        #throw the base exp so we can continue on any error from requests
        except requests.exceptions.RequestException as re:
            failures += 1
            PrintMessage(MessageType.ERROR,
            "Trying to obtain forecast for location : Timeout / httperror waiting for server connection / response", re)

        #stay within rate - not perfect, but should be ok for this...
        time.sleep(OPENWEATHER_RATE_SLEEP_SECONDS)
    
    forecastFailures = failures   
    forecastAttempts = (locationsCount)

    timer.stop()
    PrintSummary(forecastList,forecastAttempts,forecastFailures, timer.PrintSummary("getting weather forecast data"),
        "Forecast High Temperature","Obtaining Next Day Forecast High Temperatures From Web Service", argparse.debug)

    return forecastList


def CreateHistogram(forecastData,outputFile,buckets,argsparse):
    """ 
    Create histogram bin file (tsv)
    Returns: file and prints to console (option)
    """
    #TODO - send this to a tab delimited file (tsv); if have time might offer zip option in args
    freq, bins  = numpy.histogram(forecastData,buckets)
    binCount = (len(bins) - 1)
    print("Min\tMax\tFreq\n")
    for index,item in enumerate(bins, start=0):
        if index != binCount:
            print(item,end="\t")
            print(bins[index+1],end="\t")
            print(freq[index],end="")
            print("\n")


################################
# - Utility functions / classes
################################

class MessageType(Enum):
    """ Message type enumeration"""
    INVALID = 0
    DEBUG = 1
    INFO = 2
    ERROR = 3

class SimpleTimer(object):
    """ simple timer for util purposes """
    import time
    startTime = 0.0
    stopTime = 0.0
    elapsed = 0.0

    def __init__(self):
        self.startTime = time.time()

    def stop(self):
        self.stopTime = time.time()

    def getElapsed(self):
        self.stopTime = time.time()
        self.elapsed = (self.stopTime - self.startTime)
        return self.elapsed

    def PrintSummary(self, doingWhat="do something"):
        return "[ {0} ] Time elapsed {1}".format(TimeFromFloat(self.elapsed),doingWhat)


def CalculatePercentage(x,y):
    p = 0
    if(x is not 0):
        p = ((x / y) * 100)
    return ('{:.2f}%'.format(p))


def TimeFromFloat(f):
    return time.strftime("%H:%M:%S", time.gmtime(f))


def PrintProgress(total, current,currentElapsed):
    #print("->")
    if(not current % 5):
        PrintMessage(MessageType.INFO,
            "Processing [{0}] of [{1}] - [{2}] percent complete - Elapsed time [{3}]"\
            .format(current,total,CalculatePercentage(current,total), TimeFromFloat(currentElapsed)))


def PrintMessage(messageType,friendlyMessage,detailMessage="None"):
    print("[{0}] - {1} - More Details [{2}]".format(str(messageType.name),friendlyMessage,detailMessage))


def PrintSummary(data,attempts,failures,timeSummary,description,title, debug):
        print("-----------------------------------------")
        print("- STEP SUMMARY : [{0}] ".format(title))
        if debug:
            print("- {0} data [{1}]".format(description,data))
        print("- {0} attempted [{1}]".format(description,attempts))
        print("- {0} failures [{1}]".format(description,failures))
        print("- {0} failed: [{1}]".format(description,CalculatePercentage(failures,attempts)))
        print(timeSummary)
        print("-----------------------------------------")

def PrintFinalSummary():
    #TODO -
    pass


if __name__ == '__main__':
    Main()