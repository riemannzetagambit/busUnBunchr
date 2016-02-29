#!/usr/bin/python

# avl2postgis.py: load AVL data (currently NextBus) into PostGIS
# Copyright 2011 Matt Conway

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Authors:
# Matt Conway: main code
# David Stone: edited for PostgreSQL input, and modified options
# original code taken from:
# http://www.indicatrix.org/2011/05/29/archiving-historical-data-from-nextbus/

# The table you connect to should look like this:
# agency varchar
# vehicle varchar
# direction varchar
# heading int
# route varchar
# time timestamp
# the_geom

from optparse import OptionParser
from pyquery import PyQuery as pq
from time import sleep
# These next two imports I am taking from the 'python_sql_dev_setups' jupyter notebook
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
import psycopg2
from psycopg2 import connect
from urllib2 import urlopen
import sys, datetime
import numpy as np
import pandas as pd
from math import radians, cos, sin, asin, sqrt


# Parse the options
# to add to options: username, route number
parser = OptionParser()
parser.add_option('-a', '--agency', dest='agency', type='string',
                  help='the NextBus agency name (e.g. sf-muni)',
                  metavar='AGENCY', default='sf-muni')
parser.add_option('-t', '--table', dest='table', type='string',
                  help='the table to store data in',
                  metavar='TABLE', default='nextbus_aws')
parser.add_option('-d', '--dsn', dest='dsn', type='string',
                  help='database dsn, as documented at http://initd.org/psycopg/docs/module.html#psycopg2.connect',
                  metavar='DSN', default='sf_muni_arrivals_aws')
parser.add_option('-i', '--interval', dest='interval', type='int',
                  help='number of seconds to pause between NextBus requests',
                  metavar='interval', default=30)
parser.add_option('-u', '--user', dest='user', type='string',
                  help='username to start the database with',
                  metavar='user', default='ec2-user')
#parser.add_option('-r', '--route', dest='route', type='string',
#                  help='Muni short name route number',
#                  metavar='route', default='30')
parser.add_option('--all-vehicles', dest='allvehicles',
                  help='query all vehicles each time, instead of just updated ones',
                  default=False)
parser.add_option('--no-deltas', dest='nodeltas',
                  help="Don't use deltas to calculate time, just put in retrieval time",
                  default=False)

options, args = parser.parse_args()

# create the SQL datbase
username = options.user # change this as you will
engine = create_engine('postgres://{0}@localhost/{1}'.format(username,options.dsn))
if not database_exists(engine.url):
    create_database(engine.url)

# connect to database I just created
db_con = None
db_con = psycopg2.connect(database = options.dsn, user = username)

# Load list of Muni routes (must make sure this is in same directory)
list_of_muni_routes = np.load('list_of_muni_routes.npy')


# start with all reported locations in last 15 mins
since_time = 0
update_since_time = False

# We will need this function to compute the distance between two (lat,lon) points, in meters
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

