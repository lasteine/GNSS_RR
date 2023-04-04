""" Run RTKLib automatically for differential GNSS post processing and SWE estimation at the surroundings of the NeumayerIII station
http://www.rtklib.com/

Reference: Steiner et al., Combined GNSS reflectometry/refractometry for continuous in situ surface mass balance estimation on an Antarctic ice shelf, AGU, 2022.

input:  - GNSS config file (.conf)
        - GNSS rover file (rinex)
        - GNSS base file (rinex)
        - GNSS navigation ephemerides file (.nav); ftp://cddis.nasa.gov/archive/gnss/data/daily/YYYY/brdc/brdc*.yy[nge].gz
        - GNSS precise ephemerides file (.eph/.sp3); ftp://ftp.aiub.unibe.ch/YYYY_M/COD*.EPH_M.zip

output: - position (.pos) file; (UTC, E, N, U)
        - plots (SWE timeseries, DeltaSWE timeseries, scatter plots)

created by: L. Steiner (Orchid ID: 0000-0002-4958-0849)
created on: 17.05.2022
updated on: 08.10.2022
"""

# IMPORT modules
import os
import functions as f
import datetime as dt

# CHOOSE: DEFINE data paths, file names (base, rover, navigation orbits, precise orbits, config), time interval, and processing steps !!!
scr_path = '//smb.isibhv.dmawi.de/projects/p_gnss/Data/'                                        # data source path at AWI server (data copied from Antarctica via O2A)
dest_path = 'C:/Users/sladina.BGEO02P102/Documents/SD_Card/Postdoc/AWI/05_Analysis/Run_RTKLib/data_neumayer/'    # data destination path for processing
laser_path = '//smb.isibhv.dmawi.de/projects/mob/Neumayer/data/Rohdaten/shm/'                   # data source path at AWI server for snow accumulation laser sensor from AWI MetObs
buoy_url = 'https://data.meereisportal.de/data/buoys/processed/2017S54_data.zip'                # data path for snow buoy data close to Spuso from sea ice physics group
ubuntu_path = '//wsl.localhost/Ubuntu/home/sladina/test/gnssrefl/data/'                         # data source path at the Ubuntu localhost (GNSS reflectometry processing location)
rover = 'ReachM2_sladina-raw_'                                                                  # 'NMER' or '3393' (old Emlid: 'ReachM2_sladina-raw_')
rover_name = 'NMER_original'                                                                    # 'NMER' or 'NMER_original' or 'NMLR'
receiver = 'NMER'                                                                               # 'NMER' or 'NMLB' or 'NMLR'
base_name = 'NMLB'
base = '3387'                                                                                   # rinex file name prefix for base receiver
nav = '3387'                                                                                    # navigation file name prefix for broadcast ephemerides files
sp3 = 'COD'                                                                                     # navigation file name prefix for precise ephemerides files
ti_int = '900'                                                                                  # processing time interval (seconds)
resolution = '15min'                                                                            # processing resolution (minutes)
options_Leica = 'rtkpost_options_Ladina_Leica_statisch_multisystemfrequency_neumayer_900_15'    # name of RTKLIB configuration file (.conf) for high-end receiver
options_Emlid = 'rtkpost_options_Ladina_Emlid_statisch_multisystemfrequency_neumayer_900_15'    # name of RTKLIB configuration file (.conf) for low-cost receiver
ending = ''                                                                                     # file name suffix if needed: e.g., a variant of the processing '_eleambmask15', '_noglonass'
acc_y_lim = (-400, 1600)                                                                        # y-axis limit for accumulation plots
delta_acc_y_lim = (-400, 1000)                                                                  # y-axis limit for delta accumulation plots
swe_y_lim = (-100, 700)                                                                         # y-axis limit for water equivalent plots
delta_swe_y_lim = (-200, 600)                                                                   # y-axis limit for delta water equivalent plots
xlim_dates = dt.date(2021, 11, 26), dt.date(2023, 1, 17)                                        # time series date limits to plot on x-axis
cal_date = '2022-07-24'                                                                         # calibration date for snow density estimation
yy = '21'                                                                                       # initial year of observations
save_plots = True                                                                               # show (False) or save (True) plots
total_backup = False                                                                            # copy (True) all new data to server for backup, else (False) do not copy
solplot_backup = True                                                                          # copy (True) all new solution files and plots to server for backup, else (False) do not copy


