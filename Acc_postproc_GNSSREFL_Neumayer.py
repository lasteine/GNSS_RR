""" Run GNSSREFL automatically for GNSS interferometric reflectometry (GNSS-IR)
    for snow/firn accumulation estimation at the surroundings of the NeumayerIII station

https://github.com/kristinemlarson/gnssrefl

Reference:  - Steiner et al., Combined GNSS reflectometry/refractometry for continuous in situ surface mass balance estimation on an Antarctic ice shelf, AGU, 2022.
            - Kristine M. Larson. (2021). kristinemlarson/gnssrefl: First release (1.0.10). Zenodo. https://doi.org/10.5281/zenodo.5601495
            - Thomas Nischan (2016): GFZRNX - RINEX GNSS Data Conversion and Manipulation Toolbox. GFZ Data Services. https://doi.org/10.5880/GFZ.1.1.2016.002

input:  - GNSS-IR config file (.json)
        - GNSS base file (rinex 2.xx)
        - GNSS rapid navigation ephemerides file (.nav); ftp://isdcftp.gfz-potsdam.de/gnss/products/rapid/w????/*.SP3* (???? = gpsweek, sample sp3 = 'GFZ0OPSRAP_20230930000_01D_05M_ORB.SP3.gz')

output: - Reflector height (.txt) file; (year, doy, RH, sat, UTCtime, Azim, Amp, eminO, emaxO, NumbOf, freq, rise, EdotF, PkNoise, DelT, MJD, refr-appl)

requirements:   - install gnssrefl on Linux/Mac (gnssrefl is not working on Windows, see gnssrefl docs)
                - gnssrefl (https://github.com/kristinemlarson/gnssrefl)
                - gfzrnx (https://dataservices.gfz-potsdam.de/panmetaworks/showshort.php?id=escidoc:1577894)
                - wget
                - 7zip
                - path to all programs added to the system environment variables

created by: L. Steiner (Orchid ID: 0000-0002-4958-0849)
created on: 03.05.2023
updated on: 05.05.2023
"""

# IMPORT modules
import os
import functions as f
import datetime as dt
import gnsscal
import subprocess
import glob
import shutil
from termcolor import colored
from datetime import date


# CHOOSE: DEFINE data paths, file names (base, rover, navigation orbits, precise orbits, config), time interval, and processing steps !!!
gnssir_path = '//wsl.localhost/Ubuntu/home/sladina/test/gnssrefl/'
json = gnssir_path + '/data/input/nmlb.json'
sp3_outdir = gnssir_path + 'data/temp/orbits/'
rin_temp = gnssir_path + 'data/temp/rin3/'
raporbit_path = 'ftp://isdcftp.gfz-potsdam.de/gnss/products/rapid'
dest_path = 'C:/Users/sladina.BGEO02P102/Documents/SD_Card/Postdoc/AWI/05_Analysis/Run_RTKLib/data_neumayer/'    # data destination path for processing
base_name = 'NMLB'


# Q: download, unzip, rename rapid orbits (need to match the gnssrefl input format!)
# create temporary processing folder in temp orbit dir
sp3_tempdir = sp3_outdir + 'processing/'
if not os.path.exists(sp3_tempdir):
    os.makedirs(sp3_tempdir, exist_ok=True)

# get newest year, doy from orbit file from temp orbit dir
yeardoy_newest = sorted(glob.glob(sp3_outdir + '*.gz'), reverse=True)[0].split('_')[1]
year_newest = int(yeardoy_newest[:4])
doy_newest = int(yeardoy_newest[4:7])

# convert to gpsweek and day of week (dow)
gpsweek_newest, dow_newest = gnsscal.yrdoy2gpswd(year_newest, doy_newest)

# convert today to gpsweek and day of week (dow)
gpsweek_today, dow_today = gnsscal.date2gpswd(date.today())

# define ftp subdirectories to download newly available orbit files
gpsweek_list = list(range(gpsweek_newest, gpsweek_today+1, 1))

for gpswk in gpsweek_list:
    download_path = raporbit_path + 'w' + str(gpswk) + '/'
    # download all .SP3 rapid orbits from ftp server's subfolders
    subprocess.call('wget -r -np -nc -nH --cut-dirs=4 -A .SP3.gz ' + download_path + ' -P ' + sp3_tempdir)

print(colored("\nGFZ rapid orbits downloaded to: %s" % sp3_outdir, 'blue'))


