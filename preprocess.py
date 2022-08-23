""" Functions to generate daily rinex 3.0x files from day-overlapping Emlid rinex files;
    Necessary preprocessing for daily file processing with RTKLib
    created by: L. Steiner
    created on: 17.05.2021
    updated on: 18.05.2021
"""

import subprocess
import os
import glob
import datetime
import shutil
import lzma
import tarfile
import time
import gnsscal
import datetime as dt
import pandas as pd
from termcolor import colored


""" Define general functions """


def create_folder(dest_path):
    """ create a directory if it is not already existing
    :param dest_path: path and name of new directory
    """
    # Q: create 'temp' directory if not existing
    if not os.path.exists(dest_path):
        os.makedirs(dest_path, exist_ok=True)
        print(colored("\ntemp dir created: %s" % dest_path, 'blue'))
    else:
        print(colored("\ntemp dir already existing: %s" % dest_path, 'blue'))


def remove_folder(dest_path):
    """ delete temporary directory
    :param dest_path: local temporary directory for preprocessing the GNSS rinex files
    """
    shutil.rmtree(dest_path)
    print(colored("\n!!! temporary directory removed: %s" % dest_path, 'blue'))


""" Define preprocessing functions """


def move_files2parentdir(dest_path, f):
    """ move files from temporary preprocessing to main processing directory (parent directory)
    :param dest_path: local temporary directory for preprocessing the GNSS rinex files
    :param f: file in folder
    """
    # get parent directory
    parent_dir = os.path.dirname(os.path.dirname(dest_path))
    # destination file in parent directory
    dest_path_file = os.path.join(parent_dir, f.split("\\")[-1])
    # move file if it does not already exist
    if not os.path.exists(dest_path_file):
        shutil.move(f, parent_dir)
        print("obs files moved to parent dir %s" % dest_path_file)
    else:
        print(colored("file in destination already exists, move aborted: %s" % dest_path_file, 'yellow'))


def check_existing_files(dest_path, rover):
    """ check if rinex files are already available in the processing directory, otherwise copy & uncompress files from server
    :param dest_path: temp directory for preprocessing the GNSS rinex files
    :param rover: rover file name prefix
    :return: doy_max: maximum doy in existing files, newer doys should be copied
    """
    # Q: get list of yydoys in processing folder for receiver
    # get parent directory
    parent_dir = os.path.dirname(os.path.dirname(dest_path))
    print('parent dir: ', parent_dir)

    # get newest year of files in processing folder
    years = ['0']
    for f in glob.iglob(parent_dir + '/' + rover + '???0.*O'):
        # extract doy from filename
        year = os.path.basename(f).split('.')[1][:2]
        # add doy to series of doys
        years.append(year)

    # get newest doy and return
    year_max = max(years)
    print(colored('newest year in existing files of parent dir: %s' % year_max, 'blue'))

    # get newest doy of files in processing folder
    doys = ['0']
    for f in glob.iglob(parent_dir + '/' + rover + '???0.' + year_max + 'O'):
        # extract doy from filename
        doy = os.path.basename(f).split('.')[0][4:7]
        # add doy to series of doys
        doys.append(doy)

    # get newest doy and return
    doy_max = max(doys)
    print(colored('newest doy in existing files of parent dir: %s' % doy_max, 'blue'))

    return year_max, doy_max


def copy_file_no_overwrite(source_path, dest_path, file_name):
    """ copy single files without overwriting existing files
    :param source_path: source directory
    :param dest_path: destination directory
    :param file_name: name of file to copy
    """
    # construct the src path and file name
    source_path_file = os.path.join(source_path, file_name)

    # construct the dest path and file name
    dest_path_file = os.path.join(dest_path, file_name)

    # test if the dest file exists, if false, do the copy, or else abort the copy operation.
    if not os.path.exists(dest_path_file):
        shutil.copyfile(source_path_file, dest_path_file)
        print(colored("\ncopy from %s to %s \nok" % (source_path_file, dest_path_file), 'blue'))
    else:
        print("\nfile in destination already exists: %s, \ncopy aborted!!!" % dest_path_file)
    pass


