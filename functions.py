""" Functions to generate daily rinex 3.0x files from day-overlapping Emlid rinex files;
    Necessary preprocessing for daily file processing with RTKLib
    created by: L. Steiner (Orchid ID: 0000-0002-4958-0849)
    created on: 17.05.2021
    updated on: 29.09.2021
"""

import subprocess
import os
import glob
import datetime
import shutil
import lzma
import tarfile
import gnsscal
import datetime as dt
import pandas as pd
import numpy as np
import jdcal
import matplotlib.pyplot as plt
from matplotlib.dates import YearLocator, MonthLocator, DateFormatter
from matplotlib.ticker import NullFormatter
from termcolor import colored
import requests
import zipfile
import io


""" Define general functions """


def create_folder(dest_path):
    """ create a directory if it is not already existing
    :param dest_path: path and name of new directory
    """
    # Q: create 'temp' directory if not existing
    if not os.path.exists(dest_path):
        os.makedirs(dest_path, exist_ok=True)
        print(colored("\ntemp dir created: %s" % dest_path, 'yellow'))
    else:
        print(colored("\ntemp dir already existing: %s" % dest_path, 'blue'))


def remove_folder(dest_path):
    """ delete temporary directory
    :param dest_path: local temporary directory for preprocessing the GNSS rinex files
    """
    shutil.rmtree(dest_path)
    print(colored("\n!!! temporary directory removed: %s" % dest_path, 'yellow'))


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
    # get parent directory
    parent_dir = os.path.dirname(os.path.dirname(dest_path))
    print('parent dir: ', parent_dir)

    # get file names
    files = sorted(glob.iglob(parent_dir + '/' + rover + '???0.*O', recursive=True), reverse=True)
    # get newest year of files in processing folder
    year_max = max([os.path.basename(f).split('.')[1][:2] for f in files])
    print(colored('newest year in existing files of parent dir: %s' % year_max, 'blue'))

    # get newest doy of files in processing folder
    doy_max = os.path.basename(sorted(glob.iglob(parent_dir + '/' + rover + '???0.' + year_max + 'O', recursive=True),
                                      reverse=True)[0]).split('.')[0][4:7]
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


def copy_solplotsdirs(source_path, dest_path):
    """ copy entire solution and plot directories
    :param source_path: local directory containing the solution and plot files
    :param dest_path: remote directory used for backup
    """
    shutil.copytree(source_path + '20_solutions/', dest_path + '20_solutions/', dirs_exist_ok=True)
    print('\ncopy directory: ' + source_path + '20_solutions/\nto: ' + dest_path + '20_solutions/')
    shutil.copytree(source_path + '30_plots/', dest_path + '30_plots/', dirs_exist_ok=True)
    print('copy directory: ' + source_path + '30_plots/\nto: ' + dest_path + '30_plots/')


def copy4backup(source_path, dest_path):
    """ copy entire processing directory to server
    :param source_path: local processing directory containing
    :param dest_path: remote directory used for backup
    """
    shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
    print('\ncopy directory: ' + source_path + '\nto: ' + dest_path)


def copy_rinex_files(source_path, dest_path, receiver=['NMLB', 'NMLR', 'NMER'], copy=[True, False], parent=[True, False], hatanaka=[True, False], move=[True, False], delete_temp=[True, False]):
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
            for f in sorted(glob.glob(source_path + '*.zip'), reverse=False):
                # construct the destination filename
                dest_file = os.path.join(dest_path, f.split("\\")[-1])
                # convert datetime to day of year (doy) from filename
                doy_file = datetime.datetime.strptime(os.path.basename(f).split('_')[2], "%Y%m%d%H%M").strftime('%j')
                yy_file = os.path.basename(f).split('_')[2][2:4]

                # Q: only copy files from server which are newer than the already existing doys of year=yy

                if (yy_file == year_max and doy_file > doy_max) or (yy_file > year_max):
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
                    # print(colored('file already preprocessed and available in the processing folder, skip file: %s' % f, 'yellow'))
                    # doy_file = None
                    pass
            if doy_file is None:
                print(colored('no new files available in source folder', 'green'))
        else:
            pass

        # Q: delete nav & zipped files
        if doy_file is not None:
            for f in glob.glob(dest_path + '*.*[BPzip]'):
                os.remove(f)
            print("nav files deleted %s" % dest_path)

        # Q: split & merge day-overlapping Emlid rinex files to daily rinex files (for Emlid files only!)
        if doy_file is not None:
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
                if (yy_file == year_max and doy_file > doy_max) or (yy_file > year_max):
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
                        print('file decompressed: %s' % dest_file)
                        # close xz file
                        tar.fileobj.close()
                else:
                    # print(colored('file already preprocessed and available in the processing folder, skip file: %s' % f, 'yellow'))
                    # doy_file = None
                    pass
            if doy_file is None:
                print(colored('no new files available in source folder:', 'green'))

        else:
            pass

        # Q: move obs (and nav) files to parent dir
        if parent is True:
            if receiver == 'NMLB':
                # copy observation (.yyd) & navigation (.yy[ngl]) files from base receiver
                for f in glob.glob(dest_path + 'var/www/upload/' + receiver + '/*.*'):
                    shutil.move(f, dest_path)
                if doy_file is not None:
                    print(colored("\nobs & nav files moved to parent dir %s" % dest_path, 'blue'))
            if receiver == 'NMLR':
                # copy only observation (.yyd) files from rover receivers
                for f in glob.glob(dest_path + 'var/www/upload/' + receiver + '/*.*d'):
                    shutil.move(f, dest_path)
                if doy_file is not None:
                    print(colored("\nobs files moved to parent dir %s" % dest_path, 'blue'))
        else:
            pass

        # Q: convert hatanaka compressed rinex (.yyd) to uncompressed rinex observation (.yyo) files
        if hatanaka is True:
            if doy_file is not None:
                print(colored("\ndecompress hatanaka rinex files", 'blue'))
                for hatanaka_file in glob.glob(dest_path + '*.*d'):
                    print('decompress hatanaka file: ', hatanaka_file)
                    # subprocess.Popen('crx2rnx ' + hatanaka_file)
                    subprocess.call('crx2rnx ' + hatanaka_file)
                print(colored("\nfinished decompressing hatanaka rinex files", 'blue'))
        else:
            pass

        # Q: move all obs (and nav) files from temp to parent directory
        if move is True:
            if doy_file is not None:
                print(colored("\nmove decompressed files to parent dir", 'blue'))
                for f in glob.glob(dest_path + '*.*[ongl]'):
                    move_files2parentdir(dest_path, f)
                print(colored("\nfinished moving decompressed files to parent dir", 'blue'))

        else:
            print('files are NOT moved to parent directory!')

    # Q: get the newest year, doy after copying and convert to modified julian date (mjd)
    yy_file, doy_file = check_existing_files(dest_path, rover)
    date_file = gnsscal.yrdoy2date(int('20' + yy_file), int(doy_file))
    mjd_file = jdcal.gcal2jd(date_file.year, date_file.month, date_file.day)[1]

    # Q: delete temp directory
    if delete_temp is True:
        remove_folder(dest_path)
    else:
        print('temporary directory is NOT deleted!')

    return mjd_file


def convert_datetime2doy_rinexfiles(dest_path, rover_prefix, rover_name):
    """ convert Emlid file names to match format for 'gfzrnx' rinex conversion tools
    :param dest_path: local temporary directory for preprocessing the GNSS rinex files
    :param rover_prefix: prefix of rinex files in temp directory
    :param rover_name: name of rover receiver

    input filename: 'ReachM2_sladina-raw_202111251100.21O'  [rover_prefix + datetime + '.' + yy + 'O']
    output filename: 'NMER329[a..d].21o'                    [rover_prefix + doy + '0.' + yy + 'o']
    """
    # Q: get doy from rinex filenames in temp dir with name structure: 'ReachM2_sladina-raw_202112041058.21O' [rover_prefix + datetime + '.' + yy + 'O']
    print(colored('\nrenaming all files', 'blue'))
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
    print(colored('\nstart splitting day-overlapping rinex files', 'blue'))
    for f in glob.iglob(dest_path + rover_name + '*.*o', recursive=True):
        # get filename
        rover_file = os.path.basename(f)
        print('\nstart splitting day-overlapping rinex file: %s' % rover_file)

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
    print(colored('\nrenaming all splitted rinex files', 'blue'))
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
    print(colored('\nmerging all rinex files per day at: %s' % dest_path, 'blue'))
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