# unzip all files
subprocess.call(r'7z e -y ' + sp3_tempdir + ' -o' + sp3_tempdir)
print(colored("\nGFZ rapid orbits unzipped", 'blue'))


# rename & move extracted orbits to match the gfzrnx input format
for orbit_file in glob.glob(sp3_tempdir + '*.SP3'):
    # define input and output filename
    infile = os.path.basename(orbit_file)
    outfile = infile[1:5] + 'MGX' + infile[8:]
    print('\nrename orbit file from: ', infile, ' to: ', outfile)

    # rename the file
    os.rename(orbit_file, os.path.dirname(orbit_file) + '/' + outfile)

    # define dest dir
    year = outfile.split('_')[1][:4]
    dest_dir = gnssir_path + 'data/' + year + '/sp3/'

    # move file to data directory for gnssrefl if it does not already exist
    if not os.path.exists(dest_dir + outfile):
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        shutil.move(os.path.dirname(orbit_file) + '/' + outfile, dest_dir)
        print("orbit file moved to yearly sp3 dir %s" % dest_dir)
    else:
        os.remove(os.path.dirname(orbit_file) + '/' + outfile)
        print("file in destination already exists, move aborted, file removed")
print(colored("\nGFZ rapid orbits renamed and moved to yearly (e.g. 2021): %s" % dest_dir, 'blue'))

# move zipped original orbit files (.gz) to parent dir
for f in glob.iglob(sp3_tempdir + '*.gz', recursive=True):
    shutil.move(f, sp3_outdir)
print("original zipped orbit files (.gz) moved to parent dir %s" % sp3_outdir)

# remove temporary processing directory
shutil.rmtree(sp3_tempdir)


# Q: copy, rename, convert, move rinex files
for rinex_file in sorted(glob.glob(dest_path + '3387*0.*[olng]'), reverse=True):
    # copy base rinex obs [o] and nav [lng] files
    f.copy_file_no_overwrite(dest_path, rin_temp, os.path.basename(rinex_file))

    # rename base rinex files if not exist
    outfile = base_name.lower() + os.path.basename(rinex_file)[4:]
    if not os.path.exists(rin_temp + '/' + outfile):
        os.rename(rin_temp + os.path.basename(rinex_file), rin_temp + '/' + outfile)
    else:
        os.remove(rin_temp + os.path.basename(rinex_file))

print(colored("\nRinex3 files copied and renamed to: %s" % rin_temp, 'blue'))


# convert rinex3 to rinex2 files and resample to 30s sampling rate (instead of 1Hz)
doy = []
for rinex_file in sorted(glob.glob(rin_temp + '*o'), reverse=True):
    year = '20' + os.path.basename(rinex_file)[-3:-1]
    doy_new = os.path.basename(rinex_file).split('.')[0][-4:-1]
    doy.append(doy_new)
    if not os.path.exists(gnssir_path + 'data/rinex/' + base_name.lower() + '/' + year + '/' + os.path.basename(rinex_file)):
        print(rinex_file)
        if not os.path.exists(gnssir_path + 'data/rinex/' + base_name.lower() + '/' + year + '/'):
            os.makedirs(gnssir_path + 'data/rinex/' + base_name.lower() + '/' + year + '/', exist_ok=True)
        subprocess.call(r'gfzrnx -finp ' + rinex_file + ' -vo 2 -smp 30 -fout ' + gnssir_path + 'data/rinex/' + base_name.lower() + '/' + year + '/::RX2::')

print(colored("\nRinex3 files converted to rinex2 and moved to yearly (e.g. 2021): %s" % gnssir_path + 'data/rinex/' + base_name.lower() + '/' + year + '/', 'blue'))

# return start and end year, doy for GNSS-IR processing
year_start = year[-1]   # '2021'
doy_start = doy[-1]    # '330'
year_end = year[0]
doy_end = doy[0]

# Q: Run GNSS-IR - needs linux or Mac (now run by bashscript 'run_gnssrefl_ubuntu_sh')
# convert rin2 to SNR files
# subprocess.call(r'rinex2snr ' + base_name.lower() + ' ' + year_start + ' ' + doy_start + ' -nolook=True -year_end ' + year_end + ' -doy_end ' + doy_end + ' -orb gnss -overwrite=True', shell=True)

# do reflectometry
# subprocess.call(r'gnssir ' + base_name.lower() + ' ' + year_start + ' ' + doy_start + ' -plt=False -year_end ' + year_end + ' -doy_end ' + doy_end, shell=True)

# TODO: put all steps in separate functions
