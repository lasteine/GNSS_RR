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
import subprocess
import os
import datetime as dt
import glob
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import gnsscal
import shutil
import preprocess


# CHOOSE: DEFINE year, files (base, rover, navigation orbits, precise orbits), time interval
yy = str(21)
data_path = 'data_neumayer'
scr_path = '//smb.isibhv.dmawi.de/projects/p_gnss/Data/'    # data source path at AWI server (data copied from Antarctica via O2A)
dst_path = 'C:/Users/sladina.BGEO02P102/Documents/Paper_SWE_RTK/Run_RTKLib/data_neumayer/'
rover = 'ReachM2_sladina-raw_'  # 'NMER' or '3393' (old Emlid: 'ReachM2_sladina-raw_')
rover_name = 'NMER_original'    # 'NMER' or 'NMER_original' or 'NMLR'
receiver = 'NMER'               # 'NMER' or 'NMLB' or 'NMLR'
base = '3387'
nav = '3387'
sp3 = 'COD'
ti_int = '900'
resolution = '15min'
options_Leica = 'rtkpost_options_Ladina_Leica_statisch_multisystemfrequency_neumayer'
options_Emlid = 'rtkpost_options_Ladina_Emlid_statisch_multisystemfrequency_neumayer_900_15'
ending = ''             # e.g. a variant of the processing '_eleambmask15', '_noglonass'
start_doy = 0
end_doy = 366


""" 0. Preprocess data """
# Q: Copy & uncompress data to processing folder
# copy files (NMLB + all orbits, NMLR, NMER) to data_neumayer/ (via a temporary folder for all intermediate steps)
preprocess.copy_rinex_files(scr_path + 'id8282_refractolow/', dst_path + 'temp_NMER/', yy='22', receiver='NMER', copy=True, move=True, delete_temp=True) # for emlid rover: NMER
preprocess.copy_rinex_files(scr_path + 'id8281_refracto/', dst_path + 'temp_NMLR/', yy='22', receiver='NMLR', copy=True, move=True, delete_temp=True)    # for leica rover: NMLR
preprocess.copy_rinex_files(scr_path + 'id8283_reflecto/', dst_path + 'temp_NMLB/', yy='22', receiver='NMLB', copy=True, move=True, delete_temp=True)    # for leica base: NMLB

# Q: split & merge day-overlapping Emlid rinex files to daily rinex files (for Emlid files only!)
# preprocess.dayoverlapping2daily_rinexfiles(dst_path + 'temp_NMER/', 'ReachM2_sladina-raw_', 'NMER', move=True, delete_temp=True)


# TODO: write functions for processing and plotting
""" 1. run RTKLib automatically (instead of RTKPost Gui manually) """
# Q: run rtklib for all rover files in directory
for file in glob.iglob(data_path + '/' + rover + '*.' + yy + 'O', recursive=True):
    ''' get doy from rover file names with name structure:
        Leica Rover: '33933650.21o' [rover + doy + '0.' + yy + 'o']
        Emlid Rover (pre-processed): 'NMER3650.21o' [rover + doy + '0.' + yy + 'o']
        Emlid Rover (original): 'ReachM2_sladina-raw_202112041058.21O' [rover + datetime + '.' + yy + 'O']
        '''
    rover_file = os.path.basename(file)
    if rover_name == 'NMER_original':  # Emlid original format (output from receiver, non-daily files)
        doy = dt.datetime.strptime(rover_file.split('.')[0].split('_')[2], "%Y%m%d%H%M").strftime('%j')
        options = options_Emlid
    if rover_name == 'NMER':       # Emlid pre-processed format (daily files)
        doy = rover_file.split('.')[0][4:7]
        options = options_Emlid
    if rover_name == 'NMLR':
        doy = rover_file.split('.')[0][4:7]
        options = options_Leica
    print('\nRover file: ' + rover_file, '\ndoy: ', doy)

    if int(doy) >= start_doy & int(doy) <= end_doy:

        # convert doy to gpsweek and day of week
        (gpsweek, dow) = gnsscal.yrdoy2gpswd(int('20' + yy), doy)

        # Q: define input and output filenames (for some reason it's not working when input files are stored in subfolders!)
        base_file = base + doy + '0.' + yy + 'O'
        broadcast_orbit_gps = nav + doy + '0.' + yy + 'n'
        broadcast_orbit_glonass = nav + doy + '0.' + yy + 'g'
        broadcast_orbit_galileo = nav + doy + '0.' + yy + 'l'
        precise_orbit = sp3 + str(gpsweek) + str(dow) + '.EPH_M'
        output_file = 'sol/' + rover_name + '/20' + yy + '_' + rover_name + doy + '.pos'

        # Q: change directory & run RTKLib post processing command
        # example command to run RTKLib:
        # 'rnx2rtkp -k rtkpost_options.conf -ti 900 -o sol/NMLR/15min/NMLRdoy.pos NMLR0040.17O NMLB0040.17O NMLB0040.17n NMLB0040.17g NMLB0040.17e COD17004.eph'
        os.makedirs(data_path + '/sol/', exist_ok=True)
        process = subprocess.Popen('cd ' + data_path + ' && rnx2rtkp '
                                   '-k ' + options + '.conf '
                                   '-ti ' + ti_int + ' '
                                   '-o ' + output_file + ' '
                                   + rover_file + ' ' + base_file + ' ' + broadcast_orbit_gps + ' ' + broadcast_orbit_glonass + ' ' + broadcast_orbit_galileo + ' ' + precise_orbit,
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)

        stdout, stderr = process.communicate()
        # print(stdout) # print processing output
        print(stderr)  # print processing errors

        # remove .stat files
        if os.path.exists(data_path + '/' + output_file + '.stat'):
            os.remove(data_path + '/' + output_file + '.stat')

