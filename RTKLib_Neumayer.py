""" Run RTKLib automatically for differential GNSS processing
http://www.rtklib.com/

input:  - GNSS options file (.conf)
        - GNSS rover file (rinex)
        - GNSS base file (rinex)
        - GNSS navigation ephemerides file (.nav); https://cddis.nasa.gov/archive/gnss/data/daily/2022/brdc/ (brdc0010.22n.gz)
        - GNSS precise ephemerides file (.eph/.sp3); http://ftp.aiub.unibe.ch/CODE/2022_M/ (cod22002.eph_M.gz)
output: - position (.pos) file; (UTC, X, Y, Z)
created: LS

"""

# IMPORT modules
import subprocess
import os
import datetime
import glob
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# CHOOSE: DEFINE year, files (base, rover, navigation orbits, precise orbits), time interval
yy = str(21)
rover = 'NMER'      # 'NMER' or '3393' (old Emlid: 'ReachM2_sladina-raw_')
rover_name = 'NMER' # 'NMER' or 'NMER_original' or 'NMLR'
receiver = 'NMLR'
base = '3387'
nav = '3387'
sp3 = 'COD'
ti_int = '900'
resolution = '15min'
options_Leica = 'rtkpost_options_Ladina_Leica_statisch_multisystemfrequency_neumayer'
options_Emlid = 'rtkpost_options_Ladina_Emlid_statisch_multisystemfrequency_neumayer_900_15'

# Q: example run RTKLib:
# process1 = subprocess.Popen('cd data && rnx2rtkp -k rtkpost_options_Ladina.conf -ti 3600 -o sol/out_doy4.pos '
#                            'WJU10040.17O WJLR0040.17O alrt0040.17n COD17004.eph',
#                            shell= True,
#                            stdout=subprocess.PIPE,
#                            stderr=subprocess.PIPE)
#
# stdout1, stderr1 = process1.communicate()
# print(stdout1)
# print(stderr1)