def rename_merged_rinexfiles(dest_path, rover_name, move=[True, False]):
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
    rename_merged_rinexfiles(dest_path, receiver, move)


def get_sol_yeardoy(dest_path, resolution):
    """ get the newest solution file year, doy, mjd, date for only further process new available data.
    :param resolution: processing time interval (minutes) for naming of output folder
    :return: start_yy, start_mjd, start_mjd_emlid
    """
    print(colored("\nget start year and mjd for further processing", 'blue'))
    # get the newest solution file name
    name_max = os.path.basename(sorted(glob.iglob(dest_path + '20_solutions/NMLR/' + resolution + '/*.POS', recursive=True), reverse=True)[0]).split('.')[0]
    start_yy = name_max[2:4]
    start_doy = int(name_max[-3:]) + 1
    start_date = gnsscal.yrdoy2date(int('20' + start_yy), start_doy)
    start_mjd = jdcal.gcal2jd(start_date.year, start_date.month, start_date.day)[1]
    print(colored('start year %s, doy %s, mjd %s, date %s for further processing of Leica Rover' % (start_yy, start_doy, start_mjd, start_date), 'blue'))

    # get the newest emlid solution file name
    name_max_emlid = os.path.basename(sorted(glob.iglob(dest_path + '20_solutions/NMER/' + resolution + '/*.POS', recursive=True), reverse=True)[0]).split('.')[0]
    start_yy_emlid = name_max_emlid[2:4]
    start_doy_emlid = int(name_max_emlid[-3:]) + 1
    start_date_emlid = gnsscal.yrdoy2date(int('20' + start_yy_emlid), start_doy_emlid)
    start_mjd_emlid = jdcal.gcal2jd(start_date_emlid.year, start_date_emlid.month, start_date_emlid.day)[1]
    print(colored('start year %s, doy %s, mjd %s, date %s for further processing of Leica Rover' % (start_yy_emlid, start_doy_emlid, start_mjd_emlid, start_date_emlid), 'blue'))

    return start_yy, start_mjd, start_mjd_emlid


""" Define RTKLIB functions """


def automate_rtklib_pp(dest_path, rover_prefix, mjd_start, mjd_end, ti_int, base_prefix, brdc_nav_prefix, precise_nav_prefix, resolution, ending, rover_name=['NMER_original', 'NMER', 'NMLR'], options=['options_Emlid', 'options_Leica']):
    """ create input and output files for running RTKLib post processing automatically
        for all rover rinex observation files (. yyo) available in the data path directory
        get doy from rover file names with name structure:
            Leica Rover: '33933650.21o' [rover + doy + '0.' + yy + 'o']
            Emlid Rover (pre-processed): 'NMER3650.21o' [rover + doy + '0.' + yy + 'o']
            Emlid Rover (original): 'ReachM2_sladina-raw_202112041058.21O' [rover + datetime + '.' + yy + 'O']
        :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file (all data needs to be in one folder)
        :param rover_prefix: prefix of rover rinex filename
        :param yy: start year to process
        :param yy: end year to process
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
    for file in glob.iglob(dest_path + rover_prefix + '*.*O', recursive=True):
        # Q: get doy from rover filenames
        rover_file = os.path.basename(file)
        if rover_name == 'NMER_original':
            # get date, year, modified julian date (mjd), doy, converted from datetime in Emlid original filename format (output from receiver, non-daily files)
            date = dt.datetime.strptime(rover_file.split('.')[0].split('_')[2], "%Y%m%d%H%M")
            year = str(date.year)[-2:]
            mjd = jdcal.gcal2jd(date.year, date.month, date.day)[1]
            doy = date.strftime('%j')
        if rover_name == 'NMER' or rover_name == 'NMLR':
            # get year, doy, date, modified julian date (mjd) directly from filename from Emlid pre-processed or Leica file name format (daily files)
            year = rover_file.split('.')[1][:2]
            doy = rover_file.split('.')[0][4:7]
            date = gnsscal.yrdoy2date(int('20' + year), int(doy))
            mjd = jdcal.gcal2jd(date.year, date.month, date.day)[1]

        # Q: only process files inbetween the selected mjd range
        if mjd_start <= mjd <= mjd_end:
            print('\nProcessing rover file: ' + rover_file, '; year: ', year, '; doy: ', doy)

            # convert doy to gpsweek and day of week (needed for precise orbit file names)
            (gpsweek, dow) = gnsscal.yrdoy2gpswd(int('20' + year), int(doy))

            # define input and output filenames (for some reason it's not working when input files are stored in subfolders!)
            base_file = base_prefix + doy + '0.' + year + 'O'
            broadcast_orbit_gps = brdc_nav_prefix + doy + '0.' + year + 'n'
            broadcast_orbit_glonass = brdc_nav_prefix + doy + '0.' + year + 'g'
            broadcast_orbit_galileo = brdc_nav_prefix + doy + '0.' + year + 'l'
            precise_orbit = precise_nav_prefix + str(gpsweek) + str(dow) + '.EPH_M'

            # create a solution directory if not existing
            sol_dir = '20_solutions/' + rover_name + '/' + resolution + '/temp_' + rover_name + '/'
            os.makedirs(dest_path + sol_dir, exist_ok=True)
            output_file = sol_dir + '20' + year + '_' + rover_name + doy + ending + '.pos'

            # Q: change directory to data directory & run RTKLib post processing command
            run_rtklib_pp(dest_path, options, ti_int, output_file, rover_file, base_file,
                          broadcast_orbit_gps, broadcast_orbit_glonass, broadcast_orbit_galileo, precise_orbit)

    print(colored('\n\nfinished processing all files with RTKLIB from receiver: %s' % rover_name, 'blue'))


def run_rtklib_pp(dest_path, options, ti_int, output_file, rover_file, base_file, brdc_orbit_gps, brdc_orbit_glonass, brdc_orbit_galileo, precise_orbit):
    """ run RTKLib post processing command (rnx2rtkp) as a subprocess (instead of manual RTKPost GUI)
        example: 'rnx2rtkp -k rtkpost_options.conf -ti 900 -o 20_solutions/NMLR/15min/NMLRdoy.pos NMLR0040.17O NMLB0040.17O NMLB0040.17n NMLB0040.17g NMLB0040.17e COD17004.eph'
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
    # change directory & run RTKLIB post processing command 'rnx2rtkp'
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
    """  get daily rtklib ENU solution files from solution directory and store all solutions in one dataframe and pickle
    :param header_length: length of header in solution files (dependent on processing parameters)
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :param rover_name: name of rover
    :param resolution: processing time interval (in minutes)
    :param ending: suffix of solution file names (e.g. a varian of processing options: '_noglonass'
    :return: df_enu (pandas dataframe containing all seasons solution data columns ['date', 'time', 'U', 'amb_state', 'nr_sat', 'std_u'])
    """
    # Q: read all existing ENU solution data from .pkl if already exists, else create empty dataframe
    path_to_oldpickle = dest_path + '20_solutions/' + rover_name + '_' + resolution + ending + '.pkl'
    if os.path.exists(path_to_oldpickle):
        print(colored('\nReading already existing ENU solutions from pickle: %s' % path_to_oldpickle, 'yellow'))
        df_enu_old = pd.read_pickle(path_to_oldpickle)
    else:
        print(colored('\nNo existing ENU solution pickle: %s' % path_to_oldpickle, 'yellow'))
        df_enu_old = pd.DataFrame()

    # Q: read all newly available .ENU files in solution directory, parse date and time columns to datetimeindex and add them to the dataframe
    df_enu_new = pd.DataFrame(columns=['U', 'amb_state', 'nr_sat', 'std_u', 'date', 'time'])
    path = dest_path + '20_solutions/' + rover_name + '/' + resolution + '/temp_' + rover_name
    print(colored('\nReading all newly available ENU solution files from receiver: %s' % rover_name, 'blue'))
    for file in glob.iglob(path + '/*' + ending + '.pos', recursive=True):
        print('reading ENU solution file: %s' % file)
        enu = pd.read_csv(file, header=header_length, delimiter=' ', skipinitialspace=True, index_col=['date_time'],
                          na_values=["NaN"],
                          usecols=[0, 1, 4, 5, 6, 9], names=['date', 'time', 'U', 'amb_state', 'nr_sat', 'std_u'],
                          parse_dates=[['date', 'time']])

        # add new enu data to df enu
        df_enu_new = pd.concat([df_enu_new, enu], axis=0)

        # move file from temp directory to solutions directory after reading
        shutil.move(file, path + '/../' + os.path.basename(file))

    # remove date and time columns
    df_enu_new = df_enu_new.drop(columns=['date', 'time'])

    # concatenate existing solutions with new solutions
    df_enu_total = pd.concat([df_enu_old, df_enu_new], axis=0)

    # detect all dublicates and only keep last dublicated entries
    df_enu = df_enu_total[~df_enu_total.index.duplicated(keep='last')]
    print(colored('\nstored all old and new ENU solution data (without dublicates) in dataframe df_enu:', 'blue'))
    print(df_enu)

    # store dataframe as binary pickle format
    df_enu.to_pickle(dest_path + '20_solutions/' + rover_name + '_' + resolution + ending + '.pkl')
    print(colored('\nstored all old and new ENU solution data (without dublicates) in pickle: ' + '20_solutions/' + rover_name + '_' + resolution + ending + '.pkl', 'blue'))

    # delete temporary solution directory
    if os.path.exists(path):
        shutil.rmtree(path)
    print(colored('\nAll new ENU solution files are moved to solutions dir and temp solutions directory is removed', 'blue'))

    return df_enu


