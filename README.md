# TDD code
Create Weather Histogram

## Description
Creates a tsv file of histogram bins of weather forecast based on logfile input (containing IP addresses) and requested bin size

## Usage
```
create-weather-hist.py <input-logfilename> <output-filename> <hist-buckets>
```

## Initial Setup
You will need the following third party modules, just pip3 install them as needed or use the requirements.txt file as noted below:
- requests (http://docs.python-requests.org/en/master/)
- numpy (https://www.scipy.org/scipylib/download.html , http://www.numpy.org/)

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

There are also a few other settings (constants) you may wish to set those are in the following section in the code in 'create-weather-histogram':
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
1 Weather Underground API 
- Signup: https://www.wunderground.com/weather/api/
- API docs: https://www.wunderground.com/weather/api/d/docs
- API limits and tiers: https://www.wunderground.com/weather/api/d/pricing.html

## Thanks
- requests (http://docs.python-requests.org/en/master/)
- NumPy (https://www.scipy.org/scipylib/download.html , http://www.numpy.org/)
