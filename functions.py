""" Functions to generate daily rinex 3.0x files from day-overlapping Emlid rinex files;
    Necessary preprocessing for daily file processing with RTKLib
    created by: L. Steiner (Orchid ID: 0000-0002-4958-0849)
    created on: 17.05.2021
    updated on: 10.05.2023
    
    requirements:   - install gnssrefl on Linux/Mac (gnssrefl is not working on Windows, see gnssrefl docs)
                    - gnssrefl (https://github.com/kristinemlarson/gnssrefl)
                    - gfzrnx (https://dataservices.gfz-potsdam.de/panmetaworks/showshort.php?id=escidoc:1577894)
                    - wget
                    - 7zip
                    - path to all programs added to the system environment variables
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
from datetime import date


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


def get_mjd_int(syyyy, smm, sdd, eyyyy, emm, edd):
    """ calculate start/end mjd using a start and end date of format '2022', '10', '01')
    :param dest_path: local temporary directory for preprocessing the GNSS rinex files
    """
    start_mjd = jdcal.gcal2jd(str(syyyy), str(smm), str(sdd))[1]
    end_mjd = jdcal.gcal2jd(str(eyyyy), str(emm), str(edd))[1]

    return start_mjd, end_mjd


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
        if not os.path.exists(dest_path):
            os.makedirs(dest_path, exist_ok=True)
        shutil.copyfile(source_path_file, dest_path_file)
        print("\ncopy from %s to %s \nok" % (source_path_file, dest_path_file))
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


def copy_rinex_files(source_path, dest_path, receiver=['NMLB', 'NMLR', 'NMER'], copy=[True, False],
                     parent=[True, False], hatanaka=[True, False], move=[True, False], delete_temp=[True, False]):
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
                        print(colored("\nfile in destination already exists: %s, \ncopy aborted!!!" % dest_file,
                                      'yellow'))
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
    # TODO: remove _events from sol files
    # get the newest solution file name
    name_max = os.path.basename(
        sorted(glob.iglob(dest_path + '20_solutions/NMLR/' + resolution + '/*.POS', recursive=True), reverse=True)[
            0]).split('.')[0]
    start_yy = name_max[2:4]
    start_doy = int(name_max[-3:]) + 1
    start_date = gnsscal.yrdoy2date(int('20' + start_yy), start_doy)
    start_mjd = jdcal.gcal2jd(start_date.year, start_date.month, start_date.day)[1]
    print(colored('start year %s, doy %s, mjd %s, date %s for further processing of Leica Rover' % (
    start_yy, start_doy, start_mjd, start_date), 'blue'))

    # get the newest emlid solution file name
    name_max_emlid = os.path.basename(
        sorted(glob.iglob(dest_path + '20_solutions/NMER/' + resolution + '/*.POS', recursive=True), reverse=True)[
            0]).split('.')[0]
    start_yy_emlid = name_max_emlid[2:4]
    start_doy_emlid = int(name_max_emlid[-3:]) + 1
    start_date_emlid = gnsscal.yrdoy2date(int('20' + start_yy_emlid), start_doy_emlid)
    start_mjd_emlid = jdcal.gcal2jd(start_date_emlid.year, start_date_emlid.month, start_date_emlid.day)[1]
    print(colored('start year %s, doy %s, mjd %s, date %s for further processing of Emlid Rover' % (
    start_yy_emlid, start_doy_emlid, start_mjd_emlid, start_date_emlid), 'blue'))

    return start_yy, start_mjd, start_mjd_emlid


""" Define RTKLIB functions """


def automate_rtklib_pp(dest_path, rover_prefix, mjd_start, mjd_end, ti_int, base_prefix, brdc_nav_prefix,
                       precise_nav_prefix, resolution, ending, rover_name=['NMER_original', 'NMER', 'NMLR'],
                       options=['options_Emlid', 'options_Leica']):
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
            base_file = base_prefix + doy + '*.' + year + 'O'
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


def run_rtklib_pp(dest_path, options, ti_int, output_file, rover_file, base_file, brdc_orbit_gps, brdc_orbit_glonass,
                  brdc_orbit_galileo, precise_orbit):
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
    print(colored(
        '\nstored all old and new ENU solution data (without dublicates) in pickle: ' + '20_solutions/' + rover_name + '_' + resolution + ending + '.pkl',
        'blue'))

    # delete temporary solution directory
    if os.path.exists(path):
        shutil.rmtree(path)
    print(colored('\nAll new ENU solution files are moved to solutions dir and temp solutions directory is removed',
                  'blue'))

    return df_enu


def filter_rtklib_solutions(dest_path, rover_name, resolution, df_enu, ambiguity=[1, 2, 5], threshold=2, window='D', ending=''):
    """ filter and clean ENU solution data (outlier filtering, median filtering, adjustments for observation mast heightening)
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :param df_enu: pandas dataframe containing all seasons solution data columns ['date', 'time', 'U (m)', 'amb_state', 'nr_sat', 'std_u (m)']
    :param rover_name: name of rover
    :param resolution: processing time interval (in minutes)
    :param ambiguity: ambiguity resolution state [1: fixed, 2: float, 5: standalone]
    :param threshold: set threshold for outlier removing using the standard deviation (default=2 sigma)
    :param window: window for median filter (default='D')
    :param ending: suffix of solution file names (e.g. a varian of processing options: '_noglonass'
    :return: fil_df, fil, fil_clean, m, s, jump, swe_gnss, swe_gnss_daily, std_gnss_daily
    """

    print(colored('\nFiltering data', 'blue'))

    # Q: select only data where ambiguities are fixed (amb_state==1) or float (amb_state==2) and sort datetime index
    print('\nselect data with ambiguity solution state: %s' % ambiguity)
    fil_df = pd.DataFrame(df_enu[(df_enu.amb_state == ambiguity)])
    fil_df.index = pd.DatetimeIndex(fil_df.index)
    fil_df = fil_df.sort_index()
    u = fil_df.U * 1000     # convert up (swe) component to mm

    # Q: adjust for snow mast heightening (approx. 3m elevated several times a year)
    print('\ndata is corrected for snow mast heightening events (remove sudden jumps > 1m)')
    jump = u[(u.diff() < -1000)]

    # get value of jump difference (of values directly after - before jump)
    jump_ind = jump.index.format()[0]
    jump_val = u[jump_ind] - u[:jump_ind][-2]

    while jump.empty is False:
        print('\njump of height %s is detected! at %s' % (jump_val, jump.index.format()[0]))
        adj = u[(u.index >= jump.index.format()[0])] - jump_val  # correct all observations after jump [0]
        u = pd.concat([u[~(u.index >= jump.index.format()[0])],
                       adj])  # concatenate all original obs before jump with adjusted values after jump
        jump = u[(u.diff() < -1000)]

    print('\nno jump detected!')

    # Q: remove outliers based on x*sigma threshold
    print('\nremove outliers based on %s * sigma threshold' % threshold)
    upper_limit = u.rolling('3D').median() + threshold * u.rolling('3D').std()
    lower_limit = u.rolling('3D').median() - threshold * u.rolling('3D').std()
    u_clean = u[(u > lower_limit) & (u < upper_limit)]

    # Q: filter data with a rolling median
    print('\ndata is median filtered with window length: %s' % window)
    swe_gnss = u_clean.rolling(window).median()
    std_gnss = u_clean.rolling(window).std()

    # Q: correct values to be positive values (add min value -3258.5 on '2021-12-13 20:29:42')
    swe_gnss = swe_gnss - swe_gnss.min()
    swe_gnss.index = swe_gnss.index + pd.Timedelta(seconds=18)

    # resample data per day, calculate median and standard deviation (noise) per day to fit manual reference data
    swe_gnss_daily = swe_gnss.resample('D').median()
    std_gnss_daily = swe_gnss.resample('D').std()

    # Q: store swe results to pickle
    print(colored(
        '\ndata is filtered, cleaned, and corrected and SWE results are stored to pickle and .csv: %s' % '20_solutions/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl',
        'blue'))
    os.makedirs(dest_path + '20_solutions/SWE_results/', exist_ok=True)
    swe_gnss.to_pickle(
        dest_path + '20_solutions/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl')
    swe_gnss.to_csv(dest_path + '20_solutions/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.csv')

    return fil_df, u, u_clean, swe_gnss, std_gnss, swe_gnss_daily, std_gnss_daily


def read_swe_gnss(dest_path, swe_gnss, rover_name, resolution, ending):
    # read gnss swe results from pickle
    if swe_gnss is None:
        print(colored(
            '\nSWE results are NOT available, reading from pickle: %s' % '20_solutions/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl',
            'orange'))
        swe_gnss = pd.read_pickle(
            dest_path + '20_solutions/SWE_results/swe_gnss_' + rover_name + '_' + resolution + ending + '.pkl')

    return swe_gnss


""" Define reference sensors functions """


def read_manual_observations(dest_path):
    """ read and interpolate manual accumulation (cm), density (kg/m^3), SWE (mm w.e.) data
        :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
        :return: manual2, ipol
    """
    # create local directory for reference observations
    loc_ref_dir = dest_path + '00_reference_data/'
    os.makedirs(loc_ref_dir, exist_ok=True)

    # read data
    print('\nread manual observations')
    manual = pd.read_csv(loc_ref_dir + 'Manual_Spuso.csv', header=1, skipinitialspace=True,
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
    # create local directory for snow buoy observations
    loc_buoy_dir = dest_path + '00_reference_data/Snowbuoy/'
    os.makedirs(loc_buoy_dir, exist_ok=True)

    # Q: download newest snow buoy data from url
    # get data from url
    r = requests.get(url, allow_redirects=True)

    # decompress file
    z = zipfile.ZipFile(io.BytesIO(r.content))

    # store selected file from decompressed folder to working direcory subfolder
    z.extract(z.filelist[2], path=loc_buoy_dir)

    # Q: read snow buoy data
    print('\nread snow buoy observations')
    buoy_all = pd.read_csv(loc_buoy_dir + '2017S54_300234011695900_proc.csv', header=0,
                           skipinitialspace=True, delimiter=',', index_col=0, skiprows=0, na_values=["NaN"],
                           parse_dates=[0],
                           names=['lat', 'lon', 'sh1', 'sh2', 'sh3', 'sh4', 'pressure', 'airtemp', 'bodytemp',
                                  'gpstime'])

    # select only accumulation data from season 21/22 & convert to mm
    buoy = buoy_all[['sh1', 'sh2', 'sh3', 'sh4']]['2021-11-26':] * 1000

    # Q: adjust for snow mast heightening (approx. 1m elevated); value of jump difference (of values directly after - before jump): 2023-01-24 21:01:00 1036.0
    print('\ndata is corrected for snow buoy heightening events (remove sudden jumps > 1m)')
    jump_ind = '2023-01-24 21:01:00'
    jump_val = 1036

    print('\ncorrect jump of height %s: at %s' % (jump_val, jump_ind))
    adj = buoy[['sh1', 'sh2', 'sh3', 'sh4']][
              (buoy.index >= jump_ind)] + jump_val  # correct all observations after jump [0]
    buoy_corr = pd.concat([buoy[['sh1', 'sh2', 'sh3', 'sh4']][~(buoy.index >= jump_ind)],
                           adj])  # concatenate all original obs before jump with adjusted values after jump

    # Q: Differences in accumulation & conversion to SWE
    # calculate change in accumulation (in mm) for each buoy sensor add it as an additional column to the dataframe buoy
    buoy_change = (buoy_corr[['sh1', 'sh2', 'sh3', 'sh4']] - buoy_corr[['sh1', 'sh2', 'sh3', 'sh4']].min())
    buoy_change.columns = ['dsh1', 'dsh2', 'dsh3', 'dsh4']

    # convert snow accumulation to SWE (with interpolated and constant density values)
    print('\n-- convert buoy observations to SWE')
    buoy_swe = convert_sh2swe(buoy_change, ipol_density)
    buoy_swe.columns = ['dswe1', 'dswe2', 'dswe3', 'dswe4']

    buoy_swe_constant = convert_sh2swe(buoy_change)
    buoy_swe_constant.columns = ['dswe_const1', 'dswe_const2', 'dswe_const3', 'dswe_const4']

    # append new columns to existing buoy dataframe
    buoy = pd.concat([buoy_corr, buoy_change, buoy_swe, buoy_swe_constant], axis=1)

    return buoy


def read_pole_observations(dest_path, ipol_density=None):
    """ read Pegelfeld Spuso accumulation data from 16 poles and convert to SWE
        :param ipol_density: interpolated density data from manual reference observations
        :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
        :return: poles
    """
    # create local directory for reference observations
    loc_ref_dir = dest_path + '00_reference_data/'
    os.makedirs(loc_ref_dir, exist_ok=True)

    # Q: read Pegelfeld Spuso pole observations
    print('\nread Pegelfeld Spuso pole observations')
    poles = pd.read_csv(loc_ref_dir + 'Pegelfeld_Spuso_Akkumulation.csv', header=0, delimiter=';',
                        index_col=0, skiprows=0, na_values=["NaN"], parse_dates=[0], dayfirst=True)

    # convert to non-negative values
    poles_corr = poles - poles.min().min()

    # Q: convert snow accumulation to SWE (with interpolated and constant density values)
    print('\n-- convert Pegelfeld Spuso pole observations to SWE')
    poles_swe = convert_sh2swe(poles_corr, ipol_density)
    poles_swe.columns = ['dswe'] + poles_swe.columns

    poles_swe_constant = convert_sh2swe(poles_corr)
    poles_swe_constant.columns = ['dswe_const'] + poles_swe_constant.columns

    # append new columns to existing poles dataframe
    poles = pd.concat([poles_corr, poles_swe, poles_swe_constant], axis=1)

    return poles


def read_laser_observations(dest_path, laser_path, yy, ipol, laser_pickle='nm_laser'):
    """ read snow accumulation observations (minute resolution) from laser distance sensor data
    :param ipol: interpolated density data from manual reference observations
    :param laser_pickle: read laser pickle (e.g., '00_reference_data/Laser/nm_shm.pkl') and logfiles creating/containing snow accumulation observations from laser distance sensor
    :param dest_path: path to GNSS rinex observation and navigation data, and rtkpost configuration file
    :return: df_shm, h, fil_h_clean, h_resampled, h_std_resampled, sh, sh_std
    """
    # create local directory for laser observations
    loc_laser_dir = dest_path + '00_reference_data/Laser/'
    os.makedirs(loc_laser_dir, exist_ok=True)

    # Q: copy laser observations (*.log/shm = *.[ls]??) from AWI server if not already existing
    print(colored("\ncopy new laser files", 'blue'))
    # get list of yearly directories newer than first year
    for year in os.listdir(laser_path)[:-1]:
        if int(year) >= int('20' + yy):
            # copy missing laser observation files
            for f in glob.glob(laser_path + year + '/*.[ls]??'):
                file = os.path.basename(f)
                # skip files of 2021 before 26th nov (no gps data before installation)
                if int(file[2:8]) > 211125:
                    if not os.path.exists(loc_laser_dir + file):
                        shutil.copy2(f, loc_laser_dir)
                        print("file copied from %s to %s" % (f, loc_laser_dir))
                    else:
                        # print(colored("\nfile in destination already exists: %s, \ncopy aborted!!!" % dest_path, 'yellow'))
                        pass
                else:
                    pass
        else:
            pass
    print(colored("\nnew laser files copied", 'blue'))

    # Q: read all existing laser observations from .pkl if already exists, else create empty dataframe
    path_to_oldpickle = loc_laser_dir + laser_pickle + '.pkl'
    if os.path.exists(path_to_oldpickle):
        print(colored('\nReading already existing laser observations from pickle: %s' % path_to_oldpickle, 'yellow'))
        laser = pd.read_pickle(path_to_oldpickle)
        old_idx = laser.index[-1].date().strftime("%y%m%d")
    else:
        print(colored('\nNo existing laser observations pickle!', 'yellow'))
        laser = pd.DataFrame()
        old_idx = '211125'

    # Q: read new snow accumulation files *.[log/shm] (minute resolution) from laser distance sensor data, parse date and time columns to datetimeindex and add them to the dataframe
    print(colored('\nReading all new logfiles from: %s' % loc_laser_dir + 'nm*.[log/shm]', 'blue'))
    for file in glob.iglob(loc_laser_dir + 'nm*.[ls]??', recursive=True):
        # read accumulation files newer than last entry in laser pickle
        if int(os.path.basename(file)[2:8]) > int(old_idx):
            print(file)

            # check if old or new type laser data format to read due to the installation of a new sensor on 22-12-2022
            if int(os.path.basename(file)[2:8]) <= 221222:
                # read all old-type snow accumulation.log files
                # header: 'date', 'time', 'snow level (m)', 'signal(-)', 'temp (°C)', 'error (-)', 'checksum (-)'
                shm = pd.read_csv(file, header=0, delimiter=r'[ >]', skipinitialspace=True, na_values=["NaN"],
                                  names=['date', 'time', 'none', 'sh', 'signal', 'temp', 'error', 'check'],
                                  usecols=[0, 1, 3, 5, 6],
                                  encoding='latin1', parse_dates=[['date', 'time']], index_col=['date_time'],
                                  engine='python', dayfirst=True)
            else:
                # read all new-type snow accumulation.shm files
                # header: Year	Month	Day	Hour	Minute	Second	Command	TelegramNumber	SerialNumber	SnowLevel	SnowSignal	Temperature	TiltAngle	Error	UmbStatus	Checksum	DistanceRaw	Unknown	Checksum660
                shm = pd.read_csv(file, header=0, delimiter=' |;', na_values=["NaN"],
                                  names=['datetime', 'Command', 'TelegramNumber', 'SerialNumber', 'sh', 'signal',
                                         'temp', 'TiltAngle', 'error', 'check'],
                                  usecols=[0, 4, 6, 8],
                                  encoding='latin1', parse_dates=['datetime'], index_col=0,
                                  engine='python')
                # only select error infos in 'error' (first column)
                shm.error = shm.error.str.split(':', expand=True)[0]
                # change outlier values ('///////') to NaN
                shm.sh = pd.to_numeric(shm.sh, errors='coerce')
                shm.error = pd.to_numeric(shm.error, errors='coerce')

            # add loaded file to existing laser df
            laser = pd.concat([laser, shm], axis=0)

        else:
            continue

    # calculate change in accumulation (in mm) and add it as an additional column to the dataframe
    laser['dsh'] = (laser['sh'] - laser['sh'][0]) * 1000

    # detect all dublicates and only keep last dublicated entries
    laser = laser[~laser.index.duplicated(keep='last')]

    # store as .pkl
    laser.to_pickle(loc_laser_dir + laser_pickle + '.pkl')
    print(colored(
        '\nstored all old and new laser observations (without dublicates) to pickle: %s' + loc_laser_dir + laser_pickle + '.pkl',
        'blue'))

    return laser


def filter_laser_observations(ipol, laser, threshold=1):
    """ filter snow accumulation observations (minute resolution) from laser distance sensor data
    :param threshold: threshold for removing outliers (default=1)
    :param ipol: interpolated density data from manual reference observations
    :param laser: laser data
    :return: laser_filtered
    """

    # Q: remove outliers in laser observations
    print('\n-- filtering laser observations')
    # 0. select only observations without errors
    dsh = laser[(laser.error == 0)].dsh

    # 1. remove huge outliers
    f = dsh[(dsh > dsh.min())]

    # 2. remove outliers based on an x sigma threshold
    print('\nremove outliers based on %s * sigma threshold' % threshold)
    upper_limit = f.rolling('7D').median() + threshold * f.rolling('7D').std()
    lower_limit = f.rolling('7D').median() - threshold * f.rolling('7D').std()
    f_clean = f[(f > lower_limit) & (f < upper_limit)]

    # 3. remove remaining outliers based on their gradient
    print('\nremove outliers based on gradient')
    gradient = f_clean.diff()
    outliers = f_clean.index[(gradient > 500) | (gradient < -500)]
    while outliers.empty is False:
        fil_dsh = f_clean.loc[~f_clean.index.isin(outliers)]
        f_clean = fil_dsh
        gradient = f_clean.diff()
        outliers = f_clean.index[(gradient > 500) | (gradient < -500)]

    # Q: filter observations
    print('\nmedian filtering')
    laser_fil = f_clean.rolling('D').median()
    laser_fil_std = f_clean.rolling('D').std()

    # calculate change in accumulation (in mm) and add it as an additional column to the dataframe
    print('\ncalculate diff to min')
    dsh_laser = (laser_fil - laser_fil.min())

    # Q: calculate SWE from accumulation data
    print('\n-- convert laser observations to SWE')
    laser_swe = convert_sh2swe(dsh_laser, ipol_density=ipol)
    laser_swe_constant = convert_sh2swe(dsh_laser)

    # append new columns to existing laser dataframe
    laser_filtered = pd.concat([dsh_laser, laser_fil_std, laser_swe, laser_swe_constant], axis=1)
    laser_filtered.columns = ['dsh', 'dsh_std', 'dswe', 'dswe_const']

    return laser_filtered


def read_reference_data(dest_path, laser_path, yy, url, read_manual=[True, False], read_buoy=[True, False],
                        read_poles=[True, False], read_laser=[True, False],
                        laser_pickle='00_reference_data/Laser/nm_laser.pkl'):
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
        laser = read_laser_observations(dest_path, laser_path, yy, ipol, laser_pickle)
        laser_filtered = filter_laser_observations(ipol, laser, threshold=1)
    else:
        laser, laser_filtered = None, None

    print(colored('\n\nreference observations are loaded', 'blue'))

    return manual, ipol, buoy, poles, laser, laser_filtered


def convert_swesh2density(swe, sh, cal_date, cal_val):
    """ calculate, calibrate, and filter snow density [kg/m3] from SWE and snow accumulation: density[kg/m3] = SWE [mm w.e.] * 1000 / sh[m])
    :param swe: dataframe containing swe values (in mm w.e.) from GNSS-refractometry
    :param sh: dataframe containing accumulation values (in m) from GNSS-reflectometry
    :param cal_date: date used for calibration (when 1m snow above antenna is reached)
    :param cal_val: calibration value from manual observations
    :return: density
    """
    # calculate density
    density = ((swe * 1000).divide(sh, axis=0)).dropna()

    # calibrate with ref manual density above antenna where 1m is reached ['2022-07-24']
    cal = cal_val - density.resample('D').median()[cal_date]
    density_fil = density.rolling('7D').median() + cal

    # remove densities lower than the density of new snow (50 kg/m3) or higher than the density of firn (830 kg/m3) or ice (917 kg/m3)
    density_cleaned = density_fil[~((density_fil < 50) | (density_fil >= 830))]

    return density_cleaned

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
    dsh_poles = (
        poles[['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']].subtract(
            leica.dsh, axis='index')).dropna()
    dswe_poles = (poles[['dswe1', 'dswe2', 'dswe3', 'dswe4', 'dswe5', 'dswe6', 'dswe7', 'dswe8', 'dswe9', 'dswe10',
                         'dswe11', 'dswe12', 'dswe13', 'dswe14', 'dswe15', 'dswe16']].subtract(leica.dswe,
                                                                                               axis='index')).dropna()

    # calculate differences to emlid data
    dsh_manual_emlid = (manual.Acc - emlid.dsh).dropna()
    dswe_manual_emlid = (manual.SWE_aboveAnt - emlid.dswe).dropna()
    dsh_laser_emlid = (laser.dsh - emlid.dsh).dropna()
    dswe_laser_emlid = (laser.dswe - emlid.dswe).dropna()

    # concatenate all difference dataframes
    diffs_sh = pd.concat([dsh_emlid, dsh_manual, dsh_laser, dsh_buoy, dsh_poles, dsh_manual_emlid, dsh_laser_emlid],
                         axis=1)
    diffs_sh.columns = ['dsh_emlid', 'dsh_manual', 'dsh_laser', 'dsh_buoy1', 'dsh_buoy2', 'dsh_buoy3', 'dsh_buoy4',
                        'dsh_pole1',
                        'dsh_pole2', 'dsh_pole3', 'dsh_pole4', 'dsh_pole5', 'dsh_pole6', 'dsh_pole7', 'dsh_pole8',
                        'dsh_pole9',
                        'dsh_pole10', 'dsh_pole11', 'dsh_pole12', 'dsh_pole13', 'dsh_pole14', 'dsh_pole15',
                        'dsh_pole16', 'dsh_manual_emlid', 'dsh_laser_emlid']

    diffs_swe = pd.concat(
        [dswe_emlid, dswe_manual, dswe_laser, dswe_buoy, dswe_poles, dswe_manual_emlid, dswe_laser_emlid], axis=1)
    diffs_swe.columns = ['dswe_emlid', 'dswe_manual', 'dswe_laser', 'dswe_buoy1', 'dswe_buoy2', 'dswe_buoy3',
                         'dswe_buoy4', 'dswe_pole1',
                         'dswe_pole2', 'dswe_pole3', 'dswe_pole4', 'dswe_pole5', 'dswe_pole6', 'dswe_pole7',
                         'dswe_pole8', 'dswe_pole9',
                         'dswe_pole10', 'dswe_pole11', 'dswe_pole12', 'dswe_pole13', 'dswe_pole14', 'dswe_pole15',
                         'dswe_pole16', 'dswe_manual_emlid', 'dswe_laser_emlid']

    print(colored('\nDifferences of all reference sensors to Leica data and manual/laser to Emlid data is calculated',
                  'blue'))

    return diffs_sh, diffs_swe


def calculate_differences2gnss_15min(emlid, leica, laser):
    """ calculate differences between reference data and GNSS (Leica) with a high resolution of 15min
    :param emlid: GNSS SWE/SH estimations from low-cost sensor
    :param leica: GNSS SWE/SH estimtions from high-end sensor
    :param laser: filtered SWE/SH observations from laser distance sensor
    :return: diffs_sh, diffs_swe, laser_15min
    """
    # resample laser observations to match resolution of GNSS data (15min)
    laser_15min = laser.resample('15min').first()

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

    print(colored('\nDifferences of laser & emlid data to Leica and laser to Emlid is calculated for 15min resolutions',
                  'blue'))

    return diffs_sh, diffs_swe, laser_15min


def calculate_crosscorr(leica_daily, emlid_daily, manual, gnss_leica, gnss_emlid, laser_15min, gnssir_acc=None,
                        gnssir_acc_daily=None, res='SWE'):
    """ calculate Pearson cross correlation coefficient for daily and 15min resolutions between
        Leica & Emlid GNSS data and manual and laser observations
    :param gnssir_acc: GNSS reflectometry results, daily resolution
    :param gnssir_acc_daily: GNSS reflectometry results, 15min resolution
    :param leica_daily: GNSS SWE/SH estimtions from high-end sensor, daily resolution
    :param emlid_daily: GNSS SWE/SH estimtions from low-cost sensor, daily resolution
    :param manual: manual SWE/SH observations, daily resolution
    :param gnss_leica: GNSS SWE/SH estimtions from high-end sensor, 15min resolution
    :param gnss_emlid: GNSS SWE/SH estimtions from low-cost sensor, 15min resolution
    :param laser_15min: SWE/SH observations from laser distance sensor, 15min resolution
    :param res: type of results ['SWE', 'Acc']
    """
    print(colored('\nGNSS reflectometry results: ' + res, 'blue'))
    if res == 'SWE':
        # SWE cross correation manual vs. GNSS (daily)
        corr_leica_daily = manual.SWE_aboveAnt.corr(leica_daily.dswe)
        corr_emlid_daily = manual.SWE_aboveAnt.corr(emlid_daily.dswe)
        print('\nPearsons correlation (manual vs. GNSS, daily), Leica: %.2f' % corr_leica_daily)
        print('Pearsons correlation (manual vs. GNSS, daily), Emlid: %.2f' % corr_emlid_daily)

        # calculate SWE cross correation laser vs. GNSS (15min)
        corr_leica_15min = laser_15min.dswe.corr(gnss_leica.dswe)
        corr_emlid_15min = laser_15min.dswe.corr(gnss_emlid.dswe)
        print('Pearsons correlation (laser vs. GNSS, 15min), Leica: %.2f' % corr_leica_15min)
        print('Pearsons correlation (laser vs. GNSS, 15min), Emlid: %.2f' % corr_emlid_15min)

    if res == 'Acc':
        # Acc cross correation manual vs. GNSS (daily)
        corr_leica_daily = manual.Acc.corr(leica_daily.dsh)
        corr_emlid_daily = manual.Acc.corr(emlid_daily.dsh)
        corr_gnssir_daily = manual.Acc.corr(gnssir_acc_daily)
        print('\nPearsons correlation (manual vs. GNSS, daily), Leica: %.2f' % corr_leica_daily)
        print('Pearsons correlation (manual vs. GNSS, daily), Emlid: %.2f' % corr_emlid_daily)
        print('Pearsons correlation (manual vs. GNSS-R, daily): %.2f' % corr_gnssir_daily)

        # calculate Acc cross correation laser vs. GNSS (15min)
        corr_leica_15min = laser_15min.dsh.corr(gnss_leica.dsh)
        corr_emlid_15min = laser_15min.dsh.corr(gnss_emlid.dsh)
        corr_gnssir_15min = laser_15min.dsh.corr(gnssir_acc)
        print('Pearsons correlation (laser vs. GNSS, 15min), Leica: %.2f' % corr_leica_15min)
        print('Pearsons correlation (laser vs. GNSS, 15min), Emlid: %.2f' % corr_emlid_15min)
        print('Pearsons correlation (laser vs. GNSS-R, 15min): %.2f' % corr_gnssir_15min)


def calculate_crosscorr_density(density_leica, density_emlid, manual):
    """ calculate Pearson cross correlation coefficient for daily and 15min resolutions between
        Leica & Emlid GNSS data and manual and laser observations
    :param density_leica: GNSS-RR density estimtions from high-end sensor, daily resolution
    :param density_emlid: GNSS-RR density estimtions from low-cost sensor, daily resolution
    :param manual: manual density observations, monthly resolution
    """
    print(colored('\nGNSS-RR results', 'blue'))
    # Acc cross correation manual vs. GNSS (daily)
    corr_leica_daily = manual.corr(density_leica)
    corr_emlid_daily = manual.corr(density_emlid)
    print('\nPearsons correlation (manual vs. GNSS-RR, monthly), Leica: %.2f' % corr_leica_daily)
    print('Pearsons correlation (manual vs. GNSS-RR, monthly), Emlid: %.2f' % corr_emlid_daily)


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
    print('Linear fit (manual vs. GNSS, daily), Emlid: m = ', round(fit_emlid_daily[0], 2), ', b = ',
          int(fit_emlid_daily[1]))

    # fit linear regression curve laser vs. GNSS (15min), Leica
    joined = pd.concat([laser_15min.dswe, gnss_leica.dswe], axis=1).dropna()
    joined.columns = ['dswe_laser', 'dswe_gnss']
    joined = joined['2021-12-23':]
    fit_15min = np.polyfit(joined.dswe_laser, joined.dswe_gnss, 1)
    predict_15min = np.poly1d(fit_15min)
    print('Linear fit (laser vs. GNSS, 15min), Leica: m = ', round(fit_15min[0], 2), ', b = ', int(fit_15min[1]))

    # fit linear regression curve laser vs. GNSS (15min), Emlid
    joined = pd.concat([laser_15min.dswe, gnss_emlid.dswe], axis=1).dropna()
    joined.columns = ['dswe_laser', 'dswe_gnss']
    joined = joined['2021-12-23':]
    fit_15min_emlid = np.polyfit(joined.dswe_laser, joined.dswe_gnss, 1)
    predict_15min_emlid = np.poly1d(fit_15min_emlid)
    print('Linear fit (laser vs. GNSS, 15min), Emlid: m = ', round(fit_15min_emlid[0], 2), ', b = ',
          int(fit_15min_emlid[1]))  # n=12, m=1.02, b=-8 mm w.e.

    return predict_daily, predict_emlid_daily, predict_15min, predict_15min_emlid


def calculate_linearfit_acc(gnss_leica, laser_15min):
    """ calculate linear regression coefficients between GNSS-IR and laser accumulation observations
        :param gnss_leica: GNSS-IR SH estimtions, 15min resolution
        :param laser_15min: SH observations from laser distance sensor, 15min resolution
        :return predict_15min
    """
    # fit linear regression curve laser vs. GNSS-IR (15min)
    joined = pd.concat([laser_15min.dsh, gnss_leica], axis=1).dropna()
    joined.columns = ['dsh_laser', 'dsh_gnssir']
    joined = joined['2021-12-23':]
    fit_15min = np.polyfit(joined.dsh_laser, joined.dsh_gnssir, 1)
    predict_15min = np.poly1d(fit_15min)
    print('Linear fit (laser vs. GNSS-R, 15min): m = ', round(fit_15min[0], 2), ', b = ', int(fit_15min[1]))

    return predict_15min


def calculate_linearfit_density(gnss_leica, gnss_emlid, manual):
    """ calculate linear regression coefficients between GNSS-RR and manual density observations
        :param gnss_leica: GNSS-RR density estimtions from high-end system, 15min resolution
        :param gnss_emlid: GNSS-RR density estimtions from low-cost system, 15min resolution
        :param manual: manual density observations, monthly resolution
        :return predict_monthly, predict_monthly_emlid
    """
    # fit linear regression curve manual vs. high-end GNSS-RR (monthly)
    joined = pd.concat([manual.Density_aboveAnt, gnss_leica], axis=1).dropna()
    joined.columns = ['manual', 'density']
    joined = joined['2021-12-23':]
    fit_monthly = np.polyfit(joined.manual, joined.density, 1)
    predict_monthly = np.poly1d(fit_monthly)
    print('Linear fit (manual vs. high-end GNSS-RR, monthly): m = ', round(fit_monthly[0], 2), ', b = ',
          int(fit_monthly[1]))

    # fit linear regression curve manual vs. low-cost GNSS-RR (monthly)
    joined = pd.concat([manual.Density_aboveAnt, gnss_emlid], axis=1).dropna()
    joined.columns = ['manual', 'density']
    joined = joined['2021-12-23':]
    fit_monthly = np.polyfit(joined.manual, joined.density, 1)
    predict_monthly_emlid = np.poly1d(fit_monthly)
    print('Linear fit (manual vs. low-cost GNSS-RR, monthly): m = ', round(fit_monthly[0], 2), ', b = ',
          int(fit_monthly[1]))

    return predict_monthly, predict_monthly_emlid


def calculate_rmse(diffs_daily, diffs_15min, manual, laser_15min, gnssir_acc=None, gnssir_acc_daily=None, res='SWE'):
    """ calculate root-mean-square-error (rmse) and number of samples
        between GNSS SWE/Acc and manual/laser SWE/Acc observations
        :param diffs_daily: differences between reference data and GNSS (Leica), daily resolution
        :param diffs_15min: differences between reference data and GNSS (Leica), 15min resolution
         :param gnssir_acc: GNSS reflectometry results, daily resolution
        :param gnssir_acc_daily: GNSS reflectometry results, 15min resolution
        :param manual: manual SWE/SH observations, daily resolution
        :param laser_15min: SWE/SH observations from laser distance sensor, 15min resolution
        :param res: type of results ['SWE', 'Acc']
    """
    print(colored('\nGNSS refractometry results: ' + res, 'blue'))
    if res == 'SWE':
        # RMSE
        rmse_manual = np.sqrt((np.sum(diffs_daily.dswe_manual ** 2)) / len(diffs_daily.dswe_manual))
        print('\nRMSE (manual vs. GNSS, daily), Leica: %.1f' % rmse_manual)
        rmse_manual_emlid = np.sqrt((np.sum(diffs_daily.dswe_manual_emlid ** 2)) / len(diffs_daily.dswe_manual_emlid))
        print('RMSE (manual vs. GNSS, daily), Emlid: %.1f' % rmse_manual_emlid)
        rmse_laser = np.sqrt((np.sum(diffs_15min.dswe_laser ** 2)) / len(diffs_15min.dswe_laser))
        print('RMSE (laser vs. GNSS, 15min), Leica: %.1f' % rmse_laser)
        rmse_laser_emlid = np.sqrt((np.sum(diffs_15min.dswe_laser_emlid ** 2)) / len(diffs_15min.dswe_laser_emlid))
        print('RMSE (laser vs. GNSS, 15min), Emlid: %.1f' % rmse_laser_emlid)

        # Number of samples
        n_manual = len(diffs_daily.dswe_manual.dropna())
        print('\nNumber of samples (manual vs. GNSS, daily), Leica: %.0f' % n_manual)
        n_manual_emlid = len(diffs_daily.dswe_manual_emlid.dropna())
        print('Number of samples (manual vs. GNSS, daily), Emlid: %.0f' % n_manual_emlid)
        n_laser = len(diffs_15min.dswe_laser)
        print('Number of samples (laser vs. GNSS, 15min), Leica: %.0f' % n_laser)
        n_laser_emlid = len(diffs_15min.dswe_laser_emlid)
        print('Number of samples (laser vs. GNSS, 15min), Emlid: %.0f' % n_laser_emlid)
    if res == 'Acc':
        # RMSE
        rmse_manual = np.sqrt((np.sum(diffs_daily.dsh_manual ** 2)) / len(diffs_daily.dsh_manual))
        print('\nRMSE (manual vs. GNSS, daily), Leica: %.1f' % rmse_manual)
        rmse_manual_emlid = np.sqrt((np.sum(diffs_daily.dsh_manual_emlid ** 2)) / len(diffs_daily.dsh_manual_emlid))
        print('RMSE (manual vs. GNSS, daily), Emlid: %.1f' % rmse_manual_emlid)
        rmse_laser = np.sqrt((np.sum(diffs_15min.dsh_laser ** 2)) / len(diffs_15min.dsh_laser))
        print('RMSE (laser vs. GNSS, 15min), Leica: %.1f' % rmse_laser)
        rmse_laser_emlid = np.sqrt((np.sum(diffs_15min.dsh_laser_emlid ** 2)) / len(diffs_15min.dsh_laser_emlid))
        print('RMSE (laser vs. GNSS, 15min), Emlid: %.1f' % rmse_laser_emlid)

        # GNSS-IR vs. manual
        diff_gnssir_manual = (manual.Acc - gnssir_acc_daily).dropna()
        rmse_manual_gnssir = np.sqrt((np.sum(diff_gnssir_manual ** 2)) / len(diff_gnssir_manual))
        print('RMSE (manual vs. GNSS-R, daily): %.1f' % rmse_manual_gnssir)

        # GNSS-IR vs. laser
        diff_gnssir_laser = (laser_15min.dsh - gnssir_acc).dropna()
        rmse_laser_gnssir = np.sqrt((np .sum(diff_gnssir_laser ** 2)) / len(diff_gnssir_laser))
        print('RMSE (laser vs. GNSS-R, 15min): %.1f' % rmse_laser_gnssir)

        # Number of GNSS-IR samples
        print('\nNumber of samples (manual vs. GNSS-R, daily): %.0f' % len(diff_gnssir_manual))
        print('Number of samples (laser vs. GNSS-R, 15min): %.0f' % len(diff_gnssir_laser))


def calculate_rmse_density(density_leica, density_emlid, manual):
    """ calculate root-mean-square-error (rmse) and number of samples
        between GNSS SWE/Acc and manual/laser SWE/Acc observations
        :param density_leica: GNSS-RR density estimtions from high-end system, 15min resolution
        :param density_emlid: GNSS-RR density estimtions from low-cost system, 15min resolution
        :param manual: manual density observations, monthly resolution
    """
    print(colored('\nGNSS-RR results', 'blue'))
    # RMSE
    diff_density_manual = (manual - density_leica).dropna()
    rmse_manual_density = np.sqrt((np.sum(diff_density_manual ** 2)) / len(diff_density_manual))
    print('Density RMSE (manual vs. GNSS-RR, monthly), Leica: %.1f' % rmse_manual_density)

    diff_density_manual_emlid = (manual - density_emlid).dropna()
    rmse_manual_density_emlid = np.sqrt((np.sum(diff_density_manual_emlid ** 2)) / len(diff_density_manual_emlid))
    print('Density RMSE (manual vs. GNSS-RR, monthly), Emlid: %.1f' % rmse_manual_density_emlid)

    # Number of GNSS-IR samples
    print('\nNumber of samples (manual vs. GNSS-RR, monthly), Leica: %.0f' % len(diff_density_manual))
    print('Number of samples (manual vs. GNSS-RR, monthly), Emlid: %.0f' % len(diff_density_manual_emlid))


""" Define plot functions """


def plot_SWE_density_acc(dest_path, leica, emlid, manual, laser, save=[False, True], std_leica=None, std_emlid=None,
                         suffix='', y_lim=(-200, 1400),
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
    manual.Density_aboveAnt.plot(color='steelblue', linestyle=' ', marker='*', markersize=8, markeredgewidth=2,
                                 label='Density (kg/m3)').grid()
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
        plt.savefig(
            dest_path + '30_plots/SWE_Accts_NM_Emlid_15s_Leica_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[
                                                                                                  -2:] + suffix + '.png',
            bbox_inches='tight')
        plt.savefig(
            dest_path + '30_plots/SWE_Accts_NM_Emlid_15s_Leica_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[
                                                                                                  -2:] + suffix + '.pdf',
            bbox_inches='tight')
    else:
        plt.show()


def plot_all_SWE(data_path, leica=None, emlid=None, manual=None, laser=None, buoy=None, poles=None, save=[False, True],
                 suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], std_leica=None,
                 std_emlid=None, y_lim=(-100, 600),
                 x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot SWE (Leica, emlid) time series with reference data (laser, buoy, poles) and error bars
    """
    plt.close()
    plt.figure()
    if leica is not None:
        leica.plot(linestyle='-', color='k', fontsize=12, figsize=(6, 5.5), ylim=y_lim).grid()
    if emlid is not None:
        emlid.plot(color='salmon', linestyle='--')
    if manual is not None:
        manual.SWE_aboveAnt.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
        plt.errorbar(manual.SWE_aboveAnt.index, manual.SWE_aboveAnt, yerr=manual.SWE_aboveAnt / 10, color='darkblue',
                     linestyle='', capsize=4, alpha=0.5)
    if laser is not None:
        laser.dswe.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
    if buoy is not None:
        plt.plot(buoy[['dswe1', 'dswe2', 'dswe3', 'dswe4']], color='lightgrey', linestyle='-', alpha=0.8)
    if poles is not None:
        plt.plot(poles[['dswe1', 'dswe2', 'dswe3', 'dswe4', 'dswe5', 'dswe6', 'dswe7', 'dswe8', 'dswe9', 'dswe10',
                        'dswe11', 'dswe12', 'dswe13', 'dswe14', 'dswe15', 'dswe16']], linestyle=':', alpha=0.4)
    if std_leica is not None:
        plt.fill_between(leica.index, leica - std_leica, leica + std_leica, color="crimson", alpha=0.2)
    if std_emlid is not None:
        plt.fill_between(emlid.index, emlid - std_emlid, emlid + std_emlid, color="salmon", alpha=0.2)

    laser.dswe.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
    manual.SWE_aboveAnt.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
    plt.errorbar(manual.SWE_aboveAnt.index, manual.SWE_aboveAnt, yerr=manual.SWE_aboveAnt / 10, color='darkblue',
                 linestyle='', capsize=4, alpha=0.5)

    plt.xlabel(None)
    plt.ylabel('SWE (mm w.e.)', fontsize=14)
    plt.legend(leg, fontsize=12, loc='upper left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(
            data_path + '/30_plots/SWE_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png',
            bbox_inches='tight')
        plt.savefig(
            data_path + '/30_plots/SWE_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf',
            bbox_inches='tight')
    else:
        plt.show()


