#!/usr/bin/python3
"""
Create Weather Histogram
-----------------------
Creates a tsv file of histogram bins based on logfile input 
(containing IP addresses) and requested bin size
-----------------------

Third party APIs (or databases) used
-----------------------
1 - Weatherunderground API:
    - https://www.wunderground.com/weather/api/d/docs?d=index

Usage:
-----------------------
create-weather-hist.py <input-logfilename> <output-filename> <hist-buckets>

BJP - 4/12/18

TODOs - future features?
- Option to grab latest geopIP db and decompress to ensure current info
- option to zip resultant tsv output file; remove header option
- quiet mode to remove all console messages (server mode) - store in local std log instead
"""

#--3rd party - see readme for pip install
import requests
import numpy

#--std mod/libs
import time, datetime
import socket, sys, os
import json
import csv
import argparse
from enum import Enum

##########################################
#- Modify the options below as needed
##########################################

#-Weather APIs
WUNDERGROUND_BASEURL = "http://api.wunderground.com/api/{0}/forecast/q/autoip.json"
WUNDERGROUND_APIKEY = ""
#These are passed to be safe on rate limits (free tier: 10 per minute; 500 per day)
WUNDERGROUND_RATE_SLEEP_SECONDS = 7 #seconds to wait between calls to fail within limits
WUNDERGROUND_RATE_HARD_LIMIT = 500 #per day limit (so its our per run limit)
WUNDERGROUND_CONNECT_TIMEOUT = 5 # wait no longer than 5 seconds for a response (avg is less than second)

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
    # parser.add_argument("-q", "--quiet", action="store_true", 
    #         help="Do not print to console.  Output messages to a standard logfile.")
    parser.add_argument("-v", "--version", action="version", version="1.0")
    args = parser.parse_args()

    logfile = args.logfile.strip()
    outputFile = args.outputfile.strip()
    numberBuckets = args.buckets

    try:
        ipAddressList = ParseLogFile(logfile,args)
        weatherForecastList = GetWeatherForecast(ipAddressList,args)
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

    ipAddressFailures = failures
    ipAddressAttempts = len(ipList)
    timer.stop()
    PrintSummary(ipAddresses,ipAddressAttempts,ipAddressFailures, timer.PrintSummary("getting IPs from local logfile"),
            "Log file IPs","Processing IPs From Local Log File",argparse.debug)

    return ipAddresses

def GetWeatherForecast(ipAddressList,argparse):
    """ 
    Get Weather forecast for next day 
    Returns: forecastList
    TODO - need to see what rate limit looks like on response; break loop on limit hit
    """
    locationsCount = len(ipAddressList)
    rateEstimate = (WUNDERGROUND_RATE_SLEEP_SECONDS)
    PrintMessage(MessageType.INFO,
        "Getting forecast info from service for [{0}] locations. "\
        "This will take approximately [{1}]".format(locationsCount, TimeFromFloat(locationsCount * rateEstimate)))

    if (locationsCount > 500):
        PrintMessage(MessageType.INFO,"NOTE: This is a large dataset! We will hit the rate limit depending on service tier "\
        "You might want to go get a cup of coffee...")
    
    timer = SimpleTimer()
    forecastList = []
    failures = 0
    for count,item in enumerate(ipAddressList, start=1):
        try: 
            url = WUNDERGROUND_BASEURL.format(WUNDERGROUND_APIKEY)
            payload = {"geo_ip":item}
            response = requests.get(url, params=payload, timeout=5)
            response.raise_for_status()
            if response.status_code == 200:
                jsonResult = response.json()
                forecastList.append(int(jsonResult["forecast"]["simpleforecast"]["forecastday"][1]["high"]["fahrenheit"]))
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
        time.sleep(WUNDERGROUND_RATE_SLEEP_SECONDS)
    
    forecastFailures = failures   
    forecastAttempts = (locationsCount)
    timer.stop()
    PrintSummary(forecastList,forecastAttempts,forecastFailures, timer.PrintSummary("getting weather forecast data"),
        "Forecast High Temperature","Obtaining Next Day Forecast High Temperatures From Web Service", argparse.debug)

    return forecastList


def CreateHistogram(forecastData,outputFile,buckets,argparse):
    """ 
    Create histogram bin file (tsv)
    Returns: file and prints to console (option)
    """
  
    timer = SimpleTimer()
    #create histogram
    numpy.set_printoptions(precision=2)
    freq, bins = numpy.histogram(forecastData,buckets)

    #floatformatter = lambda x: "%.2f" % x #test
    #find bucket min/max based on edges etc; arrange 
    #precision for display - accept float precision on weather data
    tsvdata = []
    binCount = (len(bins) - 1)
    for index,item in enumerate(bins, start=0):
        if index != binCount:
            tsvdata.append([FloatFormatter(item),FloatFormatter(bins[index+1]),freq[index]])

    header = ['bucketMin','bucketMax','count']
    with open(outputFile, "w") as outfile:
        csvwriter = csv.writer(outfile, delimiter='\t')
        csvwriter.writerow(header)
        csvwriter.writerows(tsvdata)

    timer.stop()
    PrintSimpleSummary(tsvdata,timer.PrintSummary("writing tsv file {}".format(outputFile)),
        "TSV file","Creating Histogram TSV File", argparse.debug)
    print("-----------------------------------------")
    print("\n -> Process Complete!!!")


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


def FloatFormatter(f):
    return "%.2f" % f

def TimeFromFloat(f):
    return time.strftime("%H:%M:%S", time.gmtime(f))


def PrintProgress(total, current,currentElapsed):
    print("-> Working...(Throttled due to rate limit)")
    if(not current % 5):
        PrintMessage(MessageType.INFO,
            "Processing [{0}] of [{1}] - [{2}] percent complete - Elapsed time [{3}]"\
            .format(current,total,CalculatePercentage(current,total), TimeFromFloat(currentElapsed)))


def PrintMessage(messageType,friendlyMessage,detailMessage="None"):
    print("[{0}] - {1} - More Details [{2}]".format(str(messageType.name),friendlyMessage,detailMessage))


def PrintSimpleSummary(data,timeSummary,description,title, debug):
        print("-----------------------------------------")
        print("- STEP SUMMARY : [{0}] ".format(title))
        print(timeSummary)
        print("-----------------------------------------")
        if debug:
            PrintMessage(MessageType.DEBUG,"{0} data [{1}]".format(description,data))


def PrintSummary(data,attempts,failures,timeSummary,description,title, debug):
        print("-----------------------------------------")
        print("- STEP SUMMARY : [{0}] ".format(title))
        print("- {0} attempted [{1}]".format(description,attempts))
        print("- {0} failures [{1}]".format(description,failures))
        print("- {0} failed: [{1}]".format(description,CalculatePercentage(failures,attempts)))
        print("- {0}".format(timeSummary))
        print("-----------------------------------------")
        if debug:
            PrintMessage(MessageType.DEBUG,"{0} data [{1}]".format(description,data))


if __name__ == '__main__':
    Main()