print('\n\nfinished with all files :-)')


""" 2. Get rtklib ENU solution files"""
# create empty dataframe for all .ENU solution files
df_enu = pd.DataFrame()

# Q read all .ENU files in folder, parse date and time columns to datetimeindex and add them to the dataframe
for file in glob.iglob(data_path + '/sol/' + rover + '/' + resolution + '/*' + ending + '.pos', recursive=True):
    print(file)
    enu = pd.read_csv(file, header=24, delimiter=' ', skipinitialspace=True, index_col=['date_time'], na_values=["NaN"],
                      usecols=[0, 1, 4, 5, 6, 9], names=['date', 'time', 'U', 'amb_state', 'nr_sat', 'std_u'],
                      parse_dates=[['date', 'time']])
    df_enu = pd.concat([df_enu, enu], axis=0)

# store dataframe as binary pickle format
# df_enu.to_pickle(data_path + '/sol/' + rover_name + '_' + resolution + ending + '.pkl')

# hier wäre gut: globals()[f"df_enu{ending}"] = df_enu

# TODO: check where to implement generic variable names
# # import RTKLib solution files from different solution variants
# globals()[f"df_enu{ending}"] = df_enu
# globals()[f"fil_df{ending}"] = pd.DataFrame(df_enu[(df_enu.amb_state == 1)])
# fil_df = globals()[f"fil_df{ending}"]
# globals()[f"fil{ending}"] = (fil_df.U - fil_df.U[1]) * 1000
# fil = globals()[f"fil{ending}"]
# # remove outliers
# upper_limit = fil.median() + 3 * fil.std()
# lower_limit = fil.median() - 3 * fil.std()
# globals()[f"fil_clean{ending}"] = fil[(fil > lower_limit) & (fil < upper_limit)]
#
# # filter data
# globals()[f"m{ending}"] = globals()[f"fil_clean{ending}"].rolling('D').median()       # .resample('15min').median()
# globals()[f"s{ending}"] = globals()[f"fil_clean{ending}"].rolling('D').std()
#
# # adjust for snow mast heightening (approx. 3m elevated)
# m_15min = globals()[f"m{ending}"]
# jump = m_15min[(m_15min.diff() < -1000)]    # detect jumps (>2m) in the dataset
# adj = m_15min[(m_15min.index > jump.index.format()[0])] - jump[0]     # correct jump [1]
# globals()[f"m_adj{ending}"] = m_15min[~(m_15min.index >= jump.index.format()[0])].append(adj)   # adjusted dataset
#
# globals()[f"swe{ending}"] = globals()[f"m_adj{ending}"]-globals()[f"m_adj{ending}"][0]
# globals()[f"swe{ending}"].index = globals()[f"swe{ending}"].index + pd.Timedelta(seconds=18)


''' 3. Filter and clean ENU solution data '''
# read all data from .pkl and combine, if necessary multiple parts
# df_enu = pd.read_pickle(data_path + '/sol/' + rover + '_' + resolution + ending + '.pkl')

# select only data where ambiguities are fixed (amb_state==1) and sort datetime index
fil_df = pd.DataFrame(df_enu[(df_enu.amb_state == 1)])
# if rover_name == 'NMLR':
#     # select data where ambiguities are fixed (amb_state==1)
#     fil_df = pd.DataFrame(df_enu[(df_enu.amb_state == 1)])  # for high-end data
# else:
#     # select data where ambiguities are float (amb_state==2) and have a low stdev (<2.5mm)
#     fil_df = pd.DataFrame(df_enu[(df_enu.amb_state == 2) & (df_enu.std_u < 0.0025)])    # for low-cost data

fil_df.index = pd.DatetimeIndex(fil_df.index)
fil_df = fil_df.sort_index()

# adapt up values to reference SWE values in mm (median of first hours)
fil = (fil_df.U - fil_df.U[:48].median()) * 1000

# remove outliers based on a 3*sigma threshold
upper_limit = fil.median() + 3 * fil.std()
lower_limit = fil.median() - 3 * fil.std()
fil_clean = fil[(fil > lower_limit) & (fil < upper_limit)]

