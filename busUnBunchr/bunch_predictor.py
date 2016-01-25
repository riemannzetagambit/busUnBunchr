# General analysis
import numpy as np
import pandas as pd
import patsy

# Needed to load hardcoded RF result from disk
import pickle

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


