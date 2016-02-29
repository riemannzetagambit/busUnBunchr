# busUnBunchr
Working code for Insight Data Science product. 

BusUnBunchr is an app intended to recommend to a user whether or not they should take an upcoming SF Muni vehicle based upon whether or not that vehicle is 'bunched' or not.
The assumption is that if two vehicles are bunched, the forward vehicle is likely overcrowded (this is the usual cause of delays in transit systems). The user will surely prefer a less packed vehicle if the next upcoming vehicle is only a few minutes behind the overcrowded one.

The app is a website, currently hosted on AWS at busunbunchr.xyz.
The machine learning model used to provide the predictions for bunching was constructed in the Jupyter notebook included below. 
The rest of the infrastructure used to build the database on which the model is trained on, and also the front end infrastructure for the website itself, are all also included.

Main files:
<ul>
	<li>busUnBunchr_model_construction.ipynb </li>
  main Jupyter notebook used to build random forest model to predict bunching. Includes data exploration and model validation.
 <li>call_NextBus_API_with_predictions.py</li>
  script used to build database of pairs of vehicles in the SF Muni system. Makes realtime calls to the Nextbus API indefinitely.
 <li>build_database_with_freqs.ipynb</li>
  a Jupyter notebook that cleans the database built from the above script to be more amenable to the analysis done in the main Jupyter analysis notebook
 <li>busUnBunchr_site/</li>
  includes all front end pieces, including Flask scripts and html for website
</ul>
