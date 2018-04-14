# TDD code
Create Weather Histogram

## Description
Creates a tsv file of histogram bins of weather forecast based on logfile input (containing IP addresses) and requested bin size

## Initial Setup
You will need the following third party modules, just pip3 install them as needed:
- requests (http://docs.python-requests.org/en/master/)
- geoip2.database (https://github.com/maxmind/GeoIP2-python)
- python 3 (tested on python 3.6.5 on Linux)

### The following settings must be manually preconfigured in 'create-weather-histogram.py'

Under 'src' directory you will find the compressed GeoLite2 city database, decompress into the files directory and
change the reference below if needed
```
GEOIP2_DB = "files/GeoLite2-City-20180403.mmdb"
```

Go to https://openweathermap.org/api and obtain a free tier API key (note the limitations; this code should respect them) 
Fill in your API key here:
```
OPENWEATHER_APIKEY = "" #appid - free tier
```

There are also a few other settings (constants) you may wish to set those are in the following section in the code:
```
##########################################
#- Modify the options below as needed
##########################################

 ...

##########################################
#- END - Do not modify below here!!!
##########################################
```

##### NOTE: This code was tested on Fedora Linux (python 3.6.5) - there are no guarantees it will work on other platforms YMMV

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
