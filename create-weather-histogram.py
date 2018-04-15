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
- option to zip resultant tsv output file
- option remove header in tsv
- 'quiet' mode to remove all console messages (server mode) - store in local std log instead

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
WUNDERGROUND_RATE_SLEEP_SECONDS = 7 #seconds to wait between calls to fail within limits (free tier set to 6-7!!)
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
            "Uses 3rd party web APIs (weatherunderground)." \
            "Please see source of this file to set options appropriately (keys, etc)")
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
        Check(WUNDERGROUND_BASEURL,WUNDERGROUND_APIKEY)
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
        PrintMessage(MessageType.INFO,"NOTE: This is a large dataset! "\
        "We will likely hit the rate limit depending on service tier. "\
        "If we do, processing will be halted and we will generate the histogram based on current data.  "\
        "Also, you might want to go get a cup of coffee...or two or three.")
    
    timer = SimpleTimer()
    forecastList = []
    failures = 0
    #must not be zero padded as wunderground according to docs returns no pad
    tomorrow = int((datetime.date.today() + datetime.timedelta(days=1)).strftime('%-d'))

    for count,item in enumerate(ipAddressList, start=1):
        try: 

            if count == WUNDERGROUND_RATE_HARD_LIMIT:
                PrintMessage(MessageType.ERROR,
                "You are hitting (or are about to hit) the hard daily limit for the wunderground service tier! "\
                "Halting calls to web service and building the histogram from the data we have. ",
                "Limit is set as WUNDERGROUND_RATE_HARD_LIMIT - currently = [ {0} ]".format(WUNDERGROUND_RATE_HARD_LIMIT))
                break

            url = WUNDERGROUND_BASEURL.format(WUNDERGROUND_APIKEY)
            payload = {"geo_ip":item}
            response = requests.get(url, params=payload, timeout=5)
            response.raise_for_status()
            if response.status_code == 200:
                jsonResult = response.json()
                if argparse.debug:
                    PrintMessage(MessageType.DEBUG,"wunderground web API response",jsonResult)
                
                #check for errors - especially rate limit errors
                #docs suck on errors, but types here: 
                # https://apicommunity.wunderground.com/weatherapi/topics/error-code-list
                if jsonResult["response"].get("error"):
                    #supposed to mean rate limit exceeded
                    if jsonResult["response"]["error"]["type"] == "invalidkey":
                        failures += 1
                        PrintMessage(MessageType.ERROR,
                        "Rate limit exceeded!!  Stopping processing of new locations for weather forecast!")
                        break
                    elif jsonResult["response"]["error"]["type"] == "querynotfound":
                        failures += 1
                        PrintMessage(MessageType.ERROR,
                        "Trying to obtain forecast for location : "\
                        "Location not found via weather API. Skipping...")
                else:
                    for jcount,jitem in enumerate(jsonResult["forecast"]["simpleforecast"]["forecastday"], start=0):
                        if(jitem["date"]["day"] == tomorrow):
                            forecastList.append(int(jitem["high"]["fahrenheit"]))
                            break

                PrintProgress(locationsCount,count,timer.getElapsed())
            else:
                failures += 1
                PrintMessage(MessageType.ERROR,
                "Server did not return status 200 - returned [{0}] ".format(response.status_code))
        
        except KeyError as ke:
            failures += 1
            #KeyErrors could point to weatherunderground rate limits; break out
            PrintMessage(MessageType.ERROR,
                "Unrecoverable error with weather service API", ke)
            break

        #throw the base exp so we can continue on any error from requests
        except requests.exceptions.RequestException as re:
            failures += 1
            PrintMessage(MessageType.ERROR,
                "Trying to obtain forecast for location : Timeout / httperror waiting"\
                "for server connection / response", re)


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

def Check(url,apikey):
    """ 
    simple check to make sure things are in order.  Namely have an API key :) 
    Can extend later for more pre-run checks
    
    """
    if not url:
        raise ValueError("Weather API url is empty.  Please check your config!")
    if not apikey:
        raise ValueError("Weather API key is empty.  Please check your config!")


def PrintProgress(total, current,currentElapsed):
    """ prints progress for web calls """
    print("-> Working...(Throttled due to rate limit)")
    if(not current % 5):
        PrintMessage(MessageType.INFO,
            "Processed [{0}] of [{1}] - [{2}] percent complete - Elapsed time [{3}]"\
            .format(current,total,CalculatePercentage(current,total), TimeFromFloat(currentElapsed)))


def PrintMessage(messageType,friendlyMessage,detailMessage="None"):
    """ prints messages in format we want """
    print("[{0}] - {1} - More Details [{2}]".format(str(messageType.name),friendlyMessage,detailMessage))


def PrintSimpleSummary(data,timeSummary,description,title, debug):
    """ prints simple summary """
    print("-----------------------------------------")
    print("- STEP SUMMARY : [{0}] ".format(title))
    print(timeSummary)
    print("-----------------------------------------")
    if debug:
        PrintMessage(MessageType.DEBUG,"{0} data [{1}]".format(description,data))


def PrintSummary(data,attempts,failures,timeSummary,description,title, debug):
    """ prints complete failure/attempt summary for step """
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