# filter data with a rolling median and resample resolution to fit reference data (30min)
m_15min = fil_clean.rolling('D').median()       # .resample('15min').median()
s_15min = fil_clean.rolling('D').std()

# adjust for snow mast heightening (approx. 3m elevated)
jump = m_15min[(m_15min.diff() < -1000)]    # detect jumps (>2m) in the dataset
adj = m_15min[(m_15min.index > jump.index.format()[0])] - jump[0]     # correct jump [1]
m_15min_adj = m_15min[~(m_15min.index >= jump.index.format()[0])].append(adj)   # adjusted dataset
swe_gnss = m_15min_adj-m_15min_adj[0]
swe_gnss.index = swe_gnss.index + pd.Timedelta(seconds=18)

# resample data, calculate median and standard deviation (noise) per day to fit manual reference data
m = swe_gnss.resample('D').median()
s = swe_gnss.resample('D').std()


# store swe results to pickle
os.makedirs('sol/SWE_results/', exist_ok=True)
swe_gnss.to_pickle(data_path + '/sol/SWE_results/2021_22_swe_gnss_' + rover_name + '.pkl')
swe_gnss.to_csv(data_path + '/sol/SWE_results/2021_22_swe_gnss_' + rover_name + '.csv')

# read gnss swe results from pickle
swe_leica = pd.read_pickle(data_path + '/sol/SWE_results/2021_22_swe_gnss_NMLR.pkl')
swe_emlid = pd.read_pickle(data_path + '/sol/SWE_results/2021_22_swe_gnss_NMER.pkl')


''' 3. Read reference sensors .csv data '''
# Q: Accumulation (cm), Density (kg/m^3), SWE (mm w.e.)
manual = pd.read_csv('data_neumayer/03_Densitypits/Manual_Spuso.csv', header=1, skipinitialspace=True, delimiter=';', index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0], dayfirst=True, names=['Acc', 'Density', 'SWE', 'Density_aboveAnt', 'SWE_aboveAnt'])
manual2 = manual
manual2.index = manual2.index + pd.Timedelta(days=0.2)
ipol = manual.Density_aboveAnt.resample('min').interpolate(method='linear', limit_direction = 'backward')

# Q: read snow buoy data
buoy_all = pd.read_csv('data_neumayer/06_SHM/Snowbuoy/2017S54_300234011695900_proc.csv', header=0, skipinitialspace=True, delimiter=',', index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0],
                   names=['lat', 'lon', 'sh1', 'sh2', 'sh3', 'sh4', 'pressure', 'airtemp', 'bodytemp', 'gpstime'])

# select only data from season 21/22
buoy = buoy_all['2021-11-26':]

# Differences in accumulation (in mm)
for i in range(4):
    globals()[f"sh_buoy{i+1}"] = (buoy['sh' + str(i+1)] - buoy['sh' + str(i+1)][0]) * 1000
    # calculate accumulation gain
    print('Accumulation gain sh_buoy' + str(i+1) + ': ', round(globals()[f"sh_buoy{i+1}"].dropna()['2021-12-23'][1],1))


# Q: read Pegelfeld Spuso accumulation from poles
poles = pd.read_csv(data_path + '/03_Densitypits/Pegelfeld_Spuso_Akkumulation.csv', header=0, delimiter=';', index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0], dayfirst=True)


# Q. read snow depth observations (minute resolution)
# # create empty dataframe for all .log files
# df_shm = pd.DataFrame()
# # read all snow accumulation.log files in folder, parse date and time columns to datetimeindex and add them to the dataframe
# for file in glob.iglob(data_path + '/shm/nm*.log', recursive=True):
#     print(file)
#     # header: 'date', 'time', 'snow level (m)', 'signal(-)', 'temp (°C)', 'error (-)', 'checksum (-)'
#     shm = pd.read_csv(file, header=0, delimiter=r'[ >]', skipinitialspace=True, na_values=["NaN"], names=['date', 'time', 'none','h', 'signal', 'temp', 'error', 'check'], usecols=[0,1,3,5,6],
#                       encoding='latin1', parse_dates=[['date', 'time']], index_col=['date_time'], engine='python', dayfirst=True)
#     df_shm = pd.concat([df_shm, shm], axis=0)
#
# # store as .pkl
# df_shm.to_pickle(data_path + '/shm/nm_shm.pkl')
df_shm = pd.read_pickle(data_path + '/shm/nm_shm.pkl')
h = df_shm[(df_shm.error == 0)].h * 1000
fil_h = (h - h[0])  # adapt to reference SWE values in mm

# clean outliers
ul = fil_h.median() + 1 * fil_h.std()
ll = fil_h.median() - 1 * fil_h.std()
fil_h_clean = fil_h[(fil_h > ll) & (fil_h < ul)]

