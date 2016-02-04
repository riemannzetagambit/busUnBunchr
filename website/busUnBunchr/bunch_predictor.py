# General analysis
import numpy as np
import pandas as pd
import patsy

# Needed to load hardcoded RF result from disk
import pickle

def probability_of_bunching(bus_pair, forest):
	# A formula from patsy/dmatrices so we can feed into our RF classifier
	# Input format is expected for dataframe coming in from get_bus_info function
	#formula_for_realtime = 'bunched ~ time.dt.hour + time.dt.minute + lat_x + lon_x + speed_x  + lat_y + lon_y + speed_y + dist_percentile'

	# if using frequency information
	#formula_for_realtime = 'bunched ~ time.dt.hour + time.dt.minute + lat_x + lon_x + speed_x  + lat_y + lon_y + speed_y + dist + freq'

	# xtmp will be a single dataframe entry that we can feed into the RF classifier
	#ytmp, xtmp = patsy.dmatrices(formula_for_realtime, data=bus_pair, return_type='dataframe')

	# construct appropriate one hot-encoded matrices for the forest to fit on
	features = ['lat_x','lon_x','speed_x','time','lat_y','lon_y','speed_y','dist','freq','route_x']
	xtest = bus_pair[features]
	xtest['hour'] = xtest.apply(lambda row: row['time'].hour, axis=1)
	xtest['minute'] = xtest.apply(lambda row: row['time'].minute, axis=1)
	xtest.drop('time', inplace=True, axis=1)

	list_of_muni_routes = np.load('list_of_muni_routes.npy')
	for i, route in enumerate(list_of_muni_routes,1):
	    df_tmp = pd.DataFrame({'route_x': route}, index=[i])
	    xtest = pd.concat([xtest,df_tmp])

	encoding = pd.get_dummies(xtest['route_x'])
	xtest = pd.concat([xtest,encoding], axis=1)
	xtest.drop(['route_x'], inplace=True, axis=1)
	xtest = xtest.head(1)
	xtest = xtest.as_matrix()

	# for classifier
	#prediction = forest.predict_proba(xtmp)[0]

	# for regressor
	prediction = forest.predict(xtest)

	# output is an array, first entry is 
	# p, probability that it is classified as bunching
	# second is 1 - p
	return prediction[0]
