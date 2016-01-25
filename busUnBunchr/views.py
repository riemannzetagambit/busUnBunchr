import flask
from flask import render_template
from flask import jsonify
#from flask import request
from busUnBunchr import app
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
import pandas as pd
import psycopg2

from bunch_predictor import probability_of_bunching
from get_upcoming_vehicle_info import subsequent_bus_info

@app.route('/')
@app.route('/input')
def input():
	return render_template("input.html")

@app.route('/app', methods = ['GET','POST'])
def read_in_directions():
	if flask.request.method == 'POST':
		start = flask.request.form['start']
		# give back a json to jQuery to deal with updates to page
		# put this return at end of function
		return jsonify({'res': 'a', 'res2': 'b'})
	#start = flask.request.args.get('starting_location')
	#end = flask.request.args.get('ending_location')
	print 'start is '+str(start)
	print 'end is '+str(end)
	# Use this to display the google maps transit directions in the background
	transit_url='https://www.google.com/maps/embed/v1/directions?key=AIzaSyDWQv6WWQptI-6rjbavkoZ1TpVZhHKOm4w&origin='+str(start)+'&destination='+str(end)+'&mode=transit'

	print 'transit_url is:\n'+transit_url

	# Get dataframe of next bus info 
	df_next_bus_pair = subsequent_bus_info(str(start), str(end))
	print df_next_bus_pair.head()
	#tmp = get_googlemaps_json('51 Blair Terrace', '24th St BART Station')

	route_1 = df_next_bus_pair['route_x'][0]
	
	expected_arrival_1 = df_next_bus_pair['arrival_x'][0]
	expected_arrival_2 = df_next_bus_pair['arrival_y'][0]

	position1 = [0,0]
	position2 = [0,0]
	position1[0] = df_next_bus_pair['lat_x'][0]
	position1[1] = df_next_bus_pair['lon_x'][0]
	position2[0] = df_next_bus_pair['lat_y'][0]
	position2[1] = df_next_bus_pair['lon_y'][0]

	print '(lat, lon) 1st bus: ('+str(position1[0])+','+str(position1[1])+')'
	print '(lat, lon) 2nd bus: ('+str(position2[0])+','+str(position2[1])+')'

	prediction = probability_of_bunching(df_next_bus_pair)

	jsonify(results = 
	return render_template('output.html', \
			starting_loc = start, ending_loc = end, transit_url = transit_url, \
			route_1 = route_1, \
			expected_arrival_1 = expected_arrival_1, \
			expected_arrival_2 = expected_arrival_2, \
			position1 = position1, \
			position2 = position2, \
			prediction = prediction)