# resample snow accumulation data
h = fil_h_clean.resample('6H').median()
h_std = fil_h_clean.resample('H').std()
sh = fil_h_clean.rolling('D').median()
sh_std = fil_h_clean.rolling('D').std()

# calculate SWE from snow accumulation and mean density data (at 0.5m)
swe_laser_constant = (sh/1000)*408   # swe = h[m] * density[kg/m3]; mean_density(0.5m)=408 from Hecht_2022
swe_laser_constant_15min = swe_laser_constant.resample('15min').median()

# with interpolated density data from layers in depths above the buried antenna
swe_laser = (sh/1000) * ipol
swe_laser_15min = swe_laser.resample('15min').median()


# Q: difference gnss sh to shm sh (ab dem 23.dez);
# pegelfeld spuso: 59cm schneezutrag zw. 26.11 und 26.12
# shm: ca. 50cm schneezutrag
sh_gnss = swe_gnss * 1000 / 408     # convert gnss swe to snow accumulation with mean density (at 0.5m)
sh_diff = (sh.resample('D').median() - sh_gnss.resample('D').median()).median().round(0)    # 278mm

# calculate sh from GNSS SWE with a mean constant density value for h=0.5m (Hecht, 2022)
sh_leica_const = swe_leica * 1000 / 408
sh_emlid_const = swe_emlid * 1000 / 408

# calculate sh from GNSS SWE with interpolated density values (Spuso)
sh_leica = swe_leica * 1000 / ipol
sh_emlid = swe_emlid * 1000 / ipol

# resample sh and swe data (daily)
sh_leica_daily = sh_leica.resample('D').median()
swe_leica_daily = swe_leica.resample('D').median()
sh_emlid_daily = sh_emlid.resample('D').median()
swe_emlid_daily = swe_emlid.resample('D').median()
sh_manual_daily = manual2.Acc.astype('float64')*10
swe_manual_daily = manual2.SWE_aboveAnt.astype('float64')
sh_laser_daily = sh.resample('D').median()
swe_laser_daily = sh_laser_daily / 1000 * ipol
for i in range(4):
    globals()[f"sh_buoy{i+1}_daily"] = globals()[f"sh_buoy{i+1}"].resample('D').median()
    globals()[f"swe_buoy{i + 1}_daily"] = globals()[f"sh_buoy{i+1}_daily"]/1000*ipol
for i in range(15):
    globals()[f"sh_poles{i+1}_daily"] = poles[str(i+1)].resample('D').median()
    globals()[f"swe_poles{i + 1}_daily"] = globals()[f"sh_poles{i+1}_daily"]/100*ipol

""" 4. Calculate differences, linear regressions, RMSE & MRB between GNSS and reference data """
# Q: calculate differences between GNSS (Leica) and reference data
dsh_emlid_daily = (sh_emlid_daily - sh_leica_daily).dropna()
dswe_emlid_daily = (swe_emlid_daily - swe_leica_daily).dropna()
dsh_manual_daily = (sh_manual_daily - sh_leica_daily).dropna()
dswe_manual_daily = (dsh_manual_daily/1000*ipol).dropna()
dsh_laser_daily = (sh_laser_daily - sh_leica_daily).dropna()
dswe_laser_daily = (dsh_laser_daily/1000*ipol).dropna()
for i in range(4):
    globals()[f"dsh_buoy{i+1}_daily"] = (globals()[f"sh_buoy{i+1}_daily"] - sh_leica_daily).dropna()
    globals()[f"dswe_buoy{i + 1}_daily"] = (globals()[f"swe_buoy{i + 1}_daily"] - swe_leica_daily).dropna()
for i in range(15):
    globals()[f"dsh_poles{i+1}_daily"] = (globals()[f"sh_poles{i+1}_daily"] - sh_leica_daily).dropna()
    globals()[f"dswe_poles{i + 1}_daily"] = (globals()[f"swe_poles{i + 1}_daily"] - sh_leica_daily).dropna()

# concatenate all difference dataframes
diffs = pd.concat([dsh_emlid_daily, dswe_emlid_daily, dsh_manual_daily, dswe_manual_daily, dsh_laser_daily, dswe_laser_daily], axis=1)
diffs.columns = ['dsh_emlid', 'dswe_emlid', 'dsh_manual', 'dswe_manual', 'dsh_laser', 'dswe_laser']

# Q: cross correlation and linear fit (daily & 30min)
# merge ref and gnss data (daily)
all_daily = pd.concat([sh_leica_daily, sh_emlid_daily, swe_emlid_daily, sh_manual_daily, swe_manual_daily, sh_laser_daily, swe_laser_daily], axis=1)
all_daily_nonan = all_daily.dropna()
# merge scale and gnss data (30min)
all_15min = pd.concat([sh_leica, sh_emlid, swe_laser_15min], axis=1)
all_15min_nonan = all_15min.dropna()