def copy_rinex_files(source_path, dest_path, receiver=['NMLB', 'NMLR', 'NMER'], copy=[True, False], move=[True, False], delete_temp=[True, False]):
    """ copy rinex files of remote directory to a local temp directory if it does not already exist
        & uncompress files, keep observation (and navigation) files
        & delete compressed files and subfolders afterwards
    :param source_path: remote directory hosting compressed GNSS rinex files
    :param dest_path: local directory for processing the GNSS rinex files
    :param receiver: high-end (Leica) or low-cost (Emlid), needs to be treated differently
    :param copy: do you want to copy (True) the data or skip copying (False) the data and just decompress and further?
    :param move: move renamed files to parent directory (True) or not (False)
    :param delete_temp: delete temporary directory (True) or not (False)
    """
    # Q: create temp directory if not existing
    create_folder(dest_path)

    # Q: check which rinex files are already existing in the processing directory
    # prepare file prefix
    if receiver == 'NMLR':
        rover = '3393'
    if receiver == 'NMLB':
        rover = '3387'
    if receiver == 'NMER':
        rover = receiver

    # Q: check already existing years and doys of files in processing directory, get newest yeardoy
    year_max, doy_max = check_existing_files(dest_path, rover)

    if receiver == 'NMER':
        # Q: copy files from network drive to local temp folder
        if copy is True:
            for f in glob.glob(source_path + '*.zip'):
                # construct the destination filename
                dest_file = os.path.join(dest_path, f.split("\\")[-1])
                # convert datetime to day of year (doy) from filename
                doy_file = datetime.datetime.strptime(os.path.basename(f).split('_')[2], "%Y%m%d%H%M").strftime('%j')
                yy_file = os.path.basename(f).split('_')[2][2:4]

                # Q: only copy files from server which are newer than the already existing doys of year=yy

                if yy_file == year_max and doy_file > doy_max:
                    # copy file if it does not already exist
                    if not os.path.exists(dest_file):
                        shutil.copy2(f, dest_path)
                        print("\nfile copied from %s to %s" % (f, dest_file))
                    else:
                        print(colored("\nfile in destination already exists: %s, \ncopy aborted!!!" % dest_file, 'yellow'))
                        continue

                    # Q: uncompress file
                    shutil.unpack_archive(dest_file, dest_path)
                    print('file decompressed: %s' % dest_file)
                else:
                    print(colored('file already preprocessed and available in the processing folder, skip file: %s' % f, 'yellow'))
                    pass

        else:
            pass

        # Q: delete nav & zipped files
        for f in glob.glob(dest_path + '*.*[BPzip]'):
            os.remove(f)
        print("nav files deleted %s" % dest_path)

        # Q: split & merge day-overlapping Emlid rinex files to daily rinex files (for Emlid files only!)
        dayoverlapping2daily_rinexfiles(dest_path, 'ReachM2_sladina-raw_', receiver, move, delete_temp)

    if receiver == 'NMLB' or receiver == 'NMLR':
        # Q: copy files from network drive to local temp folder
        if copy is True:
            for f in glob.glob(source_path + '*.tar.xz'):
                # create destination filename
                dest_file = dest_path + f.split("\\")[-1]
                doy_file = os.path.basename(f)[4:7]
                yy_file = os.path.basename(f).split('.')[1][:2]

                # Q: only copy files from server which are newer than the already existing doys of year=yy
                if yy_file == year_max and doy_file > doy_max:
                    # copy file if it does not already exist
                    if not os.path.exists(dest_file):
                        shutil.copy2(f, dest_path)
                        print("\nfile copied from %s to %s" % (f, dest_file))
                    else:
                        print(colored("\nfile in destination already exists: %s, \ncopy aborted!!!" % dest_file,
                                      'yellow'))
                        continue

                    # Q: uncompress .tar.xz file
                    with tarfile.open(fileobj=lzma.open(dest_file)) as tar:
                        tar.extractall(dest_path)
                        tar.close()
                        print('file decompressed: %s' % dest_file)
                else:
                    print(colored('file already preprocessed and available in the processing folder, skip file: %s' % f , 'yellow'))
                    pass
        else:
            pass

        # Q: move obs (and nav) files to parent dir
        time.sleep(60)
        if receiver == 'NMLB':
            # copy observation (.yyd) & navigation (.yy[ngl]) files from base receiver
            for f in glob.glob(dest_path + 'var/www/upload/' + receiver + '/*.*'):
                shutil.move(f, dest_path)
            print("obs & nav files moved to parent dir %s" % dest_path)
        if receiver == 'NMLR':
            # copy only observation (.yyd) files from rover receivers
            for f in glob.glob(dest_path + 'var/www/upload/' + receiver + '/*.*d'):
                shutil.move(f, dest_path)
            print("obs files moved to parent dir %s" % dest_path)

        # Q: convert hatanaka compressed rinex (.yyd) to uncompressed rinex observation (.yyo) files
        time.sleep(10)
        for hatanaka_file in glob.glob(dest_path + '*.*d'):
            print('decompress hatanaka file: ', hatanaka_file)
            subprocess.Popen('crx2rnx ' + hatanaka_file)

        # Q: move all obs (and nav) files from temp to parent directory
        time.sleep(60)
        if move is True:
            for f in glob.glob(dest_path + '*.*[ongl]'):
                move_files2parentdir(dest_path, f)
        else:
            print('files are NOT moved to parent directory!')

        # Q: delete temp directory
        if delete_temp is True:
            remove_folder(dest_path)
        else:
            print('temporary directory is NOT deleted!')