# Q: For Emlid and Leica Rover (working properly now for Emlid files)
# TODO: check for Leica files
for file in glob.iglob('data_neumayer/' + rover + '*.' + yy + 'O', recursive=True):
    ''' get doy from rover file names with name structure:
        Leica Rover: '33933650.21o' [rover + doy + '0.' + yy + 'o']
        Emlid Rover (pre-processed): 'NMER3650.21o' [rover + doy + '0.' + yy + 'o']
        Emlid Rover (original): 'ReachM2_sladina-raw_202112041058.21O' [rover + datetime + '.' + yy + 'O']
        '''
    rover_file = os.path.basename(file)
    if rover_name == 'NMER_original':  # Emlid original format (output from receiver, non-daily files)
        doy = datetime.datetime.strptime(rover_file.split('.')[0].split('_')[2], "%Y%m%d%H%M").strftime('%j')
        options = options_Emlid
    if rover_name == 'NMER':       # Emlid pre-processed format (daily files)
        doy = rover_file.split('.')[0][-4:-1]
        options = options_Emlid
    if rover_name == 'NMLR':
        doy = rover_file.split('.')[0][-4:-1]
        options = options_Leica
    print('\nRover file: ' + rover_file, '\ndoy: ', doy)

    # define input and output filenames (for some reason it's not working when input files are stored in subfolders!)
    base_file = base + doy + '0.' + yy + 'O'
    broadcast_orbit_gps = nav + doy + '0.' + yy + 'n'
    broadcast_orbit_glonass = nav + doy + '0.' + yy + 'g'
    broadcast_orbit_galileo = nav + doy + '0.' + yy + 'l'
    precise_orbit = sp3 + yy + doy + '.sp3'
    output_file = 'sol/' + rover_name + '/20' + yy + '_' + rover_name + doy + '.pos'

    # run RTKLib automatically (instead of RTKPost Gui manually)
    process = subprocess.Popen('cd data_neumayer && rnx2rtkp '
                               '-k ' + options + '.conf '
                               '-ti ' + ti_int + ' '
                               '-o ' + output_file + ' '
                               + rover_file + ' ' + base_file + ' ' + broadcast_orbit_gps + ' ' + broadcast_orbit_glonass + ' ' + broadcast_orbit_galileo,
                               shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()
    # print(stdout) # print processing output
    print(stderr)  # print processing errors

    # remove .stat files
    if os.path.exists('data_neumayer/' + output_file + '.stat'):
        os.remove('data_neumayer/' + output_file + '.stat')

print('\n\nfinished with all files :-)')

# Q: For Leica Rover (working well)
# iterator for 3-digit numbers (001 etc.)
doy_list = ["%.3d" % i for i in range(330, 366)]

# for each day of year, do:
for doy in doy_list:
    doy = str(doy)
    print('doy: ', doy, doy[-1])

    # define input and output filenames (for some reason it's not working when input files are stored in subfolders!)
    base_file = base + doy + '0.' + yy + 'O'
    rover_file = rover + doy + '0.' + yy + 'O'
    broadcast_orbit_gps = nav + doy + '0.' + yy + 'n'
    broadcast_orbit_glonass = nav + doy + '0.' + yy + 'g'
    broadcast_orbit_galileo = nav + doy + '0.' + yy + 'l'
    precise_orbit = sp3 + yy + doy + '.sp3'
    output_file = 'sol/' + rover_name + '/' + rover_name + doy + '.pos'

    # run RTKLib automatically (instead of RTKPost Gui manually)
    process = subprocess.Popen('cd data_neumayer && rnx2rtkp '
                               '-k ' + options + '.conf '
                               '-ti ' + ti_int + ' '
                               '-o ' + output_file + ' '
                               + rover_file + ' ' + base_file + ' ' + broadcast_orbit_gps + ' ' + broadcast_orbit_glonass + ' ' + broadcast_orbit_galileo,
                               shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()
    # print(stdout) # print processing output
    print(stderr)   # print processing errors

    # remove .stat files
    if os.path.exists('data_neumayer/' + output_file + '.stat'):
        os.remove('data_neumayer/' + output_file + '.stat')

print('\n\nfinished with all files :-)')


''' import RTKLib solution .txt files '''
# create empty dataframe for all .ENU files
df_enu = pd.DataFrame()

# read all .ENU files in folder, parse date and time columns to datetimeindex and add them to the dataframe
for file in glob.iglob('data_neumayer/sol/' + receiver + '/*.pos', recursive=True):
    print(file)
    enu = pd.read_csv(file, header=26, delimiter=' ', skipinitialspace=True, index_col=['date_time'], na_values=["NaN"],
                      usecols=[0, 1, 4, 5, 6, 9], names=['date', 'time', 'U', 'amb_state', 'nr_sat', 'std_u'],
                      parse_dates=[['date', 'time']])
    df_enu = pd.concat([df_enu, enu], axis=0)

# store dataframe as binary pickle format
df_enu.to_pickle('data_neumayer/sol/' + receiver + '_' + resolution + '.pkl')


''' Read binary stored ENU data '''
# read all data from .pkl and combine, if necessary multiple parts
df_enu = pd.read_pickle('data_neumayer/sol/' + receiver + '_' + resolution + '.pkl')

# select data without outliers
# select data where ambiguities are fixed (amb_state==1)
fil_df = pd.DataFrame(df_enu[(df_enu.amb_state == 1)])
# if rover_name == 'NMLR':
#     # select data where ambiguities are fixed (amb_state==1)
#     fil_df = pd.DataFrame(df_enu[(df_enu.amb_state == 1)])  # for high-end data
# else:
#     # select data where ambiguities are float (amb_state==2) and have a low stdev (<2.5mm)
#     fil_df = pd.DataFrame(df_enu[(df_enu.amb_state == 2) & (df_enu.std_u < 0.0025)])    # for low-cost data
fil_df.index = pd.DatetimeIndex(fil_df.index)
fil = (fil_df.U - fil_df.U[1]) * 1000   # adapt to reference SWE values in mm (median of last week without snow)

# remove outliers
upper_limit = fil.median() + 3 * fil.std()
lower_limit = fil.median() - 3 * fil.std()
fil_clean = fil[(fil > lower_limit) & (fil < upper_limit)]

# calculate median (per day and 10min) and std (per day)
m = fil_clean.resample('D').median()
s = fil_clean.resample('D').std()
m_15min = fil_clean.rolling('D').median()       # .resample('15min').median()
s_15min = fil_clean.rolling('D').std()

# adjust for snow mast heightening (approx. 3m elevated)
jump = m_15min[(m_15min.diff() < -1000)]    # detect jumps (>2m) in the dataset
adj = m_15min[(m_15min.index > jump.index.format()[0])] - jump[0]     # correct jump [1]
m_15min_adj = m_15min[~(m_15min.index >= jump.index.format()[0])].append(adj)   # adjusted dataset

swe_gnss = m_15min_adj-m_15min_adj[0]
swe_gnss.index = swe_gnss.index + pd.Timedelta(seconds=18)

# store swe results to pickle
swe_gnss.to_pickle('data_neumayer/sol/SWE_results/2021_22_swe_gnss_' + receiver + '.pkl')
swe_gnss.to_csv('data_neumayer/sol/SWE_results/2021_22_swe_gnss_' + receiver + '.csv')

# read gnss swe results from pickle
swe_leica = pd.read_pickle('data_neumayer/sol/SWE_results/2021_22_swe_gnss_NMLR.pkl')
swe_emlid = pd.read_pickle('data_neumayer/sol/SWE_results/2021_22_swe_gnss_NMER.pkl')

# Q: read reference data
# Accumulation (cm), Density (kg/m^3), SWE (mm w.e.)
manual = pd.read_csv('data_neumayer/03_Densitypits/Manual_Spuso.csv', header=1, skipinitialspace=True, delimiter=';', index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0], dayfirst=True, names=['Acc', 'Density', 'SWE', 'Density_aboveAnt', 'SWE_aboveAnt'])
manual2 = manual
manual2.index = manual2.index + pd.Timedelta(days=0.2)
ipol = manual.Density_aboveAnt.resample('min').interpolate(method='linear', limit_direction = 'backward')

# read snow buoy data
buoy_all = pd.read_csv('data_neumayer/06_SHM/Snowbuoy/2017S54_300234011695900_proc.csv', header=0, skipinitialspace=True, delimiter=',', index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0],
                   names=['lat', 'lon', 'sh1', 'sh2', 'sh3', 'sh4', 'pressure', 'airtemp', 'bodytemp', 'gpstime'])