# SWE cross correation manual vs. GNSS (daily)
corr_leica_daily = all_daily.swe_manual_daily.corr(all_daily.swe_leica_daily)
corr_emlid_daily = all_daily.swe_manual_daily.corr(all_daily.swe_emlid_daily)
print('\nPearsons correlation (manual vs. GNSS, daily), Leica: %.2f' % corr_leica_daily)
print('\nPearsons correlation (manual vs. GNSS, daily), Emlid: %.2f' % corr_emlid_daily)
# calculate cross correation laser vs. GNSS (15min)
corr_leica_15min = all_15min.swe_laser_15min.corr(all_15min.swe_leica)
corr_emlid_15min = all_15min.swe_laser_15min.corr(all_15min.swe_leica)
print('Pearsons correlation (laser vs. GNSS, 15min), Leica: %.2f' % corr_leica_15min)
print('Pearsons correlation (laser vs. GNSS, 15min), Emlid: %.2f' % corr_emlid_15min)


# fit linear regression curve manual vs. GNSS (daily)
fit_daily = np.polyfit(all_daily_nonan.swe_manual_daily, all_daily_nonan.swe_leica, 1)
predict_daily = np.poly1d(fit_daily)
print('\nLinear fit (manual vs. GNSS, daily): \nm = ', round(fit_daily[0], 2), '\nb = ', int(fit_daily[1]))
# fit linear regression curve laser vs. GNSS (15min), Leica
fit_15min = np.polyfit(all_15min_nonan.swe_laser_15min, all_15min_nonan.swe_leica, 1)
predict_15min = np.poly1d(fit_15min)
print('Linear fit (laser vs. GNSS, 15min), Leica: \nm = ', round(fit_15min[0], 2), '\nb = ', int(fit_15min[1]))
# fit linear regression curve laser vs. GNSS (15min), Emlid
fit_15min_emlid = np.polyfit(all_15min_nonan.swe_laser_15min, all_15min_nonan.swe_emlid, 1)
predict_15min_emlid = np.poly1d(fit_15min_emlid)
print('Linear fit (laser vs. GNSS, 15min), Emlid: \nm = ', round(fit_15min_emlid[0], 2), '\nb = ', int(fit_15min_emlid[1]))     # n=12, m=1.02, b=-8 mm w.e.


# RMSE
rmse_manual = np.sqrt((np.sum(dswe_manual_daily**2))/len(dswe_manual_daily))
print('\nRMSE (manual vs. GNSS, daily): %.1f' % rmse_manual)
rmse_laser = np.sqrt((np.sum(dswe_laser_daily**2))/len(dswe_laser_daily))
print('RMSE (scale vs. GNSS, 30min): %.1f' % rmse_laser)

# MRB
mrb_manual = (dswe_manual_daily/swe_manual_daily).mean() * 100
print('\nMRB (manual vs. GNSS, daily): %.1f' % mrb_manual)
mrb_laser = (dswe_laser_daily/swe_laser_daily).mean() * 100
print('MRB (laser vs. GNSS, 30min): %.1f' % mrb_laser)

# Number of samples
n_manual = len(dswe_laser_daily)
print('\nNumber of samples (manual vs. GNSS, daily): %.0f' % n_manual)
n_scale = len(dswe_laser_daily)
print('Number of samples (scale vs. GNSS, 30min): %.0f' % n_scale)


''' 5. Plot results (SWE, ΔSWE, scatter) '''
os.makedirs(data_path + '/plots/', exist_ok=True)

# Q: plot SWE
# plot SWE Leica, Emlid, laser, buoy, poles
plt.figure()
swe_leica.plot(linestyle='-', color='crimson', fontsize=12, figsize=(6, 5.5), ylim=(-100, 500)).grid()
swe_emlid.plot(color='salmon', linestyle='--')
swe_manual_daily.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
plt.errorbar(swe_manual_daily.index, swe_manual_daily, yerr=swe_manual_daily/10, color='darkblue', linestyle='',capsize=4, alpha=0.5)
swe_laser_15min.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
for i in range(4):
    (globals()[f"swe_buoy{i + 1}_daily"][(globals()[f"swe_buoy{i + 1}_daily"] < globals()[f"swe_buoy{i + 1}_daily"].median() + 2 * globals()[f"swe_buoy{i + 1}_daily"].std())]).plot(color='lightgrey', linestyle='-').grid()
for i in range(15):
    globals()[f"swe_poles{i + 1}_daily"].plot(linestyle=':', alpha=0.6, legend=False).grid()