def convert_datetime2doy_rinexfiles(dest_path, rover_prefix, rover_name):
    """ convert Emlid file names to match format for 'gfzrnx' rinex conversion tools
    :param dest_path: local temporary directory for preprocessing the GNSS rinex files
    :param rover_prefix: prefix of rinex files in temp directory
    :param rover_name: name of rover receiver

    input filename: 'ReachM2_sladina-raw_202111251100.21O'  [rover_prefix + datetime + '.' + yy + 'O']
    output filename: 'NMER329[a..d].21o'                    [rover_prefix + doy + '0.' + yy + 'o']
    """
    # Q: get doy from rinex filenames in temp dir with name structure: 'ReachM2_sladina-raw_202112041058.21O' [rover_prefix + datetime + '.' + yy + 'O']
    for f in glob.iglob(dest_path + rover_prefix + '*.*O', recursive=True):
        # get rinex filename and year
        rover_file = os.path.basename(f)
        yy = rover_file.split('.')[-1][:2]
        # convert datetime to day of year (doy)
        doy = datetime.datetime.strptime(rover_file.split('.')[0].split('_')[2], "%Y%m%d%H%M").strftime('%j')
        # create new filename with doy
        new_filename = dest_path + rover_name + doy + 'a.' + yy + 'o'
        print('\nRover file: ' + rover_file, '\ndoy: ', doy, '\nNew filename: ', new_filename)

        # check if new filename already exists and rename file
        file_exists = os.path.exists(new_filename)  # True or False
        if file_exists is True:
            new_filename = dest_path + rover_name + doy + 'b.' + yy + 'o'
            # check if new filename already exists and rename file
            file_exists = os.path.exists(new_filename)  # True or False
            if file_exists is True:
                new_filename = dest_path + rover_name + doy + 'c.' + yy + 'o'
                # check if new filename already exists and rename file
                file_exists = os.path.exists(new_filename)  # True or False
                if file_exists is True:
                    new_filename = dest_path + rover_name + doy + 'd.' + yy + 'o'
                else:
                    os.rename(f, new_filename)
                    print('\nNew filename already existing --> renamed to: ', new_filename)
            else:
                os.rename(f, new_filename)
                print('\nNew filename already existing --> renamed to: ', new_filename)
        else:
            os.rename(f, new_filename)

    print(colored('\nfinished renaming all files', 'blue'))


def split_rinex(dest_path, rover_name):
    """ split day-overlapping rinex files at midnight --> get multiple subdaily files
    :param dest_path: local temporary directory for preprocessing the GNSS rinex files
    :param rover_name: name of rover receiver

    gfzrnx split input:  'NMER329[a..d].21o'    [rover + doy + '.' + yy + 'o']
    gfzrnx split output: '    00XXX_R_20213291100_01D_30S_MO.rnx'
    """
    for f in glob.iglob(dest_path + rover_name + '*.*o', recursive=True):
        # get filename
        rover_file = os.path.basename(f)
        print(colored('\nstart splitting day-overlapping rinex file: %s' % rover_file, 'blue'))

        # split rinex file at midnight with command: 'gfzrnx -finp NMER345.21o -fout ::RX3:: -split 86400'
        process1 = subprocess.Popen('cd ' + dest_path + ' && '
                                    'gfzrnx -finp ' + rover_file + ' -fout ::RX3:: -split 86400',
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)

        stdout1, stderr1 = process1.communicate()
        print(stdout1)
        print(stderr1)

    print(colored('\nfinished splitting all day-overlapping rinex files at: %s' % dest_path, 'blue'))


def rename_splitted_rinexfiles(dest_path, rover_name):
    """ rename gfzrnx splitted rinex files output names to match input for gfzrnx merge files:
    :param dest_path: local temporary directory for preprocessing the GNSS rinex files
    :param rover_name: name of rover receiver

    gfzrx split output: '    00XXX_R_20213291100_01D_30S_MO.rnx'
    gfzrx merge input:  'NMER00XXX_R_20213291100_01D_30S_MO.yyo'
    """
    # Q: rename all .rnx files (gfzrnx split output --> gfzrnx merge input)
    for f in glob.iglob(dest_path + '*.rnx', recursive=True):
        rover_file = os.path.basename(f)
        yy = rover_file.split('_')[2][2:4]
        new_filename = dest_path + rover_name + rover_file.split('.')[0][4:] + '.' + yy + 'o'
        print('\nRover file: ' + rover_file, '\nNew filename: ', new_filename)
        os.rename(f, new_filename)

    print(colored('\nfinished renaming all splitted rinex files', 'blue'))


def merge_rinex(dest_path):
    """ merge rinex files together per day --> get daily rinex files
    :param dest_path: local temporary directory for preprocessing the GNSS rinex files

    gfzrnx merge input:  'NMER00XXX_R_2021329????_01D_30S_MO.yyo'
    gfzrnx merge output: 'NMER00XXX_R_2021330????_01D_30S_MO.rnx'
    """
    for f in glob.iglob(dest_path + 'NMER00XXX_R_20' + '*.*O', recursive=True):
        # get filename
        rover_file = os.path.basename(f)
        yy = rover_file.split('_')[2][2:4]
        # extract doy
        doy = rover_file.split('.')[0][16:19]
        print('\nRover file: ' + rover_file, '\ndoy: ', doy)

        # merge rinex files per day with command: 'gfzrnx -finp NMER00XXX_R_2021330????_01D_30S_MO.21o' -fout ::RX3D:: -d 86400'
        process1 = subprocess.Popen('cd ' + dest_path + ' && '
                                    'gfzrnx -finp NMER00XXX_R_20' + yy + doy + '????_01D_30S_MO.' + yy + 'o -fout ::RX3D:: -d 86400',
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)

        stdout1, stderr1 = process1.communicate()
        print(stdout1)
        print(stderr1)

    print(colored('\nfinished merging all rinex files per day at: %s' % dest_path, 'blue'))