""" 0. Preprocess data """
# create processing directory
os.makedirs(dest_path, exist_ok=True)

# copy & uncompress new rinex files (NMLB + all orbits, NMLR, NMER) to processing folder 'data_neumayer/' (via a temporary folder for all preprocessing steps)
end_mjd_emlid = f.copy_rinex_files(scr_path + 'id8282_refractolow/', dest_path + 'temp_NMER/', receiver='NMER', copy=True,
                                   parent=True, hatanaka=True, move=True, delete_temp=True)  # for emlid rover: NMER
end_mjd = f.copy_rinex_files(scr_path + 'id8281_refracto/', dest_path + 'temp_NMLR/', receiver='NMLR', copy=True,
                             parent=True, hatanaka=True, move=True, delete_temp=True)  # for leica rover: NMLR
end_mjd_base = f.copy_rinex_files(scr_path + 'id8283_reflecto/', dest_path + 'temp_NMLB/', receiver='NMLB', copy=True,
                                  parent=True, hatanaka=True, move=True, delete_temp=True)  # for leica base: NMLB

# check available solution data to only further process new data (first mjd in 2021 here: 59544.0)
yy, start_mjd, start_mjd_emlid = f.get_sol_yeardoy(dest_path, resolution)

# # for proceedina manually without preprocessing: calculate start/end mjd using a given start/end date
# start_mjd, end_mjd = f.get_mjd_int(2021, 11, 12, 2023, 2, 28)
# start_mjd_emlid, end_mjd_emlid = start_mjd, end_mjd


""" 1. run RTKLib automatically (instead of RTKPost Gui manually) """
# process data using RTKLIB post processing command line tool 'rnx2rtkp' for a specific year and a range of day of years (doys)
f.automate_rtklib_pp(dest_path, 'NMER', start_mjd_emlid, end_mjd_emlid, ti_int, base, nav, sp3, resolution, ending, 'NMER', options_Emlid)
f.automate_rtklib_pp(dest_path, '3393', start_mjd, end_mjd, ti_int, base, nav, sp3, resolution, ending, 'NMLR', options_Leica)


''' 2. Get RTKLib ENU solution files '''
# read all RTKLib ENU solution files (daily) and store them in one dataframe for whole season
df_enu_emlid = f.get_rtklib_solutions(dest_path, 'NMER', resolution, ending, header_length=26)
df_enu_leica = f.get_rtklib_solutions(dest_path, 'NMLR', resolution, ending, header_length=26)


''' 3. Filter and clean ENU solution data '''
fil_df_emlid, u_emlid, u_clean_emlid, swe_gnss_emlid, std_gnss_emlid, swe_gnss_daily_emlid, std_gnss_daily_emlid = f.filter_rtklib_solutions(
    dest_path, 'NMER', resolution, df_enu=df_enu_emlid, ambiguity=1, threshold=3, window='D', ending=ending)

fil_df_leica, u_leica, u_clean_leica, swe_gnss_leica, std_gnss_leica, swe_gnss_daily_leica, std_gnss_daily_leica = f.filter_rtklib_solutions(
    dest_path, 'NMLR', resolution, df_enu=df_enu_leica, ambiguity=1, threshold=3, window='D', ending=ending)


""" 4. Read reference sensors data """
manual, ipol, buoy, poles, laser, laser_filtered = f.read_reference_data(
    dest_path, laser_path, yy, url=buoy_url, read_manual=True, read_buoy=True, read_poles=True, read_laser=True, laser_pickle='nm_laser')


''' 5. Convert swe to snow accumulation and add to df '''
gnss_leica = f.convert_swe2sh_gnss(swe_gnss_leica, ipol_density=ipol)
gnss_emlid = f.convert_swe2sh_gnss(swe_gnss_emlid, ipol_density=ipol)


