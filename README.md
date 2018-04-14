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
- geoip2(https://github.com/maxmind/GeoIP2-python)
- numpy (https://www.scipy.org/scipylib/download.html , http://www.numpy.org/)

Example pip3 install the requirements:
```
pip3 install -r requirements.txt

```

Note: Tested and developed on python 3.6.5 on Linux (Fedora)

### The following settings must be manually preconfigured in 'create-weather-histogram.py'

1 Under 'src' directory you will find the compressed GeoLite2 city database, decompress into the files directory and change the reference below as needed
```
GEOIP2_DB = "files/GeoLite2-City-20180403.mmdb"
```

Go to https://openweathermap.org/api and obtain a free tier API key (note the limitations; this code should respect them).  Fill in your API key here:
```
OPENWEATHER_APIKEY = "" #appid - free tier
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

## Third Party APIs / Libraries Used

1 GeoLite2 location database (download) and py lib/mod: 
- https://dev.maxmind.com/geoip/geoip2/geolite2/
- http://geolite.maxmind.com/download/geoip/database/GeoLite2-City.tar.gz
- https://github.com/maxmind/GeoIP2-python (library/module)

2 openweathermap.org - get weather based on location (lat/long/city/state etc)
- API docs: https://openweathermap.org/current
- API limits and tiers: https://openweathermap.org/price

## Thanks

- requests (http://docs.python-requests.org/en/master/)
- geoip2.database (https://github.com/maxmind/GeoIP2-python)
- NumPy (https://www.scipy.org/scipylib/download.html , http://www.numpy.org/)