def rename_merged_rinexfiles(dest_path, rover_name, move=[True, False], delete_temp=[True, False]):
    """ rename gfzrnx merge files output names to match rtklib and leica rinex file names:
    :param dest_path: local temporary directory for preprocessing the GNSS rinex files
    :param rover_name: name of rover receiver
    :param move: move renamed files to parent directory (True) or not (False)
    :param delete_temp: delete temporary directory (True) or not (False)

    gfzrnx merge output: 'NMER00XXX_R_2021330????_01D_30S_MO.rnx'
    rtklib input: 'NMERdoy0.yyo'  [rover_prefix + doy + '0.' + yy + 'o']
    """
    for f in glob.iglob(dest_path + '*.rnx', recursive=True):
        rover_file = os.path.basename(f)
        yy = rover_file.split('_')[2][2:4]
        new_filename = dest_path + rover_name + rover_file.split('.')[0][16:19] + '0.' + yy + 'o'
        print('\nRover file: ' + rover_file, '\nNew filename: ', new_filename)
        os.rename(f, new_filename)

    print(colored('\nfinished renaming all merged rinex files', 'blue'))

    # move renamed files to parent directory
    if move is True:
        for f in glob.iglob(dest_path + 'NMER???0.*O', recursive=True):
            move_files2parentdir(dest_path, f)
    else:
        print('renamed merged daily files are NOT moved to parent directory!')

    # delete 'temp' directory and remaining files in 'temp' directory
    if delete_temp is True:
        remove_folder(dest_path)
    else:
        print('temporary directory is kept!')


def dayoverlapping2daily_rinexfiles(dest_path, rover_prefix, receiver, move=[True, False], delete_temp=[True, False]):
    """ convert day-overlapping Emlid rinex files to daily rinex files names to match rtklib input and leica files
        :param dest_path: local temporary directory for preprocessing the GNSS rinex files
        :param rover_prefix: prefix of rinex files in temp directory
        :param receiver: name of rover receiver ['NMER']
        """
    # create temporary directory if not already existing
    create_folder(dest_path)

    # convert Emlid files [rover_prefix + datetime + '.' + yy + 'O'] to format for 'gfzrnx' rinex conversion [rover_prefix + doy + '0.' + yy + 'o']
    convert_datetime2doy_rinexfiles(dest_path, rover_prefix, receiver)

    # split rinex files at midnight for day-overlapping files --> get subdaily rinex files
    split_rinex(dest_path, receiver)

    # rename splitted (subdaily) rinex files to match input for 'gfzrnx -merge'
    rename_splitted_rinexfiles(dest_path, receiver)

    # merge rinex files together per day --> get daily rinex files
    merge_rinex(dest_path)

    # rename merged (daily) rinex files to match rtklib input format [rover_prefix + doy + '0.' + yy + 'o'] & move to parent directory & delete temp dir
    rename_merged_rinexfiles(dest_path, receiver, move, delete_temp)


""" Define RTKLIB functions """