# select only data from season 21/22
buoy = buoy_all['2021-11-26':]

# Differences in accumulation (in mm)
dsh1 = (buoy.sh1-buoy.sh1[0])*1000
dsh2 = (buoy.sh2-buoy.sh2[0])*1000
dsh3 = (buoy.sh3-buoy.sh3[0])*1000
dsh4 = (buoy.sh4-buoy.sh4[0])*1000
dsh = pd.concat([dsh1, dsh2, dsh3, dsh4], axis=1)

# calculate accumulation gain
offset = dsh.dropna()['2021-12-23'][:1]

# read Pegelfeld Spuso accumulation from poles
poles = pd.read_csv('data_neumayer/03_Densitypits/Pegelfeld_Spuso_Akkumulation.csv', header=0, delimiter=';', index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0], dayfirst=True)


# read snow height data
# # create empty dataframe for all .log files
# df_shm = pd.DataFrame()
# # read all snow accumulation.log files in folder, parse date and time columns to datetimeindex and add them to the dataframe
# for file in glob.iglob('data_neumayer/shm/nm*.log', recursive=True):
#     print(file)
#     # header: 'date', 'time', 'snow level (m)', 'signal(-)', 'temp (°C)', 'error (-)', 'checksum (-)'
#     shm = pd.read_csv(file, header=0, delimiter=r'[ >]', skipinitialspace=True, na_values=["NaN"], names=['date', 'time', 'none','h', 'signal', 'temp', 'error', 'check'], usecols=[0,1,3,5,6],
#                       encoding='latin1', parse_dates=[['date', 'time']], index_col=['date_time'], engine='python', dayfirst=True)
#     df_shm = pd.concat([df_shm, shm], axis=0)
#
# # store as .pkl
# df_shm.to_pickle('data_neumayer/shm/nm_shm.pkl')
df_shm = pd.read_pickle('data_neumayer/shm/nm_shm.pkl')

h = df_shm[(df_shm.error == 0)].h * 1000
fil_h = (h - h[0])  # adapt to reference SWE values in mm

# clean outliers
ul = fil_h.median() + 1 * fil_h.std()
ll = fil_h.median() - 1 * fil_h.std()
fil_h_clean = fil_h[(fil_h > ll) & (fil_h < ul)]

