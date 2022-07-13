""" Script to generate daily rinex 3.0x files from day-overlapping Emlid rinex files;
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
from zipfile import ZipFile

yy = str(22)
rover_name = 'NMER'             # 'NMER' or 'NMLR'
rover = 'ReachM2_sladina-raw_'  # 'ReachM2_sladina-raw_' or '3393'


# Q: create 'temp' directory
os.makedirs('data_neumayer/temp/')

# Q: unzip Emlid folders and move observation files (.yyO) to directory
for file in glob.iglob('data_neumayer/' + rover + '*.zip', recursive=True):
    for f in ZipFile(file).namelist():
        if f.endswith('.' + yy + 'O'):
            ZipFile(file).extract(f, 'data_neumayer/temp/')
    print("Extract: ", f)
print("Extracted all: ", f + '.' + yy + 'O')


# Q: convert Emlid file names to match format for 'gfzrnx'
# ReachM2_sladina-raw_202111251100.21O to NMERdoy{a..d}.21o

for file in glob.iglob('data_neumayer/temp/' + rover + '*.' + yy + 'O', recursive=True):
    ''' get doy from rover file names with name structure:
        Leica Rover: '33933650.21o' [rover + doy + '0.' + yy + 'o']
        Emlid Rover: 'ReachM2_sladina-raw_202112041058.21O' [rover + datetime + '.' + yy + 'O']
        '''
    dir_name = os.path.dirname(file)
    rover_file = os.path.basename(file)
    doy = datetime.datetime.strptime(rover_file.split('.')[0].split('_')[2], "%Y%m%d%H%M").strftime('%j')
    new_filename = dir_name + '/' + rover_name + doy + 'a.' + yy + 'o'
    print('\nRover file: ' + rover_file, '\ndoy: ', doy, '\nNew filename: ', new_filename)

    # check if new filename already exists and rename file
    file_exists = os.path.exists(new_filename)  # True or False
    if file_exists is True:
        new_filename = dir_name + '/' + rover_name + doy + 'b.' + yy + 'o'
        # check if new filename already exists and rename file
        file_exists = os.path.exists(new_filename)  # True or False
        if file_exists is True:
            new_filename = dir_name + '/' + rover_name + doy + 'c.' + yy + 'o'
            # check if new filename already exists and rename file
            file_exists = os.path.exists(new_filename)  # True or False
            if file_exists is True:
                new_filename = dir_name + '/' + rover_name + doy + 'd.' + yy + 'o'
            else:
                os.rename(file, new_filename)
                print('\nNew filename already existing --> renamed to: ', new_filename)
        else:
            os.rename(file, new_filename)
            print('\nNew filename already existing --> renamed to: ', new_filename)
    else:
        os.rename(file, new_filename)

print('\n\nfinished renaming all files :-)')


# Q: split files at midnight for day-overlapping rinex files --> get subdaily files
# run command: 'gfzrnx -finp NMER345.21o -fout ::RX3:: -split 86400'
for file in glob.iglob('data_neumayer/temp/' + rover_name + '*.' + yy + 'o', recursive=True):
    ''' get doy from rover file names with name structure:
        Emlid Rover: 'NMER329[a..d].21o' [rover + doy + '.' + yy + 'o']
        '''
    rover_file = os.path.basename(file)
    doy = rover_file.split('.')[0][-4:-1]
    doy_end = str(int(doy) + 1)
    print('\nRover file: ' + rover_file, '\ndoy: ', doy, '\ndoy_end: ', doy_end)

    # define input and output filenames (for some reason it's not working when input files are stored in subfolders!)
    out_file = rover_name + doy_end + 'D.' + yy + 'O'
    process1 = subprocess.Popen('cd data_neumayer/temp && '
                                'gfzrnx -finp ' + rover_file + ' -fout ::RX3:: -split 86400',
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

    stdout1, stderr1 = process1.communicate()
    print(stdout1)
    print(stderr1)

print('\n\nfinished splitting all files :-)')


# Q: rename all .rnx files (gfzrnx split output --> gfzrnx merge input)
for file in glob.iglob('data_neumayer/temp/*.rnx', recursive=True):
    ''' rename gfzrnx split files output names to match input for gfzrnx merge files:
        gfzrx split output: '    00XXX_R_20213291100_01D_30S_MO.rnx' 
        gfzrx merge input:  'NMER00XXX_R_20213291100_01D_30S_MO.yyo'
        '''
    dir_name = os.path.dirname(file)
    rover_file = os.path.basename(file)
    new_filename = dir_name + '/' + rover_name + rover_file.split('.')[0][4:] + '.' + yy + 'o'
    print('\nRover file: ' + rover_file, '\nNew filename: ', new_filename)
    os.rename(file, new_filename)

print('\n\nfinished renaming all files :-)')


# Q: merge files together per day --> get daily files
# run command: 'gfzrnx -finp NMER00XXX_R_2021330????_01D_30S_MO.21o -fout ::RX3D:: -d 86400'
for file in glob.iglob('data_neumayer/temp/NMER00XXX_R_20' + '*.' + yy + 'O', recursive=True):
    ''' get doy from rover file names with name structure:
        gfzrx merge input:   'NMER00XXX_R_2021329????_01D_30S_MO.yyo'
        gfzrnx merge output: 'NMER00XXX_R_2021330????_01D_30S_MO.rnx'
        '''
    print(file)
    rover_file = os.path.basename(file)
    doy = rover_file.split('.')[0][16:19]
    doy_end = str(int(doy) + 1)
    print('\nRover file: ' + rover_file, '\ndoy: ', doy, '\ndoy_end: ', doy_end)

    # define input and output filenames (for some reason it's not working when input files are stored in subfolders!)
    out_file = rover_name + doy_end + 'D.' + yy + 'O'
    process1 = subprocess.Popen('cd data_neumayer/temp && '
                                'gfzrnx -finp NMER00XXX_R_20' + yy + doy + '????_01D_30S_MO.' + yy + 'o '
                                '-fout ::RX3D:: -d 86400',
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

    stdout1, stderr1 = process1.communicate()
    print(stdout1)
    print(stderr1)

print('\n\nfinished merging all files :-)')


# Q: rename output to NMERdoy0.yyo
for file in glob.iglob('data_neumayer/temp/*.rnx', recursive=True):
    ''' rename gfzrnx merge files output names to match rtklib and leica file names:
        gfzrnx merge output: 'NMER00XXX_R_2021330????_01D_30S_MO.rnx'
        rtklib input: 'NMERdoy0.yyo'  (typical rinex naming convention format)
        '''
    dir_name = os.path.dirname(file)
    rover_file = os.path.basename(file)
    new_filename = dir_name + '/' + rover_name + rover_file.split('.')[0][16:19] + '0.' + yy + 'o'
    print('\nRover file: ' + rover_file, '\nNew filename: ', new_filename)
    os.rename(file, new_filename)

print('\n\nfinished renaming all files :-)')


# Q: move files to main directory
for file in glob.iglob('data_neumayer/temp/NMER???0.' + yy + 'O', recursive=True):
    shutil.move(file, 'data_neumayer/')

# delete 'temp' directory and remaining files in 'temp' directory
shutil.rmtree('data_neumayer/temp/')
