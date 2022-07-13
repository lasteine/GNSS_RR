""" Run RTKLib automatically for differential GNSS processing
http://www.rtklib.com/

input:  - GNSS options file (.conf)
        - GNSS rover file (rinex)
        - GNSS base file (rinex)
        - GNSS navigation ephemerides file (.nav); https://cddis.nasa.gov/Data_and_Derived_Products/GNSS/broadcast_ephemeris_data.html#GPSdaily
        - GNSS precise ephemerides file (.eph/.sp3); https://cddis.nasa.gov/Data_and_Derived_Products/GNSS/orbit_products.html
output: - position (.pos) file; (UTC, X, Y, Z)
created: LS

"""

# IMPORT modules
import subprocess
import os

# DEFINE year, files(base, rover, navigation orbits, precise orbits), time interval
yy = str(17)
base = 'WJLR'
rover = 'WJU1'  # 'WJL0'
nav = 'alrt'
sp3 = 'COD'
ti_int = '900'
options = 'rtkpost_options_Ladina'  # 'rtkpost_options_Ladina_Leica'
resolution = '15min'


# example: 
# process1 = subprocess.Popen('cd data && rnx2rtkp -k rtkpost_options_Ladina.conf -ti 3600 -o sol/out_doy4.pos '
#                            'WJU10040.17O WJLR0040.17O alrt0040.17n COD17004.eph',
#                            shell= True,
#                            stdout=subprocess.PIPE,
#                            stderr=subprocess.PIPE)
#
# stdout1, stderr1 = process1.communicate()
# print(stdout1)
# print(stderr1)


# iterator for 3-digit numbers (001 etc.)
doy_list = ["%.3d" % i for i in range(36, 184)]

# for each day of year, do:
for doy in doy_list:
    doy = str(doy)
    print('doy: ', doy, doy[-1])

    # define input and output filenames (for some reason it's not working when input files are stored in subfolders!)
    base_file = base + doy + '0.' + yy + 'O'
    rover_file = rover + doy + '0.' + yy + 'O'
    broadcast_orbit = nav + doy + '0.' + yy + 'n'
    precise_orbit = sp3 + yy + doy + '.sp3'
    output_file = 'sol/' + rover + '/' + resolution + '/' + rover + doy + '.pos'

    # run RTKLib automatically (instead of RTKPost Gui manually)
    process = subprocess.Popen('cd data && rnx2rtkp '
                               '-k ' + options + '.conf '
                               '-ti ' + ti_int + ' '
                               '-o ' + output_file + ' '
                               + rover_file + ' ' + base_file + ' ' + broadcast_orbit + ' ' + precise_orbit,
                               shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()
    # print(stdout) # print processing output
    print(stderr)   # print processing errors

    # remove .stat files
    os.remove('data/' + output_file + '.stat')

print('\n\nfinished with all files :-)')