h = fil_h_clean.resample('6H').median()
h_std = fil_h_clean.resample('H').std()
sh = fil_h_clean.rolling('D').median()
sh_std = fil_h_clean.rolling('D').std()
swe = (sh/1000)*408   # swe = h[m] * density[kg/m3]; mean_density(0.5m)=408 from Hecht_2022
swe_15min = swe.resample('15min').median()
# with interpolated density data
swe_corr = (sh/1000) * ipol
swe_corr_15min = swe_corr.resample('15min').median()

# TODO: finding jumps in shm data
mx = swe.diff().max()           # 217.14
mn = swe.diff().min()           # -122.81
maxind = swe.diff().idxmax()    # '2021-12-23 09:42:00'
minind = swe.diff().idxmin()    # '2022-05-03 18:50:00'
swe.diff().plot();plt.plot(swe.diff().idxmax(), swe.diff().max(), marker='+');plt.show()

swe_adj = swe[(swe.index >= swe.diff().idxmax())] - swe.diff().max()      # correct jump
shm_swe_adj = swe[~(swe.index >= swe.diff().idxmax())].append(swe_adj)   # adjusted dataset
shm_swe_adj.plot(); swe_gnss.plot();plt.show()

# difference gnss sh to shm sh (ab dem 23.dez);
# pegelfeld spuso: 59cm schneezutrag zw. 26.11 und 26.12
# shm: ca. 50cm schneezutrag
sh_gnss = swe_gnss * 1000 / 408
sh_diff = (sh.resample('D').median() - sh_gnss.resample('D').median()).median().round(0) # 278mm

# calculate sh from GNSS SWE with a mean constant density value for h=0.5m (Hecht, 2022)
sh_leica_const = swe_leica * 1000 / 408
sh_emlid_const = swe_emlid * 1000 / 408

# calculate sh from GNSS SWE with interpolated density values (Spuso)
sh_leica = swe_leica * 1000 / ipol
sh_emlid = swe_emlid * 1000 / ipol


''' plot data '''
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
plt.xlim(datetime.datetime.strptime('2021-11-26', "%Y-%m-%d"), datetime.datetime.strptime('2022-05-01', "%Y-%m-%d"))
plt.xticks(fontsize=14)
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
plt.xlim(datetime.datetime.strptime('2021-11-26', "%Y-%m-%d"), datetime.datetime.strptime('2022-05-01', "%Y-%m-%d"))
plt.xticks(fontsize=14)
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
plt.xlim(datetime.datetime.strptime('2021-11-26', "%Y-%m-%d"), datetime.datetime.strptime('2022-05-01', "%Y-%m-%d"))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
#plt.show()
plt.savefig('data_neumayer/plots/Delta_Acc_Emlid_Manual_Laser_2021_22.png', bbox_inches='tight')
plt.savefig('data_neumayer/plots/Delta_Acc_Emlid_Manual_Laser_2021_22.pdf', bbox_inches='tight')


# # fit linear regression curve manual vs. GNSS (daily)
all_daily = pd.concat([swe_15min, swe_gnss], axis=1)
all_daily_nonan = all_daily.dropna()
fit = np.polyfit(all_daily_nonan.h, all_daily_nonan.U, 1)
predict = np.poly1d(fit)
print('Linear fit: \nm = ', round(fit[0], 2), '\nb = ', int(fit[1]))     # n=12, m=1.02, b=-8 mm w.e.

# calculate cross correation manual vs. GNSS (daily)
corr = all_daily.h.corr(all_daily.U)
print('Pearsons correlation: %.2f' % corr)

# plot scatter plot (GNSS vs. manual, daily)
plt.close()
plt.figure()
ax = all_daily_nonan.plot.scatter(x='h', y='U', figsize=(5, 4.5))
plt.plot(range(-50, 220), predict(range(-50, 220)), c='k', linestyle='--', alpha=0.7)    # linear regression
ax.set_ylabel('GNSS SWE (mm w.e.)', fontsize=12)
ax.set_ylim(-50, 250)
ax.set_xlim(-50, 250)
ax.set_xlabel('SHM SWE (mm w.e.)', fontsize=12)
plt.legend(['r=%.2f' % corr], fontsize=12, loc='upper left')
plt.xticks(fontsize=12)
plt.yticks(fontsize=12)
plt.grid()
plt.show()
#plt.savefig('plots/scatter_SWE_NM_manual.png', bbox_inches='tight')
#plt.savefig('plots/scatter_SWE_NM_manual.pdf', bbox_inches='tight')