def automate_rtklib_pp(dest_path, rover_prefix, yy, ti_int, base_prefix, brdc_nav_prefix, precise_nav_prefix, resolution, ending, doy_start=0, doy_end=366, rover_name=['NMER_original', 'NMER', 'NMLR'], options=['options_Emlid', 'options_Leica']):
    """ create input and output files for running RTKLib post processing automatically
        for all rover rinex observation files (. yyo) available in the data path directory
        get doy from rover file names with name structure:
            Leica Rover: '33933650.21o' [rover + doy + '0.' + yy + 'o']
            Emlid Rover (pre-processed): 'NMER3650.21o' [rover + doy + '0.' + yy + 'o']
            Emlid Rover (original): 'ReachM2_sladina-raw_202112041058.21O' [rover + datetime + '.' + yy + 'O']
        :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file (all data needs to be in one folder)
        :param rover_prefix: prefix of rover rinex filename
        :param yy: year to process
        :param doy_start: start day of year (doy) for processing files, range (0, 365)
        :param doy_end: end doy for processing files, range (1, 366)
        :param resolution: processing time interval (in minutes)
        :param ending: suffix of solution file names (e.g. a varian of processing options: '_noglonass'
        :param ti_int: processing time interval (in seconds)
        :param base_prefix: prefix of base rinex filename
        :param brdc_nav_prefix: prefix of broadcast navigation filename
        :param precise_nav_prefix: prefix of precise orbit filename
        :param rover_name: name of rover
        :param options: rtkpost configuration file
    """
    # Q: run rtklib for all rover files in directory
    print(colored('\n\nstart processing files with RTKLIB from receiver: %s' % rover_name, 'blue'))
    for file in glob.iglob(dest_path + rover_prefix + '*.' + yy + 'O', recursive=True):
        # Q: get doy from rover filenames
        rover_file = os.path.basename(file)
        if rover_name == 'NMER_original':
            # get doy, converted from datetime in Emlid original filename format (output from receiver, non-daily files)
            doy = dt.datetime.strptime(rover_file.split('.')[0].split('_')[2], "%Y%m%d%H%M").strftime('%j')
        if rover_name == 'NMER' or rover_name == 'NMLR':
            # get doy directly from filename from Emlid pre-processed or Leica file name format (daily files)
            doy = rover_file.split('.')[0][4:7]

        # only process files of selected year and inbetween the selected doy range
        if doy_start <= int(doy) <= doy_end:
            print('\nProcessing rover file: ' + rover_file, '; doy: ', doy)

            # convert doy to gpsweek and day of week (needed for precise orbit file names)
            (gpsweek, dow) = gnsscal.yrdoy2gpswd(int('20' + yy), int(doy))

            # define input and output filenames (for some reason it's not working when input files are stored in subfolders!)
            base_file = base_prefix + doy + '0.' + yy + 'O'
            broadcast_orbit_gps = brdc_nav_prefix + doy + '0.' + yy + 'n'
            broadcast_orbit_glonass = brdc_nav_prefix + doy + '0.' + yy + 'g'
            broadcast_orbit_galileo = brdc_nav_prefix + doy + '0.' + yy + 'l'
            precise_orbit = precise_nav_prefix + str(gpsweek) + str(dow) + '.EPH_M'
            output_file = 'sol/' + rover_name + '/' + resolution + '/20' + yy + '_' + rover_name + doy + ending + '.pos'

            # create a solution directory if not existing
            os.makedirs(dest_path + 'sol/' + rover_name + '/' + resolution + '/', exist_ok=True)

            # Q: change directory to data directory & run RTKLib post processing command
            run_rtklib_pp(dest_path, options, ti_int, output_file, rover_file, base_file,
                          broadcast_orbit_gps, broadcast_orbit_glonass, broadcast_orbit_galileo, precise_orbit)

    print(colored('\n\nfinished processing all files with RTKLIB from receiver: %s' % rover_name, 'blue'))


