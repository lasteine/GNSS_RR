""" Run 'GNSSREFL' software automatically for GNSS interferometric reflectometry (GNSS-IR)
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
updated on: 10.05.2023
"""

# IMPORT modules
import functions as f


# CHOOSE: DEFINE paths, config file, and filenames !!!
dest_path = 'C:/Users/sladina.BGEO02P102/Documents/SD_Card/Postdoc/AWI/05_Analysis/Run_RTKLib/data_neumayer/'    # data destination path for processing
gnssir_path = '//wsl.localhost/Ubuntu/home/sladina/test/gnssrefl/'      # GNSS-Reflectometry ('gnssrefl') working directory (on Ubuntu)
raporbit_path = 'ftp://isdcftp.gfz-potsdam.de/gnss/products/rapid'      # GFZ data server from where GNSS rapid orbits are downloaded
sp3_outdir = gnssir_path + 'data/temp/orbits/'                          # temporary output directory to store & convert downloaded orbit files
rin_temp = gnssir_path + 'data/temp/rin3/'                              # temporary output directory to copy & convert rinex observation files
json = gnssir_path + '/data/input/nmlb.json'                            # path to gnssrefl configfile '.json'
base_name = 'NMLB'                                                      # prefix of base rinex observation files, e.g. station name


""" 0. Preprocess data """
# Q: Prepare GNSS orbit & observation files for 'gnssrefl'
# download, unzip, rename & move GNSS rapid orbit files
f.prepare_orbits(sp3_outdir, raporbit_path, gnssir_path)

# copy, rename, convert & move GNSS rinex observation files
year_start, year_end, doy_start, doy_end = f.prepare_obs(dest_path, rin_temp, base_name, gnssir_path)


""" 1. run 'GNSSREFL' automatically (on Linux) """
# Q: Run GNSS-IR (now run by bashscript 'run_gnssrefl_ubuntu_sh' on Ubuntu App)
# convert rin2 to SNR files
# subprocess.call(r'rinex2snr ' + base_name.lower() + ' ' + year_start + ' ' + doy_start + ' -nolook=True -year_end ' + year_end + ' -doy_end ' + doy_end + ' -orb gnss -overwrite=True', shell=True)

# do reflectometry
# subprocess.call(r'gnssir ' + base_name.lower() + ' ' + year_start + ' ' + doy_start + ' -plt=False -year_end ' + year_end + ' -doy_end ' + doy_end, shell=True)
