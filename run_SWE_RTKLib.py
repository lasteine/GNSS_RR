import datetime
import glob
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

''' import RTKLib solution .txt files '''
resolution = '15min'
receiver = 'WJL0'       # 'WJU1' for ublox, 'WJL0' for Leica

# # create empty dataframe for all .ENU files
# df_enu = pd.DataFrame()
#
# # read all .ENU files in folder, parse date and time columns to datetimeindex and add them to the dataframe
# for file in glob.iglob('data/sol/' + receiver + '/' + resolution + '/*.pos', recursive=True):
#     print(file)
#     enu = pd.read_csv(file, header=24, delimiter=' ', skipinitialspace=True, index_col=['date_time'], na_values=["NaN"],
#                       usecols=[0, 1, 4, 5, 6, 9], names=['date', 'time', 'U', 'amb_state', 'nr_sat', 'std_u'],
#                       parse_dates=[['date', 'time']])
#     df_enu = pd.concat([df_enu, enu], axis=0)
#
# # store dataframe as binary pickle format
# df_enu.to_pickle('data/sol/' + receiver + '_' + resolution + '.pkl')



''' Read binary stored ENU data '''
# read all data from .pkl and combine, if necessary multiple parts
df_enu = pd.read_pickle('data/sol/' + receiver + '_' + resolution + '.pkl')

# select data where ambiguities are fixed (amb_state==1)
fil_df = pd.DataFrame(df_enu[(df_enu.amb_state == 1)])
fil_df.index = pd.DatetimeIndex(fil_df.index)
fil_df = fil_df.sort_index()
fil = (fil_df.U - fil_df.U[-900:].median()) * 1000  # adapt to reference SWE values in mm (median of last week without snow)

#
# # remove outliers
# upper_limit = fil.median() + 3 * fil.std()  # 2 sigma for WJU1
# lower_limit = fil.median() - 3 * fil.std()  # 2 sigma for WJU1
# fil_clean = fil[(fil > lower_limit) & (fil < upper_limit)]

# calculate median (per day and 10min) and std (per day)
m = fil.resample('D').median()
s = fil.resample('D').std()
m_30 = fil.rolling('D').median()       # .resample('15min').median()
s_30 = fil.rolling('D').std()
m_30min = m_30.resample('30min').mean()       # .resample('15min').median()
s_30min = s_30.resample('30min').mean()

''' Read reference .csv data '''
# read SWE observations (30min resolution)
wfj = pd.read_csv('data/ref/WFJ.csv', header=0, delimiter=';', index_col=0, na_values=["NaN"], names=['scale', 'pillow'])
wfj.index = pd.DatetimeIndex(wfj.index)
wfj = wfj.rolling('D').median()
wfj2 = wfj
wfj2.index = wfj2.index - pd.Timedelta(days=0.5)
wfj2.index = wfj2.index.tz_convert(None)    # convert to timezone unaware index
manual = pd.read_csv('data/ref/manual.csv', header=None, skipinitialspace=True, delimiter=';', index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0], dayfirst=True, usecols=[0, 2], names=['date', 'manual'])

# calculate median (per day and 10min) and relative bias (per day)
scale_res = wfj2.scale.resample('D').median()
scale_err = scale_res/10     # calculate 10% relative bias
scale_30min = wfj2.scale   # calculate median per 10min (filtered over one day)

# # combine daily manual and resampled scale observations in one dataframe
# ref = pd.concat([scale_res, manual], axis=1)
#
# # combine reference and GNSS data
# all_daily = pd.concat([ref, m[:-1]], axis=1)
# all_10min = pd.concat([scale_10min, m_15min], axis=1)

''' Plot results (SWE, ΔSWE, scatter): now only GNSS'''
m_ref = (ref['pillow'] + ref['scale'])/2 * 1000
ref['rtklib'] = ref['rtklib'] *1000


# Linear fits
# m=0.95, b=8, cc=099   # scale vs. high-end GNSS
# m=1.03, b=-20, cc=098   # pillow vs. high-end GNSS

# RMS between snow scale and GNSS Leica
# rms = np.sqrt((np.sum(m_60min-m_60)**2)/len(m_60min))
# scale vs ublox: 36.0 mm
# pillow vs ublox: 46.3 mm


# plot SWE
plt.figure()
scale_res.plot(linestyle='--', color='steelblue', fontsize=12, figsize=(6, 5.5), ylim=(-1, 1000))
manual.manual.plot(color='k', linestyle=' ', marker='+', markersize=8, markeredgewidth=2)
plt.errorbar(manual.index, manual.manual, yerr=manual.manual/10, color='k', linestyle='',capsize=4, alpha=0.5)
m.plot(linestyle='-', color='crimson').grid()
plt.fill_between(scale_res.index, scale_res - scale_err, scale_res + scale_err, color="steelblue", alpha=0.1)
plt.fill_between(m.index, m - s, m + s, color="crimson", alpha=0.2)
plt.xlabel(None)
plt.ylabel('SWE (mm w.e.)', fontsize=14)
plt.legend(['Snow scale', 'Manual', 'GNSS'], fontsize=12, loc='upper left')
plt.xlim(datetime.datetime.strptime('2016-11-01', "%Y-%m-%d"), datetime.datetime.strptime('2017-07-01', "%Y-%m-%d"))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
# plt.show()
plt.savefig('plots/SWE_WFJ_Leica_15min.png', bbox_inches='tight')
plt.savefig('plots/SWE_WFJ_Leica_15min.pdf', bbox_inches='tight')

# plot SWE difference
dscale_daily = (scale_res - m).dropna()
dscale = (scale_30min - m_30min).dropna()
dmanual = (manual.manual - m).dropna()

