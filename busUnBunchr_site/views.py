import flask
from flask import render_template
from flask import jsonify
#from flask import request
from busUnBunchr import app
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
import pandas as pd
import psycopg2
import pickle

from bunch_predictor import probability_of_bunching
from get_upcoming_vehicle_info import subsequent_bus_info

# load up RF
print 'opening saved rf'
with open('model/busUnBunchr/rf_fit_2016_02_02.pkl','rb') as input:
#with open('../rf_fit_2016_01_21.pkl','rb') as input:
    forest = pickle.load(input)
print 'rf loaded successfully'

@app.route('/')
@app.route('/index')
def index():
	return render_template("index.html")

@app.route('/app', methods = ['GET','POST'])
def read_in_directions():
	if flask.request.method == 'POST':
		start = flask.request.form['start']
		end = flask.request.form['end']

	# Use this to display the google maps transit directions in the background
	transit_url='https://www.google.com/maps/embed/v1/directions?key=AIzaSyDWQv6WWQptI-6rjbavkoZ1TpVZhHKOm4w&origin='+str(start).replace(' ','+')+'&destination='+str(end).replace(' ','+')+'&mode=transit'
	# This url will link to the actual google maps and will be supplied 
	google_maps_url='https://www.google.com/maps/dir/'+str(start).replace(' ','+')+'/'+str(end).replace(' ','+')

	print 'transit_url is:\n'+transit_url

	# Get dataframe of next bus info 
	df_next_bus_pair = subsequent_bus_info(str(start), str(end))
	if df_next_bus_pair.empty:
		message = '<div id="status_message"><br><div class=\"text-center\" style=\"color: #FFF;\">Sorry! We don\'t have any information from Muni for the route requested. \
					<br> <div class="text-center" style="font-size: 12px;"><a href='+str(google_maps_url)+'>Check Google Maps directly</a></div></div>'
		print 'There does not seem to be any information for this route. Try again?'
		# At least return the message
		return jsonify({'message': message})
	else:
		message = '<div id="status_message" class="text-center" style="color: #FFF;"><br>Success! Realtime Muni data found for initial transit segment.</div>'

		print df_next_bus_pair.head()
		#tmp = get_googlemaps_json('51 Blair Terrace', '24th St BART Station')
	
		route_1 = df_next_bus_pair['route_x'][0]
		
		expected_arrival_1 = df_next_bus_pair['arrival_x'][0]
		expected_arrival_2 = df_next_bus_pair['arrival_y'][0]
	
		stop_name = df_next_bus_pair['stop_name'][0]
		vehicle_type = df_next_bus_pair['vehicle_type'][0]
	
		position1 = [0,0]
		position2 = [0,0]
		position1[0] = df_next_bus_pair['lat_x'][0]
		position1[1] = df_next_bus_pair['lon_x'][0]
		position2[0] = df_next_bus_pair['lat_y'][0]
		position2[1] = df_next_bus_pair['lon_y'][0]
	
		print '(lat, lon) 1st bus: ('+str(position1[0])+','+str(position1[1])+')'
		print '(lat, lon) 2nd bus: ('+str(position2[0])+','+str(position2[1])+')'
	
		prediction = probability_of_bunching(df_next_bus_pair, forest)
	
		print 'prediction is '+str(prediction)
		directions_box_1 = render_template('directions_box.html',route_1=route_1, prediction=prediction, arrival_time_1=expected_arrival_1,
				arrival_time_2=expected_arrival_2, google_maps_url=google_maps_url, stop_name=stop_name, vehicle_type=vehicle_type)
	
		print 'testing directions_box: \n'+str(directions_box_1)
	
		# Return this information to the javascript in 'index.html' to update the page via AJAX
		return jsonify({'starting_loc': start, 'ending_loc': end, 'transit_url': transit_url, 'route_1': route_1, \
				'expected_arrival_1': expected_arrival_1, 'expected_arrival_2': expected_arrival_2, 'prediction': prediction, \
				'position1': position1, 'position2': position2, 'directions_box_1': directions_box_1, \
				'google_maps_url': google_maps_url, 'message': message, 'vehicle_type': vehicle_type})
