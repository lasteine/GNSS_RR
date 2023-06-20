""" Run RTKLib automatically for differential GNSS post processing and SWE estimation at the surroundings of the NeumayerIII station
http://www.rtklib.com/

Reference:  - Steiner et al., Combined GNSS reflectometry/refractometry for continuous in situ surface mass balance estimation on an Antarctic ice shelf, AGU, 2022.
            - T.Takasu, RTKLIB: Open Source Program Package for RTK-GPS, FOSS4G 2009 Tokyo, Japan, November 2, 2009
            - Thomas Nischan (2016): GFZRNX - RINEX GNSS Data Conversion and Manipulation Toolbox. GFZ Data Services. https://doi.org/10.5880/GFZ.1.1.2016.002

input:  - GNSS config file (.conf)
        - GNSS rover file (rinex)
        - GNSS base file (rinex)
        - GNSS navigation ephemerides file (.nav); ftp://cddis.nasa.gov/archive/gnss/data/daily/YYYY/brdc/brdc*.yy[nge].gz
        - GNSS precise ephemerides file (.eph/.sp3); ftp://ftp.aiub.unibe.ch/YYYY_M/COD*.EPH_M.zip

output: - position (.pos) file; (UTC, E, N, U)
        - plots (SWE timeseries, DeltaSWE timeseries, scatter plots)

requirements:   - rtklib (v2.4.3 b34, https://www.rtklib.com/)
                - gfzrnx (https://dataservices.gfz-potsdam.de/panmetaworks/showshort.php?id=escidoc:1577894)
                - path to all programs added to the system environment variables

created by: L. Steiner (Orchid ID: 0000-0002-4958-0849)
created on: 17.05.2022
updated on: 10.05.2023
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
<<<<<<< HEAD
base_name = 'NMLB'                                                                              # prefix of base rinex observation files, e.g. station name
=======
base_name = 'NMLB'
>>>>>>> 05d3630 (Optimized for reading only new data textfiles and attach them to the binary pickle.)
base = '3387'                                                                                   # rinex file name prefix for base receiver
nav = '3387'                                                                                    # navigation file name prefix for broadcast ephemerides files
sp3 = 'COD'                                                                                     # navigation file name prefix for precise ephemerides files
ti_int = '900'                                                                                  # processing time interval (seconds)
resolution = '15min'                                                                            # processing resolution (minutes)
options_Leica = 'rtkpost_options_Ladina_Leica_statisch_multisystemfrequency_neumayer_900_15'    # name of RTKLIB configuration file (.conf) for high-end receiver
options_Emlid = 'rtkpost_options_Ladina_Emlid_statisch_multisystemfrequency_neumayer_900_15'    # name of RTKLIB configuration file (.conf) for low-cost receiver
ending = ''                                                                                     # file name suffix if needed: e.g., a variant of the processing '_eleambmask15', '_noglonass'
<<<<<<< HEAD
acc_y_lim = (-100, 2000)                                                                        # y-axis limit for accumulation plots
delta_acc_y_lim = (-200, 1000)                                                                  # y-axis limit for delta accumulation plots
swe_y_lim = (-100, 700)                                                                         # y-axis limit for water equivalent plots
delta_swe_y_lim = (-100, 500)                                                                   # y-axis limit for delta water equivalent plots
xlim_dates = dt.date(2021, 11, 26), dt.date(2023, 4, 1)                                         # time series date limits to plot on x-axis
cal_date = '2022-07-24'                                                                         # calibration date for snow density estimation
yy = '21'                                                                                       # initial year of observations
=======
acc_y_lim = (-200, 1600)                                                                        # y-axis limit for accumulation plots
delta_acc_y_lim = (-400, 1000)                                                                  # y-axis limit for delta accumulation plots
swe_y_lim = (-100, 700)                                                                         # y-axis limit for water equivalent plots
delta_swe_y_lim = (-200, 600)                                                                   # y-axis limit for delta water equivalent plots
xlim_dates = dt.date(2021, 11, 26), dt.date(2023, 1, 17)      # time series date limits to plot on x-axis
offset_le = 28                                                                                   # offset between leica and emlid rover antennas in mm w.e
yy = '21'                                                                                        # initial year of observations
>>>>>>> 05d3630 (Optimized for reading only new data textfiles and attach them to the binary pickle.)
save_plots = True                                                                               # show (False) or save (True) plots
total_backup = False                                                                            # copy (True) all new data to server for backup, else (False) do not copy
solplot_backup = True                                                                           # copy (True) all new solution files and plots to server for backup, else (False) do not copy


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

<<<<<<< HEAD
# # for proceeding manually without preprocessing: calculate start/end mjd using a given start/end date
=======
# # for proceedina manually without preprocessing: calculate start/end mjd using a given start/end date
>>>>>>> 05d3630 (Optimized for reading only new data textfiles and attach them to the binary pickle.)
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
<<<<<<< HEAD
fil_df_emlid, u_emlid, u_clean_emlid, swe_gnss_emlid, std_gnss_emlid, swe_gnss_daily_emlid, std_gnss_daily_emlid = f.filter_rtklib_solutions(
    dest_path, 'NMER', resolution, df_enu=df_enu_emlid, ambiguity=1, threshold=3, window='D', ending=ending)

fil_df_leica, u_leica, u_clean_leica, swe_gnss_leica, std_gnss_leica, swe_gnss_daily_leica, std_gnss_daily_leica = f.filter_rtklib_solutions(
    dest_path, 'NMLR', resolution, df_enu=df_enu_leica, ambiguity=1, threshold=3, window='D', ending=ending)
=======
# filter and clean ENU solution data (outlier filtering, median filtering, adjustments for observation mast heightening) and store results in pickle and .csv
fil_df_emlid, fil_emlid, fil_clean_emlid, m_emlid, s_emlid, jump_emlid, swe_gnss_emlid, swe_gnss_daily_emlid, std_gnss_daily_emlid = f.filter_rtklib_solutions(
    dest_path, 'NMER', resolution, df_enu=df_enu_emlid, ambiguity=1, ti_set_swe2zero=12, threshold=3, window='D',
    resample=False, resample_resolution='30min', ending=ending)

fil_df_leica, fil_leica, fil_clean_leica, m_leica, s_leica, jump_leica, swe_gnss_leica, swe_gnss_daily_leica, std_gnss_daily_leica = f.filter_rtklib_solutions(
    dest_path, 'NMLR', resolution, df_enu=df_enu_leica, ambiguity=1, ti_set_swe2zero=12, threshold=3, window='D',
    resample=False, resample_resolution='30min', ending=ending)
>>>>>>> 05d3630 (Optimized for reading only new data textfiles and attach them to the binary pickle.)

# correct offset leica to emlid
swe_gnss_emlid = swe_gnss_emlid - offset_le
swe_gnss_daily_emlid = swe_gnss_daily_emlid - offset_le


""" 4. Read reference sensors data """
manual, ipol, buoy, poles, laser, laser_filtered = f.read_reference_data(
    dest_path, laser_path, yy, url=buoy_url, read_manual=True, read_buoy=True, read_poles=True, read_laser=True, laser_pickle='nm_laser')


''' 5. Convert swe to snow accumulation and add to df '''
gnss_leica = f.convert_swe2sh_gnss(swe_gnss_leica, ipol_density=ipol)
gnss_emlid = f.convert_swe2sh_gnss(swe_gnss_emlid, ipol_density=ipol)


# resample all sensors sh and swe data to daily & 15min data
leica_daily, emlid_daily, buoy_daily, poles_daily, laser_daily = f.resample_allobs(gnss_leica, gnss_emlid, buoy, poles, laser_filtered, interval='D')


<<<<<<< HEAD
""" 6. Calculate SWE differences, linear regressions & RMSE between GNSS refractometr and reference data """
=======
""" 6. Calculate differences, linear regressions, RMSE & MRB between GNSS and reference data """
# TODO: calculate correct values (with correct input data)
>>>>>>> 05d3630 (Optimized for reading only new data textfiles and attach them to the binary pickle.)
# calculate differences between reference data and GNSS (Leica/Emlid)
diffs_sh_daily, diffs_swe_daily = f.calculate_differences2gnss(emlid_daily, leica_daily, manual, laser_daily, buoy_daily, poles_daily)
diffs_sh_15min, diffs_swe_15min, laser_15min = f.calculate_differences2gnss_15min(gnss_emlid, gnss_leica, laser_filtered)

# calculate SWE cross correation manual/laser vs. GNSS (daily & 15min)
f.calculate_crosscorr(leica_daily, emlid_daily, manual, gnss_leica, gnss_emlid, laser_15min, None, None, 'SWE')

# fit linear regression curve manual/laser vs. GNSS (daily & 15min)
predict_daily, predict_emlid_daily, predict_15min, predict_15min_emlid = f.calculate_linearfit(leica_daily, emlid_daily, manual, gnss_leica, gnss_emlid, laser_15min)

# calculate RMSE and number of samples
f.calculate_rmse(diffs_swe_daily, diffs_swe_15min, manual, laser_filtered, gnssir_acc=None, gnssir_acc_daily=None, res='SWE')


<<<<<<< HEAD
''' 7. Plot GNSS Refractometry results (SWE, ΔSWE, scatter) '''
=======
''' 7. Plot results (SWE, ΔSWE, scatter) '''
>>>>>>> 05d3630 (Optimized for reading only new data textfiles and attach them to the binary pickle.)
os.makedirs(dest_path + '30_plots/', exist_ok=True)

# plot SWE (Leica, Emlid, manual, laser, buoy, poles)
f.plot_all_SWE(dest_path, swe_gnss_daily_leica.dropna(), swe_gnss_daily_emlid.dropna(), manual, laser_15min, buoy_daily, poles_daily,
               save=save_plots, suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], std_leica=std_gnss_daily_leica.dropna(), std_emlid=std_gnss_daily_emlid.dropna(), y_lim=swe_y_lim, x_lim=xlim_dates)

# plot SWE (Leica, Emlid, manual, laser, buoy, poles)
f.plot_all_SWE(dest_path, swe_gnss_daily_leica.dropna(), swe_gnss_daily_emlid.dropna(), manual, laser_15min, buoy_daily, poles_daily,
               save=save_plots, suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser', 'Buoy', '_', '_', '_', '_', 'Poles'], std_leica=std_gnss_daily_leica.dropna(), std_emlid=std_gnss_daily_emlid.dropna(), y_lim=(-100, 800), x_lim=xlim_dates)

# plot SWE differences (Emlid, manual, laser, compared to Leica)
f.plot_all_diffSWE(dest_path, diffs_swe_daily, manual, laser_15min, None, None,
                   save=save_plots, suffix='_nobp', leg=['Low-cost GNSS', 'Manual', 'Laser'], y_lim=delta_swe_y_lim, x_lim=xlim_dates)

# plot SWE differences (Emlid, manual, laser, buoy, poles compared to Leica)
f.plot_all_diffSWE(dest_path, diffs_swe_daily, manual, laser_15min, buoy_daily, poles_daily,
<<<<<<< HEAD
                   save=save_plots, suffix='', leg=['Low-cost GNSS', 'Manual', 'Laser', 'Buoy', '_', '_', '_', '_', 'Poles'], y_lim=delta_swe_y_lim, x_lim=xlim_dates)
=======
                   save=save_plots, suffix='', leg=['Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=delta_swe_y_lim, x_lim=xlim_dates)
>>>>>>> 05d3630 (Optimized for reading only new data textfiles and attach them to the binary pickle.)

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

# Q: plot quality control
# plot number of satellites
<<<<<<< HEAD
f.plot_nrsat(dest_path, fil_df_leica.nr_sat, fil_df_emlid.nr_sat, save=save_plots, suffix='', y_lim=(0, 25), x_lim=xlim_dates)
=======
f.plot_nrsat(dest_path, fil_df_leica.nr_sat, fil_df_emlid.nr_sat, save=save_plots, suffix='', y_lim=(0, 35), x_lim=xlim_dates)
>>>>>>> 05d3630 (Optimized for reading only new data textfiles and attach them to the binary pickle.)

# plot ambiguity resolution state
f.plot_solquality(dest_path, df_enu_leica.amb_state, df_enu_emlid.amb_state, save=save_plots, suffix='', y_lim=(0, 100), x_lim=xlim_dates)

# plot PPP position solutions
# df_ppp_ref = f.plot_PPP_solution(dest_path, 'NMLB', save=False, suffix='', x_lim=xlim_dates)
# df_ppp_rover = f.plot_PPP_solution(dest_path, 'NMLR', save=False, suffix='', x_lim=xlim_dates)


''' 8. Read GNSS-IR results '''
<<<<<<< HEAD
# read and filter gnss-ir snow accumulation results (processed using 'gnssrefl' on Linux)
df_rh = f.read_gnssir(dest_path, ubuntu_path, base_name, yy, copy=False, pickle='nmlb')
gnssir_acc, gnssir_acc_daily, gnssir_acc_daily_std, gnssir_rh_clean = f.filter_gnssir(df_rh, freq='2nd', threshold=2)


""" 9. Calculate accumulation differences, linear regressions & RMSE between GNSS-IR and reference data """
# calculate Acc cross correation manual/laser vs. GNSS-IR (daily & 15min)
f.calculate_crosscorr(leica_daily, emlid_daily, manual, gnss_leica, gnss_emlid, laser_15min, gnssir_acc, gnssir_acc_daily, 'Acc')

# calculate RMSE and number of samples
f.calculate_rmse(diffs_sh_daily, diffs_sh_15min, manual, laser_filtered, gnssir_acc, gnssir_acc_daily, res='Acc')

# fit linear regression curve laser vs. GNSS-IR (15min)
predict_gnssir_15min = f.calculate_linearfit_acc(gnssir_acc.rolling('D').median()/10, laser_15min/10)


''' 10. Plot GNSS-IR results (Acc, ΔAcc, scatter) '''
# f.plot_gnssir(dest_path, gnssir_acc, gnssir_acc_daily, gnssir_acc_daily_std, laser_daily, leica_daily, emlid=None, manual=None, buoy=None, poles=None, leg=['GNSS-Reflectometry', '_', 'GNSS-Refractometry', 'Laser (SHM)'], save=save_plots, suffix='_leica', x_lim=xlim_dates, y_lim=acc_y_lim)
f.plot_gnssir(dest_path, gnssir_acc, gnssir_acc_daily, gnssir_acc_daily_std, laser_daily, leica_daily, emlid=emlid_daily, manual=None, buoy=None, poles=None, leg=['GNSS-Reflectometry', '_', 'High-end GNSS-Refractometry', 'Low-cost GNSS-Refractometry', 'Laser (SHM)'], save=save_plots, suffix='_leica_emlid', x_lim=xlim_dates, y_lim=acc_y_lim)

# plot scatter plot (GNSS-IR vs. laser, 15min)
f.plot_scatter(dest_path, gnssir_acc.rolling('D').median()/10, laser_15min.dsh/10, predict_gnssir_15min, x_label='Laser', lim=(-5, 140), save=save_plots)

# plot all gnssir and laser only
f.plot_all_Acc_gnssir(dest_path, None, None, None, laser_15min/10, None, None, gnssir_acc/10, gnssir_acc_daily/10,
                      save=True, suffix='_gnssir', leg=['_', 'Laser', 'GNSS-Reflectometry'], y_lim=(-10, 200), x_lim=xlim_dates)

# plot all Accumulation data without refractometry (laser, buoy, poles)
f.plot_all_Acc_gnssir(dest_path, None, None, manual/10, laser_15min/10, buoy/10, poles/10, None, None,
                      save=True, suffix='_all_noRR', leg=['Manual', '_', 'Laser', 'Buoy', '_', '_', '_', '_', 'Poles'], y_lim=(-10, 200), x_lim=xlim_dates)


# plot Difference in Accumulation (compared to Leica)
f.plot_all_diffAcc_gnssir(dest_path, manual/10, laser_daily/10, buoy_daily/10, poles_daily/10, gnssir_acc_daily/10, save=save_plots,
                          suffix='_gnssir', leg=['Laser', 'Manual', 'Buoy', '_', '_', '_', '_', 'Poles'], y_lim=(-40, 80), x_lim=xlim_dates)


''' 11. Calculate snow density from GNSS-RR: Combine GNSS-IR & GNSS refractometry '''
density_leica = f.convert_swesh2density(gnss_leica.dswe.dropna(), gnssir_acc.dropna(), cal_date, cal_val=manual.Density_aboveAnt[cal_date])
density_emlid = f.convert_swesh2density(gnss_emlid.dswe.dropna(), gnssir_acc.dropna(), cal_date, cal_val=manual.Density_aboveAnt[cal_date])


""" 12. Calculate density differences, linear regressions & RMSE between GNSS-RR and reference data """
# fit linear regression curve density manual vs. GNSS-RR (monthly)
predict_density, predict_density_emlid = f.calculate_linearfit_density(density_leica.resample('D').median(), density_emlid.resample('D').median(), manual)

# calculate density cross correation manual vs. GNSS-RR (monthly)
f.calculate_crosscorr_density(density_leica.resample('D').median(), density_emlid.resample('D').median(), manual.Density_aboveAnt)

# calculate density RMSE and number of samples
f.calculate_rmse_density(density_leica.resample('D').median(), density_emlid.resample('D').median(), manual.Density_aboveAnt)


''' 13. Plot GNSS-RR results (Density, ΔDensity, scatter) '''
# plot SWE and GNSS-IR accumulation with two-y-axes
f.plot_all_SWE_Acc(dest_path, swe_gnss_daily_leica.dropna(), swe_gnss_daily_emlid.dropna(), gnssir_acc / 10,
                   gnssir_acc_daily / 10, save=save_plots, suffix='_SWE_Acc_gnssir', leg=['High-end GNSS', 'Low-cost GNSS', 'GNSS-Reflectometry'],
                   std_leica=std_gnss_daily_leica.dropna(), std_emlid=std_gnss_daily_emlid.dropna(), y_lim=(-200, 1800), x_lim=xlim_dates)

# plot median filtered density time series (window=1week)
f.plot_density(dest_path, density_leica, density_emlid, laser=None, manual=manual, leg=['High-end GNSS-RR', 'Low-cost GNSS-RR', 'Manual'], save=save_plots, suffix='_leica_emlid', x_lim=xlim_dates)

# plot difference to manual density observation
f.plot_diff_density(dest_path, manual.Density_aboveAnt - density_leica.resample('D').median(), manual.Density_aboveAnt - density_emlid.resample('D').median(), laser=None, manual=manual, leg=['High-end GNSS-RR', 'Low-cost GNSS-RR'], save=save_plots, suffix='_leica_emlid', x_lim=xlim_dates)

# plot scatter plot (GNSS-RR vs. manual, monthly)
f.plot_scatter_density(dest_path, density_leica.resample('D').median(), density_emlid.resample('D').median(), manual.Density_aboveAnt, predict_density, predict_density_emlid, x_label='Manual', lim=(300,600), save=save_plots)


''' 13. Back up data '''
if solplot_backup is True:
    # copy solution and plot directories back to server
=======
# best results: ele=5-30, f=2, azi=30-160 & 210-310

# read and filter gnss-ir snow accumulation results
df_rh, gnssir_acc, gnssir_acc_sel = f.read_gnssir(dest_path, ubuntu_path, base_name, yy, freq='2nd', excl_azi=True, copy=False, pickle='nmlb')

# plot gnss-ir snow accumulation results
gnssir_acc_median, gnssir_acc_std = f.plot_gnssir(dest_path, gnssir_acc_sel, laser_daily, leica_daily, emlid=None, manual=None, buoy=None, poles=None, leg=['GNSS-Reflectometry', '_', 'GNSS-Refractometry', 'Laser (SHM)'], save=save_plots, suffix='_leica', x_lim=xlim_dates)
f.plot_gnssir(dest_path, gnssir_acc_sel, laser_daily, leica_daily, emlid=emlid_daily, manual=None, buoy=None, poles=None, leg=['GNSS-Reflectometry', '_', 'High-end GNSS-Refractometry', 'Low-cost GNSS-Refractometry', 'Laser (SHM)'], save=save_plots, suffix='_emlid', x_lim=xlim_dates)


''' 9. Calculate snow density from GNSS-RR: Combine GNSS-IR & GNSS refractometry '''
density_leica, density_leica_cleaned = f.convert_swesh2density((leica_daily.dswe + 45).dropna(), (gnssir_acc_sel + 110).dropna())
density_emlid, density_emlid_cleaned = f.convert_swesh2density((emlid_daily.dswe + 45).dropna(), (gnssir_acc_sel + 110).dropna())

# calibrate with ref manual density above antenna where 1m is reached ['2022-09-22']
cal_leica_1m = manual.Density_aboveAnt['2022-09-22'] - density_leica_cleaned['2022-09-22']
cal_emlid_1m = manual.Density_aboveAnt['2022-09-22'] - density_emlid_cleaned['2022-09-22']

# plot density time series
f.plot_density(dest_path, density_leica_cleaned + cal_leica_1m, density_emlid=None, laser=None, manual=manual, leg=['High-end GNSS-RR', 'Manual'], save=save_plots, suffix='_leica', x_lim=xlim_dates)
f.plot_density(dest_path, density_leica_cleaned, density_emlid_cleaned, laser=None, manual=manual, leg=['High-end GNSS-RR', 'Low-cost GNSS-RR', 'Manual'], save=save_plots, suffix='_leica_emlid', x_lim=xlim_dates)
f.plot_density(dest_path, density_leica=None, density_emlid=density_emlid_cleaned + cal_emlid_1m, laser=None, manual=manual, leg=['_', 'Low-cost GNSS-RR', 'Manual'], save=save_plots, suffix='_emlid', x_lim=xlim_dates)

# plot difference to manual density observation
f.plot_diff_density(dest_path, manual.Density_aboveAnt - (density_leica_cleaned + cal_leica_1m), manual.Density_aboveAnt - (density_emlid_cleaned + cal_emlid_1m), laser=None, manual=manual, leg=['_', 'Low-cost GNSS-RR', 'Manual'], save=save_plots, suffix='_emlid', x_lim=xlim_dates)


''' 10. Back up data '''
if solplot_backup is True:
    # copy solutions and plots directories back to server
>>>>>>> 05d3630 (Optimized for reading only new data textfiles and attach them to the binary pickle.)
    f.copy_solplotsdirs(dest_path, scr_path + '../Processing/Run_RTKLib/data_neumayer/')

if total_backup is True:
    # copy entire processing directory back to server
    f.copy4backup(dest_path + '../', scr_path + '../Processing/Run_RTKLib/')
<<<<<<< HEAD


''' New stuff '''
# # STDs (AGM 2023)
# laser_15min.dsh_std.mean()              # laser
# std_gnss_daily_leica.dropna().mean()    # leica
# std_gnss_daily_emlid.dropna().mean()    # emlid
# gnssir_acc.resample('D').std().median() # GNSS-IR
# rms
# np.sqrt(np.sum((f-g)**2)/n)
=======
>>>>>>> 05d3630 (Optimized for reading only new data textfiles and attach them to the binary pickle.)







''' New stuff '''
# TODO: test ppp diff - works!
# ppp_diff = ((df_ppp_rover.dh-df_ppp_ref.dh) * 1000)
# ppp_diff_sel = ppp_diff[(ppp_diff.index > '2021-12-01')]
# ppp_diff_sel = (ppp_diff_sel - ppp_diff_sel[0]).rolling('D').median()
#
# # Q: adjust for snow mast heightening (approx. 3m elevated several times a year)
# print('\ndata is corrected for snow mast heightening events (remove sudden jumps > 1m)')
# jump = ppp_diff_sel['2022-02-09'].median()  # detect jumps (> 1000mm) in the dataset
#
# print('\njump of height %s is detected!' % jump)
# adj = ppp_diff_sel[(ppp_diff_sel.index >= '2022-02-09')] - jump  # correct all observations after jump [0]
# ppp_diff_sel = pd.concat([ppp_diff_sel[~(ppp_diff_sel.index >= '2022-02-09')],
#                adj])  # concatenate all original obs before jump with adjusted values after jump
#
# swe_gnss_ppp = ppp_diff_sel - ppp_diff_sel[0]
# swe_gnss_ppp = swe_gnss_ppp[(swe_gnss_ppp > -1000) & (swe_gnss_ppp < 1000)]
# swe_gnss_ppp_cleaned = swe_gnss_ppp[(swe_gnss_ppp.diff() > -50) & (swe_gnss_ppp.diff() < 50) ]
# swe_gnss_ppp_cleaned.plot();plt.grid(); plt.show()

# # STDs (AGM 2023)
# laser_15min.dsh_std.mean()              # laser
# std_gnss_daily_leica.dropna().mean()    # leica
# std_gnss_daily_emlid.dropna().mean()    # emlid
# gnssir_acc.resample('D').std().median() # GNSS-IR
# rms
# np.sqrt(np.sum((f-g)**2)/n)

# TODO: add copy reflectometry solution files from ubuntu localhost
# Q: copy reflectometry solution files (*.txt) from the local Ubuntu server if not already existing
ubuntu_path = '//wsl.localhost/Ubuntu/home/sladina/test/gnssrefl/data/'
print(colored("\ncopy new reflectometry solution files", 'blue'))
print(ubuntu_path)
# get list of yearly directories newer than first year
for f in glob.glob(ubuntu_path + '2*'):
    year = int(os.path.basename(f))
    print(year)
    # if year >= int('20' + yy):
    #     # copy missing laser observation files
    #     for f in glob.glob(laser_path + year + '/*.[ls]??'):
    #         file = os.path.basename(f)
    #         # skip files of 2021 before 26th nov (no gps data before installation)
    #         if int(file[2:8]) > 211125:
    #             if not os.path.exists(loc_laser_dir + file):
    #                 shutil.copy2(f, loc_laser_dir)
    #                 print("file copied from %s to %s" % (f, loc_laser_dir))
    #             else:
    #                 # print(colored("\nfile in destination already exists: %s, \ncopy aborted!!!" % dest_path, 'yellow'))
    #                 pass
    #         else:
    #             pass
    # else:
    #     pass
print(colored("\nnew reflectometry solution files copied", 'blue'))

# test
if jump2.iloc[0] is not None:
    print(jump2.iloc[0], jump2.index.format()[0])