# calculate differences
diffs = pd.concat([dmanual, dscale], axis=1)
diffs.columns = ['Manual', 'Snow scale']


plt.close()
plt.figure()
dscale_daily.plot(color='steelblue', linestyle='--', fontsize=14, figsize=(6, 5.5), ylim=(-200, 200)).grid()
dmanual.plot(color='k', linestyle=' ', marker='+', markersize=8, markeredgewidth=2).grid()
plt.xlabel(None)
plt.ylabel('ΔSWE (mm w.e.)', fontsize=14)
plt.legend(['Snow scale', 'Manual'], fontsize=14, loc='upper left')
plt.xlim(datetime.datetime.strptime('2016-11-01', "%Y-%m-%d"), datetime.datetime.strptime('2017-07-01', "%Y-%m-%d"))
plt.xticks(fontsize=14)
plt.yticks(fontsize=14)
# plt.show()
plt.savefig('plots/diff_SWE_WFJ_highend.png', bbox_inches='tight')
plt.savefig('plots/diff_SWE_WFJ_highend.pdf', bbox_inches='tight')

# fit linear regression curve manual vs. GNSS (daily)
all_daily = pd.concat([manual.manual, m], axis=1)
all_daily_nonan = all_daily.dropna()
fit = np.polyfit(all_daily_nonan.manual, all_daily_nonan.U, 1)
predict = np.poly1d(fit)
print('Linear fit: \nm = ', round(fit[0], 2), '\nb = ', int(fit[1]))     # n=12, m=1.02, b=-8 mm w.e.

# calculate cross correation manual vs. GNSS (daily)
corr = all_daily.manual.corr(all_daily.U)
print('Pearsons correlation: %.2f' % corr)

# plot scatter plot (GNSS vs. manual, daily)
plt.close()
plt.figure()
ax = all_daily.plot.scatter(x='manual', y='U', figsize=(5, 4.5))
plt.plot(range(10, 750), predict(range(10, 750)), c='k', linestyle='--', alpha=0.7)    # linear regression
ax.set_ylabel('GNSS SWE (mm w.e.)', fontsize=12)
ax.set_ylim(0, 800)
ax.set_xlim(0, 800)
ax.set_xlabel('Manual SWE (mm w.e.)', fontsize=12)
plt.legend(['r=%.2f' % corr], fontsize=12, loc='upper left')
plt.xticks(fontsize=12)
plt.yticks(fontsize=12)
plt.grid()
# plt.show()
plt.savefig('plots/scatter_SWE_WFJ_manual.png', bbox_inches='tight')
plt.savefig('plots/scatter_SWE_WFJ_manual.pdf', bbox_inches='tight')


# fit linear regression curve scale vs. GNSS (30min)
all_daily = pd.concat([scale_30min, m_30min], axis=1)
all_daily_nonan = all_daily.dropna()
fit = np.polyfit(all_daily_nonan.scale, all_daily_nonan.U, 1)
predict = np.poly1d(fit)
print('Linear fit: \nm = ', round(fit[0], 2), '\nb = ', int(fit[1]))     # n=12, m=1.02, b=-8 mm w.e.

# calculate cross correation manual vs. GNSS (daily)
corr = all_daily.scale.corr(all_daily.U)
print('Pearsons correlation: %.2f' % corr)

# plot scatter plot (GNSS vs. manual, daily)
plt.close()
plt.figure()
ax = all_daily.plot.scatter(x='scale', y='U', figsize=(5, 4.5))
plt.plot(range(10, 850), predict(range(10, 850)), c='k', linestyle='--', alpha=0.7)    # linear regression
ax.set_ylabel('GNSS SWE (mm w.e.)', fontsize=12)
ax.set_ylim(0, 1000)
ax.set_xlim(0, 1000)
ax.set_xlabel('Snow scale SWE (mm w.e.)', fontsize=12)
plt.legend(['r=%.2f' % corr], fontsize=12, loc='upper left')
plt.xticks(fontsize=12)
plt.yticks(fontsize=12)
plt.grid()
# plt.show()
plt.savefig('plots/scatter_SWE_WFJ_scale_30min.png', bbox_inches='tight')
plt.savefig('plots/scatter_SWE_WFJ_scale_30min.pdf', bbox_inches='tight')




# plot boxplot of differences
dscale.describe()
dmanual.describe()
diffs[['Manual', 'Snow scale']].plot.box(ylim=(-100, 200), figsize=(3, 4.5), fontsize=12)
plt.grid()
plt.ylabel('ΔSWE (mm w.e.)', fontsize=12)
plt.show()
plt.savefig('plots/box_SWE_WFJ_diff.png', bbox_inches='tight')
plt.savefig('plots/box_SWE_WFJ_diff.pdf', bbox_inches='tight')

# plot histogram of differences
diffs[['Snow scale daily', 'Manual']].plot.hist(bins=25, xlim=(-200, 200), figsize=(3, 4.5), fontsize=12, alpha=0.8)
plt.grid()
plt.xlabel('ΔSWE (mm w.e.)', fontsize=12)
plt.legend(loc='upper left')
plt.show()
plt.savefig('ENU/hist_SWE_diff.png', bbox_inches='tight')
plt.savefig('ENU/hist_SWE_diff.pdf', bbox_inches='tight')

''' calculate RMSE and MRB '''
# RMSE
rmse_manual = np.sqrt((np.sum(dmanual**2))/len(dmanual))
rmse_scale = np.sqrt((np.sum(dscale**2))/len(dscale))

# MRB
mrb_manual = (dmanual/all_daily.Manual).mean() * 100
mrb_scale = (dscale/all_daily.Scale).mean() * 100