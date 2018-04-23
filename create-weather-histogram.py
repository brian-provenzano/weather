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
- refactor to create messaging class (remove all the printMessage calls, more DRYish)
- retries on connection issues or non HTTP 200 returns
"""

#--3rd party - see readme for pip install
import requests
import requests_cache
import numpy

#--std mod/libs
import time, datetime
import ipaddress 
import sys, os
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
#requests cache - https://requests-cache.readthedocs.io/en/latest/user_guide.html (sqlite)
REQUESTSCACHE_DBEXPIRE = 300 # cache expires after this time period in seconds (defaulting to 5 minutes)

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
        ipAddresses = []
        failures = 0
        for linecount,item in enumerate(ipList, start=1):
            for count,field in enumerate(item.split("\t")):
                #ip address is in 23rd position (zero based)
                if (count == 23):
                    try:
                        #detect if we have X-Forwarded-For style IP format in the field and handle it
                        #e.g. 121.7.37.91, 10.168.83.120
                        if "," in field:
                            alist = field.split(",")
                            for ip in alist:
                                ipAddress = ipaddress.ip_address(ip.strip())
                                if IsPublicIPAddress(ipAddress,linecount):
                                    ipAddresses.append(ip.strip())
                                else:
                                    failures += 1
                        else:
                            ipAddress = ipaddress.ip_address(field)
                            if IsPublicIPAddress(ipAddress,linecount):
                                ipAddresses.append(field)
                            else:
                                failures += 1
                    except ValueError as ve:
                        failures += 1
                        PrintMessage(MessageType.ERROR,
                            "Invalid IP Address [{0}] found at line [ {1} ]!  Skipping line... "\
                            "Please double check the logfile!".format(field,linecount),ve)

    ipAddressFailures = failures
    ipAddressAttempts = len(ipList)
    timer.Stop()
    PrintSummary(ipAddresses,ipAddressAttempts,ipAddressAttempts,ipAddressFailures, timer.PrintSummary("getting IPs from local logfile"),
            "Log file IPs","Processing IPs From Local Log File",argparse.debug)

    return ipAddresses


def GetWeatherForecast(ipAddressList,argparse):
    """ 
    Get Weather forecast for next day 
    Returns: forecastList
    """

    locationsCount = len(ipAddressList)
    estimate = TimeFromFloat(locationsCount * WUNDERGROUND_RATE_SLEEP_SECONDS)
    PrintMessage(MessageType.INFO,
        "Getting forecast info from service for [{0}] locations. "\
        "This will take approximately [{1}]".format(locationsCount, estimate))

    if (locationsCount > 500):
        PrintMessage(MessageType.INFO,"NOTE: This is a large dataset! "\
        "We will likely hit the rate limit depending on service tier. "\
        "If we do, processing will be halted and we will generate the histogram based on current data.  "\
        "Also, you might want to go get a cup of coffee...or two or three.")
    
    timer = SimpleTimer()
    forecastList = []
    alreadyForecasted = {}
    failures = 0
    skipped = 0
    cached = 0
    #must not be zero padded as wunderground API according to docs returns no pad on day
    tomorrow = int((datetime.date.today() + datetime.timedelta(days=1)).strftime('%-d'))

    for count,item in enumerate(ipAddressList, start=1):
        try: 
            if count == WUNDERGROUND_RATE_HARD_LIMIT:
                PrintMessage(MessageType.ERROR,
                "You are hitting (or are about to hit) the hard daily limit for the wunderground service tier! "\
                "Halting calls to web service and building the histogram from the data we have. ",
                "Limit is set as WUNDERGROUND_RATE_HARD_LIMIT - currently = [ {0} ]".format(WUNDERGROUND_RATE_HARD_LIMIT))
                break

            #if already located/forecasted the IP; skip the web API call; but still add to temp data
            # essentially we will treat this as a INPROCESS cache (of sorts)
            if item in alreadyForecasted:
                forecastList.append(alreadyForecasted.get(item))
                PrintProgress(locationsCount,count,timer.GetElapsed(),item,True,CacheType.INPROCESS)
                skipped += 1
            else:
                url = WUNDERGROUND_BASEURL.format(WUNDERGROUND_APIKEY)
                # caching - using requests-cache
                requests_cache.install_cache(expire_after=REQUESTSCACHE_DBEXPIRE)
                # hook requests module for requests-cache sleep (throttle for wunderground) if not cached
                rcache = requests_cache.CachedSession(expire_after=REQUESTSCACHE_DBEXPIRE)
                rcache.hooks = {'response': ThrottleHook(WUNDERGROUND_RATE_SLEEP_SECONDS)}
                response = rcache.get(url, params={"geo_ip":item}, timeout=WUNDERGROUND_CONNECT_TIMEOUT)
                response.raise_for_status()
                if response.status_code == 200:
                    jsonResult = response.json()
                    if argparse.debug:
                        PrintMessage(MessageType.DEBUG,"wunderground web API response",jsonResult)
                    
                    #check for errors - especially rate limit errors
                    #docs suck on defining errors (there are none), but types appear here in a forum post: 
                    # https://apicommunity.wunderground.com/weatherapi/topics/error-code-list
                    if jsonResult["response"].get("error"):
                        #"invalidkey" - supposed to mean rate limit exceeded; break
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
                        #lookup high forecast in Fahrenheit from 5 day forecast json results
                        #order is not assumed, so loop and check based on date (tomorrow)
                        for jcount,jitem in enumerate(jsonResult["forecast"]["simpleforecast"]["forecastday"], start=0):
                            if(jitem["date"]["day"] == tomorrow):
                                forecastList.append(int(jitem["high"]["fahrenheit"]))
                                if item not in alreadyForecasted:
                                    alreadyForecasted[item] = int(jitem["high"]["fahrenheit"])
                                break
                    
                    if response.from_cache:
                        cached += 1
                        PrintProgress(locationsCount,count,timer.GetElapsed(),item, True, CacheType.DISK)
                    else:
                        PrintProgress(locationsCount,count,timer.GetElapsed(),item)

                else:
                    failures += 1
                    PrintMessage(MessageType.ERROR,
                    "Server did not return status 200 - returned [{0}] ".format(response.status_code))

        #KeyErrors could point to weatherunderground rate limits (docs are unclear); break out just in case
        except KeyError as ke:
            failures += 1
            PrintMessage(MessageType.ERROR, "Unrecoverable error with weather service API", ke)
            break

        #throw the base request ex so we can continue on any error from requests module
        except requests.exceptions.RequestException as re:
            failures += 1
            PrintMessage(MessageType.ERROR, "Trying to obtain forecast for location : Timeout / httperror waiting"\
                "for server connection / response", re)
            #if we have an exception, I'd like to wait a little for the next try on the next item
            time.sleep(WUNDERGROUND_RATE_SLEEP_SECONDS)

    forecastFailures = failures
    forecastCached = cached + skipped
    forecastAttempts = locationsCount - (skipped + cached)
    timer.Stop()
    PrintSummary(forecastList,locationsCount,forecastAttempts,forecastFailures, timer.PrintSummary("getting weather forecast data"),
        "Forecast High Temperature","Obtaining Next Day Forecast High Temperatures From Web Service", 
        argparse.debug,forecastCached)

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

    timer.Stop()
    PrintSimpleSummary(tsvdata,timer.PrintSummary("writing tsv file {}".format(outputFile)),
        "TSV file","Creating Histogram TSV File", argparse.debug)
    print("-----------------------------------------")
    print("\n -> Process Complete!!!")


################################
# - Utility functions / classes
################################

def ThrottleHook(timeout=WUNDERGROUND_RATE_SLEEP_SECONDS):
    """
    Returns a response (requests module) hook function which sleeps 
    for `timeout` seconds if response is not cached 
    to stay within rate limit wunderground weather API
    """
    def hook(response, *args, **kwargs):
        if not getattr(response, 'from_cache', False):
            time.sleep(timeout)
        return response
    return hook


def IsPublicIPAddress(ipAddress, currentLine):
    """ 
    Check IP Address is private
    Returns: isPublicIP (is IP public or not)
    """
    isPublicIP = True
    if ipAddress.is_private:
        isPublicIP = False
        PrintMessage(MessageType.ERROR,
            "Invalid IP Address [{0}] found at line [ {1} ]!  Skipping line... "\
            "Please double check the logfile!".format(str(ipAddress),currentLine),"Is Private IP Address")
    return isPublicIP


class MessageType(Enum):
    """ Message type enumeration"""
    INVALID = 0
    DEBUG = 1
    INFO = 2
    ERROR = 3


class CacheType(Enum):
    """ Cache type enumeration"""
    INVALID = 0
    DISK = 1
    INPROCESS = 2


class SimpleTimer(object):
    """ simple timer for util purposes """
    import time
    startTime = 0.0
    StopTime = 0.0
    elapsed = 0.0

    def __init__(self):
        self.startTime = time.time()

    def Stop(self):
        self.StopTime = time.time()

    def GetElapsed(self):
        self.StopTime = time.time()
        self.elapsed = (self.StopTime - self.startTime)
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


def PrintProgress(total, current,currentElapsed, item, cache=False, cacheType=CacheType.INVALID):
    """ prints progress for web calls """
    if cache:
        print("-> Cached [{0}] - skipping API; this request [{1}] is from local cache".format(str(cacheType.name),item))
    else:
        print ("-> {0}".format("Looking up Forecast for [{0}] via API - (Throttled due to rate limit)".format(item)))
    
    if(not current % 5):
        PrintMessage(MessageType.INFO,
            "Processed [{0}] of [{1}] - [{2}] percent complete - Elapsed time [{3}]"\
            .format(current,total,CalculatePercentage(current,total), TimeFromFloat(currentElapsed)))


def PrintMessage(messageType,friendlyMessage,detailMessage="None"):
    """ prints messages in format we want """
    if messageType == messageType.DEBUG:
        color = fg.YELLOW
        coloroff = style.RESET_ALL
    elif messageType == messageType.INFO:
        color = fg.GREEN
        coloroff = style.RESET_ALL
    elif messageType == messageType.ERROR:
        color = fg.RED
        coloroff = style.RESET_ALL
    else:
        color = ""
        coloroff = ""

    print("{3}[{0}] - {1} - More Details [{2}]{4}".format(str(messageType.name),friendlyMessage,detailMessage,color,coloroff))


def PrintSimpleSummary(data,timeSummary,description,title, debug):
    """ prints simple summary """
    print("-----------------------------------------")
    print("- STEP SUMMARY : [{0}] ".format(title))
    print(timeSummary)
    print("-----------------------------------------")
    if debug:
        PrintMessage(MessageType.DEBUG,"{0} data [{1}]".format(description,data))


def PrintSummary(data, total, attempts, failures, timeSummary, description, title, debug, cached=0):
    """ 
    prints complete failure/attempt summary for step 
    ---
    Attempts = active web API calls (this could be fraction of Total if cached)
    Total = total that were requested to be processed (this number is TOTAL)
    """
    color = ""
    coloroff = ""
    print("-----------------------------------------")
    print("- STEP SUMMARY : [{0}] ".format(title))
    print("- {0} total [{1}]".format(description,total))
    print("- {0} attempted [{1}]".format(description,attempts))
    if cached != 0:
        print("- {0} cached [{1}]".format(description,cached))
    if failures != 0:
        color = fg.RED
        coloroff = style.RESET_ALL
    print("{2}- {0} failures [{1}]{3}".format(description,failures,color,coloroff))
    print("{2}- {0} failed: [{1}]{3}".format(description,CalculatePercentage(failures,attempts),color,coloroff))
    print("- {0}".format(timeSummary))
    print("-----------------------------------------")
    if debug:
        PrintMessage(MessageType.DEBUG,"{0} data [{1}]".format(description,data))

# Terminal color definitions - cheap and easy colors for this application
class fg:
    BLACK   = '\033[30m'
    RED     = '\033[31m'
    GREEN   = '\033[32m'
    YELLOW  = '\033[33m'
    BLUE    = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN    = '\033[36m'
    WHITE   = '\033[37m'
    RESET   = '\033[39m'

class bg:
    BLACK   = '\033[40m'
    RED     = '\033[41m'
    GREEN   = '\033[42m'
    YELLOW  = '\033[43m'
    BLUE    = '\033[44m'
    MAGENTA = '\033[45m'
    CYAN    = '\033[46m'
    WHITE   = '\033[47m'
    RESET   = '\033[49m'

class style:
    BRIGHT    = '\033[1m'
    DIM       = '\033[2m'
    NORMAL    = '\033[22m'
    RESET_ALL = '\033[0m'


if __name__ == '__main__':
    Main()