# main function to enter route data with predictions into database
def enter_pairs_for_route_into_database(specified_route, specified_engine, specified_table):
    global since_time, options, update_since_time

    if options.allvehicles:
        qtime = 0
    else:
        qtime = since_time

    # 

    # Get last stops of inbound and outbound buses for this route
    url_get_route_config='http://webservices.nextbus.com/service/publicXMLFeed?command=routeConfig&a={agency}&r={route}'.format(agency=options.agency, route=specified_route)
    route_config = pq(urlopen(url_get_route_config).read())
    for direction in pq(route_config('direction')):
        dirIO = pq(direction).attr('tag')
        stop_tag = pq(direction[-1]).attr('tag')
        print 'stop_tag: '+str(stop_tag)
        if 'I' in str(dirIO):
            stop_tag_inbound = stop_tag
        if 'O' in str(dirIO):
            stop_tag_outbound = stop_tag
            
    # Get predictions in pairs
    # First 
    try:
        stop_tag_inbound
    except:
        stop_tag_inbound = None
        df_I = pd.DataFrame()
    if stop_tag_inbound is not None:
        #print 'stop_tag_inbound is not None'
        url_get_predictions_inbound='http://webservices.nextbus.com/service/publicXMLFeed?command=predictions&a={agency}&s={stop_tag_I}&r={route}'.format(agency=options.agency, stop_tag_I=stop_tag_inbound, route=specified_route)
        predictions_I = pq(urlopen(url_get_predictions_inbound).read())
        df_I = pd.DataFrame()
        indexer=0
        # Deal with lack of pairs later, but throw that as an error and don't display bunching
        for i in range(len(predictions_I('prediction'))-1):
            if pq(predictions_I('prediction')[i]).attr.affectedByLayover is None or pq(predictions_I('prediction')[i+1]).attr.affectedByLayover is None: 
                prediction1 = pq(predictions_I('prediction')[i])
                prediction2 = pq(predictions_I('prediction')[i+1])
                df_tmp = pd.DataFrame({'vehicle1': prediction1.attr.vehicle, \
                                    'vehicle2': prediction2.attr.vehicle, \
                                    'pred1': prediction1.attr.minutes, \
                                    'pred2': prediction2.attr.minutes}, index=[indexer])
                df_I = df_I.append(df_tmp)
                indexer += 1
            
    #print 'finished inbound loop'

    # Now outbound
    try:
        stop_tag_outbound
    except:
        stop_tag_outbound = None
        df_O = pd.DataFrame()
    if stop_tag_outbound is not None:
        #print 'stop_tag_outbound is not None'
        url_get_predictions_outbound='http://webservices.nextbus.com/service/publicXMLFeed?command=predictions&a={agency}&s={stop_tag_O}&r={route}'.format(agency=options.agency, stop_tag_O=stop_tag_outbound, route=specified_route)
        predictions_O = pq(urlopen(url_get_predictions_outbound).read())
        df_O = pd.DataFrame()
        indexer=0
        # Deal with lack of pairs later, but throw that as an error and don't display bunching
        for i in range(len(predictions_O('prediction'))-1):
            if pq(predictions_O('prediction')[i]).attr.affectedByLayover is None or pq(predictions_O('prediction')[i+1]).attr.affectedByLayover is None: 
                prediction1 = pq(predictions_O('prediction')[i])
                prediction2 = pq(predictions_O('prediction')[i+1])
                df_tmp = pd.DataFrame({'vehicle1': prediction1.attr.vehicle, \
                                    'vehicle2': prediction2.attr.vehicle, \
                                    'pred1': prediction1.attr.minutes, \
                                    'pred2': prediction2.attr.minutes}, index=[indexer])
                df_O = df_O.append(df_tmp)
                indexer += 1
    
    #print 'finished outbound loop'
    if df_I.empty and df_O.empty:
        print 'Not adding anything'
        return
    elif df_I.empty:
        df_array = [df_O]
    elif df_O.empty:
        df_array = [df_I]
    else:
        df_array = [df_I, df_O]
    #print 'checked for df_I and df_O emptiness'

    # Now go to realtime predictions and match the vehicle numbers (vehicles should have a unique ID)
    url_get_realtime_posits='http://webservices.nextbus.com/service/publicXMLFeed?command=vehicleLocations&a={agency}&t={since_time}&r={route}'.format(agency=options.agency, since_time=qtime, route=specified_route)
    realtime_posits = pq(urlopen(url_get_realtime_posits).read())
    df_total = pd.DataFrame()

    # update time after making that realtime call
    #print 'before since_time = '+str(since_time)
    # actually, only change since_time if it is the last route in the route_list
    if update_since_time:
        since_time = int(pq(pq(realtime_posits('vehicle')[-1]).siblings()[-1]).attr('time'))
    #print 'after since_time'
    time_stamp = datetime.datetime.utcfromtimestamp(int(pq(pq(realtime_posits('vehicle')[-1]).siblings()[-1]).attr('time'))/1000)

    #print 'at loop over inbound/outbound arrays'
    for df_tmp in df_array: 
        # for each pair in df_I, find the match in the realtime_posits
        df1 = pd.DataFrame()
        df2 = pd.DataFrame()
        for i in range(df_tmp.shape[0]):
            for vehicle in realtime_posits('vehicle'):
                v = pq(vehicle)
                if v.attr.id == df_tmp.loc[i]['vehicle1']:
                    df1 = pd.DataFrame({'ind':i, 'time': time_stamp,'lat_x': float(v.attr.lat), 'lon_x': float(v.attr.lon), 'speed_x': float(v.attr.speedKmHr), 'route_x': str(v.attr.routeTag), 'pred_x': df_tmp.loc[i]['pred1']},index=[0])
                    #df1 = df1.append(df1_tmp)
                elif v.attr.id == df_tmp.loc[i]['vehicle2']:
                    df2 = pd.DataFrame({'ind':i, 'lat_y': float(v.attr.lat), 'lon_y': float(v.attr.lon), 'speed_y': float(v.attr.speedKmHr), 'pred_y': df_tmp.loc[i]['pred2']},index=[0])
                    #df2 = df2.append(df2_tmp)
            if df1.empty or df2.empty:
                continue
            else:
                df_tmp1 = pd.merge(left=df1, right=df2)
                df_total = df_total.append(df_tmp1)

    # check to make sure we've actually found something
    if not df_total.empty:
        'Added stuff'

    if df_total.empty:
        # don't add anything this time around (remember, this just adds buses from this route for this specific call)
        return
    else:
        # some cleaning
        df_total.drop('ind', inplace=True, axis=1)
        df_total.index = np.arange(df_total.shape[0])
        # add distance after computing for this route
        df_total['dist'] = df_total.apply(lambda row: haversine(row['lat_x'],row['lon_x'],row['lat_y'],row['lon_y']), axis=1)
        
        # Now right this beast to a SQL database specified by input
        df_total.to_sql(specified_table, specified_engine, if_exists='append')

# Execute for loop over all routes inside infinite loop at end

# Loop forever, or until killed
i = 0
while 1:
    try:
        update_since_time = False
        # Loop over every route
        for i, route in enumerate(list_of_muni_routes):
            print 'doing route = '+str(route)

            # If at last of routes, then update the time
            if i == len(list_of_muni_routes):
                update_since_time = True
            enter_pairs_for_route_into_database(route, engine, options.table)

        # Commit every 10 calls
        if i == 10:
            db_con.commit()
            i = 0
        else:
            i += 1
    except:
        print sys.exc_info()
        print 'Exception occured - skipping this iteration (connection reset by peer?)'

    # The reason this is inside a try...except is b/c
    # sometimes people want to skip the sleep and go straight to the
    # next iteration.
    try:
        sleep(options.interval)
    except:
        pass
        


