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
import datetime as dt
import glob
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import preprocess

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
preprocess.copy_rinex_files(scr_path + 'id8282_refractolow/', dst_path + 'temp_NMER/', receiver='NMER', copy=True,
                            parent=True, hatanaka=True, move=True, delete_temp=True)  # for emlid rover: NMER
preprocess.copy_rinex_files(scr_path + 'id8281_refracto/', dst_path + 'temp_NMLR/', receiver='NMLR', copy=True,
                            parent=True, hatanaka=True, move=True, delete_temp=True)  # for leica rover: NMLR
preprocess.copy_rinex_files(scr_path + 'id8283_reflecto/', dst_path + 'temp_NMLB/', receiver='NMLB', copy=True,
                            parent=True, hatanaka=True, move=True, delete_temp=True)  # for leica base: NMLB

""" 1. run RTKLib automatically (instead of RTKPost Gui manually) """
# process data using RTKLIB post processing command line tool 'rnx2rtkp' for a specific year and a range of day of years (doys)
preprocess.automate_rtklib_pp(dst_path, 'NMER', yy, ti_int, base, nav, sp3, resolution, ending, start_doy, end_doy,
                              'NMER', options_Emlid)
preprocess.automate_rtklib_pp(dst_path, '3393', yy, ti_int, base, nav, sp3, resolution, ending, start_doy, end_doy,
                              'NMLR', options_Leica)

""" 2. Get RTKLib ENU solution files """
# read all RTKLib ENU solution files (daily) and store them in one dataframe for whole season
df_enu_emlid = preprocess.get_rtklib_solutions(dst_path, 'NMER', resolution, ending, header_length=26)
df_enu_leica = preprocess.get_rtklib_solutions(dst_path, 'NMLR', resolution, ending, header_length=27)


''' 3. Filter and clean ENU solution data '''
# filter and clean ENU solution data (outlier filtering, median filtering, adjustments for observation mast heightening) and store results in pickle and .csv
df_enu_emlid, fil_df_emlid, fil_emlid, fil_clean_emlid, m_emlid, s_emlid, jump_emlid, swe_gnss_emlid, swe_gnss_daily_emlid, std_gnss_daily_emlid = preprocess.filter_rtklib_solutions(
    dst_path, df_enu_emlid, 'NMER', resolution, ambiguity=1, ti_set_swe2zero=12, threshold=3, window='D',
    resample=False, resample_resolution='30min', ending=ending)

df_enu_leica, fil_df_leica, fil_leica, fil_clean_leica, m_leica, s_leica, jump_leica, swe_gnss_leica, swe_gnss_daily_leica, std_gnss_daily_leica = preprocess.filter_rtklib_solutions(
    dst_path, df_enu_leica, 'NMLR', resolution, ambiguity=1, ti_set_swe2zero=12, threshold=3, window='D',
    resample=False, resample_resolution='30min', ending=ending)


''' 4. Read reference sensors data '''
manual, ipol, buoy, poles, laser, laser_filtered = preprocess.read_reference_data(
    dst_path, read_manual=True, read_buoy=True, read_poles=True, read_laser=True, laser_pickle='shm/nm_laser.pkl')


''' 5. Convert swe to snow accumulation and add to df '''
gnss_leica = preprocess.convert_swe2sh_gnss(swe_gnss_leica, ipol_density=ipol)
gnss_emlid = preprocess.convert_swe2sh_gnss(swe_gnss_emlid, ipol_density=ipol)

# resample all sensors sh and swe data to daily & 15min data
leica_daily, emlid_daily, buoy_daily, poles_daily, laser_daily = preprocess.resample_allobs(gnss_leica, gnss_emlid, buoy, poles, laser_filtered, interval='D')


""" 6. Calculate differences, linear regressions, RMSE & MRB between GNSS and reference data """
# calculate differences between reference data and GNSS (Leica/Emlid)
diffs_sh_daily, diffs_swe_daily = preprocess.calculate_differences2gnss(emlid_daily, leica_daily, manual, laser_daily, buoy_daily, poles_daily)
diffs_sh_15min, diffs_swe_15min, laser_15min = preprocess.calculate_differences2gnss_15min(gnss_emlid, gnss_leica, laser_filtered)

