#! /bin/bash
year_start=$1
doy_start=$2
year_end=$3
doy_end=$4
station=$5 # nmlb, nmsh
echo " "
echo "++++++++++++++++++++++++"
echo "  Convert rinex to SNR  "
echo "++++++++++++++++++++++++"
echo " "
rinex2snr $station $year_start $doy_start -nolook=True -year_end $year_end -doy_end $doy_end -orb gnss -overwrite=True
echo " "
echo "++++++++++++++++++++++++"
echo "    Do Reflectometry    "
echo "++++++++++++++++++++++++"
echo " "
gnssir $station $year_start $doy_start -plt=False -year_end $year_end -doy_end $doy_end