# resample all sensors sh and swe data to daily & 15min data
leica_daily, emlid_daily, buoy_daily, poles_daily, laser_daily = f.resample_allobs(gnss_leica, gnss_emlid, buoy, poles, laser_filtered, interval='D')


""" 6. Calculate differences, linear regressions, RMSE & MRB between GNSS and reference data """
# calculate differences between reference data and GNSS (Leica/Emlid)
diffs_sh_daily, diffs_swe_daily = f.calculate_differences2gnss(emlid_daily, leica_daily, manual, laser_daily, buoy_daily, poles_daily)
diffs_sh_15min, diffs_swe_15min, laser_15min = f.calculate_differences2gnss_15min(gnss_emlid, gnss_leica, laser_filtered)

# calculate SWE cross correation manual/laser vs. GNSS (daily & 15min)
corr_leica_daily, corr_emlid_daily, corr_leica_15min, corr_emlid_15min = f.calculate_crosscorr(leica_daily, emlid_daily, manual, gnss_leica, gnss_emlid, laser_15min)

# fit linear regression curve manual/laser vs. GNSS (daily & 15min)
predict_daily, predict_emlid_daily, predict_15min, predict_15min_emlid = f.calculate_linearfit(leica_daily, emlid_daily, manual, gnss_leica, gnss_emlid, laser_15min)

# calculate RMSE and number of samples
f.calculate_rmse(diffs_swe_daily, diffs_swe_15min, manual, laser_15min)


''' 7. Plot results (SWE, ΔSWE, scatter) '''
os.makedirs(dest_path + '30_plots/', exist_ok=True)

# plot SWE (Leica, Emlid, manual, laser, buoy, poles)
f.plot_all_SWE(dest_path, swe_gnss_daily_leica.dropna(), swe_gnss_daily_emlid.dropna(), manual, laser_15min, buoy_daily, poles_daily,
               save=save_plots, suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], std_leica=std_gnss_daily_leica.dropna(), std_emlid=std_gnss_daily_emlid.dropna(), y_lim=swe_y_lim, x_lim=xlim_dates)

