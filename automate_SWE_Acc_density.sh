#!/bin/bash

# change directory to python working directory
cd C:/Users/sladina.BGEO02P102/Documents/SD_Card/Postdoc/AWI/05_Analysis/Run_RTKLib/

# run python script SWE_postproc_RTKLIB_Neumayer.py and output console log to logfile
python SWE_postproc_RTKLIB_Neumayer.py | tee data_neumayer/30_plots/SWE_postproc_RTKLIB_Neumayer.log

# wait for user to terminate console (enter)
read