# PPP position solutions
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
plt.xlim(datetime.datetime.strptime('2021-11-26', "%Y-%m-%d"), datetime.datetime.strptime('2021-12-05', "%Y-%m-%d"))
plt.show()
plt.savefig('plots/LLH_base.png', bbox_inches='tight')
plt.savefig('plots/LLH_base.pdf', bbox_inches='tight')


# Q: plot SWE
plt.figure()
swe_leica.plot(linestyle='-', color='crimson', fontsize=12, figsize=(6, 5.5), ylim=(-100, 500)).grid()
swe_emlid.plot(color='salmon', linestyle='--')
(manual.SWE_aboveAnt.astype('float64')).plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
plt.errorbar((manual.SWE_aboveAnt.astype('float64')).index, (manual.SWE_aboveAnt.astype('float64')), yerr=(manual.SWE_aboveAnt.astype('float64'))/10, color='darkblue', linestyle='',capsize=4, alpha=0.5)
(sh/1000*ipol).dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
fil_dsh1 = ((dsh1)/1000*ipol).dropna()
(fil_dsh1[(fil_dsh1 < fil_dsh1.median() + 2 * fil_dsh1.std())]).plot(color='darkgrey', linestyle='-').grid()
((dsh2)/1000*ipol).dropna().plot(color='lightgrey', linestyle='-').grid()
((dsh3)/1000*ipol).dropna().plot(color='darkgrey', linestyle=':').grid()
((dsh4)/1000*ipol).dropna().plot(color='lightgrey', linestyle=':').grid()
for i in range(15):
    (poles[str(i+1)]/1000*ipol).dropna().plot(linestyle=':', alpha=0.6, legend=False).grid()
