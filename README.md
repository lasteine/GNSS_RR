# GNSS_RR
Continuous estimation of in-situ snow/firn accumulation, snow water equivalent (snow mass), and snow/firn density 
on a fast-moving surface (ice shelf) using combined Global Navigation Satellite System (GNSS) reflectometry/refractometry (GNSS-RR)}


In case of a moving ground surface such as an ice shelf or glacier, the GNSS base and rover need to be physically (mechanically) connected 
to each other to enable a stable GNSS baseline, especially in the height component. Otherwise, it is not possible to separate 
the snow induced effect from the station height movement!

Snow accumulation is estimated using GNSS interferometric reflectometry (GNSS-IR) and the open-source "gnssrefl" software on Linux. 
A high-end receiver is used in the field setup, connected to a high-end multi-frequency and multi-GNSS antenna. The GNSS base 
receiver logged multi-GNSS RINEX data with a 1s sampling rate.

Snow water equivalent (SWE) is estimated using GNSS refractometry based on the biased up-component and post processing on Windows. 
The biased up-component of a short GNSS baseline between a base antenna (mounted on a pole) and a rover antenna (mounted underneath the snowpack) 
is used in this approach. High-end receivers are used in the field setup, connected to high-end multi-frequency and multi-GNSS antennas for the base. 
The receivers logged multi-GNSS RINEX data with 30s sampling rate, which are used for post processing using the open-source GNSS processing software "RTKLIB". 

Snow density is derived by combining the results (accumulation and SWE) from both individual methods.



A gnssrefl and a RTKLIB configuration file are attached, which are used in Steiner et al. (2023). 
By now, the processing is run using three individual bash scripts as all code was coded on Windows, but the gnssrefl software only runs on Linux (or Apple).
The scripts should be executed one after the other (at the earliest when the previous script finished):

1. automate_Acc_preprocess.sh (on Windows)
   runs a python script which defines all data paths and prepares (download, unzip, rename & move GNSS rapid orbit files) GNSS orbit & observation files needed for "gnssrefl".
   
2. run_gnssrefl_ubuntu.sh (on Linux)
   runs "gnssrefl" by first converting all GNSS rinex files to column-based SNR files needed as input for then running the GNSS-IR processing.

3. automate_SWE_Acc_density.sh (on Windows)
   runs a python script which does all the rest. Data paths need to be defined here. The python script contains the workflow from definition 
   of data paths, preprocessing of data, "RTKLIB" post processing of daily GNSS RINEX files to filtered and plotted snow accumulation, SWE, and 
   density timeseries. GNSS-IR results are copied from the Linux folder and combined with the GNSS refractometry results to output density time series. 
   Reference data from available ground truth sensors are automatically copied or downloaded for comparison.



The method follows Steiner et al. (2023, 2022, 2020): 

Steiner, L.; Schmithüsen, H.; Wickert, J.; Eisen, O. Combined GNSS Reflectometry/Refractometry for
Continuous In Situ Surface Mass Balance Estimation on an Antarctic Ice Shelf, 2023, submitted to The Cryosphere.

Steiner, L.; Studemann, G.; Grimm, D.E.; Marty, C.; Leinss, S. (Near) Real-Time Snow Water Equivalent Observation Using GNSS Refractometry and RTKLIB. 
Sensors 2022, 22, 6918, https://doi.org/10.3390/s22186918.

L. Steiner, M. Meindl, C. Marty and A. Geiger, "Impact of GPS Processing on the Estimation of Snow Water Equivalent Using Refracted GPS Signals," 
in IEEE Transactions on Geoscience and Remote Sensing, vol. 58, no. 1, pp. 123-135, Jan. 2020, https://doi.org/10.1109/TGRS.2019.2934016.





Example data is publicly available on the PANGAEA data repository:

Steiner, Ladina; Eisen, Olaf; Schmithüsen, Holger (2023): GNSS refractometry/reflectometry (GNSS-RR)
raw data near Neumayer Station in 2021-2023. PANGAEA, https://doi.org/10.1594/PANGAEA.958973, embargoed until 1.8.2023.

