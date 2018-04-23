# TDD code
Create Weather Histogram

## Description
Creates a tsv file of histogram bins of weather forecast based on logfile input (containing IP addresses) and requested bin size

## Usage
```
usage: create-weather-histogram [-h] [-d] [-v] logfile outputfile buckets

Creates a tsv file of histogram bins of weather forecasts based on logfile
location input (containing IP addresses) and requested bin size. Uses 3rd
party web APIs (weatherunderground).Please see source of this file to set
options appropriately (keys, etc)

positional arguments:
  logfile        Log source file containing locations to find weather forecast
                 data for
  outputfile     Name of the file to output the histogram data to in tsv
                 format
  buckets        Number of buckets for histogram

optional arguments:
  -h, --help     show this help message and exit
  -d, --debug    Debug mode - show more informational messages for debugging
  -v, --version  show program's version number and exit

```

## Initial Setup
You will need the following third party modules, just pip3 install them as needed or use the requirements.txt file as noted below:
- requests: http://docs.python-requests.org/en/master/
- requests-cache: http://docs.python-requests.org/en/master/ (caching options; cache to sqlite)
- numpy: https://www.scipy.org/scipylib/download.html , http://www.numpy.org/

Example pip3 install the requirements:
```
pip3 install -r requirements.txt

```

Note: Tested and developed on python 3.6.5 on Linux (Fedora)

### The following settings must be manually preconfigured in 'create-weather-histogram.py'


1 Go to https://www.wunderground.com/weather/api/ and obtain a free tier API key (note the limitations; this code should respect them).  Fill in your API key here:
```
WUNDERGROUND_APIKEY = ""
```

There are also a few other settings (e.g. caching expirations) you may wish to set. Those are located in the following section in 'create-weather-histogram':
```
##########################################
#- Modify the options below as needed
##########################################

 ...settings here...

##########################################
#- END - Do not modify below here!!!
##########################################
```

##### NOTE: This code was tested on Fedora Linux (python 3.6.5) - there are no guarantees it will work on other platforms.  It should but YMMV.

## Third Party Web Service APIs Used
Weather Underground API 
- Signup: https://www.wunderground.com/weather/api/
- API docs: https://www.wunderground.com/weather/api/d/docs
- API limits and tiers: https://www.wunderground.com/weather/api/d/pricing.html

## Thanks
- requests: http://docs.python-requests.org/en/master/
- requests-cache: https://requests-cache.readthedocs.io/en/latest/user_guide.html
- NumPy: https://www.scipy.org/scipylib/download.html , http://www.numpy.org/
- Colors!!! ANSI codes in python chart: http://ozzmaker.com/add-colour-to-text-in-python/ , https://gist.github.com/minism/1590432#file-color-py
