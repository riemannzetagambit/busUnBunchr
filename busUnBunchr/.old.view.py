import flask
from flask import render_template
#from flask import request
from busUnBunchr import app
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
import pandas as pd
import psycopg2

#from bunch_predictor import probability_of_bunching
#from get_upcoming_vehicle_info import subsequent_bus_info
###############################################
# define functions
###############################################

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
import patsy, pickle



# Grab json from Google Maps API
#def get_googlemaps_json(start_loc, end_loc):
def my_func(start_loc, end_loc):
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
def subsequent_bus_info(starting_loc, ending_loc):
	data = my_func(starting_loc, ending_loc)
	'''Returns a dataframe that is a pair of subsequent buses
	   and their distance percentile score
	'''

	# Get route name, (lat,lon), and stop name from Google maps
	steps = data['routes'][0]['legs'][0]['steps']
	for i, step in enumerate(steps):
		if step['travel_mode'] == 'TRANSIT':
			transit_step = i
			break
	 
	route_name = str(steps[transit_step]['transit_details']['line']['short_name'])
	departure_stop = str(steps[transit_step]['transit_details']['departure_stop']['name'])
	departure_lat = round(float(steps[transit_step]['transit_details']['departure_stop']['location']['lat']),5)
	departure_lon = round(float(steps[transit_step]['transit_details']['departure_stop']['location']['lng']),5)

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
	print 'Getting predictions for: '+url_get_stop_info
	stop_config = pq(urlopen(url_get_stop_info).read())
	
	vehicle_array = []
	arrival_time_array = []
	for prediction in stop_config('prediction'):
	    vehicle_array.append(pq(prediction).attr.vehicle)
	    arrival_time_array.append(pq(prediction).attr.minutes)
	
	vehicle_1 = vehicle_array[0]
	vehicle_2 = vehicle_array[1]
	arrival_time_1 = arrival_time_array[0]
	arrival_time_2 = arrival_time_array[1]

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
	bus_pair['arrival_x'] = arrival_time_1
	bus_pair['arrival_y'] = arrival_time_2
	# Necessary only for patsy
	bus_pair['bunched'] = 0

	# Return the dataframe (do processing in bunch_predictor.py)
	return bus_pair
#	if fromUser != 'Default':
#		return bus_pair
#	else:
#		return 'check your input'


def probability_of_bunching(bus_pair):
	# A formula from patsy/dmatrices so we can feed into our RF classifier
	# Input format is expected for dataframe coming in from get_bus_info function
	formula_for_realtime = 'bunched ~ time.dt.hour + time.dt.minute + lat_x + lon_x + speed_x  + lat_y + lon_y + speed_y + dist_percentile'

	# xtmp will be a single dataframe entry that we can feed into the RF classifier
	ytmp, xtmp = patsy.dmatrices(formula_for_realtime, data=bus_pair, return_type='dataframe')

	with open('rf_fit_2016_01_21.pkl','rb') as input:
		forest = pickle.load(input)

	prediction = forest.predict_proba(xtmp)
	# output is an array, first entry is 
	# p, probability that it is classified as bunching
	# second is 1 - p
	return prediction[0][0]
#	if fromUser != 'Default':
#		# output is an array, first entry is 
#		# p, probability that it is classified as bunching
#		# second is 1 - p
#		return prediction[0][0]
#	else:
#		return 'check your input'


@app.route('/')
@app.route('/input')
def index():
	return render_template("input.html")

@app.route('/app')
def read_in_directions():
	start = flask.request.args.get('starting_location')
	end = flask.request.args.get('ending_location')
	print 'start is '+str(start)
	print 'end is '+str(end)
	# Get dataframe of next bus info 
	df_next_bus_pair = subsequent_bus_info(str(start), str(end))
	print df_next_bus_pair.head()
	#tmp = my_func('51 Blair Terrace', '24th St BART Station')

	route_1 = df_next_bus_pair['route_x'][0]
	
	expected_arrival_1 = df_next_bus_pair['arrival_x'][0]
	expected_arrival_2 = df_next_bus_pair['arrival_y'][0]

	position1 = [0,0]
	position2 = [0,0]
	position1[0] = df_next_bus_pair['lat_x'][0]
	position1[1] = df_next_bus_pair['lon_x'][0]
	position2[0] = df_next_bus_pair['lat_y'][0]
	position2[1] = df_next_bus_pair['lon_y'][0]

	prediction = probability_of_bunching(df_next_bus_pair)

	return render_template('output.html', \
			starting_loc = start, ending_loc = end, \
			route_1 = route_1, \
			expected_arrival_1 = expected_arrival_1, \
			expected_arrival_2 = expected_arrival_2, \
			position1 = position1, \
			position2 = position2, \
			prediction = prediction)
