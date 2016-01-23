# General
import datetime

# web input parsing
import json
from urllib2 import urlopen
from pyquery import PyQuery as pq

# Math and data analysis
from math import radians, cos, sin, asin, sqrt
from scipy import stats
import pandas as pd
import numpy as np



# Grab json from Google Maps API
def get_googlemaps_json(start_loc, end_loc, fromUser='Default'):
    print 'in get_googlemaps_json start_loc is '+str(start_loc)
    print 'in get_googlemaps_json end_loc is '+str(end_loc)
    my_googlemaps_auth = 'AIzaSyDWQv6WWQptI-6rjbavkoZ1TpVZhHKOm4w'
    googlemaps_url = 'https://maps.googleapis.com/maps/api/directions/json?origin='+str(start_loc).replace(' ','+')+'&destination='+str(end_loc).replace(' ','+')+'&mode=transit&key='+str(my_googlemaps_auth)
    print googlemaps_url
    tmp = urlopen(googlemaps_url)
    return json.load(tmp)



# Compute distance between two (lat,lon)s in meters
def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    meters = 6367 * c * 1000
    return meters

# Compute the percentile score of two (lat,lon)s based upon distribution of distances for that route
def compute_distance_percentile(route_num, lat1, lon1, lat2, lon2):
        tmp_dist = haversine(lat1,lon1,lat2,lon2)
        path_to_dist_distribution = 'muni_route_distance_distributions/route_'+str(route_num)+'_distribution.npy'
        route_dist_distribution = np.load(path_to_dist_distribution)
        percentile_score = 1 - stats.percentileofscore(route_dist_distribution, tmp_dist)/100
        return percentile_score



######################################################################
# Main function to get next two buses' data and return a dataframe entry with that information
######################################################################
def subsequent_bus_info(fromUser = 'Default', starting_loc = '', ending_loc = ''):
	data = get_googlemaps_json(starting_loc, ending_loc)
	'''Returns a dataframe that is a pair of subsequent buses
	   and their distance percentile score
	'''

	# Get route name, (lat,lon), and stop name from Google maps
	route_name = str(data['routes'][0]['legs'][0]['steps'][0]['transit_details']['line']['short_name'])
	departure_stop = str(data['routes'][0]['legs'][0]['steps'][0]['transit_details']['departure_stop']['name'])
	departure_lat = round(float(data['routes'][0]['legs'][0]['steps'][0]['transit_details']['departure_stop']['location']['lat']),5)
	departure_lon = round(float(data['routes'][0]['legs'][0]['steps'][0]['transit_details']['departure_stop']['location']['lng']),5)

	# Get stopID from Nextbus 'routeConfig'
	url_get_route_config='http://webservices.nextbus.com/service/publicXMLFeed?command=routeConfig&a=sf-muni&r='+str(route_name)
	route_config = pq(urlopen(url_get_route_config).read())	
	
	for bus_stop_obj in route_config('stop'):
		bus_stop = pq(bus_stop_obj)
		if bus_stop.attr('lat') is not None:
			stop_name = str(bus_stop.attr('title'))
			stop_lat = round(float(bus_stop.attr('lat')),5)
			stop_lon = round(float(bus_stop.attr('lon')),5)
			if stop_name == departure_stop and stop_lat == departure_lat and stop_lon == departure_lon:
				stop_id = str(bus_stop.attr('stopId'))

	# Get next two vehicle from Nextbus 'predictions'	
	url_get_stop_info='http://webservices.nextbus.com/service/publicXMLFeed?command=predictions&a=sf-muni&stopId='+stop_id+'&r='+str(route_name)
	stop_config = pq(urlopen(url_get_stop_info).read())
	
	vehicle_array = []
	for prediction in stop_config('prediction'):
	    vehicle_array.append(pq(prediction).attr.vehicle)
	
	vehicle_1 = vehicle_array[0]
	vehicle_2 = vehicle_array[1]

	# Get both vehicles' information from Nextbus 'vehicleLocations'
	url_get_realtime_info='http://webservices.nextbus.com/service/publicXMLFeed?command=vehicleLocations&a=sf-muni&r='+str(route_name)+'&t=0'
	realtime_posits = pq(urlopen(url_get_realtime_info).read())

	time_stamp = datetime.datetime.utcfromtimestamp(int(pq(pq(realtime_posits('vehicle')[-1]).siblings()[-1]).attr('time'))/1000)
	for vehicle in realtime_posits('vehicle'):
		v = pq(vehicle)
		if v.attr.id == vehicle_1:
			df1 = pd.DataFrame({'ind': 0,'time': time_stamp,'lat_x': float(v.attr.lat), 'lon_x': float(v.attr.lon), 'speed_x': float(v.attr.speedKmHr), 'route_x': str(v.attr.routeTag)},index=[0])
		elif v.attr.id == vehicle_2:
			df2 = pd.DataFrame({'ind': 0,'lat_y': float(v.attr.lat), 'lon_y': float(v.attr.lon), 'speed_y': float(v.attr.speedKmHr)},index=[0])

	# Merge the dataframes and compute the distance percentile score for each bus
	bus_pair  = pd.merge(left=df1, right=df2)
	bus_pair['dist_percentile'] = compute_distance_percentile(route_name, float(bus_pair['lat_x'][0]), float(bus_pair['lon_x'][0]), float(bus_pair['lat_y'][0]), float(bus_pair['lon_y'][0]))	
	# Necessary only for patsy
	bus_pair['bunched'] = 0

	# Return the dataframe (do processing in bunch_predictor.py)
	if fromUser != 'Default':
		return bus_pair
	else:
		return 'check your input'