def plot_all_diffSWE(data_path, diffs_swe, manual=None, laser=None, buoy=None, poles=None, save=[False, True],
                     suffix='',
                     leg=['Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=(-200, 600),
                     x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot SWE (Leica, emlid) time series with reference data (laser, buoy, poles) and error bars
    """
    plt.close()
    plt.figure()
    diffs_swe.dswe_emlid.plot(linestyle='--', color='salmon', fontsize=12, figsize=(6, 5.5), ylim=y_lim).grid()
    if manual is not None:
        diffs_swe.dswe_manual.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
        plt.errorbar(diffs_swe.dswe_manual.index, diffs_swe.dswe_manual, yerr=diffs_swe.dswe_manual / 10,
                     color='darkblue',
                     linestyle='', capsize=4, alpha=0.5)
    if laser is not None:
        diffs_swe.dswe_laser.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
    if buoy is not None:
        plt.plot(diffs_swe[['dswe_buoy1', 'dswe_buoy2', 'dswe_buoy3', 'dswe_buoy4']], color='lightgrey', linestyle='-')
    if poles is not None:
        plt.plot(diffs_swe[
                     ['dswe_pole1', 'dswe_pole2', 'dswe_pole3', 'dswe_pole4', 'dswe_pole5', 'dswe_pole6', 'dswe_pole7',
                      'dswe_pole8', 'dswe_pole9', 'dswe_pole10', 'dswe_pole11', 'dswe_pole12', 'dswe_pole13',
                      'dswe_pole14', 'dswe_pole15', 'dswe_pole16']].dropna(), linestyle=':', alpha=0.6)

    diffs_swe.dswe_laser.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
    diffs_swe.dswe_manual.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
    plt.errorbar(diffs_swe.dswe_manual.index, diffs_swe.dswe_manual, yerr=diffs_swe.dswe_manual / 10, color='darkblue',
                 linestyle='', capsize=4, alpha=0.5)

    plt.xlabel(None)
    plt.ylabel('ΔSWE (mm w.e.)', fontsize=14)
    plt.legend(leg, fontsize=12, loc='upper left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(data_path + '/30_plots/deltaSWE_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[
                                                                                       -2:] + suffix + '.png',
                    bbox_inches='tight')
        plt.savefig(data_path + '/30_plots/deltaSWE_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[
                                                                                       -2:] + suffix + '.pdf',
                    bbox_inches='tight')
    else:
        plt.show()


def plot_scatter(data_path, y_leica, y_emlid, x_value, predict_daily=None, predict_emlid_daily=None, x_label='Manual',
                 lim=(-100, 600), save=[False, True]):
    plt.close()
    plt.figure()
    leica_x = pd.concat([y_leica, x_value], axis=1)
    leica_x.columns = ['dswe_y', 'dswe_x']
    emlid_x = pd.concat([y_emlid, x_value], axis=1)
    emlid_x.columns = ['dswe_y', 'dswe_x']
    ax = leica_x.plot.scatter(x='dswe_x', y='dswe_y', color='k')
    emlid_x.plot.scatter(x='dswe_x', y='dswe_y', color='salmon', ax=ax)
    if predict_daily is not None:
        plt.plot(range(50, 650), predict_daily(range(50, 650)), c='k', linestyle='--',
                 alpha=0.7)  # linear regression leica
    if predict_emlid_daily is not None:
        plt.plot(range(50, 650), predict_emlid_daily(range(50, 650)), c='salmon', linestyle='-.',
                 alpha=0.7)  # linear regression emlid
    ax.set_ylabel('GNSS SWE (mm w.e.)', fontsize=14)
    ax.set_ylim(lim)
    ax.set_xlim(lim)
    ax.set_xlabel(x_label + ' SWE (mm w.e.)', fontsize=14)
    plt.legend(['High-end GNSS', 'Low-cost GNSS'], fontsize=12, loc='upper left')
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.gca().set_aspect('equal', adjustable='box')
    plt.grid()
    if save is True:
        plt.savefig(data_path + '/30_plots/scatter_SWE_' + x_label + '.png', bbox_inches='tight')
        plt.savefig(data_path + '/30_plots/scatter_SWE_' + x_label + '.pdf', bbox_inches='tight')
    else:
        plt.show()


def plot_scatter_acc(data_path, y_leica, x_value, predict_daily=None, x_label='Manual',
                 lim=(-100, 600), save=[False, True]):
    plt.close()
    plt.figure()
    leica_x = pd.concat([y_leica, x_value], axis=1)
    leica_x.columns = ['dsh_y', 'dsh_x']
    ax = leica_x.plot.scatter(x='dsh_x', y='dsh_y', color='steelblue')
    if predict_daily is not None:
        plt.plot(range(15, 130), predict_daily(range(15, 130)), c='steelblue', linestyle='-',
                 alpha=0.7)  # linear regression leica
    ax.set_ylabel('GNSS accumulation (cm)', fontsize=14)
    ax.set_ylim(lim)
    ax.set_xlim(lim)
    ax.set_xlabel(x_label + ' accumulation (cm)', fontsize=14)
    plt.legend(['GNSS-Reflectometry'], fontsize=12, loc='upper left')
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.gca().set_aspect('equal', adjustable='box')
    plt.grid()
    if save is True:
        plt.savefig(data_path + '/30_plots/scatter_acc_' + x_label + '.png', bbox_inches='tight')
        plt.savefig(data_path + '/30_plots/scatter_acc_' + x_label + '.pdf', bbox_inches='tight')
    else:
        plt.show()


def plot_scatter_density(data_path, y_leica, y_emlid, x_value, predict_daily=None, predict_emlid_daily=None, x_label='Manual',
                 lim=(-100, 600), save=[False, True]):
    plt.close()
    plt.figure()
    leica_x = pd.concat([y_leica, x_value], axis=1)
    leica_x.columns = ['dswe_y', 'dswe_x']
    emlid_x = pd.concat([y_emlid, x_value], axis=1)
    emlid_x.columns = ['dswe_y', 'dswe_x']
    ax = leica_x.plot.scatter(x='dswe_x', y='dswe_y', color='k')
    emlid_x.plot.scatter(x='dswe_x', y='dswe_y', color='salmon', ax=ax)
    if predict_daily is not None:
        plt.plot(range(320, 550), predict_daily(range(320, 550)), c='k', linestyle='--',
                 alpha=0.7)  # linear regression leica
    if predict_emlid_daily is not None:
        plt.plot(range(320, 550), predict_emlid_daily(range(320, 550)), c='salmon', linestyle='-.',
                 alpha=0.7)  # linear regression emlid
    ax.set_ylabel('GNSS-RR density (kg/m3)', fontsize=14)
    ax.set_ylim(lim)
    ax.set_xlim(lim)
    ax.set_xlabel(x_label + ' density (kg/m3)', fontsize=14)
    plt.legend(['High-end GNSS', 'Low-cost GNSS'], fontsize=12, loc='upper right')
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.gca().set_aspect('equal', adjustable='box')
    plt.grid()
    if save is True:
        plt.savefig(data_path + '/30_plots/scatter_density_' + x_label + '.png', bbox_inches='tight')
        plt.savefig(data_path + '/30_plots/scatter_density_' + x_label + '.pdf', bbox_inches='tight')
    else:
        plt.show()


def plot_swediff_boxplot(dest_path, diffs, y_lim=(-100, 500), save=[False, True]):
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
                 suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=(-200, 1400),
                 x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
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
        plt.errorbar(manual.Acc.index, manual.Acc, yerr=manual.Acc / 10, color='darkblue', linestyle='', capsize=4,
                     alpha=0.5)
    if laser is not None:
        laser.dsh.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
    if buoy is not None:
        plt.plot(buoy[['dsh1', 'dsh2', 'dsh3', 'dsh4']], color='lightgrey', linestyle='-', alpha=0.8)
    if poles is not None:
        plt.plot(poles[['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']],
                 linestyle=':', alpha=0.6)

    plt.xlabel(None)
    plt.ylabel('Snow accumulation (mm)', fontsize=14)
    plt.legend(leg, fontsize=12, loc='upper left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(
            data_path + '/30_plots/Acc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png',
            bbox_inches='tight')
        plt.savefig(
            data_path + '/30_plots/Acc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf',
            bbox_inches='tight')
    else:
        plt.show()


def plot_all_diffAcc(data_path, diffs_sh, diffs_sh_15min, manual=None, laser=None, buoy=None, poles=None,
                     save=[False, True],
                     suffix='', leg=['Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=(-400, 1000),
                     x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot SWE (Leica, emlid) time series with reference data (laser, buoy, poles) and error bars
    """
    plt.close()
    plt.figure()
    diffs_sh.dsh_emlid.plot(linestyle='--', color='salmon', fontsize=12, figsize=(6, 5.5), ylim=y_lim).grid()
    if manual is not None:
        diffs_sh.dsh_manual.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
        plt.errorbar(diffs_sh.dsh_manual.index, diffs_sh.dsh_manual, yerr=diffs_sh.dsh_manual / 10, color='darkblue',
                     linestyle='', capsize=4, alpha=0.5)
    if laser is not None:
        diffs_sh_15min.dsh_laser.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()
    if buoy is not None:
        plt.plot(diffs_sh[['dsh_buoy1', 'dsh_buoy2', 'dsh_buoy3', 'dsh_buoy4']], color='lightgrey', linestyle='-', alpha=0.8)
    if poles is not None:
        plt.plot(diffs_sh[['dsh_pole1', 'dsh_pole2', 'dsh_pole3', 'dsh_pole4', 'dsh_pole5', 'dsh_pole6', 'dsh_pole7',
                           'dsh_pole8', 'dsh_pole9', 'dsh_pole10', 'dsh_pole11', 'dsh_pole12', 'dsh_pole13',
                           'dsh_pole14', 'dsh_pole15', 'dsh_pole16']].dropna(), linestyle=':', alpha=0.6)

    plt.xlabel(None)
    plt.ylabel('ΔSnow accumulation (mm)', fontsize=14)
    plt.legend(leg, fontsize=12, loc='upper left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(data_path + '/30_plots/deltaAcc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[
                                                                                       -2:] + suffix + '.png',
                    bbox_inches='tight')
        plt.savefig(data_path + '/30_plots/deltaAcc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[
                                                                                       -2:] + suffix + '.pdf',
                    bbox_inches='tight')
    else:
        plt.show()


def plot_all_diffAcc_gnssir(data_path, manual=None, laser=None, buoy=None, poles=None, gnssir_acc_daily=None,
                            save=[False, True],
                            suffix='', leg=['Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=(-400, 1000),
                            x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot SWE (Leica, emlid) time series with reference data (laser, buoy, poles) and error bars
    """
    plt.close()
    plt.figure()

    # differences
    diff_laser = (laser.dsh - gnssir_acc_daily).dropna()
    diff_manual = (manual.Acc - gnssir_acc_daily).dropna()
    diff_buoy = (buoy[['dsh1', 'dsh2', 'dsh3', 'dsh4']].subtract(gnssir_acc_daily, axis='index')).dropna()
    diff_poles = (
    poles[['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']].subtract(
        gnssir_acc_daily, axis='index')).dropna()

    # plot
    if laser is not None:
        diff_laser.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)', fontsize=12,
                                 figsize=(6, 5.5), ylim=y_lim).grid()
    if manual is not None:
        diff_manual.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
        plt.errorbar(diff_manual.index, diff_manual, yerr=diff_manual / 10, color='darkblue',
                     linestyle='', capsize=4, alpha=0.5)
    if buoy is not None:
        plt.plot(diff_buoy, color='lightgrey', linestyle='-', alpha=0.8)
    if poles is not None:
        plt.plot(diff_poles, linestyle=':', alpha=0.6)

    diff_laser.dropna().plot(color='darkblue', linestyle='-.')
    diff_manual.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
    plt.errorbar(diff_manual.index, diff_manual, yerr=diff_manual / 10, color='darkblue',
                 linestyle='', capsize=4, alpha=0.5)

    plt.xlabel(None)
    plt.ylabel('ΔSnow accumulation (cm)', fontsize=14)
    plt.legend(leg, fontsize=12, loc='upper left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(data_path + '/30_plots/deltaAcc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[
                                                                                       -2:] + suffix + '.png',
                    bbox_inches='tight')
        plt.savefig(data_path + '/30_plots/deltaAcc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[
                                                                                       -2:] + suffix + '.pdf',
                    bbox_inches='tight')
    else:
        plt.show()


def plot_nrsat(data_path, nr_sat_leica, nr_sat_emlid, save=[False, True], suffix='', y_lim=(0, 35),
               x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot number of satellites for high-end and low-cost rovers
    """
    plt.close()
    plt.figure()
    nr_sat_leica.plot(linestyle='-', color='k', fontsize=12, figsize=(6, 5.5), ylim=y_lim, x_compat=True).grid()
    nr_sat_emlid.plot(color='salmon', linestyle='--', alpha=0.8).grid()

    plt.xlabel(None)
    plt.ylabel('Number of satellites', fontsize=14)
    plt.legend(['High-end GNSS', 'Low-cost GNSS'], fontsize=12, loc='upper left')
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


def plot_solquality(data_path, amb_leica, amb_emlid, save=[False, True], suffix='', y_lim=(0, 100),
                    x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot quality of ambiguity resolution (1=fix, 2=float, 5=standalone) for high-end and low-cost rovers
    """
    plt.close()
    plt.figure()

    # calculate number of fixed and float ambiguity solutions per day
    nr_float_leica = amb_leica[(amb_leica == 2)].resample('D').count()
    nr_fixed_leica = amb_leica[(amb_leica == 1)].resample('D').count()
    nr_amb_leica = pd.concat([nr_fixed_leica, nr_float_leica], axis=1).fillna(0).astype(int)
    nr_amb_leica.columns = ['Fixed', 'Float']
    nr_float_emlid = amb_emlid[(amb_emlid == 2)].resample('D').count()
    nr_fixed_emlid = amb_emlid[(amb_emlid == 1)].resample('D').count()
    nr_amb_emlid = pd.concat([nr_fixed_emlid, nr_float_emlid], axis=1).fillna(0).astype(int)
    nr_amb_emlid.columns = ['Fixed', 'Float']

    # plot number of fixed and float ambiguity solutions per day
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(6, 5.5))
    nr_amb_leica[(nr_amb_leica != 0)].plot(ax=axes[0], linestyle='', marker='o', markersize=2, ylim=y_lim).grid()
    nr_amb_emlid[(nr_amb_emlid != 0)].plot(ax=axes[1], linestyle='', marker='o', markersize=2, ylim=y_lim).grid()
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    axes[0].legend(fontsize=11, loc='center left')
    axes[1].legend(fontsize=11, loc='center left')
    axes[0].set_xlim(x_lim)
    axes[1].set_xlim(x_lim)
    axes[0].set_ylabel('High-end solution', fontsize=12)
    axes[1].set_ylabel('Low-cost solution', fontsize=12)
    if save is True:
        plt.savefig(
            data_path + '/30_plots/Ambstate_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png',
            bbox_inches='tight')
        plt.savefig(
            data_path + '/30_plots/Ambstate_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf',
            bbox_inches='tight')
    else:
        plt.show()


def plot_PPP_solution(dest_path, receiver, df_ppp=None, save=[False, True], suffix='',
                      x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Read GNSS precise point processing (PPP) solution files (.pos) in ITRF20 reference frame, processed online using the Canadian governmental PPP service:
        https://webapp.csrs-scrs.nrcan-rncan.gc.ca/geod/tools-outils/ppp.php
        and plot them
    """
    # # create empty dataframe for all .log files
    # df_ppp = pd.DataFrame()
    # # read all PPP solution files in folder, parse date and time columns to datetimeindex and add them to the dataframe
    # for file in glob.iglob(dest_path + '10_ppp/' + receiver + '/*.pos', recursive=True):
    #     print(file)
    #     # header: 'date', 'time', 'snow level (m)', 'signal(-)', 'temp (°C)', 'error (-)', 'checksum (-)'
    #     ppp = pd.read_csv(file, header=7, delimiter=' ', skipinitialspace=True, na_values=["NaN"],
    #                       usecols=[4, 5, 10, 11, 12, 22, 24, 25], parse_dates=[['date', 'time']],
    #                       names=['date', 'time', 'dlat', 'dlon', 'dh', 'h', 'utm_e', 'utm_n'],
    #                       index_col=['date_time'], encoding='latin1', engine='python')
    #     df_ppp = pd.concat([df_ppp, ppp], axis=0)

    # correct antenna height change in rinex obs files data
    dh_pre = df_ppp.dh[(df_ppp.index < df_ppp.dh.diff().idxmin())] - 3.61
    dh_corr = pd.concat([dh_pre, df_ppp.dh[~(df_ppp.index < df_ppp.dh.diff().idxmin())]])

    dh_post = dh_corr[(dh_corr.index > '2022-12-24 00:00:00')] + 2.89
    dh_corr2 = pd.concat([dh_corr[~(dh_corr.index > '2022-12-24 00:00:00')], dh_post])

    # correct lat/lon
    dlat_post = df_ppp.dlat[(df_ppp.index > '2022-12-24 00:00:00')] + 150.5085
    dlat_corr = pd.concat([df_ppp.dlat[~(df_ppp.index > '2022-12-24 00:00:00')], dlat_post])
    dlon_post = df_ppp.dlon[(df_ppp.index > '2022-12-24 00:00:00')] - 38.359
    dlon_corr = pd.concat([df_ppp.dlon[~(df_ppp.index > '2022-12-24 00:00:00')], dlon_post])

    # exclude outliers
    dh_corr = dh_corr[dh_corr.index != dh_corr.idxmax()]
    dh_corr = dh_corr[dh_corr.index != dh_corr.idxmin()]

    # plot lat, lon, h timeseries
    fig, axes = plt.subplots(nrows=3, ncols=1, sharex=True)
    (dlat_corr - dlat_corr[0]).plot(ax=axes[0], ylim=(-10, 250), color='steelblue', fontsize=12).grid()
    (dlon_corr - dlon_corr[0]).plot(ax=axes[1], ylim=(-250, 10), color='steelblue', fontsize=12).grid()
    ((dh_corr2 - dh_corr2[(dh_corr2.index < '2021-11-27')].median()) * 100).rolling('7D').median().dropna().plot(
        ax=axes[2], ylim=(-250, 500),
        color='steelblue', fontsize=12).grid()
    axes[0].set_ylabel('ΔLat (m)', fontsize=14)
    axes[1].set_ylabel('ΔLon (m)', fontsize=14)
    axes[2].set_ylabel('ΔH (cm)', fontsize=14)
    axes[0].set_yticks([0, 50, 100, 150, 200, 250])
    axes[1].set_yticks([0, -50, -100, -150, -200, -250])
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xlabel(None)
    plt.xlim(x_lim)
    if save is True:
        plt.savefig(dest_path + '/30_plots/ppp_LLH_' + receiver + '_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[
                                                                                                   -2:] + suffix + '.png',
                    bbox_inches='tight')
        plt.savefig(dest_path + '/30_plots/ppp_LLH_' + receiver + '_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[
                                                                                                   -2:] + suffix + '.pdf',
                    bbox_inches='tight')
    else:
        plt.show()

    return df_ppp

# -------------------- GNSS Reflectometry functions ------------------------------------------


def prepare_orbits(sp3_outdir, raporbit_path, gnssir_path):
    """ Download, unzip, rename & rapid move orbits (need to match the gnssrefl input format!)
        :param sp3_outdir: Temporary output directory to store & convert downloaded orbit files
        :param raporbit_path: GFZ data server from where GNSS rapid orbits are downloaded
        :param gnssir_path: output directory for gnssrefl input (yearly directories)

    """
    # Q: download rapid orbits
    sp3_tempdir = get_orbits(sp3_outdir, raporbit_path)

    # Q: unzip orbits
    unzip_orbits(sp3_tempdir)

    # Q: rename orbit files (need to match the gnssrefl input name format!)
    rename_orbits(sp3_tempdir, gnssir_path)


def get_orbits(sp3_outdir, raporbit_path):
    """ Download, uzip, rename rapid orbits from GFZ Data Server: 'ftp://isdcftp.gfz-potsdam.de/gnss/products/rapid/w????/*.SP3*'
        (???? = gpsweek, sample sp3 = 'GFZ0OPSRAP_20230930000_01D_05M_ORB.SP3.gz')
        example orbit file: 'GFZ0OPSRAP_20231190000_01D_05M_ORB.SP3.gz'
        :param sp3_outdir: Temporary output directory to store & convert downloaded orbit files
        :param raporbit_path: GFZ data server from where GNSS rapid orbits are downloaded
        :return: sp3_tempdir
        """

    # Q: download, unzip, rename rapid orbits (need to match the gnssrefl input format!)
    # create temporary preprocessing folder in temp orbit dir
    sp3_tempdir = sp3_outdir + 'preprocessing/'
    if not os.path.exists(sp3_tempdir):
        os.makedirs(sp3_tempdir, exist_ok=True)

    # get the newest year, doy from orbit file from temp orbit dir
    yeardoy_newest = sorted(glob.glob(sp3_outdir + '*.gz'), reverse=True)[0].split('_')[1]
    year_newest = int(yeardoy_newest[:4])
    doy_newest = int(yeardoy_newest[4:7])

    # convert to gpsweek and day of week (dow)
    gpsweek_newest, dow_newest = gnsscal.yrdoy2gpswd(year_newest, doy_newest)

    # convert today to gpsweek and day of week (dow)
    gpsweek_today, dow_today = gnsscal.date2gpswd(date.today())

    # define ftp subdirectories to download newly available orbit files
    gpsweek_list = list(range(gpsweek_newest, gpsweek_today + 1, 1))

    for gpswk in gpsweek_list:
        download_path = raporbit_path + 'w' + str(gpswk) + '/'
        # download all .SP3 rapid orbits from ftp server's subfolders
        subprocess.call('wget -r -np -nc -nH --cut-dirs=4 -A .SP3.gz ' + download_path + ' -P ' + sp3_tempdir)

    print(colored("\nGFZ rapid orbits downloaded to: %s" % sp3_outdir, 'blue'))

    return sp3_tempdir


def unzip_orbits(sp3_tempdir):
    """ Unzip all orbit files in the temporary orbit processing directory
        example from orbit file: 'GFZ0OPSRAP_20231190000_01D_05M_ORB.SP3.gz' to '_GFZ0OPSRAP_20231190000_01D_05M_ORB.SP3'
        :param sp3_tempdir: temporary orbit processing directory
        """
    # unzip all files
    subprocess.call(r'7z e -y ' + sp3_tempdir + ' -o' + sp3_tempdir)
    print(colored("\nGFZ rapid orbits unzipped", 'blue'))


def rename_orbits(sp3_tempdir, gnssir_path, sp3_outdir):
    """ Rename & move orbit files (need to match the gnssrefl input name format!)
        example from 'GFZ0OPSRAP_20231190000_01D_05M_ORB.SP3' to 'GFZ0MGXRAP_20231190000_01D_05M_ORB.SP3'
        :param sp3_tempdir: temporary orbit processing directory
        :param gnssir_path: output directory for gnssrefl input (yearly directories)
        :param sp3_outdir: temporary output directory to store & convert downloaded orbit files
    """
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

    # remove temporary preprocessing directory
    shutil.rmtree(sp3_tempdir)


def prepare_obs(dest_path, rin_temp, base_name, gnssir_path):
    """ copy, rename, convert, move rinex files
        :param rin_temp: temporary rinex processing folder
        :param dest_path: data destination path for python processing
        :param base_name: prefix of base rinex observation files, e.g. station name ('NMLB')
        :param gnssir_path: gnssrefl processing folder
        :return: year_start, year_end, doy_start, doy_end
    """
    # Q: copy & rename base rinex observations to temporary directory
    copy_obs(dest_path, rin_temp, base_name)

    # Q: Convert rinex3 to rinex2 files and resample to 30s sampling rate (instead of 1Hz)
    year_start, year_end, doy_start, doy_end = conv_obs(rin_temp, gnssir_path, base_name)

    return year_start, year_end, doy_start, doy_end


def copy_obs(dest_path, rin_temp, base_name):
    """ copy & rename base rinex observations to temporary directory
        :param rin_temp: temporary rinex processing folder
        :param dest_path: data destination path for python processing
        :param base_name: prefix of base rinex observation files, e.g. station name ('NMLB')
    """
    for rinex_file in sorted(glob.glob(dest_path + '3387*0.*[olng]'), reverse=True):
        # copy base rinex obs [o] and nav [lng] files
        copy_file_no_overwrite(dest_path, rin_temp, os.path.basename(rinex_file))

        # rename base rinex files if not exist
        outfile = base_name.lower() + os.path.basename(rinex_file)[4:]
        if not os.path.exists(rin_temp + '/' + outfile):
            print('rename file')
            os.rename(rin_temp + os.path.basename(rinex_file), rin_temp + '/' + outfile)
        else:
            os.remove(rin_temp + os.path.basename(rinex_file))

    print(colored("\nRinex3 files copied and renamed to: %s" % rin_temp, 'blue'))


def conv_obs(rin_temp, gnssir_path, base_name):
    """ Convert rinex3 to rinex2 files and resample to 30s sampling rate (instead of 1Hz) & get
        start/end year, doy from newly downloaded files (to not process older files again)
        :param rin_temp: temporary rinex processing folder
        :param gnssir_path: gnssrefl processing folder
        :param base_name: prefix of base rinex observation files, e.g. station name ('NMLB')
        :return: year_start, year_end, doy_start, doy_end
    """
    doy = []
    for rinex_file in sorted(glob.glob(rin_temp + '*o'), reverse=True):
        year = '20' + os.path.basename(rinex_file)[-3:-1]
        doy_new = os.path.basename(rinex_file).split('.')[0][-4:-1]
        doy.append(doy_new)
        if not os.path.exists(
                gnssir_path + 'data/rinex/' + base_name.lower() + '/' + year + '/' + os.path.basename(rinex_file)):
            print(rinex_file)
            if not os.path.exists(gnssir_path + 'data/rinex/' + base_name.lower() + '/' + year + '/'):
                os.makedirs(gnssir_path + 'data/rinex/' + base_name.lower() + '/' + year + '/', exist_ok=True)
            subprocess.call(
                r'gfzrnx -finp ' + rinex_file + ' -vo 2 -smp 30 -fout ' + gnssir_path + 'data/rinex/' + base_name.lower() + '/' + year + '/::RX2::')

    print(colored(
        "\nRinex3 files converted to rinex2 and moved to yearly (e.g. 2021): %s" % gnssir_path + 'data/rinex/' + base_name.lower() + '/' + year + '/',
        'blue'))

    # return start and end year, doy for GNSS-IR processing
    year_start = year[-1]  # '2021'
    doy_start = doy[-1]  # '330'
    year_end = year[0]
    doy_end = doy[0]

    return year_start, year_end, doy_start, doy_end


def read_gnssir(dest_path, ubuntu_path, base_name, yy='21', copy=False, pickle='nmlb'):
    """ Plot GNSS interferometric reflectometry (GNSS-IR) accumulation results from the high-end base station
        :param dest_path: path to processing directory
        :param ubuntu_path: path to Ubuntu localhost where the GNSS-IR results are processed/stored (e.g.: '//wsl.localhost/Ubuntu/home/sladina/test/gnssrefl/data/')
        :param base_name: name of reflectometry solution file base_name, e.g.: 'nmlb'
        :copy: copy (True) or not (False) reflectometry solutions from ubuntu localhost to local folder
        :param pickle: name of pickle file (default = 'nmlb.pkl')
        :return df_rh
    """
    # create local directory for GNSS-IR observations
    loc_gnssir_dir = dest_path + '20_solutions/' + base_name + '/rh2-8m_ele5-30/'
    os.makedirs(loc_gnssir_dir, exist_ok=True)

    # Q: copy GNSS-IR solution files (*.txt) from the local Ubuntu server if not already existing
    if copy is True:
        print(colored("\ncopy new reflectometry solution files", 'blue'))
        # get list of yearly directories
        for f in glob.glob(ubuntu_path + '2*'):
            year = os.path.basename(f)
            if int(year) >= int('20' + yy):
                # copy missing reflectometry solution files
                for f in glob.glob(ubuntu_path + year + '/results/' + base_name.lower() + '/rh2-8m_ele5-30/*.txt'):
                    file = os.path.basename(f)
                    # skip files of 2021 before 26th nov (no gps data before installation)
                    if not os.path.exists(loc_gnssir_dir + file):
                        # check if the name of the solution file begins with the year
                        if file[:4] == year:
                            print(file)
                        else:
                            # rename GNSS-IR solution files from doy.txt to year_nmlbdoy.txt
                            os.rename(f, ubuntu_path + year + '/results/' + base_name.lower() + '/' + year + '_' + base_name.lower() + file)
                            print("\nGNSS-IR solution files renamed from %s to %s" % (file, year + '_' + base_name.lower() + file))

                        # copy the files
                        shutil.copy2(f, loc_gnssir_dir)
                        print("file copied from %s to %s" % (f, loc_gnssir_dir))
                    else:
                        # print(colored("\nfile in destination already exists: %s, \ncopy aborted!!!" % dest_path, 'yellow'))
                        pass
            else:
                pass
        print(colored("\nnew reflectometry solution files copied", 'blue'))
    else:
        print("\nno files to copy")

    # Q: read all existing GNSS-IR observations from .pkl if already exists, else create empty dataframe
    loc_gnssir_dir = dest_path + '20_solutions/' + base_name + '/rh2-8m_ele5-30/'
    path_to_oldpickle = loc_gnssir_dir + pickle + '.pkl'
    if os.path.exists(path_to_oldpickle):
        print(
            colored('\nReading already existing reflectometry solutions from pickle: %s' % path_to_oldpickle, 'yellow'))
        df_rh = pd.read_pickle(path_to_oldpickle)
        old_idx = df_rh.index[-1].date().strftime("%Y%j")
        old_idx_year = int(old_idx[:4])
        old_idx_doy = int(old_idx[-3:])
    else:
        print(colored('\nNo existing reflectometry solutions pickle!', 'yellow'))
        df_rh = pd.DataFrame()
        old_idx_year = 2021
        old_idx_doy = 330

    # read all reflector height solution files in folder, parse mjd column to datetimeindex and add them to the dataframe
    print(colored('\nReading all new reflectometry solution files from: %s' % loc_gnssir_dir + '*.txt', 'blue'))
    for file in glob.iglob(loc_gnssir_dir + '*.txt', recursive=True):
        # read solution files newer than last entry in reflectometry solutions pickle, check year and doy
        if ((int(os.path.basename(file)[:4]) >= old_idx_year) & (int(os.path.basename(file)[-7:-4]) > old_idx_doy)) \
                or (int(os.path.basename(file)[:4]) > old_idx_year):
            print(file)

            # header: year, doy, RH (m), sat,UTCtime (hrs), Azim (deg), Amp (v/v), eminO (deg), emaxO (deg), NumbOf (values), freq,rise,EdotF (hrs), PkNoise, DelT (min), MJD, refr-appl (1=yes)
            rh = pd.read_csv(file, header=4, delimiter=' ', skipinitialspace=True, na_values=["NaN"],
                             names=['year', 'doy', 'RH', 'sat', 'UTCtime', 'Azim', 'Amp', 'eminO', 'emaxO', 'NumbOf',
                                    'freq', 'rise', 'EdotF', 'PkNoise', 'DelT', 'MJD', 'refr-appl'], index_col=False)
            df_rh = pd.concat([df_rh, rh], axis=0)
        else:
            pass

    # convert year doy UTCtime to datetimeindex
    df_rh.index = pd.DatetimeIndex(pd.to_datetime(df_rh.year * 1000 + df_rh.doy, format='%Y%j')
                                   + pd.to_timedelta(df_rh.UTCtime, unit='h')).floor('s')

    # detect all dublicates and only keep last dublicated entries
    df_rh = df_rh[~df_rh.index.duplicated(keep='last')]

    # store dataframe as binary pickle format
    df_rh.to_pickle(loc_gnssir_dir + pickle + '.pkl')
    print(colored(
        '\nstored all old and new reflectometry solution data (without dublicates) in pickle: %s' + loc_gnssir_dir + pickle + '.pkl',
        'blue'))

    return df_rh


def filter_gnssir(df_rh, freq=[1, 5, 101, 102, 201, 202, 207, 'all', '1st', '2nd'], threshold=2):
    """ Plot GNSS interferometric reflectometry (GNSS-IR) accumulation results from the high-end base station
        best results: ele=5-30, f=2, azi=30-160 & 210-310
        :param df_rh: GNSS-IR data
        :param freq: chosen satellite system frequency to use results, 1=gps l1, 5=gps l5, 101=glonass l1, 102=glonass l2, 201=galileo l1, 202=galileo l2, 207=galileo l5
        :param threshold: threshold for outlier detection (x sigma)
        :return df_rh, gnssir_acc, gnssir_acc_sel
    """

    # Q: select frequencies to analyze
    if freq == 'all':  # select all frequencies from all systems
        print('all frequencies are selected')
        gnssir_rh = df_rh[['RH', 'Azim']]
    elif freq == '2nd':  # select all second frequencies from GPS, GLONASS, GALILEO
        print('2nd frequencies are selected')
        gnssir_rh = df_rh[['RH', 'Azim']][(df_rh.freq.isin([5, 102, 205, 207]))]
    elif freq == '1st':  # select all first frequencies from GPS, GLONASS, GALILEO
        print('1st frequencies are selected')
        gnssir_rh = df_rh[['RH', 'Azim']][(df_rh.freq.isin([1, 101, 201]))]
    else:  # select chosen single frequency
        print('single frequency is selected')
        gnssir_rh = df_rh[['RH', 'Azim']][(df_rh.freq == freq)]

    # Q: excluding spuso e-m-wave bending and reflection zone azimuths and convert to mm
    gnssir_rh = gnssir_rh[(gnssir_rh.Azim > 30) & (gnssir_rh.Azim < 310)]
    gnssir_rh = gnssir_rh.RH[(gnssir_rh.Azim > 210) | (gnssir_rh.Azim < 160)] * 1000

    # Q: adjust for snow mast heightening (approx. 3m elevated several times a year)
    print('\ndata is corrected for snow mast heightening events (remove sudden jumps > 1m)')
    # sort index
    gnssir_rh = gnssir_rh.sort_index()

    # detect jump
    jump = gnssir_rh[(gnssir_rh.diff() > 2500)]  # detect jumps (> 2500mm) in the dataset

    # get value of jump difference (of values directly after - before jump)
    jump_ind = jump.index.format()[0]
    jump_val = gnssir_rh[jump_ind] - gnssir_rh[:jump_ind][-2]

    # detect and correct all jumps
    while jump.empty is False:
        print('\njump of height %s is detected! at %s' % (jump_val, jump.index.format()[0]))
        adj = gnssir_rh[
                  (gnssir_rh.index >= jump.index.format()[0])] - jump_val  # correct all observations after jump [0]
        gnssir_rh = pd.concat([gnssir_rh[~(gnssir_rh.index >= jump.index.format()[0])],
                               adj])  # concatenate all original obs before jump with adjusted values after jump
        jump = gnssir_rh[(gnssir_rh.diff() > 2500)]

    print('\nno jump detected!')

    # Q: remove outliers based on x*sigma threshold
    print('\nremove outliers based on %s * sigma threshold' % threshold)
    upper_limit = gnssir_rh.rolling('3D').median() + threshold * gnssir_rh.rolling('3D').std()
    lower_limit = gnssir_rh.rolling('3D').median() - threshold * gnssir_rh.rolling('3D').std()
    gnssir_rh_clean = gnssir_rh[(gnssir_rh > lower_limit) & (gnssir_rh < upper_limit)]

    # resample to 15min
    gnssir_rh_clean = gnssir_rh_clean.resample('15min').median().dropna()
    gnssir_rh_clean_daily = gnssir_rh_clean.resample('D').median()

    # Q: convert to accumulation & only allow non-negative values, adjust to maximum
    gnssir_acc = (gnssir_rh_clean_daily.max() - gnssir_rh_clean)

    # resample accumulation data
    gnssir_acc_daily = gnssir_acc.resample('D').median()
    gnssir_acc_daily_std = gnssir_acc.resample('D').std()

    return gnssir_acc, gnssir_acc_daily, gnssir_acc_daily_std, gnssir_rh_clean


def plot_gnssir(dest_path, gnssir_acc, gnssir_acc_daily, gnssir_acc_daily_std, laser, leica, emlid=None, manual=None,
                buoy=None, poles=None,
                leg=['_', 'GNSS-IR', 'Laser (SHM)', 'High-end GNSS'], save=False, suffix='',
                x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1)), y_lim=(-400,1600)):
    """ Plot GNSS interferometric reflectometry (GNSS-IR) accumulation results from the high-end base station """

    # plot gnssir snow accumulation (resampled median per day)
    plt.close()
    gnssir_acc_daily.dropna().plot(color='steelblue', ylim=y_lim, fontsize=12,
                          xlim=x_lim,
                          figsize=(6, 5.5)).grid()

    # plot variation: use all GNSS-IR results
    gnssir_acc.plot(color="steelblue", alpha=0.4)

    # plot variation: use 2 * sigma GNSS-IR results
    # plt.fill_between(gnssir_acc_daily.index, gnssir_acc_daily - 2 * gnssir_acc_daily_std, gnssir_acc_daily + 2 * gnssir_acc_daily_std, color="steelblue", alpha=0.4)

    # plot gnss-refractometry accumulation data (converted from SWE)
    if leica is not None:
        leica.dsh.plot(color='crimson').grid()
    if emlid is not None:
        emlid.dsh.plot(color='salmon', linestyle='--').grid()

    # plot manual accumulation data
    if manual is not None:
        manual.Acc.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
        plt.errorbar(manual.Acc.index, manual.Acc, yerr=manual.Acc / 10, color='darkblue', linestyle='', capsize=4,
                     alpha=0.5)

    # plot snow accumulation data from laser, buoy, and poles
    if laser is not None:
        laser.dsh.plot(color='darkblue', linestyle='-.').grid()
    if buoy is not None:
        plt.plot(buoy[['dsh1', 'dsh2', 'dsh3', 'dsh4']], color='lightgrey', linestyle='-')
    if poles is not None:
        plt.plot(poles[['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']],
                 linestyle=':', alpha=0.6)

    # define plot settings
    plt.legend(leg, fontsize=12, loc='upper left')
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.grid()
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.ylabel('Snow accumulation (mm)', fontsize=14)
    plt.grid()
    if save is True:
        plt.savefig(dest_path + '/30_plots/Acc_gnssir' + suffix + '.png', bbox_inches='tight')
        plt.savefig(dest_path + '/30_plots/Acc_gnssir' + suffix + '.pdf', bbox_inches='tight')
    else:
        plt.show()

    plt.close()