# plot SWE differences (Emlid, manual, laser, buoy, poles compared to Leica)
f.plot_all_diffSWE(dest_path, diffs_swe_daily, manual, laser_15min, buoy_daily, poles_daily,
                   save=save_plots, suffix='', leg=['Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=delta_swe_y_lim, x_lim=xlim_dates)

# plot boxplot of differences (Emlid, manual, laser compared to Leica)
f.plot_swediff_boxplot(dest_path, diffs_swe_daily, y_lim=delta_swe_y_lim, save=save_plots)

# plot scatter plot (GNSS vs. manual/laser, daily/15min)
f.plot_scatter(dest_path, leica_daily.dswe, emlid_daily.dswe, manual.SWE_aboveAnt, predict_daily, predict_emlid_daily,
               x_label='Manual', lim=swe_y_lim, save=save_plots)

f.plot_scatter(dest_path, gnss_leica.dswe, gnss_emlid.dswe, laser_15min.dswe, predict_15min, predict_15min_emlid,
               x_label='Laser', lim=swe_y_lim, save=save_plots)

# plot all Accumulation data (Leica, Emlid, laser, buoy, poles)
f.plot_all_Acc(dest_path, leica_daily, emlid_daily, manual, laser_15min, buoy_daily, poles_daily,
               save=save_plots, suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=acc_y_lim, x_lim=xlim_dates)

# plot Difference in Accumulation (compared to Leica)
f.plot_all_diffAcc(dest_path, diffs_sh_daily, diffs_sh_15min, manual, laser_15min, buoy_daily, poles_daily,
                   save=save_plots, suffix='', leg=['Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=delta_acc_y_lim, x_lim=xlim_dates)

# plot SWE, Density, Accumulation (from manual obs at Spuso)
f.plot_SWE_density_acc(dest_path, swe_gnss_daily_leica.dropna(), swe_gnss_daily_emlid.dropna(), manual, laser_15min,
                       save=save_plots, std_leica=std_gnss_daily_leica.dropna(), std_emlid=std_gnss_daily_emlid.dropna(), suffix='', y_lim=acc_y_lim, x_lim=xlim_dates)

# plot number of satellites
f.plot_nrsat(dest_path, fil_df_leica.nr_sat, fil_df_emlid.nr_sat, save=save_plots, suffix='', y_lim=(0, 35), x_lim=xlim_dates)

# plot ambiguity resolution state
f.plot_solquality(dest_path, df_enu_leica.amb_state, df_enu_emlid.amb_state, save=save_plots, suffix='', y_lim=(0, 100), x_lim=xlim_dates)

# plot PPP position solutions
# TODO: calculate new values
# df_ppp_ref = f.plot_PPP_solution(dest_path, 'NMLB', save=False, suffix='', x_lim=xlim_dates)
# df_ppp_rover = f.plot_PPP_solution(dest_path, 'NMLR', save=False, suffix='', x_lim=xlim_dates)


''' 8. Read GNSS-IR results '''
# read and filter gnss-ir snow accumulation results
df_rh = f.read_gnssir(dest_path, ubuntu_path, base_name, yy, copy=False, pickle='nmlb')
gnssir_acc, gnssir_acc_daily, gnssir_acc_daily_std, gnssir_rh_clean = f.filter_gnssir(df_rh, freq='2nd', threshold=2)

# plot gnss-ir snow accumulation results
f.plot_gnssir(dest_path, gnssir_acc, gnssir_acc_daily, gnssir_acc_daily_std, laser_daily, leica_daily, emlid=None, manual=None, buoy=None, poles=None, leg=['GNSS-Reflectometry', '_', 'GNSS-Refractometry', 'Laser (SHM)'], save=save_plots, suffix='_leica', x_lim=xlim_dates, y_lim=acc_y_lim)
f.plot_gnssir(dest_path, gnssir_acc, gnssir_acc_daily, gnssir_acc_daily_std, laser_daily, leica_daily, emlid=emlid_daily, manual=None, buoy=None, poles=None, leg=['GNSS-Reflectometry', '_', 'High-end GNSS-Refractometry', 'Low-cost GNSS-Refractometry', 'Laser (SHM)'], save=save_plots, suffix='_emlid', x_lim=xlim_dates, y_lim=acc_y_lim)


''' 9. Calculate snow density from GNSS-RR: Combine GNSS-IR & GNSS refractometry '''
density_leica = f.convert_swesh2density(gnss_leica.dswe.dropna(), gnssir_acc.dropna(), cal_date, cal_val=manual.Density_aboveAnt[cal_date])
density_emlid = f.convert_swesh2density(gnss_emlid.dswe.dropna(), gnssir_acc.dropna(), cal_date, cal_val=manual.Density_aboveAnt[cal_date])

# plot median filtered density time series (window=1week)
f.plot_density(dest_path, density_leica, density_emlid, laser=None, manual=manual, leg=['High-end GNSS-RR', 'Low-cost GNSS-RR', 'Manual'], save=save_plots, suffix='_leica_emlid', x_lim=xlim_dates)

# plot difference to manual density observation
f.plot_diff_density(dest_path, manual.Density_aboveAnt - density_leica.resample('D').median(), manual.Density_aboveAnt - density_emlid.resample('D').median(), laser=None, manual=manual, leg=['High-end GNSS-RR', 'Low-cost GNSS-RR'], save=save_plots, suffix='_leica_emlid', x_lim=xlim_dates)

# TODO: add scatter plot for density

''' 10. Back up data '''
if solplot_backup is True:
    # copy solutions and plots directories back to server
    f.copy_solplotsdirs(dest_path, scr_path + '../Processing/Run_RTKLib/data_neumayer/')

if total_backup is True:
    # copy entire processing directory back to server
    f.copy4backup(dest_path + '../', scr_path + '../Processing/Run_RTKLib/')


''' New stuff '''
# # STDs (AGM 2023)
# laser_15min.dsh_std.mean()              # laser
# std_gnss_daily_leica.dropna().mean()    # leica
# std_gnss_daily_emlid.dropna().mean()    # emlid
# gnssir_acc.resample('D').std().median() # GNSS-IR
# rms
# np.sqrt(np.sum((f-g)**2)/n)