def run_rtklib_pp(dest_path, options, ti_int, output_file, rover_file, base_file, brdc_orbit_gps, brdc_orbit_glonass, brdc_orbit_galileo, precise_orbit):
    """ run RTKLib post processing command (rnx2rtkp) as a subprocess (instead of manual RTKPost GUI)
        example: 'rnx2rtkp -k rtkpost_options.conf -ti 900 -o sol/NMLR/15min/NMLRdoy.pos NMLR0040.17O NMLB0040.17O NMLB0040.17n NMLB0040.17g NMLB0040.17e COD17004.eph'
        :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file (all data needs to be in one folder)
        :param options: rtkpost configuration file
        :param ti_int: processing time interval (in seconds)
        :param output_file: rtkpost solution file
        :param rover_file: GNSS observation file (rinex) from the rover receiver
        :param base_file: GNSS observation file (rinex) from the base receiver
        :param brdc_orbit_gps: GNSS broadcast (predicted) orbit for GPS satellites
        :param brdc_orbit_glonass: GNSS broadcast (predicted) orbit for GLONASS satellites
        :param brdc_orbit_galileo: GNSS broadcast (predicted) orbit for GALILEO satellites
        :param precise_orbit: GNSS precise (post processed) orbit for multi-GNSS (GPS, GLONASS, GALILEO, BEIDOU)
    """
    # change directory & run RTKLIB post processing command
    process = subprocess.Popen('cd ' + dest_path + ' && rnx2rtkp '
                               '-k ' + options + '.conf '
                               '-ti ' + ti_int + ' '
                               '-o ' + output_file + ' '
                               + rover_file + ' ' + base_file + ' ' + brdc_orbit_gps + ' ' + brdc_orbit_glonass + ' ' + brdc_orbit_galileo + ' ' + precise_orbit,
                               shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

    stdout, stderr = process.communicate()
    # print(stdout) # print processing output
    print(stderr)  # print processing errors


def get_rtklib_solutions(dest_path, rover_name, resolution, ending, header_length):
    """  get daily rtklib ENU solution files from solution directory and store all solutions in one (whole season) dataframe and pickle
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :param rover_name: name of rover
    :param resolution: processing time interval (in minutes)
    :param ending: suffix of solution file names (e.g. a varian of processing options: '_noglonass'
    :return: df_enu (pandas dataframe containing all seasons solution data columns ['date', 'time', 'U', 'amb_state', 'nr_sat', 'std_u'])
    """
    # create empty dataframe for all .ENU solution files
    df_enu = pd.DataFrame()

    # Q read all .ENU files in solution directory, parse date and time columns to datetimeindex and add them to the dataframe
    print(colored('\n\nstart reading all ENU solution files from receiver: %s' % rover_name, 'blue'))
    for file in glob.iglob(dest_path + 'sol/' + rover_name + '/' + resolution + '/*' + ending + '.pos', recursive=True):
        print('\nreading ENU file: %s' % file)
        enu = pd.read_csv(file, header=header_length, delimiter=' ', skipinitialspace=True, index_col=['date_time'],
                          na_values=["NaN"],
                          usecols=[0, 1, 4, 5, 6, 9], names=['date', 'time', 'U', 'amb_state', 'nr_sat', 'std_u'],
                          parse_dates=[['date', 'time']])
        df_enu = pd.concat([df_enu, enu], axis=0)

    # store dataframe as binary pickle format
    df_enu.to_pickle(dest_path + 'sol/' + rover_name + '_' + resolution + ending + '.pkl')

    print(colored('\nstored all ENU solution data in dataframe df_enu:', 'blue'))
    print(df_enu)
    print(colored('\nstored all ENU solution data in pickle: ' + 'sol/' + rover_name + '_' + resolution + ending + '.pkl', 'blue'))

    return df_enu


def filter_rtklib_solutions(dest_path, df_enu, rover_name, resolution, ambiguity=[1, 2, 5], ti_set_swe2zero=12, threshold=3, window='D', resample=[True, False], resample_resolution='30min', ending=''):
    """ filter and clean ENU solution data (outlier filtering, median filtering, adjustments for observation mast heightening)
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :param df_enu: pandas dataframe containing all seasons solution data columns ['date', 'time', 'U (m)', 'amb_state', 'nr_sat', 'std_u (m)']
    :param rover_name: name of rover
    :param resolution: processing time interval (in minutes)
    :param ambiguity: ambiguity resolution state [1: fixed, 2: float, 5: standalone]
    :param ti_set_swe2zero: number of hours used to set swe to zero (default=12 hours)
    :param threshold: set threshold for outlier removing using the standard deviation (default=3 sigma)
    :param window: window for median filter (default='D')
    :param resample: resample data to match the reference data's resolution (True) or not (False)
    :param resample_resolution: resolution for resampling the data (e.g., the resolution of the reference data)
    :param ending: suffix of solution file names (e.g. a varian of processing options: '_noglonass'
    :return: df_enu, fil_df, fil, fil_clean, m, s, jump, swe_gnss, swe_gnss_daily, std_gnss_daily
    """
    # Q: read all data from .pkl if no df_enu is provided
    if df_enu is None:
        print(colored('\nENU solution dataframe is NOT available, reading from pickle: %s' % 'sol/' + rover_name + '_' + resolution + ending + '.pkl', 'yellow'))
        df_enu = pd.read_pickle(dest_path + 'sol/' + rover_name + '_' + resolution + ending + '.pkl')

    print(colored('\nENU solution dataframe is available, start filtering data', 'blue'))

    # Q: select only data where ambiguities are fixed (amb_state==1) or float (amb_state==2) and sort datetime index
    print('\nselect data with ambiguity solution state: %s' % ambiguity)
    fil_df = pd.DataFrame(df_enu[(df_enu.amb_state == ambiguity)])
    fil_df.index = pd.DatetimeIndex(fil_df.index)
    fil_df = fil_df.sort_index()

    # adapt up values to reference SWE values in mm (median of first hours)
    swe_zero = int((60/int(resolution[:2]))*ti_set_swe2zero)    # get number of observations to use to set swe to zero
    fil = (fil_df.U - fil_df.U[:swe_zero].median()) * 1000

    # Q: remove outliers based on x*sigma threshold
    print('\nremove outliers based on %s * sigma threshold' % threshold)
    upper_limit = fil.median() + threshold * fil.std()
    lower_limit = fil.median() - threshold * fil.std()
    fil_clean = fil[(fil > lower_limit) & (fil < upper_limit)]

    # Q: filter data with a rolling median and, if necessary, resample resolution to fit reference data resolution
    if resample is True:
        print('\ndata is median filtered (window length = %s) and resampled to %s resolution' % window % resample_resolution)
        resolution = resample_resolution
        m = fil_clean.rolling(window).median().resample(resample_resolution).median()
    else:
        print('\ndata is median filtered with window length: %s' % window)
        m = fil_clean.rolling(window).median()
    s = fil_clean.rolling(window).std()

    # Q: adjust for snow mast heightening (approx. 3m elevated several times a year)
    print('\ndata is corrected for snow mast heightening events (remove sudden jumps > 1m)')
    jump = m[(m.diff() < -1000)]  # detect jumps (> 1000mm) in the dataset

    if jump.empty is True:
        print('\nno jump detected!')
        swe_gnss = m - m[0]
    else:
        print('\njump of height %s is detected!' % jump[0])
        adj = m[(m.index > jump.index.format()[0])] - jump[0]  # correct jump [0]
        m_adj = m[~(m.index >= jump.index.format()[0])].append(adj)  # adjusted dataset
        swe_gnss = m_adj - m_adj[0]

    swe_gnss.index = swe_gnss.index + pd.Timedelta(seconds=18)

    # resample data per day, calculate median and standard deviation (noise) per day to fit manual reference data
    swe_gnss_daily = swe_gnss.resample('D').median()
    std_gnss_daily = swe_gnss.resample('D').std()

    # Q: store swe results to pickle
    print(colored('\ndata is filtered, cleaned, and corrected and SWE results are stored to pickle and .csv: %s' % 'sol/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl', 'blue'))
    os.makedirs(dest_path + 'sol/SWE_results/', exist_ok=True)
    swe_gnss.to_pickle(dest_path + 'sol/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl')
    swe_gnss.to_csv(dest_path + 'sol/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.csv')

    return df_enu, fil_df, fil, fil_clean, m, s, jump, swe_gnss, swe_gnss_daily, std_gnss_daily


def read_swe_gnss(dest_path, swe_gnss, rover_name, resolution, ending):
    # read gnss swe results from pickle
    if swe_gnss is None:
        print(colored('\nSWE results are NOT available, reading from pickle: %s' % 'sol/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl', 'orange'))
        swe_gnss = pd.read_pickle(dest_path + 'sol/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl')

    return swe_gnss


def read_manual_observations(dest_path):
    """ read and interpolate manual accumulation (cm), density (kg/m^3), SWE (mm w.e.) data
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :return: manual2, ipol
    """
    # read data
    print('\nread manual observations')
    manual = pd.read_csv(dest_path + '03_Densitypits/Manual_Spuso.csv', header=1, skipinitialspace=True,
                         delimiter=';', index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0], dayfirst=True,
                         names=['Acc', 'Density', 'SWE', 'Density_aboveAnt', 'SWE_aboveAnt'])
    manual2 = manual
    manual2.index = manual2.index + pd.Timedelta(days=0.2)

    # interpolate manual data
    print('\ninterpolate manual reference observations')
    ipol = manual.Density_aboveAnt.resample('min').interpolate(method='linear', limit_direction='backward')

    return manual2, ipol


