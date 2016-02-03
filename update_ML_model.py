##########################################################
# import appropriate packages
##########################################################
# all purpose
import datetime, re
from math import radians, cos, sin, asin, sqrt

# for talking to SQL databases
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database

# all purpose data analysis and plotting
from scipy import stats
import pandas as pd
import numpy as np

# for ML
import patsy
from sklearn.ensemble import RandomForestRegressor
from sklearn import cross_validation, metrics, linear_model, svm
# needed for cross-validation on sets where the test data is not binary/multiclass 
# (i.e. needed for regressors, not classifiers)
from sklearn.cross_validation import train_test_split
from sklearn.cross_validation import KFold

# for saving output
import pickle

# load up Muni routes
list_of_muni_routes = np.load('list_of_muni_routes.npy')

    
##########################################################
# define functions needed later
##########################################################
def tanh_func(normed_pred_diff):
    # do tanh(1/x) so that x = 0 (on top of each other) gets mapped to 1 (bunched)
    # Multiply by 3 to get steeper fall off, 'bunched(0.5) = 0.57 [chosen ad hoc]
    # offset by 0.01 so np doesn't explode its brain at x=0
    return np.tanh(1/(2*(normed_pred_diff+0.001)))

##########################################################
# connect to the SQL database
##########################################################
dbname = 'sf_muni_arrivals_aws'
username = 'ec2-user'
table = 'nextbus_realtime_with_predictions_and_freqs'

# Open up an engine, that we will use to create the database if it doesn't exist
engine = create_engine('postgres://%s@localhost:63333/%s'%(username,dbname))

if not database_exists(engine.url):
    create_database(engine.url)
   
# If I want to filter the data first:
# connect:
db_con = None
db_con = psycopg2.connect(database = dbname, user = username)

##########################################################
# build dataframe from SQL database
##########################################################
sql_query = '''SELECT * FROM {table};'''.format(table=remote_table)
df_all = pd.read_sql_query(sql_query, db_con)

##########################################################
# build bunching parameter for each entry
##########################################################
# Compose a dictionary, two for each route. 
# For each route, drop all duplicates 
# (taking first and last for first and second part of each dict, respectively). 
bunching_dict={}
for i in list_of_muni_routes:
    my_key1 = 'route_'+str(i)+'_'+str(1)
    my_key2 = 'route_'+str(i)+'_'+str(2)
    if my_key1 not in bunching_dict:
        bunching_dict[my_key1] = 0
    if my_key2 not in bunching_dict:
        bunching_dict[my_key2] = 0 
        
# Declare a total dataframe to take everything in, appending sequentially later
df_total = pd.DataFrame()

# Compute the bunching parameter via convolution
kernel = [0.125,0.25,0.5,1,0.5,0.25,0.125]
terms_to_drop = (len(kernel)-1)/2
for route in list_of_muni_routes:
    for i in range(2):
        key = 'route_'+str(route)+'_'+str(i)
        bunching_dict[key] = df_all[df_all.route_x == str(route)]
        #print bunching_dict[key].head(5)
        if i == 0:
            bunching_dict[key] = bunching_dict[key].drop_duplicates(subset='time', keep='first')
        elif i == 1:
            bunching_dict[key] = bunching_dict[key].drop_duplicates(subset='time', keep='last')
        if not bunching_dict[key].empty:
            bunched_tmp=map(tanh_func,np.convolve(bunching_dict[key]['normed_pred_diff'],kernel)/sum(kernel))
            bunched_tmp=bunched_tmp[terms_to_drop:]
            bunched_tmp=bunched_tmp[:-terms_to_drop]
            bunching_dict[key]['bunched'] = bunched_tmp
            df_total = df_total.append(bunching_dict[key])

##########################################################
# build Random Forest regressor
##########################################################
forest = RandomForestRegressor(n_estimators = 250)

# There is no point in splitting the data 
# for the model that we will use for live data, 
# so we use all data and prepare it for the RF Regressor
features = ['lat_x','lon_x','speed_x','time','lat_y','lon_y','speed_y','dist','freq', 'route_x']
xtrain = df_total[features]
xtrain = xtrain.reset_index(drop=True)
xtrain['hour'] = xtrain.apply(lambda row: row['time'].hour, axis=1)
xtrain['minute'] = xtrain.apply(lambda row: row['time'].minute, axis=1)
xtrain.drop('time', inplace=True, axis=1)

# Need to be a bit careful about encoding. To be safe, we add 
# all routes and then drop them afterward
rows_to_keep = xtrain.shape[0]
for i, route in enumerate(list_of_muni_routes,rows_to_keep+1):
    df_tmp = pd.DataFrame({'route_x': route}, index=[i])
    xtrain = pd.concat([xtrain,df_tmp])
encoding_route = pd.get_dummies(xtrain['route_x'])
xtrain = pd.concat([xtrain,encoding_route], axis=1)
xtrain.drop(['route_x'], inplace=True, axis=1)
xtrain = xtrain.head(rows_to_keep)
xtrain = xtrain.as_matrix()

ytrain = df_total.as_matrix(columns=[train_data.columns[-1]])

# Train the RF Regressor on all the data (again, not point in splitting data)
rfr = forest.fit(xtrain,ytrain.ravel())

# Write to disk
today = !date '+%Y_%m_%d'
savefile = 'rf_fit_'+str(today[0])+'.pkl'

with open(savefile,'wb') as output:
    pickle.dump(rfr, output, pickle.HIGHEST_PROTOCOL)