# calculate SWE cross correation manual/laser vs. GNSS (daily & 15min)
corr_leica_daily, corr_emlid_daily, corr_leica_15min, corr_emlid_15min = preprocess.calculate_crosscorr(leica_daily, emlid_daily, manual, gnss_leica, gnss_emlid, laser_15min)

# fit linear regression curve manual/laser vs. GNSS (daily & 15min)
predict_daily, predict_emlid_daily, predict_15min, predict_15min_emlid = preprocess.calculate_linearfit(leica_daily, manual, gnss_leica, gnss_emlid, laser_15min)

# calculate RMSE, MRB, and number of samples
preprocess.calculate_rmse_mrb(diffs_swe_daily, diffs_swe_15min, manual, laser_15min)


# TODO: write functions
''' 6. Plot results (SWE, ΔSWE, scatter) '''
os.makedirs(dst_path + 'plots/', exist_ok=True)

# Q: plot SWE
# plot SWE Leica, Emlid, laser, buoy, poles
preprocess.plot_all_SWE(dst_path, leica_daily, emlid_daily, manual, laser_15min, buoy_daily, poles_daily,
                        save=False, suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'])

# Q. plot SWE differences (compared to Leica)
preprocess.plot_all_diffSWE(dst_path, diffs_swe_daily, manual, laser_15min, buoy_daily, poles_daily,
                            save=False, suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'])


# Q: plot scatter plot (GNSS vs. manual, daily)
plt.close()
plt.figure()
ax = all_daily.plot.scatter(x='manual', y='U', figsize=(5, 4.5))
plt.plot(range(10, 750), predict_daily(range(10, 750)), c='k', linestyle='--', alpha=0.7)  # linear regression
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


# Q: plot scatter plot (GNSS vs. laser, 15min)
plt.close()
plt.figure()
ax = all_15min.plot.scatter(x='laser', y='U', figsize=(5, 4.5))
plt.plot(range(10, 850), predict_15min(range(10, 850)), c='k', linestyle='--', alpha=0.7)  # linear regression
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
(manual.Acc.astype('float64') * 10).plot(color='darkblue', linestyle=' ', marker='o', markersize=5,
                                         markeredgewidth=1).grid()
plt.errorbar((manual.Acc.astype('float64') * 10).index, (manual.Acc.astype('float64') * 10),
             yerr=(manual.Acc.astype('float64') * 10) / 10, color='darkblue', linestyle='', capsize=4, alpha=0.5)
sh.plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
for i in range(15):
    poles[str(i + 1)].dropna().plot(linestyle=':', alpha=0.6, legend=False).grid()
for i in range(4):
    globals()[f"sh_buoy{i + 1}_daily"].plot(color='lightgrey', linestyle='-', legend=False).grid()
sh.plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
# plt.fill_between(sh_std.index, sh - sh_std, sh + sh_std, color="darkblue", alpha=0.2)
# plt.fill_between(sh_leica.index, sh_leica - sh_leica/10, sh_leica + sh_leica/10, color="crimson", alpha=0.2)
# plt.fill_between(sh_emlid.index, sh_emlid - sh_emlid/10, sh_emlid + sh_emlid/10, color="salmon", alpha=0.2)
plt.xlabel(None)
plt.ylabel('Snow accumulation (mm)', fontsize=14)
plt.legend(['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='upper left')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
plt.show()
# plt.savefig('data_neumayer/plots/Acc_all_2021_22.png', bbox_inches='tight')
# plt.savefig('data_neumayer/plots/Acc_all_2021_22.pdf', bbox_inches='tight')


# plot Difference in Accumulation (compared to Leica)
plt.figure()
(sh_emlid.resample('D').median() - sh_leica.resample('D').median()).dropna().plot(color='salmon', linestyle='--',
                                                                                  fontsize=12, figsize=(6, 5.5),
                                                                                  ylim=(-200, 1000)).grid()
((manual.Acc.astype('float64') * 10).resample('D').median() - sh_leica.resample('D').median()).dropna().plot(
    color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
(sh.resample('D').median() - sh_leica.resample('D').median()).dropna().plot(color='darkblue', linestyle='-.',
                                                                            label='Accumulation (cm)').grid()
for i in range(4):
    (globals()[f"dsh_buoy{i + 1}_daily"][(
            globals()[f"dsh_buoy{i + 1}_daily"] < globals()[f"dsh_buoy{i + 1}_daily"].median() +
            2 * globals()[f"dsh_buoy{i + 1}_daily"].std())]).plot(color='lightgrey', linestyle='-').grid()
for i in range(15):
    (poles[str(i + 1)].resample('D').median() - sh_leica.resample('D').median()).dropna().plot(linestyle=':', alpha=0.6,
                                                                                               legend=False).grid()
plt.xlabel(None)
plt.ylabel('ΔSnow accumulation (mm)', fontsize=14)
plt.legend(['Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='best')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
# plt.show()
plt.savefig('data_neumayer/plots/Delta_Acc_all_2021_22.png', bbox_inches='tight')
plt.savefig('data_neumayer/plots/Delta_Acc_all_2021_22.pdf', bbox_inches='tight')

# plot snow accumulation from all four sensors of the snow buoy
plt.close()
globals()[f"dsh_buoy1_daily"].plot(linestyle='-')
globals()[f"dsh_buoy2_daily"].plot(linestyle='--')
globals()[f"dsh_buoy3_daily"].plot(linestyle='-.')
globals()[f"dsh_buoy4_daily"].plot(linestyle=':', xlim=('2021-11-26', '2022-05-01'), ylim=(-10, 60), fontsize=14,
                                   grid=True)
plt.legend(['buoy1', 'buoy2', 'buoy3', 'buoy4'], loc='lower right', fontsize=12)
plt.ylabel('Snow accumulation (cm)', fontsize=14)
plt.show()

# calculate difference in pole accumulation to Leica
for i in range(15):
    p = (poles[str(i + 1)].resample('D').median() - sh_leica.resample('D').median()).dropna()
    p_day = p[(p.index == '2021-12-25')]
    print(int(p_day))

# plot SWE, Density, Accumulation (from manual obs at Spuso)
plt.figure()
swe_gnss_leica.plot(linestyle='-', color='crimson', fontsize=12, figsize=(6, 5.5), ylim=(-200, 1000)).grid()
swe_gnss_emlid.plot(color='salmon', linestyle='--')
plt.errorbar((manual.SWE_aboveAnt.astype('float64')).index, (manual.SWE_aboveAnt.astype('float64')),
             yerr=(manual.SWE_aboveAnt.astype('float64')) / 10, color='k', linestyle='', capsize=4, alpha=0.5)
sh.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
(manual.Acc.astype('float64') * 10).plot(color='darkblue', linestyle=' ', marker='o', markersize=5,
                                         markeredgewidth=1).grid()
plt.errorbar((manual.Acc.astype('float64') * 10).index, (manual.Acc.astype('float64') * 10),
             yerr=(manual.Acc.astype('float64') * 10) / 10, color='darkblue', linestyle='', capsize=4, alpha=0.5)
(sh / 1000 * ipol).dropna().plot(color='k', linestyle='--').grid()
(manual.SWE_aboveAnt.astype('float64')).plot(color='k', linestyle=' ', marker='+', markersize=8,
                                             markeredgewidth=2).grid()
(manual.Density_aboveAnt.dropna()).plot(color='steelblue', linestyle=' ', marker='*', markersize=8, markeredgewidth=2,
                                        label='Density (kg/m3)').grid()
plt.errorbar(manual.index, manual.SWE_aboveAnt, yerr=manual.SWE_aboveAnt / 10, color='k', linestyle='', capsize=4,
             alpha=0.5)
# plt.fill_between(sh_std.index, sh - sh_std, sh + sh_std, color="darkblue", alpha=0.2)
# plt.fill_between(s_15min.index, (m_15min-m_15min[0]) - s_15min, (m_15min-m_15min[0]) + s_15min, color="crimson", alpha=0.2)
plt.xlabel(None)
plt.ylabel('SWE (mm w.e.)', fontsize=14)
plt.legend(
    ['High-end GNSS', 'Low-cost GNSS', 'Accumulation_Laser (mm)', 'Accumulation_Manual (mm)', 'Laser (SHM)', 'Manual',
     'Density (kg/m3)'], fontsize=11, loc='upper left')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
# plt.show()
plt.savefig('data_neumayer/plots/SWE_Accts_NM_Emlid_30s_Leica_all_2021_22.png', bbox_inches='tight')
plt.savefig('data_neumayer/plots/SWE_Accts_NM_Emlid_30s_Leica_all_2021_22.pdf', bbox_inches='tight')

# plot Difference in SWE (compared to Leica), fitting above plot
plt.figure()
((sh_emlid.resample('D').median() - sh_leica.resample('D').median()) / 1000 * ipol).dropna().plot(color='salmon',
                                                                                                  linestyle='--',
                                                                                                  fontsize=12,
                                                                                                  figsize=(6, 5.5),
                                                                                                  ylim=(
                                                                                                      -100, 500)).grid()
(((manual.Acc.astype('float64') * 10).resample('D').median() - sh_leica.resample(
    'D').median()) / 1000 * ipol).dropna().plot(color='k', linestyle=' ', marker='+', markersize=8,
                                                markeredgewidth=2).grid()
((sh.resample('D').median() - sh_leica.resample('D').median()) / 1000 * ipol).dropna().plot(color='k', linestyle='--',
                                                                                            label='Accumulation (cm)').grid()
plt.xlabel(None)
plt.ylabel('ΔSWE (mm w.e.)', fontsize=14)
plt.legend(['Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='upper left')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
# plt.show()
plt.savefig('data_neumayer/plots/Delta_SWE_Emlid_Manual_Laser_2021_22.png', bbox_inches='tight')
plt.savefig('data_neumayer/plots/Delta_SWE_Emlid_Manual_Laser_2021_22.pdf', bbox_inches='tight')

# plot Difference in Accumulation (compared to Leica), fitting above plot
plt.figure()
(sh_emlid.resample('D').median() - sh_leica.resample('D').median()).dropna().plot(color='salmon', linestyle='--', fontsize=12, figsize=(6, 5.5), ylim=(-200, 1000)).grid()
((manual.Acc.astype('float64') * 10).resample('D').median() - sh_leica.resample('D').median()).dropna().plot(
    color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
(sh.resample('D').median() - sh_leica.resample('D').median()).dropna().plot(color='darkblue', linestyle='-.',
                                                                            label='Accumulation (cm)').grid()
plt.xlabel(None)
plt.ylabel('ΔAccumulation (mm)', fontsize=14)
plt.legend(['Low-cost GNSS', 'Manual', 'Laser (SHM)'], fontsize=12, loc='upper left')
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
# plt.show()
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
    ppp = pd.read_csv(file, header=7, delimiter=' ', skipinitialspace=True, na_values=["NaN"],
                      usecols=[4, 5, 10, 11, 12, 22, 24, 25], parse_dates=[['date', 'time']],
                      names=['date', 'time', 'dlat', 'dlon', 'dh', 'h', 'utm_e', 'utm_n'],
                      index_col=['date_time'], encoding='latin1', engine='python')
    df_ppp = pd.concat([df_ppp, ppp], axis=0)

# plot lat, lon, h timeseries
fig, axes = plt.subplots(nrows=3, ncols=1, sharex=True)
(df_ppp * 100).dlat.plot(ax=axes[0], ylim=(-250, 250)).grid()
(df_ppp * 100).dlon.plot(ax=axes[1], ylim=(-250, 250)).grid()
(df_ppp * 100).dh.plot(ax=axes[2], ylim=(-100, 500)).grid()
axes[0].set_ylabel('ΔLat (cm)', fontsize=14)
axes[1].set_ylabel('ΔLon (cm)', fontsize=14)
axes[2].set_ylabel('ΔH (cm)', fontsize=14)
plt.xlabel(None)
plt.xlim(dt.date(2021, 11, 26), dt.date(2022, 5, 1))
plt.show()
plt.savefig('plots/LLH_base.png', bbox_inches='tight')
plt.savefig('plots/LLH_base.pdf', bbox_inches='tight')
