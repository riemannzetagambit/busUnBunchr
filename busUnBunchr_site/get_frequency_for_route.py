# General analysis
import numpy as np
import pandas as pd
import patsy

# Needed to load hardcoded RF result from disk
import pickle

def get_frequency_for_route(pair_route, pair_time):
	''' Must past pair_time as a time stamp 
		(which should come from dataframe that you are adding to) 
	'''
	with open('busUnBunchr_site/route_frequencies/route_'+str(pair_route)+'_frequencies.pkl','rb') as input:
		freq_df  = pickle.load(input)
	t0 = '1970-01-01 '+str(pair_time.hour)+':'+str(pair_time.minute)+':00'
	# set to end of day, no messing around
	t1 = '1970-01-01 23:59:00'
	# some more error catching
	try:
		return freq_df.loc[t0:t1]['freq'][0]
	except:
		# return last frequency you found
		return freq_df.iloc[-1]['freq']
