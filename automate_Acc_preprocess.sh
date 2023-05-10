#!/bin/bash

# change directory to python working directory
cd C:/Users/sladina.BGEO02P102/Documents/SD_Card/Postdoc/AWI/05_Analysis/Run_RTKLib/

# run python script Acc_postproc_GNSSREFL_Neumayer.py and output console log to logfile
python Acc_postproc_GNSSREFL_Neumayer.py | tee data_neumayer/30_plots/Acc_postproc_GNSSREFL_Neumayer.log

# wait for user to terminate console (enter)
read