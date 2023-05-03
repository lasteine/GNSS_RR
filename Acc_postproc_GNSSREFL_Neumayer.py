""" Run GNSSREFL automatically for GNSS interferometric reflectometry (GNSS-IR)
    for snow/firn accumulation estimation at the surroundings of the NeumayerIII station

https://github.com/kristinemlarson/gnssrefl

Reference:  - Steiner et al., Combined GNSS reflectometry/refractometry for continuous in situ surface mass balance estimation on an Antarctic ice shelf, AGU, 2022.
            - Kristine M. Larson. (2021). kristinemlarson/gnssrefl: First release (1.0.10). Zenodo. https://doi.org/10.5281/zenodo.5601495

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
import subprocess
import glob
import shutil
from termcolor import colored


# CHOOSE: DEFINE data paths, file names (base, rover, navigation orbits, precise orbits, config), time interval, and processing steps !!!
gnssir_path = '//wsl.localhost/Ubuntu/home/sladina/test/gnssrefl/'
json = gnssir_path + '/data/input/nmlb.json'
sp3_outdir = gnssir_path + 'data/temp/orbits/'
rin_temp = gnssir_path + 'data/temp/rin3/'
raporbit_path = 'ftp://isdcftp.gfz-potsdam.de/gnss/products/rapid'   # later: subdir /w????/ > 2184
dest_path = 'C:/Users/sladina.BGEO02P102/Documents/SD_Card/Postdoc/AWI/05_Analysis/Run_RTKLib/data_neumayer/'    # data destination path for processing
prefix = 'nmlb'


# Q: download, unzip, rename rapid orbits (need to match the gnssrefl input format!)
# download all .SP3 rapid orbits from ftp server's subfolders
subprocess.call('wget -r -np -nc -nH --cut-dirs=4 -A .SP3.gz ' + raporbit_path + ' -P ' + sp3_outdir)
print(colored("\nGFZ rapid orbits downloaded to: %s" % sp3_outdir, 'blue'))

# unzip all files
subprocess.call(r'7z e -y ' + sp3_outdir + ' -o' + sp3_outdir)
print(colored("\nGFZ rapid orbits unzipped", 'blue'))

# rename & move extracted orbits to match the gfzrnx input format
for orbit_file in glob.glob(sp3_outdir + '*.SP3'):
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
        print("file in destination already exists, move aborted")
print(colored("\nGFZ rapid orbits renamed and moved to yearly (e.g. 2021): %s" % dest_dir, 'blue'))


# Q: copy, rename, convert, move rinex files
for rinex_file in glob.glob(dest_path + '3387*0.*[olng]'):
    # copy base rinex obs [o] and nav [lng] files
    f.copy_file_no_overwrite(dest_path, rin_temp, os.path.basename(rinex_file))

    # rename base rinex files if not exist
    outfile = prefix + os.path.basename(rinex_file)[4:]
    if not os.path.exists(rin_temp + '/' + outfile):
        os.rename(rin_temp + os.path.basename(rinex_file), rin_temp + '/' + outfile)
    else:
        os.remove(rin_temp + os.path.basename(rinex_file))

print(colored("\nRinex3 files copied and renamed to: %s" % rin_temp, 'blue'))


# convert rinex3 to rinex2 files and resample to 30s sampling rate (instead of 1Hz)
for rinex_file in glob.glob(rin_temp + '*o'):
    year = '20' + os.path.basename(rinex_file)[-3:-1]
    if not os.path.exists(gnssir_path + 'data/rinex/' + prefix + '/' + year + '/' + os.path.basename(rinex_file)):
        print(rinex_file)
        if not os.path.exists(gnssir_path + 'data/rinex/' + prefix + '/' + year + '/'):
            os.makedirs(gnssir_path + 'data/rinex/' + prefix + '/' + year + '/', exist_ok=True)
        subprocess.call(r'gfzrnx -finp ' + rinex_file + ' -vo 2 -smp 30 -fout ' + gnssir_path + 'data/rinex/' + prefix + '/' + year + '/::RX2::')

print(colored("\nRinex3 files converted to rinex2 and moved to yearly (e.g. 2021): %s" % gnssir_path + 'data/rinex/' + prefix + '/' + year + '/', 'blue'))


# TODO: convert rin2 to SNR files


# TODO: run gnssrefl, do GNSS-IR


# TODO: rename, copy GNSS-IR solutions


# TODO: put all steps in separate functions