plt.fill_between(swe_leica.index, swe_leica - swe_leica/10, swe_leica + swe_leica/10, color="crimson", alpha=0.2)
plt.fill_between(swe_emlid.index, swe_emlid - swe_emlid/10, swe_emlid + swe_emlid/10, color="salmon", alpha=0.2)
plt.xlabel(None)
plt.ylabel('SWE (mm w.e.)', fontsize=14)
plt.legend(['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='upper left')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
plt.show()
# plt.savefig(data_path + '/plots/SWE_all_poles_2021_22.png', bbox_inches='tight')
# plt.savefig(data_path + '/plots/SWE_all_poles_2021_22.pdf', bbox_inches='tight')


# Q. plot SWE difference (compared to Leica)
plt.figure()
dswe_emlid_daily.dropna().plot(color='salmon', linestyle='--', fontsize=12, figsize=(6, 5.5), ylim=(-100, 500)).grid()
dswe_manual_daily.dropna().plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
dswe_laser_daily.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
for i in range(4):
    (globals()[f"dswe_buoy{i + 1}_daily"][(globals()[f"dswe_buoy{i + 1}_daily"] < globals()[f"dswe_buoy{i + 1}_daily"].median() + 2 * globals()[f"dswe_buoy{i + 1}_daily"].std())]).plot(color='lightgrey', linestyle='-').grid()
for i in range(15):
    globals()[f"dswe_poles{i + 1}_daily"].plot(linestyle=':', alpha=0.6, legend=False).grid()
plt.xlabel(None)
plt.ylabel('$\Delta$SWE (mm w.e.)', fontsize=14)
plt.legend(['Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='upper left')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
plt.show()
# plt.savefig(data_path + '/plots/Delta_SWE_all_2021_22.png', bbox_inches='tight')
# plt.savefig(data_path + '/plots/Delta_SWE_all_2021_22.pdf', bbox_inches='tight')


# Q: plot scatter plot (GNSS vs. manual, daily)
plt.close()
plt.figure()
ax = all_daily.plot.scatter(x='manual', y='U', figsize=(5, 4.5))
plt.plot(range(10, 750), predict_daily(range(10, 750)), c='k', linestyle='--', alpha=0.7)    # linear regression
ax.set_ylabel('GNSS SWE (mm w.e.)', fontsize=12)
ax.set_ylim(0, 1000)
ax.set_xlim(0, 1000)
ax.set_xlabel('Manual SWE (mm w.e.)', fontsize=12)
plt.legend(['r(Leica)=%.2f \nr(Emlid)=%.2f' % corr_leica_daily % corr_emlid_daily], fontsize=12, loc='upper left')
plt.xticks(fontsize=12)
plt.yticks(fontsize=12)
plt.grid()
plt.show()
# plt.savefig(data_path + '/plots/scatter_SWE_WFJ_manual.png', bbox_inches='tight')
# plt.savefig(data_path + '/plots/scatter_SWE_WFJ_manual.pdf', bbox_inches='tight')


# Q: plot scatter plot (GNSS vs. scale, 30min)
plt.close()
plt.figure()
ax = all_15min.plot.scatter(x='laser', y='U', figsize=(5, 4.5))
plt.plot(range(10, 850), predict_15min(range(10, 850)), c='k', linestyle='--', alpha=0.7)    # linear regression
ax.set_ylabel('GNSS SWE (mm w.e.)', fontsize=12)
ax.set_ylim(0, 1000)
ax.set_xlim(0, 1000)
ax.set_xlabel('Snow scale SWE (mm w.e.)', fontsize=12)
plt.legend(['r=%.2f' % corr_leica_15min], fontsize=12, loc='upper left')
plt.xticks(fontsize=12)
plt.yticks(fontsize=12)
plt.grid()
plt.show()
# plt.savefig(data_path + '/plots/scatter_SWE_WFJ_scale_30min.png', bbox_inches='tight')
# plt.savefig(data_path + '/plots/scatter_SWE_WFJ_scale_30min.pdf', bbox_inches='tight')

# Q: plot boxplot of differences
dswe_manual_daily.describe()
dswe_laser_daily.describe()
dswe_emlid_daily.describe()
diffs[['Manual', 'Laser', 'Low-cost GNSS']].plot.box(ylim=(-100, 200), figsize=(3, 4.5), fontsize=12)
plt.grid()
plt.ylabel('ΔSWE (mm w.e.)', fontsize=12)
plt.show()
# plt.savefig('plots/box_SWE_WFJ_diff.png', bbox_inches='tight')
# plt.savefig('plots/box_SWE_WFJ_diff.pdf', bbox_inches='tight')

# Q: plot all Accumulation data (Leica, Emlid, laser, buoy, poles)
plt.close()
plt.figure()
sh_leica.dropna().plot(linestyle='-', color='crimson', fontsize=12, figsize=(6, 5.5), ylim=(-200, 1000)).grid()
sh_emlid.dropna().plot(color='salmon', linestyle='--')
(manual2.Acc.astype('float64')*10).plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
plt.errorbar((manual2.Acc.astype('float64')*10).index, (manual2.Acc.astype('float64')*10), yerr=(manual2.Acc.astype('float64')*10)/10, color='darkblue', linestyle='',capsize=4, alpha=0.5)
sh.plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
for i in range(15):
    poles[str(i+1)].dropna().plot(linestyle=':', alpha=0.6, legend=False).grid()
for i in range(4):
    globals()[f"sh_buoy{i+1}_daily"].plot(color='lightgrey', linestyle='-', legend=False).grid()
sh.plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
#plt.fill_between(sh_std.index, sh - sh_std, sh + sh_std, color="darkblue", alpha=0.2)
#plt.fill_between(sh_leica.index, sh_leica - sh_leica/10, sh_leica + sh_leica/10, color="crimson", alpha=0.2)
#plt.fill_between(sh_emlid.index, sh_emlid - sh_emlid/10, sh_emlid + sh_emlid/10, color="salmon", alpha=0.2)
plt.xlabel(None)
plt.ylabel('Snow accumulation (mm)', fontsize=14)
plt.legend(['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='upper left')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
plt.show()
#plt.savefig('data_neumayer/plots/Acc_all_2021_22.png', bbox_inches='tight')
#plt.savefig('data_neumayer/plots/Acc_all_2021_22.pdf', bbox_inches='tight')


# plot Difference in Accumulation (compared to Leica)
plt.figure()
(sh_emlid.resample('D').median()-sh_leica.resample('D').median()).dropna().plot(color='salmon', linestyle='--', fontsize=12, figsize=(6, 5.5), ylim=(-200, 1000)).grid()
((manual2.Acc.astype('float64')*10).resample('D').median()-sh_leica.resample('D').median()).dropna().plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
(sh.resample('D').median()-sh_leica.resample('D').median()).dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
for i in range(4):
    (globals()[f"dsh_buoy{i+1}_daily"][(globals()[f"dsh_buoy{i+1}_daily"] < globals()[f"dsh_buoy{i+1}_daily"].median() + 2 * globals()[f"dsh_buoy{i+1}_daily"].std())]).plot(color='lightgrey', linestyle='-').grid()
for i in range(15):
    (poles[str(i+1)].resample('D').median()-sh_leica.resample('D').median()).dropna().plot(linestyle=':', alpha=0.6, legend=False).grid()
plt.xlabel(None)
plt.ylabel('$\Delta$Snow accumulation (mm)', fontsize=14)
plt.legend(['Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='best')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
#plt.show()
plt.savefig('data_neumayer/plots/Delta_Acc_all_2021_22.png', bbox_inches='tight')
plt.savefig('data_neumayer/plots/Delta_Acc_all_2021_22.pdf', bbox_inches='tight')


# plot snow accumulation from all four sensors of the snow buoy
plt.close()
globals()[f"dsh_buoy1_daily"].plot(linestyle='-')
globals()[f"dsh_buoy2_daily"].plot(linestyle='--')
globals()[f"dsh_buoy3_daily"].plot(linestyle='-.')
globals()[f"dsh_buoy4_daily"].plot(linestyle=':', xlim=('2021-11-26', '2022-05-01'), ylim=(-10,60), fontsize=14, grid=True)
plt.legend(['buoy1', 'buoy2', 'buoy3', 'buoy4'], loc='lower right', fontsize=12)
plt.ylabel('Snow accumulation (cm)', fontsize=14)
plt.show()

# calculate difference in pole accumulation to Leica
for i in range(15):
    p = (poles[str(i+1)].resample('D').median()-sh_leica.resample('D').median()).dropna()
    p_day = p[(p.index == '2021-12-25')]
    print(int(p_day))


# plot SWE, Density, Accumulation (from manual obs at Spuso)
plt.figure()
swe_leica.plot(linestyle='-', color='crimson', fontsize=12, figsize=(6, 5.5), ylim=(-200, 1000)).grid()
swe_emlid.plot(color='salmon', linestyle='--')
plt.errorbar((manual.SWE_aboveAnt.astype('float64')).index, (manual.SWE_aboveAnt.astype('float64')), yerr=(manual.SWE_aboveAnt.astype('float64'))/10, color='k', linestyle='',capsize=4, alpha=0.5)
sh.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
(manual.Acc.astype('float64')*10).plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
plt.errorbar((manual.Acc.astype('float64')*10).index, (manual.Acc.astype('float64')*10), yerr=(manual.Acc.astype('float64')*10)/10, color='darkblue', linestyle='',capsize=4, alpha=0.5)
(sh/1000*ipol).dropna().plot(color='k', linestyle='--').grid()
(manual.SWE_aboveAnt.astype('float64')).plot(color='k', linestyle=' ', marker='+', markersize=8, markeredgewidth=2).grid()
(manual.Density_aboveAnt.dropna()).plot(color='steelblue', linestyle=' ', marker='*', markersize=8, markeredgewidth=2, label='Density (kg/m3)').grid()
plt.errorbar(manual.index, manual.SWE_aboveAnt, yerr=manual.SWE_aboveAnt/10, color='k', linestyle='',capsize=4, alpha=0.5)
#plt.fill_between(sh_std.index, sh - sh_std, sh + sh_std, color="darkblue", alpha=0.2)
#plt.fill_between(s_15min.index, (m_15min-m_15min[0]) - s_15min, (m_15min-m_15min[0]) + s_15min, color="crimson", alpha=0.2)
plt.xlabel(None)
plt.ylabel('SWE (mm w.e.)', fontsize=14)
plt.legend(['High-end GNSS', 'Low-cost GNSS', 'Accumulation_Laser (mm)', 'Accumulation_Manual (mm)', 'Laser (SHM)', 'Manual', 'Density (kg/m3)'], fontsize=11, loc='upper left')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
#plt.show()
plt.savefig('data_neumayer/plots/SWE_Accts_NM_Emlid_30s_Leica_all_2021_22.png', bbox_inches='tight')
plt.savefig('data_neumayer/plots/SWE_Accts_NM_Emlid_30s_Leica_all_2021_22.pdf', bbox_inches='tight')


# plot Difference in SWE (compared to Leica), fitting above plot
plt.figure()
((sh_emlid.resample('D').median()-sh_leica.resample('D').median())/1000*ipol).dropna().plot(color='salmon', linestyle='--', fontsize=12, figsize=(6, 5.5), ylim=(-100, 500)).grid()
(((manual2.Acc.astype('float64')*10).resample('D').median()-sh_leica.resample('D').median())/1000*ipol).dropna().plot(color='k', linestyle=' ', marker='+', markersize=8, markeredgewidth=2).grid()
((sh.resample('D').median()-sh_leica.resample('D').median())/1000*ipol).dropna().plot(color='k', linestyle='--', label='Accumulation (cm)').grid()
plt.xlabel(None)
plt.ylabel('$\Delta$SWE (mm w.e.)', fontsize=14)
plt.legend(['Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='upper left')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
#plt.show()
plt.savefig('data_neumayer/plots/Delta_SWE_Emlid_Manual_Laser_2021_22.png', bbox_inches='tight')
plt.savefig('data_neumayer/plots/Delta_SWE_Emlid_Manual_Laser_2021_22.pdf', bbox_inches='tight')


# plot Difference in Accumulation (compared to Leica), fitting above plot
plt.figure()
((sh_emlid.resample('D').median()-sh_leica.resample('D').median())).dropna().plot(color='salmon', linestyle='--', fontsize=12, figsize=(6, 5.5), ylim=(-200, 1000)).grid()
(((manual2.Acc.astype('float64')*10).resample('D').median()-sh_leica.resample('D').median())).dropna().plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
((sh.resample('D').median()-sh_leica.resample('D').median())).dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
plt.xlabel(None)
plt.ylabel('$\Delta$Accumulation (mm)', fontsize=14)
plt.legend(['Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='upper left')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
#plt.show()
plt.savefig('data_neumayer/plots/Delta_Acc_Emlid_Manual_Laser_2021_22.png', bbox_inches='tight')
plt.savefig('data_neumayer/plots/Delta_Acc_Emlid_Manual_Laser_2021_22.pdf', bbox_inches='tight')


# Q: plot PPP position solutions
# read ppp data
# create empty dataframe for all .log files
df_ppp = pd.DataFrame()
# read all .ENU files in folder, parse date and time columns to datetimeindex and add them to the dataframe
for file in glob.iglob('data_neumayer/ppp/*.pos', recursive=True):
    print(file)
    # header: 'date', 'time', 'snow level (m)', 'signal(-)', 'temp (°C)', 'error (-)', 'checksum (-)'
    ppp = pd.read_csv(file, header=7, delimiter=' ', skipinitialspace=True, na_values=["NaN"], usecols=[4,5,10,11,12, 22,24,25],parse_dates=[['date', 'time']], names=['date', 'time', 'dlat', 'dlon', 'dh', 'h', 'utm_e', 'utm_n'],
            index_col=['date_time'], encoding='latin1', engine='python')
    df_ppp = pd.concat([df_ppp, ppp], axis=0)

# plot lat, lon, h timeseries
fig, axes = plt.subplots(nrows=3, ncols=1, sharex=True)
(df_ppp*100).dlat.plot(ax=axes[0], ylim=(-250,250)).grid()
(df_ppp*100).dlon.plot(ax=axes[1], ylim=(-250,250)).grid()
(df_ppp*100).dh.plot(ax=axes[2], ylim=(-100,500)).grid()
axes[0].set_ylabel('$\Delta$Lat (cm)', fontsize=14)
axes[1].set_ylabel('$\Delta$Lon (cm)', fontsize=14)
axes[2].set_ylabel('$\Delta$H (cm)', fontsize=14)
plt.xlabel(None)
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))plt.show()
plt.savefig('plots/LLH_base.png', bbox_inches='tight')
plt.savefig('plots/LLH_base.pdf', bbox_inches='tight')