def read_snowbuoy_observations(dest_path):
    """ read snow buoy accumulation data from four sensors & pressure, airtemp
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :return: buoy
    """
    # Q: read snow buoy data
    print('\nread snow buoy observations')
    buoy_all = pd.read_csv(dest_path + '06_SHM/Snowbuoy/2017S54_300234011695900_proc.csv', header=0,
                           skipinitialspace=True, delimiter=',', index_col=0, skiprows=0, na_values=["NaN"],
                           parse_dates=[0],
                           names=['lat', 'lon', 'sh1', 'sh2', 'sh3', 'sh4', 'pressure', 'airtemp', 'bodytemp',
                                  'gpstime'])

    # select only data from season 21/22
    buoy = buoy_all['2021-11-26':]

    # Q: Differences in accumulation
    # calculate change in accumulation (in mm) for each buoy sensor add it as an additional column to the dataframe buoy
    for i in range(4):
        buoy['dsh' + str(i+1)] = (buoy['sh' + str(i + 1)] - buoy['sh' + str(i + 1)][0]) * 1000

        # calculate accumulation gain on 2021-12-23
        print('Accumulation gain on 2021-12-23 for buoy dsh' + str(i + 1) + ': ',
              round(buoy['dsh' + str(i+1)].dropna()['2021-12-23'][1], 1))

    return buoy


def read_pole_observations(dest_path):
    """ read Pegelfeld Spuso accumulation data from 16 poles
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :return: poles
    """
    print('\nread Pegelfeld Spuso pole observations')
    poles = pd.read_csv(dest_path + '03_Densitypits/Pegelfeld_Spuso_Akkumulation.csv', header=0, delimiter=';',
                        index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0], dayfirst=True)

    return poles