def plot_all_Acc_gnssir(data_path, leica=None, emlid=None, manual=None, laser=None, buoy=None, poles=None,
                        gnssir_acc=None, gnssir_acc_daily=None, save=[False, True],
                        suffix='', leg=['High-end GNSS', 'Low-cost GNSS', 'Manual', 'Laser (SHM)'], y_lim=(-200, 1400),
                        x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot Accumulation (Leica, emlid) time series with reference data (laser, buoy, poles) and error bars
    """
    plt.close()
    plt.figure()
    if leica is not None:
        leica.dsh.plot(linestyle='-', color='crimson', fontsize=12, figsize=(6, 5.5), ylim=y_lim, x_compat=True).grid()
    if leica is None:
        if gnssir_acc is not None:
            gnssir_acc.plot(linestyle='-', color='steelblue', alpha=0.4, fontsize=12, figsize=(6, 5.5), ylim=y_lim,
                            x_compat=True).grid()
        if manual is not None:
            manual.Acc.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1, fontsize=12,
                            figsize=(6, 5.5), ylim=y_lim, x_compat=True).grid()
            plt.errorbar(manual.Acc.index, manual.Acc, yerr=manual.Acc / 10, color='darkblue', linestyle='', capsize=4,
                         alpha=0.5)
        else:
            print(colored('Please provide a reference for the figure', 'red'))

    if emlid is not None:
        emlid.dsh.plot(color='salmon', linestyle='--')
    if manual is not None:
        manual.Acc.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1).grid()
        plt.errorbar(manual.Acc.index, manual.Acc, yerr=manual.Acc / 10, color='darkblue', linestyle='', capsize=4,
                     alpha=0.5)
    if laser is not None:
        laser.dsh.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()

    if gnssir_acc_daily is not None:
        gnssir_acc_daily.dropna().plot(color='steelblue').grid()

    if buoy is not None:
        plt.plot(buoy[['dsh1', 'dsh2', 'dsh3', 'dsh4']], color='lightgrey', linestyle='-', alpha=0.8)
    if poles is not None:
        plt.plot(poles[['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']],
                 linestyle=':', alpha=0.6)

    if laser is not None:
        laser.dsh.dropna().plot(color='darkblue', linestyle='-.', label='Accumulation (cm)').grid()

    plt.xlabel(None)
    plt.ylabel('Snow accumulation (cm)', fontsize=14)
    plt.legend(leg, fontsize=12, loc='upper left')
    plt.xlim(x_lim)
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    if save is True:
        plt.savefig(
            data_path + '/30_plots/Acc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.png',
            bbox_inches='tight')
        plt.savefig(
            data_path + '/30_plots/Acc_all_' + str(x_lim[0].year) + '_' + str(x_lim[1].year)[-2:] + suffix + '.pdf',
            bbox_inches='tight')
    else:
        plt.show()


def plot_density(dest_path, density_leica, density_emlid, laser=None, manual=None, leg=['High-end GNSS-RR', 'Manual'], save=False, suffix='', x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot derived density timeseries from GNSS reflectometry based accumulation and GNSS-refractometry based SWE """

    # plot density (all data & resampled median per day)
    plt.close()
    if density_leica is not None:
        density_leica.plot(color='k', linestyle='-', ylim=(-1, 1000), fontsize=12, xlim=x_lim, figsize=(6, 5.5)).grid()
    else:
        if density_emlid is not None:
            density_emlid.plot(color='salmon', linestyle='--', ylim=(-1, 1000), fontsize=12, xlim=x_lim, figsize=(6, 5.5)).grid()

    if density_emlid is not None:
        density_emlid.plot(color='salmon', linestyle='--').grid()

    # plt.fill_between(gnssir_acc_median.index, gnssir_acc_median - gnssir_acc_std, gnssir_acc_median + gnssir_acc_std, color="steelblue", alpha=0.4)

    # plot manual density data & error
    if manual is not None:
        # plot density of layers above antenna
        manual.Density_aboveAnt.plot(color='darkblue', linestyle=' ', marker='o', markersize=5, markeredgewidth=1,
                                     label='Manual').grid()
        plt.errorbar(manual.Density_aboveAnt.index, manual.Density_aboveAnt, yerr=manual.Density_aboveAnt / 10,
                     color='darkblue', linestyle='', capsize=4,
                     alpha=0.8)
        # # plot density of upper 1m layer
        # manual.Density.plot(color='k', linestyle=' ', marker='o', markersize=4, markeredgewidth=1,
        #                              label='Manual', alpha=0.3).grid()
        # plt.errorbar(manual.Density.index, manual.Density, yerr=manual.Density / 10,
        #              color='k', linestyle='', capsize=4,
        #              alpha=0.3)

    # plot snow accumulation data from laser, buoy, and poles
    if laser is not None:
        laser.dsh.plot(color='darkblue', linestyle='-.').grid()

    # define plot settings
    plt.legend(leg, fontsize=12, loc='upper right')
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.grid()
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.ylabel('Density (kg/m3)', fontsize=14)
    plt.grid()
    if save is True:
        plt.savefig(dest_path + '/30_plots/Density' + suffix + '.png', bbox_inches='tight')
        plt.savefig(dest_path + '/30_plots/Density' + suffix + '.pdf', bbox_inches='tight')
    else:
        plt.show()


def plot_diff_density(dest_path, density_leica, density_emlid, laser=None, manual=None,
                      leg=['High-end GNSS-RR', 'Manual'], save=False, suffix='', x_lim=(dt.date(2021, 11, 26), dt.date(2022, 12, 1))):
    """ Plot derived density timeseries from GNSS reflectometry based accumulation and GNSS-refractometry based SWE """

    # plot density (all data & resampled median per day)
    plt.close()

    if density_leica is not None:
        density_leica.plot(color='k', linestyle=' ', marker='o', markersize=5, markeredgewidth=1,
                           ylim=(-300, 300), fontsize=12,
                           xlim=x_lim, figsize=(6, 5.5)).grid()

    if density_emlid is not None:
        density_emlid.plot(color='salmon', linestyle=' ', marker='o', markersize=5, markeredgewidth=1, ylim=(-300, 300),
                           fontsize=12,
                           xlim=x_lim, figsize=(6, 5.5)).grid()

    # define plot settings
    plt.legend(leg, fontsize=12, loc='upper right')
    plt.gca().xaxis.set_major_locator(MonthLocator())
    plt.gca().xaxis.set_minor_locator(MonthLocator(bymonthday=15))
    plt.grid()
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.ylabel('ΔDensity (kg/m3)', fontsize=14)
    plt.grid()
    if save is True:
        plt.savefig(dest_path + '/30_plots/diff_Density' + suffix + '.png', bbox_inches='tight')
        plt.savefig(dest_path + '/30_plots/diff_Density' + suffix + '.pdf', bbox_inches='tight')
    else:
        plt.show()
