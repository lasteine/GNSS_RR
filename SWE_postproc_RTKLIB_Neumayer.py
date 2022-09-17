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

created: L. Steiner (Orchid ID: 0000-0002-4958-0849)
date:    8.8.2022
"""

# IMPORT modules
import os
import functions as f

# CHOOSE: DEFINE year, files (base, rover, navigation orbits, precise orbits), time interval
scr_path = '//smb.isibhv.dmawi.de/projects/p_gnss/Data/'  # data source path at AWI server (data copied from Antarctica via O2A)
dst_path = 'C:/Users/sladina.BGEO02P102/Documents/SD_Card/Postdoc/AWI/05_Analysis/Run_RTKLib/data_neumayer/'
rover = 'ReachM2_sladina-raw_'  # 'NMER' or '3393' (old Emlid: 'ReachM2_sladina-raw_')
rover_name = 'NMER_original'  # 'NMER' or 'NMER_original' or 'NMLR'
receiver = 'NMER'  # 'NMER' or 'NMLB' or 'NMLR'
base = '3387'
nav = '3387'
sp3 = 'COD'
ti_int = '900'
resolution = '15min'
options_Leica = 'rtkpost_options_Ladina_Leica_statisch_multisystemfrequency_neumayer'
options_Emlid = 'rtkpost_options_Ladina_Emlid_statisch_multisystemfrequency_neumayer_900_15'
ending = ''  # e.g. a variant of the processing '_eleambmask15', '_noglonass'
yy = str(22)
start_doy = 0
end_doy = 5


""" 0. Preprocess data """
# copy & uncompress new rinex files (NMLB + all orbits, NMLR, NMER) to processing folder 'data_neumayer/' (via a temporary folder for all preprocessing steps)
f.copy_rinex_files(scr_path + 'id8282_refractolow/', dst_path + 'temp_NMER/', receiver='NMER', copy=True,
                            parent=True, hatanaka=True, move=True, delete_temp=True)  # for emlid rover: NMER
f.copy_rinex_files(scr_path + 'id8281_refracto/', dst_path + 'temp_NMLR/', receiver='NMLR', copy=True,
                            parent=True, hatanaka=True, move=True, delete_temp=True)  # for leica rover: NMLR
f.copy_rinex_files(scr_path + 'id8283_reflecto/', dst_path + 'temp_NMLB/', receiver='NMLB', copy=True,
                            parent=True, hatanaka=True, move=True, delete_temp=True)  # for leica base: NMLB


""" 1. run RTKLib automatically (instead of RTKPost Gui manually) """
# process data using RTKLIB post processing command line tool 'rnx2rtkp' for a specific year and a range of day of years (doys)
f.automate_rtklib_pp(dst_path, 'NMER', yy, ti_int, base, nav, sp3, resolution, ending, start_doy, end_doy,
                              'NMER', options_Emlid)
f.automate_rtklib_pp(dst_path, '3393', yy, ti_int, base, nav, sp3, resolution, ending, start_doy, end_doy,
                              'NMLR', options_Leica)


""" 2. Get RTKLib ENU solution files """
# read all RTKLib ENU solution files (daily) and store them in one dataframe for whole season
df_enu_emlid = f.get_rtklib_solutions(dst_path, 'NMER', resolution, ending, header_length=26)
df_enu_leica = f.get_rtklib_solutions(dst_path, 'NMLR', resolution, ending, header_length=27)


''' 3. Filter and clean ENU solution data '''
# filter and clean ENU solution data (outlier filtering, median filtering, adjustments for observation mast heightening) and store results in pickle and .csv
df_enu_emlid, fil_df_emlid, fil_emlid, fil_clean_emlid, m_emlid, s_emlid, jump_emlid, swe_gnss_emlid, swe_gnss_daily_emlid, std_gnss_daily_emlid = f.filter_rtklib_solutions(
    dst_path, df_enu_emlid, 'NMER', resolution, ambiguity=1, ti_set_swe2zero=12, threshold=3, window='D',
    resample=False, resample_resolution='30min', ending=ending)

df_enu_leica, fil_df_leica, fil_leica, fil_clean_leica, m_leica, s_leica, jump_leica, swe_gnss_leica, swe_gnss_daily_leica, std_gnss_daily_leica = f.filter_rtklib_solutions(
    dst_path, df_enu_leica, 'NMLR', resolution, ambiguity=1, ti_set_swe2zero=12, threshold=3, window='D',
    resample=False, resample_resolution='30min', ending=ending)


''' 4. Read reference sensors data '''
manual, ipol, buoy, poles, laser, laser_filtered = f.read_reference_data(
    dst_path, read_manual=True, read_buoy=True, read_poles=True, read_laser=True, laser_pickle='shm/nm_laser.pkl')


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
predict_daily, predict_emlid_daily, predict_15min, predict_15min_emlid = f.calculate_linearfit(leica_daily, manual, gnss_leica, gnss_emlid, laser_15min)

# calculate RMSE, MRB, and number of samples
f.calculate_rmse_mrb(diffs_swe_daily, diffs_swe_15min, manual, laser_15min)


''' 7. Plot results (SWE, ΔSWE, scatter) '''
os.makedirs(dst_path + 'plots/', exist_ok=True)

# plot SWE (Leica, Emlid, manual, laser, buoy, poles)
f.plot_all_SWE(dst_path, leica_daily, emlid_daily, manual, laser_15min, buoy_daily, poles_daily,
                        save=False, suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'])

# plot SWE differences (Emlid, manual, laser, buoy, poles compared to Leica)
f.plot_all_diffSWE(dst_path, diffs_swe_daily, manual, laser_15min, buoy_daily, poles_daily,
                            save=False, suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'])

# plot boxplot of differences (Emlid, manual, laser compared to Leica)
f.plot_swediff_boxplot(dst_path, diffs_swe_daily, save=False)

# plot scatter plot (GNSS vs. manual/laser, daily/15min)
f.plot_scatter(dst_path, leica_daily.dswe, emlid_daily.dswe, manual.SWE_aboveAnt,
                        x_label='Manual', save=[False, True])

f.plot_scatter(dst_path, gnss_leica.dswe, gnss_emlid.dswe, laser_15min.dswe,
                        x_label='Laser', save=[False, True])


# plot all Accumulation data (Leica, Emlid, laser, buoy, poles)
f.plot_all_Acc(dst_path, leica_daily, emlid_daily, manual, laser_15min, buoy_daily, poles_daily,
                        save=False, suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'])


# plot Difference in Accumulation (compared to Leica)
f.plot_all_diffAcc(dst_path, diffs_swe_daily, manual, laser_15min, buoy_daily, poles_daily,
                            save=False, suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'])


# plot SWE, Density, Accumulation (from manual obs at Spuso)
f.plot_SWE_density_acc(dst_path, gnss_leica, gnss_emlid, manual, laser_15min, save=False)


# plot PPP position solutions
df_ppp = f.plot_PPP_solution(dst_path, save=False)


# TODO: define classes (preprocess, process, plot) and adapt functions