def filter_rtklib_solutions(dest_path, rover_name, resolution, df_enu, ambiguity=[1, 2, 5], ti_set_swe2zero=12, threshold=3, window='D', resample=[True, False], resample_resolution='30min', ending=''):
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
    :return: fil_df, fil, fil_clean, m, s, jump, swe_gnss, swe_gnss_daily, std_gnss_daily
    """

    print(colored('\nFiltering data', 'blue'))

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

    while jump.empty is False:
        print('\njump of height %s is detected!' % jump[0])
        adj = m[(m.index >= jump.index.format()[0])] - jump[0]          # correct all observations after jump [0]
        m = pd.concat([m[~(m.index >= jump.index.format()[0])], adj])   # concatenate all original obs before jump with adjusted values after jump
        jump = m[(m.diff() < -1000)]

    print('\nno jump detected!')
    swe_gnss = m - m[0]
    swe_gnss.index = swe_gnss.index + pd.Timedelta(seconds=18)

    # resample data per day, calculate median and standard deviation (noise) per day to fit manual reference data
    swe_gnss_daily = swe_gnss.resample('D').median()
    std_gnss_daily = swe_gnss.resample('D').std()

    # Q: store swe results to pickle
    print(colored('\ndata is filtered, cleaned, and corrected and SWE results are stored to pickle and .csv: %s' % '20_solutions/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl', 'blue'))
    os.makedirs(dest_path + '20_solutions/SWE_results/', exist_ok=True)
    swe_gnss.to_pickle(dest_path + '20_solutions/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl')
    swe_gnss.to_csv(dest_path + '20_solutions/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.csv')

    return fil_df, fil, fil_clean, m, s, jump, swe_gnss, swe_gnss_daily, std_gnss_daily


def read_swe_gnss(dest_path, swe_gnss, rover_name, resolution, ending):
    # read gnss swe results from pickle
    if swe_gnss is None:
        print(colored('\nSWE results are NOT available, reading from pickle: %s' % '20_solutions/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl', 'orange'))
        swe_gnss = pd.read_pickle(dest_path + '20_solutions/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl')

    return swe_gnss


""" Define reference sensors functions """


def read_manual_observations(dest_path):
    """ read and interpolate manual accumulation (cm), density (kg/m^3), SWE (mm w.e.) data
        :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
        :return: manual2, ipol
    """
    # read data
    print('\nread manual observations')
    manual = pd.read_csv(dest_path + '00_reference_data/Manual_Spuso.csv', header=1, skipinitialspace=True,
                         delimiter=';', index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0], dayfirst=True,
                         names=['Acc', 'Density', 'SWE', 'Density_aboveAnt', 'SWE_aboveAnt'])
    manual2 = manual
    manual2.index = manual2.index + pd.Timedelta(days=0.2)

    # fix dtype of column "Acc" and convert to mm
    manual2.Acc = manual2.Acc.astype('float64') * 10

    # interpolate manual data
    print('\n-- interpolate manual reference observations')
    ipol = manual.Density_aboveAnt.resample('min').interpolate(method='linear', limit_direction='backward')

    return manual2, ipol


def read_snowbuoy_observations(dest_path, url, ipol_density=None):
    """ read snow buoy accumulation data from four sensors and convert to SWE & pressure, airtemp
        :param ipol_density: interpolated density data from manual reference observations
        :param url: webpage url where daily updated snow buoy data  can be downloaded
        :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
        :return: buoy
    """
    # Q: download newest snow buoy data from url
    # get data from url
    r = requests.get(url, allow_redirects=True)

    # decompress file
    z = zipfile.ZipFile(io.BytesIO(r.content))

    # store selected file from decompressed folder to working direcory subfolder
    z.extract(z.filelist[2], path=(dest_path + '00_reference_data/Snowbuoy/'))

    # Q: read snow buoy data
    print('\nread snow buoy observations')
    buoy_all = pd.read_csv(dest_path + '00_reference_data/Snowbuoy/2017S54_300234011695900_proc.csv', header=0,
                           skipinitialspace=True, delimiter=',', index_col=0, skiprows=0, na_values=["NaN"],
                           parse_dates=[0],
                           names=['lat', 'lon', 'sh1', 'sh2', 'sh3', 'sh4', 'pressure', 'airtemp', 'bodytemp',
                                  'gpstime'])

    # select only data from season 21/22
    buoy = buoy_all['2021-11-26':]

    # Q: Differences in accumulation & conversion to SWE
    # calculate change in accumulation (in mm) for each buoy sensor add it as an additional column to the dataframe buoy
    buoy_change = (buoy[['sh1', 'sh2', 'sh3', 'sh4']]-buoy[['sh1', 'sh2', 'sh3', 'sh4']][:1].values[0]) * 1000
    buoy_change.columns = ['dsh1', 'dsh2', 'dsh3', 'dsh4']

    # convert snow accumulation to SWE (with interpolated and constant density values)
    print('\n-- convert buoy observations to SWE')
    buoy_swe = convert_sh2swe(buoy_change, ipol_density)
    buoy_swe.columns = ['dswe1', 'dswe2', 'dswe3', 'dswe4']

    buoy_swe_constant = convert_sh2swe(buoy_change)
    buoy_swe_constant.columns = ['dswe_const1', 'dswe_const2', 'dswe_const3', 'dswe_const4']

    # append new columns to existing buoy dataframe
    buoy = pd.concat([buoy, buoy_change, buoy_swe, buoy_swe_constant], axis=1)

    return buoy


def read_pole_observations(dest_path, ipol_density=None):
    """ read Pegelfeld Spuso accumulation data from 16 poles and convert to SWE
        :param ipol_density: interpolated density data from manual reference observations
        :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
        :return: poles
    """
    # Q: read Pegelfeld Spuso pole observations
    print('\nread Pegelfeld Spuso pole observations')
    poles = pd.read_csv(dest_path + '00_reference_data/Pegelfeld_Spuso_Akkumulation.csv', header=0, delimiter=';',
                        index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0], dayfirst=True)

    # Q: convert snow accumulation to SWE (with interpolated and constant density values)
    print('\n-- convert Pegelfeld Spuso pole observations to SWE')
    poles_swe = convert_sh2swe(poles, ipol_density)
    poles_swe.columns = ['dswe'] + poles_swe.columns

    poles_swe_constant = convert_sh2swe(poles)
    poles_swe_constant.columns = ['dswe_const'] + poles_swe_constant.columns

    # append new columns to existing poles dataframe
    poles = pd.concat([poles, poles_swe, poles_swe_constant], axis=1)

    return poles


def read_laser_observations(dest_path, laser_path, yy, ipol, laser_pickle='00_reference_data/Laser/nm_laser.pkl'):
    """ read snow accumulation observations (minute resolution) from laser distance sensor data
    :param ipol: interpolated density data from manual reference observations
    :param laser_pickle: read logfiles (laser_pickle == None) or pickle (e.g., '00_reference_data/Laser/nm_shm.pkl') creating/containing snow accumulation observations from laser distance sensor
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :return: df_shm, h, fil_h_clean, h_resampled, h_std_resampled, sh, sh_std
    """
    # Q: copy laser observations from AWI server if not already existing
    print(colored("\ncopy new laser files", 'blue'))
    for f in glob.glob(laser_path + '20' + yy + '/*.log'):
        file = os.path.basename(f)
        if not os.path.exists(dest_path + '00_reference_data/Laser/' + file):
            shutil.copy2(f, dest_path + '00_reference_data/Laser/')
            print("file copied from %s to %s" % (f, dest_path + '00_reference_data/Laser/'))
        else:
            # print(colored("\nfile in destination already exists: %s, \ncopy aborted!!!" % dest_path, 'yellow'))
            continue
    print(colored("\nnew laser files copied", 'blue'))

    # Q: read snow accumulation observations (minute resolution) from laser distance sensor data
    if laser_pickle is None:
        print(colored('\nlaser observations are NOT available as pickle, reading all logfiles: 00_reference_data/Laser/nm*.log', 'yellow'))
        # create empty dataframe for all .log files
        laser = pd.DataFrame()
        # read all snow accumulation.log files in folder, parse date and time columns to datetimeindex and add them to the dataframe
        for file in glob.iglob(dest_path + '00_reference_data/Laser/nm*.log', recursive=True):
            print(file)
            # header: 'date', 'time', 'snow level (m)', 'signal(-)', 'temp (°C)', 'error (-)', 'checksum (-)'
            shm = pd.read_csv(file, header=0, delimiter=r'[ >]', skipinitialspace=True, na_values=["NaN"], names=['date', 'time', 'none','sh', 'signal', 'temp', 'error', 'check'], usecols=[0,1,3,5,6],
                              encoding='latin1', parse_dates=[['date', 'time']], index_col=['date_time'], engine='python', dayfirst=True)
            laser = pd.concat([laser, shm], axis=0)

        # calculate change in accumulation (in mm) and add it as an additional column to the dataframe
        laser['dsh'] = (laser['sh'] - laser['sh'][0]) * 1000

        # store as .pkl
        laser.to_pickle(dest_path + '00_reference_data/Laser/nm_laser.pkl')

    else:
        print(colored('\nlaser observations are available as pickle, reading: %s' % laser_pickle, 'yellow'))
        laser = pd.read_pickle(dest_path + laser_pickle)

    # Q: filter laser observations
    print('\n-- filtering laser observations')
    # 0. select only observations without errors
    dsh = laser[(laser.error == 0)].dsh

    # 1. only select observations bigger than the minimum oultier
    f = dsh[(dsh > dsh.min())]

    # 2. only select observations where the gradient is smaller than 50cm (iteration)
    outliers = f.index[(f.diff() > 500) | (f.diff() < -500)]
    while outliers.empty is False:
        outliers = f.index[(f.diff() > 500) | (f.diff() < -500)]
        fil_dsh = f.loc[~f.index.isin(outliers)]
        f = fil_dsh

    # 3. filter observations
    dsh_laser = fil_dsh.rolling('D').median()
    dsh_laser_std = fil_dsh.rolling('D').std()

    # 4. manually exclude remaining outliers
    exclude_indizes = dsh_laser['2022-05'].index[(dsh_laser['2022-05'] < 400)]
    dsh_laser = dsh_laser.loc[~(dsh_laser.index.isin(exclude_indizes))]

    # Q: calculate SWE from accumulation data
    print('\n-- convert laser observations to SWE')
    laser_swe = convert_sh2swe(dsh_laser, ipol_density=ipol)
    laser_swe_constant = convert_sh2swe(dsh_laser)

    # append new columns to existing poles dataframe
    laser_filtered = pd.concat([dsh_laser, dsh_laser_std, laser_swe, laser_swe_constant], axis=1)
    laser_filtered.columns = ['dsh', 'dsh_std', 'dswe', 'dswe_const']

    return laser, laser_filtered


def read_reference_data(dest_path, laser_path, yy, url, read_manual=[True, False], read_buoy=[True, False], read_poles=[True, False], read_laser=[True, False], laser_pickle='00_reference_data/Laser/nm_laser.pkl'):
    """ read reference sensor's observations from manual observations, a snow buoy sensor, a laser distance sensor and manual pole observations
    :param read_laser: read laser accumulation data (True) or not (False)
    :param read_poles: read poles accumulation data (True) or not (False)
    :param read_buoy: read buoy accumulation data (True) or not (False)
    :param read_manual: read manual observation data (True) or not (False)
    :param laser_pickle: read logfiles (laser_pickle == None) or pickle (e.g., '00_reference_data/Laser/nm_laser.pkl') creating/containing snow accumulation observations from laser distance sensor
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :param url: path to snow buoy data on a webpage
    :param yy: year to get first data
    :param laser_path: path to laser distance sensor observation files
    :return: manual, ipol, buoy, poles, laser, laser_filtered
    """
    print(colored('\n\nread reference observations', 'blue'))

    # Q: read manual accumulation (cm), density (kg/m^3), SWE (mm w.e.) data
    if read_manual is True:
        manual, ipol = read_manual_observations(dest_path)
        manual.index = pd.DatetimeIndex(manual.index.date)
    else:
        manual, ipol = None, None

    # Q: read snow buoy data (mm)
    if read_buoy is True:
        buoy = read_snowbuoy_observations(dest_path, url, ipol_density=ipol)
    else:
        buoy = None

    # Q: read Pegelfeld Spuso accumulation data from poles
    if read_poles is True:
        poles = read_pole_observations(dest_path, ipol_density=ipol)
    else:
        poles = None

    # Q: read snow depth observations (minute resolution) from laser distance sensor data
    if read_laser is True:
        laser, laser_filtered = read_laser_observations(dest_path, laser_path, yy, ipol, laser_pickle)
    else:
        laser, laser_filtered = None, None

    print(colored('\n\nreference observations are loaded', 'blue'))

    return manual, ipol, buoy, poles, laser, laser_filtered


def convert_swe2sh(swe, ipol_density=None):
    """ calculate snow accumulation from swe: sh[m]  = SWE [mm w.e.] * 1000 / density[kg/m3]) using a mean density values or interpolated densities
    :param swe: dataframe containing swe values (in mm w.e.)
    :param ipol_density: use interpolated values, input interpolated densitiy values, otherwise=None: constant value is used
    :return: sh
    """
    if ipol_density is None:
        # calculate snow accumulation (sh) from SWE and a mean_density(0.5m)=408 from Hecht_2022
        sh = swe * 1000 / 408
    else:
        # calculate snow accumulation (sh) from SWE and interpolated density values (from manual Spuso observations)
        sh = ((swe * 1000).divide(ipol_density, axis=0)).dropna()

    return sh


def convert_sh2swe(sh, ipol_density=None):
    """ calculate swe from snow accumulation: swe[mm w.e.]  = (sh [mm] / 1000) * density[kg/m3]) using a mean density values or interpolated densities
    :param sh: dataframe containing snow accumulation (height) values (in meters)
    :param ipol_density: use interpolated values, input interpolated densitiy values, otherwise=None: constant value is used
    :return: swe
    """
    if ipol_density is None:
        # calculate SWE from snow accumulation (sh) and a mean_density(0.5m)=408 from Hecht_2022
        swe = (sh / 1000) * 408
    else:
        # calculate SWE from snow accumulation (sh) and interpolated density values (from manual Spuso observations)
        swe = ((sh / 1000).multiply(ipol_density, axis=0)).dropna()

    return swe


""" Define combined GNSS and reference sensors functions """


def convert_swe2sh_gnss(swe_gnss, ipol_density=None):
    """ convert GNSS derived SWE to snow accumulation using interpolated or a mean density value. Add SWE and converted sh to one dataframe
    :param swe_gnss: dataframe containing GNSS derived SWE estimations
    :param ipol_density: use interpolated values, input interpolated densitiy values, otherwise=None: constant value is used
    :return: gnss
    """
    print('\n-- convert GNSS SWE estimations to snow accumulation changes')
    sh_gnss = convert_swe2sh(swe_gnss, ipol_density)
    sh_gnss_const = convert_swe2sh(swe_gnss)

    # append new columns to existing gnss estimations dataframe
    gnss = pd.concat([swe_gnss, sh_gnss, sh_gnss_const], axis=1)
    gnss.columns = ['dswe', 'dsh', 'dsh_const']

    return gnss


def resample_allobs(gnss_leica, gnss_emlid, buoy, poles, laser, interval='D'):
    """ resample all sensors observations (different temporal resolutions) to other resolution
    :param gnss_leica: dataframe containing GNSS solutions (SWE, sh) from high-end system
    :param gnss_emlid: dataframe containing GNSS solutions (SWE, sh) from low-cost system
    :param buoy: dataframe containing snow buoy observations (SWE, sh)
    :param poles: dataframe containing poles observations (SWE, sh)
    :param laser: dataframe containing laser observations (SWE, sh)
    :param interval: time interval for resampling, default=daily
    :return: leica_res, emlid_res, buoy_res, poles_res, laser_res
    """
    # resample sh and swe data (daily)
    leica_res = (gnss_leica.resample(interval).median()).dropna()
    emlid_res = (gnss_emlid.resample(interval).median()).dropna()
    buoy_res = (buoy.resample(interval).median()).dropna()
    poles_res = (poles.resample(interval).median()).dropna()
    laser_res = (laser.resample(interval).median()).dropna()

    print('all data is resampled with interval: %s' % interval)

    return leica_res, emlid_res, buoy_res, poles_res, laser_res


def calculate_differences2gnss(emlid, leica, manual, laser, buoy, poles):
    """ calculate differences between reference data and GNSS (Leica)
    :param emlid: GNSS SWE/SH estimations from low-cost sensor
    :param leica: GNSS SWE/SH estimtions from high-end sensor
    :param manual: manual SWE/SH reference data
    :param laser: SWE/SH observations from laser distance sensor
    :param buoy: SWE/SH observations from snow buoy sensor
    :param poles:SWE/SH observations from poles observations
    :return: diffs_sh, diffs_swe
    """
    # calculate differences to leica data
    dsh_emlid = (emlid.dsh - leica.dsh).dropna()
    dswe_emlid = (emlid.dswe - leica.dswe).dropna()
    dsh_manual = (manual.Acc - leica.dsh).dropna()
    dswe_manual = (manual.SWE_aboveAnt - leica.dswe).dropna()
    dsh_laser = (laser.dsh - leica.dsh).dropna()
    dswe_laser = (laser.dswe - leica.dswe).dropna()
    dsh_buoy = (buoy[['dsh1', 'dsh2', 'dsh3', 'dsh4']].subtract(leica.dsh, axis='index')).dropna()
    dswe_buoy = (buoy[['dswe1', 'dswe2', 'dswe3', 'dswe4']].subtract(leica.dswe, axis='index')).dropna()
    dsh_poles = (poles[['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']].subtract(leica.dsh, axis='index')).dropna()
    dswe_poles = (poles[['dswe1', 'dswe2', 'dswe3', 'dswe4', 'dswe5', 'dswe6', 'dswe7', 'dswe8', 'dswe9', 'dswe10', 'dswe11', 'dswe12', 'dswe13', 'dswe14', 'dswe15', 'dswe16']].subtract(leica.dswe, axis='index')).dropna()

    # calculate differences to emlid data
    dsh_manual_emlid = (manual.Acc - emlid.dsh).dropna()
    dswe_manual_emlid = (manual.SWE_aboveAnt - emlid.dswe).dropna()
    dsh_laser_emlid = (laser.dsh - emlid.dsh).dropna()
    dswe_laser_emlid = (laser.dswe - emlid.dswe).dropna()

    # concatenate all difference dataframes
    diffs_sh = pd.concat([dsh_emlid, dsh_manual, dsh_laser, dsh_buoy, dsh_poles, dsh_manual_emlid, dsh_laser_emlid], axis=1)
    diffs_sh.columns = ['dsh_emlid', 'dsh_manual', 'dsh_laser', 'dsh_buoy1', 'dsh_buoy2', 'dsh_buoy3', 'dsh_buoy4', 'dsh_pole1',
                        'dsh_pole2', 'dsh_pole3', 'dsh_pole4', 'dsh_pole5', 'dsh_pole6', 'dsh_pole7', 'dsh_pole8', 'dsh_pole9',
                        'dsh_pole10', 'dsh_pole11', 'dsh_pole12', 'dsh_pole13', 'dsh_pole14', 'dsh_pole15', 'dsh_pole16', 'dsh_manual_emlid', 'dsh_laser_emlid']

    diffs_swe = pd.concat([dswe_emlid, dswe_manual, dswe_laser, dswe_buoy, dswe_poles, dswe_manual_emlid, dswe_laser_emlid], axis=1)
    diffs_swe.columns = ['dswe_emlid', 'dswe_manual', 'dswe_laser', 'dswe_buoy1', 'dswe_buoy2', 'dswe_buoy3', 'dswe_buoy4', 'dswe_pole1',
                        'dswe_pole2', 'dswe_pole3', 'dswe_pole4', 'dswe_pole5', 'dswe_pole6', 'dswe_pole7', 'dswe_pole8', 'dswe_pole9',
                        'dswe_pole10', 'dswe_pole11', 'dswe_pole12', 'dswe_pole13', 'dswe_pole14', 'dswe_pole15', 'dswe_pole16', 'dswe_manual_emlid', 'dswe_laser_emlid']

    print(colored('\nDifferences of all reference sensors to Leica data and manual/laser to Emlid data is calculated', 'blue'))

    return diffs_sh, diffs_swe


def calculate_differences2gnss_15min(emlid, leica, laser):
    """ calculate differences between reference data and GNSS (Leica) with a high resolution of 15min
    :param emlid: GNSS SWE/SH estimations from low-cost sensor
    :param leica: GNSS SWE/SH estimtions from high-end sensor
    :param laser: SWE/SH observations from laser distance sensor
    :return: diffs_sh, diffs_swe, laser_15min
    """
    # resample laser observations to match resolution of GNSS data (15min)
    laser_15min = (laser.resample('15min').median()).dropna()

    # calculate differences
    dsh_emlid = (emlid.dsh - leica.dsh).dropna()
    dswe_emlid = (emlid.dswe - leica.dswe).dropna()
    dsh_laser = (laser_15min.dsh - leica.dsh).dropna()
    dswe_laser = (laser_15min.dswe - leica.dswe).dropna()
    dsh_laser_emlid = (laser_15min.dsh - emlid.dsh).dropna()
    dswe_laser_emlid = (laser_15min.dswe - emlid.dswe).dropna()

    # concatenate all difference dataframes
    diffs_sh = pd.concat([dsh_emlid, dsh_laser, dsh_laser_emlid], axis=1)
    diffs_sh.columns = ['dsh_emlid', 'dsh_laser', 'dsh_laser_emlid']

    diffs_swe = pd.concat([dswe_emlid, dswe_laser, dswe_laser_emlid], axis=1)
    diffs_swe.columns = ['dswe_emlid', 'dswe_laser', 'dswe_laser_emlid']

    print(colored('\nDifferences of laser & emlid data to Leica and laser to Emlid is calculated for 15min resolutions', 'blue'))

    return diffs_sh, diffs_swe, laser


def calculate_crosscorr(leica_daily, emlid_daily, manual, gnss_leica, gnss_emlid, laser_15min):
    """ calculate Pearson cross correlation coefficient for daily and 15min resolutions between
        Leica & Emlid GNSS data and manual and laser observations
    :param leica_daily: GNSS SWE/SH estimtions from high-end sensor, daily resolution
    :param emlid_daily: GNSS SWE/SH estimtions from low-cost sensor, daily resolution
    :param manual: manual SWE/SH observations, daily resolution
    :param gnss_leica: GNSS SWE/SH estimtions from high-end sensor, 15min resolution
    :param gnss_emlid: GNSS SWE/SH estimtions from low-cost sensor, 15min resolution
    :param laser_15min: SWE/SH observations from laser distance sensor, 15min resolution
    :return corr_leica_daily, corr_emlid_daily, corr_leica_15min, corr_emlid_15min
    """
    # SWE cross correation manual vs. GNSS (daily)
    corr_leica_daily = manual.SWE_aboveAnt.corr(leica_daily.dswe)
    corr_emlid_daily = manual.SWE_aboveAnt.corr(emlid_daily.dswe)
    print('\nPearsons correlation (manual vs. GNSS, daily), Leica: %.2f' % corr_leica_daily)
    print('Pearsons correlation (manual vs. GNSS, daily), Emlid: %.2f' % corr_emlid_daily)

    # calculate cross correation laser vs. GNSS (15min)
    corr_leica_15min = laser_15min.dswe.corr(gnss_leica.dswe)
    corr_emlid_15min = laser_15min.dswe.corr(gnss_emlid.dswe)
    print('Pearsons correlation (laser vs. GNSS, 15min), Leica: %.2f' % corr_leica_15min)
    print('Pearsons correlation (laser vs. GNSS, 15min), Emlid: %.2f' % corr_emlid_15min)

    return corr_leica_daily, corr_emlid_daily, corr_leica_15min, corr_emlid_15min


def calculate_linearfit(leica_daily, emlid_daily, manual, gnss_leica, gnss_emlid, laser_15min):
    """ calculate linear regression coefficients between GNSS and manual/laser observations
        :param emlid_daily: GNSS SWE/SH estimtions from low-cost sensor, daily resolution
        :param leica_daily: GNSS SWE/SH estimtions from high-end sensor, daily resolution
        :param manual: manual SWE/SH observations, daily resolution
        :param gnss_leica: GNSS SWE/SH estimtions from high-end sensor, 15min resolution
        :param gnss_emlid: GNSS SWE/SH estimtions from low-cost sensor, 15min resolution
        :param laser_15min: SWE/SH observations from laser distance sensor, 15min resolution
        :return predict_daily, predict_15min, predict_15min_emlid
    """
    # fit linear regression curve manual vs. GNSS (daily), Leica
    joined = pd.concat([manual.SWE_aboveAnt, leica_daily.dswe], axis=1).dropna()
    fit_daily = np.polyfit(joined.SWE_aboveAnt, joined.dswe, 1)
    predict_daily = np.poly1d(fit_daily)
    print('\nLinear fit (manual vs. GNSS, daily), Leica: m = ', round(fit_daily[0], 2), ', b = ', int(fit_daily[1]))

    # fit linear regression curve manual vs. GNSS (daily), Emlid
    joined = pd.concat([manual.SWE_aboveAnt, emlid_daily.dswe], axis=1).dropna()
    fit_emlid_daily = np.polyfit(joined.SWE_aboveAnt, joined.dswe, 1)
    predict_emlid_daily = np.poly1d(fit_emlid_daily)
    print('Linear fit (manual vs. GNSS, daily), Emlid: m = ', round(fit_emlid_daily[0], 2), ', b = ', int(fit_emlid_daily[1]))

    # fit linear regression curve laser vs. GNSS (15min), Leica
    joined = pd.concat([laser_15min.dswe, gnss_leica.dswe], axis=1).dropna()
    joined.columns = ['dswe_laser', 'dswe_gnss']
    joined = joined['2021-12-23':]
    fit_15min = np.polyfit(joined.dswe_laser, joined.dswe_gnss, 1)
    predict_15min = np.poly1d(fit_15min)
    print('Linear fit (laser vs. GNSS, 15min), Leica: nm = ', round(fit_15min[0], 2), ', b = ', int(fit_15min[1]))

    # fit linear regression curve laser vs. GNSS (15min), Emlid
    joined = pd.concat([laser_15min.dswe, gnss_emlid.dswe], axis=1).dropna()
    joined.columns = ['dswe_laser', 'dswe_gnss']
    joined = joined['2021-12-23':]
    fit_15min_emlid = np.polyfit(joined.dswe_laser, joined.dswe_gnss, 1)
    predict_15min_emlid = np.poly1d(fit_15min_emlid)
    print('Linear fit (laser vs. GNSS, 15min), Emlid: nm = ', round(fit_15min_emlid[0], 2), ', b = ', int(fit_15min_emlid[1]))  # n=12, m=1.02, b=-8 mm w.e.

    return predict_daily, predict_emlid_daily, predict_15min, predict_15min_emlid


def calculate_rmse_mrb(diffs_swe_daily, diffs_swe_15min, manual, laser_15min):
    """ calculate root-mean-square-error (rmse), mean relative bias (mrb), and number of samples
        between GNSS SWE and manual/laser SWE observations
        :param diffs_swe_daily: differences between reference data and GNSS (Leica), daily resolution
        :param diffs_swe_15min: differences between reference data and GNSS (Leica), 15min resolution
        :param manual: manual SWE/SH observations, daily resolution
        :param laser_15min: SWE/SH observations from laser distance sensor, 15min resolution
    """
    # RMSE
    rmse_manual = np.sqrt((np.sum(diffs_swe_daily.dswe_manual ** 2)) / len(diffs_swe_daily.dswe_manual))
    print('\nRMSE (manual vs. GNSS, daily), Leica: %.1f' % rmse_manual)
    rmse_manual_emlid = np.sqrt((np.sum(diffs_swe_daily.dswe_manual_emlid ** 2)) / len(diffs_swe_daily.dswe_manual_emlid))
    print('RMSE (manual vs. GNSS, daily), Emlid: %.1f' % rmse_manual_emlid)
    rmse_laser = np.sqrt((np.sum(diffs_swe_15min.dswe_laser ** 2)) / len(diffs_swe_15min.dswe_laser))
    print('RMSE (laser vs. GNSS, 15min), Leica: %.1f' % rmse_laser)
    rmse_laser_emlid = np.sqrt((np.sum(diffs_swe_15min.dswe_laser_emlid ** 2)) / len(diffs_swe_15min.dswe_laser_emlid))
    print('RMSE (laser vs. GNSS, 15min), Emlid: %.1f' % rmse_laser_emlid)

    # MRB
    mrb_manual = (diffs_swe_daily.dswe_manual / manual.SWE_aboveAnt).mean() * 100
    print('\nMRB (manual vs. GNSS, daily), Leica: %.1f' % mrb_manual)
    mrb_manual_emlid = (diffs_swe_daily.dswe_manual_emlid / manual.SWE_aboveAnt).mean() * 100
    print('MRB (manual vs. GNSS, daily), Emlid: %.1f' % mrb_manual_emlid)
    mrb_laser = (diffs_swe_15min.dswe_laser / laser_15min.dswe).mean() * 100
    print('MRB (laser vs. GNSS, 15min), Leica: %.1f' % mrb_laser)
    mrb_laser_emlid = (diffs_swe_15min.dswe_laser_emlid / laser_15min.dswe).mean() * 100
    print('MRB (laser vs. GNSS, 15min), Emlid: %.1f' % mrb_laser_emlid)

    # Number of samples
    n_manual = len(diffs_swe_daily.dswe_manual.dropna())
    print('\nNumber of samples (manual vs. GNSS, daily), Leica: %.0f' % n_manual)
    n_manual_emlid = len(diffs_swe_daily.dswe_manual_emlid.dropna())
    print('Number of samples (manual vs. GNSS, daily), Emlid: %.0f' % n_manual_emlid)
    n_laser = len(diffs_swe_15min.dswe_laser)
    print('Number of samples (laser vs. GNSS, 15min): %.0f' % n_laser)
    n_laser_emlid = len(diffs_swe_15min.dswe_laser_emlid)
    print('Number of samples (laser vs. GNSS, 15min), Emlid: %.0f' % n_laser_emlid)


""" Define plot functions """


def plot_SWE_density_acc(dest_path, leica, emlid, manual, laser, save=[False, True], std_leica=None, std_emlid=None, suffix='', y_lim=(-200, 1400),
                         x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    plt.figure()
    leica.plot(linestyle='-', color='crimson', fontsize=12, figsize=(6, 5.5), ylim=y_lim).grid()
    emlid.plot(color='salmon', linestyle='--')
    plt.errorbar(manual.index, manual.Acc, yerr=manual.Acc / 10, color='darkblue', linestyle='', capsize=4, alpha=0.5)
    laser.dsh.plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
    manual.Acc.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
    plt.errorbar(manual.index, manual.Acc, yerr=manual.Acc / 10, color='darkblue', linestyle='', capsize=4, alpha=0.5)
    laser.dswe.plot(color='k', linestyle='--').grid()
    manual.SWE_aboveAnt.plot(color='k', linestyle=' ', marker='+', markersize=8, markeredgewidth=2).grid()
    manual.Density_aboveAnt.plot(color='steelblue', linestyle=' ', marker='*', markersize=8, markeredgewidth=2, label='Density (kg/m3)').grid()
    plt.errorbar(manual.index, manual.SWE_aboveAnt, yerr=manual.SWE_aboveAnt / 10, color='k', linestyle='', capsize=4,
                 alpha=0.5)
    if std_leica is not None:
        plt.fill_between(leica.index, leica - std_leica, leica + std_leica, color="crimson", alpha=0.2)
    if std_emlid is not None:
        plt.fill_between(emlid.index, emlid - std_emlid, emlid + std_emlid, color="salmon", alpha=0.2)
    # plt.fill_between(sh_std.index, sh - sh_std, sh + sh_std, color="darkblue", alpha=0.2)
    # plt.fill_between(s_15min.index, (m_15min-m_15min[0]) - s_15min, (m_15min-m_15min[0]) + s_15min, color="crimson", alpha=0.2)
    plt.xlabel(None)
    plt.ylabel('SWE (mm w.e.)', fontsize=14)
    plt.legend(
        ['High-end GNSS', 'Low-cost GNSS', 'Accumulation_Laser (mm)', 'Accumulation_Manual (mm)', 'Laser (SHM)',
         'Manual', 'Density (kg/m3)'], fontsize=11, loc='upper left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(dest_path + '30_plots/SWE_Accts_NM_Emlid_15s_Leica_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png', bbox_inches='tight')
        plt.savefig(dest_path + '30_plots/SWE_Accts_NM_Emlid_15s_Leica_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf', bbox_inches='tight')
    else:
        plt.show()


def plot_all_SWE(data_path, leica=None, emlid=None, manual=None, laser=None, buoy=None, poles=None, save=[False, True],
                 suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], std_leica=None, std_emlid=None, y_lim=(-100, 600),
                 x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot SWE (Leica, emlid) time series with reference data (laser, buoy, poles) and error bars
    """
    plt.close()
    plt.figure()
    if leica is not None:
        leica.plot(linestyle='-', color='crimson', fontsize=12, figsize=(6, 5.5), ylim=y_lim).grid()
    if emlid is not None:
        emlid.plot(color='salmon', linestyle='--')
    if manual is not None:
        manual.SWE_aboveAnt.plot(color='k', linestyle=' ', marker='+', markersize=8, markeredgewidth=2).grid()
        plt.errorbar(manual.SWE_aboveAnt.index, manual.SWE_aboveAnt, yerr=manual.SWE_aboveAnt / 10, color='k', linestyle='', capsize=4, alpha=0.5)
    if laser is not None:
        laser.dswe.dropna().plot(color='k', linestyle='--', label='Accumulation (cm)').grid()
    if buoy is not None:
        plt.plot(buoy[['dswe1', 'dswe2', 'dswe3', 'dswe4']], color='lightgrey', linestyle='-')
    if poles is not None:
        plt.plot(poles[['dswe1', 'dswe2', 'dswe3', 'dswe4', 'dswe5', 'dswe6', 'dswe7', 'dswe8', 'dswe9', 'dswe10', 'dswe11', 'dswe12', 'dswe13', 'dswe14', 'dswe15', 'dswe16']], linestyle=':', alpha=0.6)
    if std_leica is not None:
        plt.fill_between(leica.index, leica - std_leica, leica + std_leica, color="crimson", alpha=0.2)
    if std_emlid is not None:
        plt.fill_between(emlid.index, emlid - std_emlid, emlid + std_emlid, color="salmon", alpha=0.2)

    plt.xlabel(None)
    plt.ylabel('SWE (mm w.e.)', fontsize=14)
    plt.legend(leg, fontsize=12, loc='upper left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(data_path + '/30_plots/SWE_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png', bbox_inches='tight')
        plt.savefig(data_path + '/30_plots/SWE_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf', bbox_inches='tight')
    else:
        plt.show()


def plot_all_diffSWE(data_path, diffs_swe, manual=None, laser=None, buoy=None, poles=None, save=[False, True], suffix='',
                     leg=['Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=(-200, 600), x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot SWE (Leica, emlid) time series with reference data (laser, buoy, poles) and error bars
    """
    plt.close()
    plt.figure()
    diffs_swe.dswe_emlid.plot(linestyle='--', color='salmon', fontsize=12, figsize=(6, 5.5), ylim=y_lim).grid()
    if manual is not None:
        diffs_swe.dswe_manual.plot(color='k', linestyle=' ', marker='+', markersize=8, markeredgewidth=2).grid()
        plt.errorbar(diffs_swe.dswe_manual.index, diffs_swe.dswe_manual, yerr=diffs_swe.dswe_manual / 10, color='k', linestyle='', capsize=4, alpha=0.5)
    if laser is not None:
        diffs_swe.dswe_laser.plot(color='k', linestyle='--', label='Accumulation (cm)').grid()
    if buoy is not None:
        plt.plot(diffs_swe[['dswe_buoy1', 'dswe_buoy2', 'dswe_buoy3', 'dswe_buoy4']], color='lightgrey', linestyle='-')
    if poles is not None:
        plt.plot(diffs_swe[['dswe_pole1', 'dswe_pole2', 'dswe_pole3', 'dswe_pole4', 'dswe_pole5', 'dswe_pole6', 'dswe_pole7', 'dswe_pole8', 'dswe_pole9', 'dswe_pole10', 'dswe_pole11', 'dswe_pole12', 'dswe_pole13', 'dswe_pole14', 'dswe_pole15', 'dswe_pole16']], linestyle=':', alpha=0.6)

    plt.xlabel(None)
    plt.ylabel('ΔSWE (mm w.e.)', fontsize=14)
    plt.legend(leg, fontsize=12, loc='upper left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(data_path + '/30_plots/deltaSWE_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png', bbox_inches='tight')
        plt.savefig(data_path + '/30_plots/deltaSWE_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf', bbox_inches='tight')
    else:
        plt.show()


def plot_scatter(data_path, y_leica, y_emlid, x_value, predict_daily=None, predict_emlid_daily=None, x_label='Manual', lim=(-100, 600), save=[False, True]):
    plt.close()
    plt.figure(figsize=(4.5, 4.5))
    leica_x = pd.concat([y_leica, x_value], axis=1)
    leica_x.columns = ['dswe_y', 'dswe_x']
    emlid_x = pd.concat([y_emlid, x_value], axis=1)
    emlid_x.columns = ['dswe_y', 'dswe_x']
    ax = leica_x.plot.scatter(x='dswe_x', y='dswe_y', color='k')
    emlid_x.plot.scatter(x='dswe_x', y='dswe_y', color='salmon', ax=ax)
    if predict_daily is not None:
        plt.plot(range(50, 550), predict_daily(range(50, 550)), c='k', linestyle='--', alpha=0.7)  # linear regression leica
    if predict_emlid_daily is not None:
        plt.plot(range(50, 550), predict_emlid_daily(range(50, 550)), c='salmon', linestyle='-.', alpha=0.7)  # linear regression emlid
    ax.set_ylabel('GNSS SWE (mm w.e.)', fontsize=14)
    ax.set_ylim(lim)
    ax.set_xlim(lim)
    ax.set_xlabel(x_label + ' SWE (mm w.e.)', fontsize=14)
    plt.legend(['High-end GNSS', 'Low-cost GNSS'], fontsize=12, loc='upper left')
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.grid()
    if save is True:
        plt.savefig(data_path + '/30_plots/scatter_SWE_' + x_label + '.png', bbox_inches='tight')
        plt.savefig(data_path + '/30_plots/scatter_SWE_' + x_label + '.pdf', bbox_inches='tight')
    else:
        plt.show()


def plot_swediff_boxplot(dest_path, diffs, y_lim=(-200, 600), save=[False, True]):
    """ Plot boxplot of differences of SWE from manual/laser/emlid data to Leica data
    """
    diffs.dswe_manual.describe()
    diffs.dswe_laser.describe()
    diffs.dswe_emlid.describe()
    diffs[['dswe_manual', 'dswe_laser', 'dswe_emlid']].plot.box(ylim=y_lim, figsize=(3, 4.5), fontsize=12, rot=15)
    plt.grid()
    plt.ylabel('ΔSWE (mm w.e.)', fontsize=12)
    if save is True:
        plt.savefig(dest_path + '30_plots/box_diffSWE.png', bbox_inches='tight')
        plt.savefig(dest_path + '30_plots/box_diffSWE.pdf', bbox_inches='tight')
    else:
        plt.show()


def plot_all_Acc(data_path, leica=None, emlid=None, manual=None, laser=None, buoy=None, poles=None, save=[False, True],
                 suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=(-200, 1400), x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot Accumulation (Leica, emlid) time series with reference data (laser, buoy, poles) and error bars
    """
    plt.close()
    plt.figure()
    if leica is not None:
        leica.dsh.plot(linestyle='-', color='crimson', fontsize=12, figsize=(6, 5.5), ylim=y_lim, x_compat=True).grid()
    if emlid is not None:
        emlid.dsh.plot(color='salmon', linestyle='--')
    if manual is not None:
        manual.Acc.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
        plt.errorbar(manual.Acc.index, manual.Acc, yerr=manual.Acc / 10, color='darkblue', linestyle='', capsize=4, alpha=0.5)
    if laser is not None:
        laser.dsh.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
    if buoy is not None:
        plt.plot(buoy[['dsh1', 'dsh2', 'dsh3', 'dsh4']], color='lightgrey', linestyle='-')
    if poles is not None:
        plt.plot(poles[['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']], linestyle=':', alpha=0.6)

    plt.xlabel(None)
    plt.ylabel('Snow accumulation (mm)', fontsize=14)
    plt.legend(leg, fontsize=12, loc='upper left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(data_path + '/30_plots/Acc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png', bbox_inches='tight')
        plt.savefig(data_path + '/30_plots/Acc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf', bbox_inches='tight')
    else:
        plt.show()


def plot_all_diffAcc(data_path, diffs_sh, diffs_sh_15min, manual=None, laser=None, buoy=None, poles=None, save=[False, True],
                     suffix='', leg=['Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=(-400, 1000), x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot SWE (Leica, emlid) time series with reference data (laser, buoy, poles) and error bars
    """
    plt.close()
    plt.figure()
    diffs_sh_15min.dsh_emlid.plot(linestyle='--', color='salmon', fontsize=12, figsize=(6, 5.5), ylim=y_lim).grid()
    if manual is not None:
        diffs_sh.dsh_manual.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
        plt.errorbar(diffs_sh.dsh_manual.index, diffs_sh.dsh_manual, yerr=diffs_sh.dsh_manual / 10, color='darkblue', linestyle='', capsize=4, alpha=0.5)
    if laser is not None:
        diffs_sh_15min.dsh_laser.plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
    if buoy is not None:
        plt.plot(diffs_sh[['dsh_buoy1', 'dsh_buoy2', 'dsh_buoy3', 'dsh_buoy4']], color='lightgrey', linestyle='-')
    if poles is not None:
        plt.plot(diffs_sh[['dsh_pole1', 'dsh_pole2', 'dsh_pole3', 'dsh_pole4', 'dsh_pole5', 'dsh_pole6', 'dsh_pole7', 'dsh_pole8', 'dsh_pole9', 'dsh_pole10', 'dsh_pole11', 'dsh_pole12', 'dsh_pole13', 'dsh_pole14', 'dsh_pole15', 'dsh_pole16']], linestyle=':', alpha=0.6)

    plt.xlabel(None)
    plt.ylabel('ΔSnow accumulation (mm)', fontsize=14)
    plt.legend(leg, fontsize=12, loc='upper left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(data_path + '/30_plots/deltaAcc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png', bbox_inches='tight')
        plt.savefig(data_path + '/30_plots/deltaAcc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf', bbox_inches='tight')
    else:
        plt.show()


def plot_nrsat(data_path, nr_sat_leica, nr_sat_emlid, save=[False, True], suffix='', y_lim=(0, 35), x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot number of satellites for high-end and low-cost rovers
    """
    plt.close()
    plt.figure()
    nr_sat_leica.plot(linestyle='-', color='k', fontsize=12, figsize=(6, 5.5), ylim=y_lim, x_compat=True).grid()
    nr_sat_emlid.plot(color='salmon', linestyle='--').grid()

    plt.xlabel(None)
    plt.ylabel('Number of satellites', fontsize=14)
    plt.legend(['High-end GNSS', 'Low-cost GNSS'], fontsize=12, loc='lower left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(
            data_path + '/30_plots/Nrsat_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png',
            bbox_inches='tight')
        plt.savefig(
            data_path + '/30_plots/Nrsat_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf',
            bbox_inches='tight')
    else:
        plt.show()


def plot_solquality(data_path, amb_leica, amb_emlid, save=[False, True], suffix='', y_lim=(0, 10),
                    x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot quality of ambiguity resolution (1=fix, 2=float, 5=standalone) for high-end and low-cost rovers
    """
    plt.close()
    plt.figure()
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(6, 5.5))
    amb_emlid.plot(ax=axes[0], linestyle='', marker='o', markersize=2, color='salmon', ylim=y_lim).grid()
    amb_leica.plot(ax=axes[1], linestyle='', marker='o', markersize=2, color='k', ylim=y_lim).grid()
    plt.xlabel(None)
    plt.ylabel(None)
    # plt.legend(['High-end GNSS', 'Low-cost GNSS'], fontsize=12, loc='center left')
    # plt.xlim(x_lim)
    # plt.gca().xaxis.set_major_locator(MonthLocator())
    # plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    axes[1].xaxis.set_major_locator(MonthLocator())
    axes[1].xaxis.set_major_locator(MonthLocator(bymonthday=15))
    axes[0].legend(['Low-cost GNSS'], fontsize=12)
    axes[1].legend(['High-end GNSS'], fontsize=12)
    plt.xticks(fontsize=14)
    axes[1].set_xlim(x_lim)
    axes[0].set_yticks(ticks=[1, 2, 5], labels=['Fixed', 'Float', 'Single'], fontsize=12)
    axes[1].set_yticks(ticks=[1, 2, 5], labels=['Fixed', 'Float', 'Single'], fontsize=12)
    if save is True:
        plt.savefig(
            data_path + '/30_plots/Ambstate_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png',
            bbox_inches='tight')
        plt.savefig(
            data_path + '/30_plots/Ambstate_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf',
            bbox_inches='tight')
    else:
        plt.show()


def plot_PPP_solution(dest_path, save=[False, True], suffix='', x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Read PPP solution and plot it
    """
    # create empty dataframe for all .log files
    df_ppp = pd.DataFrame()
    # read all PPP solution files in folder, parse date and time columns to datetimeindex and add them to the dataframe
    for file in glob.iglob(dest_path + '10_ppp/*.pos', recursive=True):
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
    plt.xlim(x_lim)
    if save is True:
        plt.savefig('30_plots/ppp_LLH_base_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png', bbox_inches='tight')
        plt.savefig('30_plots/ppp_LLH_base_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf', bbox_inches='tight')
    else:
        plt.show()

    return df_ppp