def read_laser_observations(dest_path, ipol, laser_pickle='shm/nm_shm.pkl', resample_resolution='15min'):
    """ read snow accumulation observations (minute resolution) from laser distance sensor data
    :param resample_resolution: resolution for resampling the data (e.g., the resolution of the reference data)
    :param ipol: interpolated density data from manual reference observations
    :param laser_pickle: read logfiles (laser_pickle == None) or pickle (e.g., 'shm/nm_shm.pkl') creating/containing snow accumulation observations from laser distance sensor
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :return: df_shm, h, fil_h_clean, h_resampled, h_std_resampled, sh, sh_std
    """
    # Q: read snow accumulation observations (minute resolution) from laser distance sensor data
    if laser_pickle is None:
        print(colored('\nlaser observations are NOT available as pickle, reading all logfiles: shm/nm*.log', 'yellow'))
        # create empty dataframe for all .log files
        df_shm = pd.DataFrame()
        # read all snow accumulation.log files in folder, parse date and time columns to datetimeindex and add them to the dataframe
        for file in glob.iglob(dest_path + 'shm/nm*.log', recursive=True):
            print(file)
            # header: 'date', 'time', 'snow level (m)', 'signal(-)', 'temp (°C)', 'error (-)', 'checksum (-)'
            shm = pd.read_csv(file, header=0, delimiter=r'[ >]', skipinitialspace=True, na_values=["NaN"], names=['date', 'time', 'none','h', 'signal', 'temp', 'error', 'check'], usecols=[0,1,3,5,6],
                              encoding='latin1', parse_dates=[['date', 'time']], index_col=['date_time'], engine='python', dayfirst=True)
            df_shm = pd.concat([df_shm, shm], axis=0)

        # store as .pkl
        df_shm.to_pickle(dest_path + 'shm/nm_shm.pkl')

    else:
        print(colored('\nlaser observations are available as pickle: %s' % laser_pickle, 'yellow'))
        df_shm = pd.read_pickle(dest_path + laser_pickle)

    # Q: filter laser observations
    print('\nfiltering laser observations')
    # select only observations without errors (in mm)
    h = df_shm[(df_shm.error == 0)].h * 1000
    # adapt to reference SWE values
    fil_h = (h - h[0])

    # clean outliers
    ul = fil_h.median() + 1 * fil_h.std()
    ll = fil_h.median() - 1 * fil_h.std()
    fil_h_clean = fil_h[(fil_h > ll) & (fil_h < ul)]

    # resample snow accumulation data
    h_resampled = fil_h_clean.resample('6H').median()
    h_std_resampled = fil_h_clean.resample('H').std()
    sh = fil_h_clean.rolling('D').median()
    sh_std = fil_h_clean.rolling('D').std()

    # Q: calculate SWE from accumulation data
    # calculate SWE (swe = h[m] * density[kg/m3]) from snow accumulation and mean_density(0.5m)=408 from Hecht_2022
    swe_laser_constant = (sh / 1000) * 408
    swe_laser_constant_resampled = swe_laser_constant.resample(resample_resolution).median()

    # calculate SWE with interpolated density data from layers in depths above the buried antenna
    swe_laser = (sh / 1000) * ipol
    swe_laser_resampled = swe_laser.resample(resample_resolution).median()

    return df_shm, h, fil_h_clean, h_resampled, h_std_resampled, sh, sh_std, swe_laser_constant, swe_laser_constant_resampled, swe_laser, swe_laser_resampled


def read_reference_data(dest_path, read_manual=[True, False], read_buoy=[True, False], read_poles=[True, False], read_laser=[True, False], resample_resolution='30min', laser_pickle='shm/nm_shm.pkl'):
    """ read reference sensor's observations from manual observations, a snow buoy sensor, a laser distance sensor and manual pole observations
    :param read_laser: read laser accumulation data (True) or not (False)
    :param read_poles: read poles accumulation data (True) or not (False)
    :param read_buoy: read buoy accumulation data (True) or not (False)
    :param read_manual: read manual observation data (True) or not (False)
    :param laser_pickle: read logfiles (laser_pickle == None) or pickle (e.g., 'shm/nm_shm.pkl') creating/containing snow accumulation observations from laser distance sensor
    :param resample_resolution: resolution for resampling the data (e.g., the resolution of the reference data)
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :return: manual, ipol, buoy, poles, df_shm, h, fil_h_clean, h_resampled, h_std_resampled, sh, sh_std, swe_laser_constant, swe_laser_constant_resampled, swe_laser, swe_laser_resampled
    """
    print(colored('\n\nread reference observations', 'blue'))

    # Q: read manual accumulation (cm), density (kg/m^3), SWE (mm w.e.) data
    if read_manual is True:
        manual, ipol = read_manual_observations(dest_path)
    else:
        manual, ipol = None

    # Q: read snow buoy data (mm)
    if read_buoy is True:
        buoy = read_snowbuoy_observations(dest_path)
    else:
        buoy = None

    # Q: read Pegelfeld Spuso accumulation data from poles
    if read_poles is True:
        poles = read_pole_observations(dest_path)
    else:
        poles = None

    # Q: read snow depth observations (minute resolution) from laser distance sensor data
    if read_laser is True:
        df_shm, h, fil_h_clean, h_resampled, h_std_resampled, sh, sh_std, swe_laser_constant, swe_laser_constant_resampled, swe_laser, swe_laser_resampled = read_laser_observations(dest_path, laser_pickle, ipol, resample_resolution)
    else:
        df_shm, h, fil_h_clean, h_resampled, h_std_resampled, sh, sh_std, swe_laser_constant, swe_laser_constant_resampled, swe_laser, swe_laser_resampled = None

    return manual, ipol, buoy, poles, df_shm, h, fil_h_clean, h_resampled, h_std_resampled, sh, sh_std, swe_laser_constant, swe_laser_constant_resampled, swe_laser, swe_laser_resampled