plt.fill_between(swe_leica.index, swe_leica - swe_leica/10, swe_leica + swe_leica/10, color="crimson", alpha=0.2)
plt.fill_between(swe_emlid.index, swe_emlid - swe_emlid/10, swe_emlid + swe_emlid/10, color="salmon", alpha=0.2)
plt.xlabel(None)
plt.ylabel('SWE (mm w.e.)', fontsize=14)
plt.legend(['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='upper left')
plt.xlim(datetime.datetime.strptime('2021-11-26', "%Y-%m-%d"), datetime.datetime.strptime('2022-05-01', "%Y-%m-%d"))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
#plt.show()
plt.savefig('data_neumayer/plots/SWE_all_poles_2021_22.png', bbox_inches='tight')
plt.savefig('data_neumayer/plots/SWE_all_poles_2021_22.pdf', bbox_inches='tight')


# plot Difference in SWE (compared to Leica)
plt.figure()
((sh_emlid.resample('D').median()-sh_leica.resample('D').median())/1000*ipol).dropna().plot(color='salmon', linestyle='--', fontsize=12, figsize=(6, 5.5), ylim=(-100, 500)).grid()
(((manual2.Acc.astype('float64')*10).resample('D').median()-sh_leica.resample('D').median())/1000*ipol).dropna().plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
((sh.resample('D').median()-sh_leica.resample('D').median())/1000*ipol).dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
fil_dsh1 = ((dsh1.resample('D').median()-sh_leica.resample('D').median())/1000*ipol).dropna()
(fil_dsh1[(fil_dsh1 < fil_dsh1.median() + 2 * fil_dsh1.std())]).plot(color='darkgrey', linestyle='-').grid()
((dsh2.resample('D').median()-sh_leica.resample('D').median())/1000*ipol).dropna().plot(color='lightgrey', linestyle='-').grid()
((dsh3.resample('D').median()-sh_leica.resample('D').median())/1000*ipol).dropna().plot(color='darkgrey', linestyle=':').grid()
((dsh4.resample('D').median()-sh_leica.resample('D').median())/1000*ipol).dropna().plot(color='lightgrey', linestyle=':').grid()
for i in range(15):
    ((poles[str(i+1)].resample('D').median()-sh_leica.resample('D').median())/1000*ipol).dropna().plot(linestyle=':', alpha=0.6, legend=False).grid()
plt.xlabel(None)
plt.ylabel('$\Delta$SWE (mm w.e.)', fontsize=14)
plt.legend(['Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='upper left')
plt.xlim(datetime.datetime.strptime('2021-11-26', "%Y-%m-%d"), datetime.datetime.strptime('2022-05-01', "%Y-%m-%d"))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
#plt.show()
plt.savefig('data_neumayer/plots/Delta_SWE_all_2021_22.png', bbox_inches='tight')
plt.savefig('data_neumayer/plots/Delta_SWE_all_2021_22.pdf', bbox_inches='tight')


# Q: plot all Accumulation data
plt.close()
plt.figure()
sh_leica.dropna().plot(linestyle='-', color='crimson', fontsize=12, figsize=(6, 5.5), ylim=(-200, 1000)).grid()
sh_emlid.dropna().plot(color='salmon', linestyle='--')
(manual2.Acc.astype('float64')*10).plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
plt.errorbar((manual2.Acc.astype('float64')*10).index, (manual2.Acc.astype('float64')*10), yerr=(manual2.Acc.astype('float64')*10)/10, color='darkblue', linestyle='',capsize=4, alpha=0.5)
sh.plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
for i in range(15):
    poles[str(i+1)].dropna().plot(linestyle=':', alpha=0.6, legend=False).grid()
(dsh1).plot(color='darkgrey', linestyle='-').grid()
(dsh2).plot(color='lightgrey', linestyle='-', legend=False).grid()
(dsh3).plot(color='darkgrey', linestyle=':', legend=False).grid()
(dsh4).plot(color='lightgrey', linestyle=':', legend=False).grid()
sh.plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
#plt.fill_between(sh_std.index, sh - sh_std, sh + sh_std, color="darkblue", alpha=0.2)
#plt.fill_between(sh_leica.index, sh_leica - sh_leica/10, sh_leica + sh_leica/10, color="crimson", alpha=0.2)
#plt.fill_between(sh_emlid.index, sh_emlid - sh_emlid/10, sh_emlid + sh_emlid/10, color="salmon", alpha=0.2)
plt.xlabel(None)
plt.ylabel('Snow accumulation (mm)', fontsize=14)
plt.legend(['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='upper left')
plt.xlim(datetime.datetime.strptime('2021-11-26', "%Y-%m-%d"), datetime.datetime.strptime('2022-05-01', "%Y-%m-%d"))
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
fil_dsh1 = (dsh1.resample('D').median()-sh_leica.resample('D').median()).dropna()
(fil_dsh1[(fil_dsh1 < fil_dsh1.median() + 2 * fil_dsh1.std())]).plot(color='darkgrey', linestyle='-').grid()
(dsh2.resample('D').median()-sh_leica.resample('D').median()).dropna().plot(color='lightgrey', linestyle='-').grid()
(dsh3.resample('D').median()-sh_leica.resample('D').median()).dropna().plot(color='darkgrey', linestyle=':').grid()
(dsh4.resample('D').median()-sh_leica.resample('D').median()).dropna().plot(color='lightgrey', linestyle=':').grid()
for i in range(15):
    (poles[str(i+1)].resample('D').median()-sh_leica.resample('D').median()).dropna().plot(linestyle=':', alpha=0.6, legend=False).grid()
plt.xlabel(None)
plt.ylabel('$\Delta$Snow accumulation (mm)', fontsize=14)
plt.legend(['Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='best')
plt.xlim(datetime.datetime.strptime('2021-11-26', "%Y-%m-%d"), datetime.datetime.strptime('2022-05-01', "%Y-%m-%d"))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
#plt.show()
plt.savefig('data_neumayer/plots/Delta_Acc_all_2021_22.png', bbox_inches='tight')
plt.savefig('data_neumayer/plots/Delta_Acc_all_2021_22.pdf', bbox_inches='tight')


# plot snow accumulation from all four sensors of the snow buoy
plt.close()
dsh1.plot(linestyle='-')
dsh2.plot(linestyle='--')
dsh3.plot(linestyle='-.')
dsh4.plot(linestyle=':', xlim=('2021-11-26', '2022-05-01'), ylim=(-10,60), fontsize=14, grid=True)
plt.legend(['buoy1', 'buoy2', 'buoy3', 'buoy4'], loc='lower right', fontsize=12)
plt.ylabel('Snow accumulation (cm)', fontsize=14)
plt.show()

