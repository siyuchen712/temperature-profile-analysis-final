
from core.data_import import *
from core.ptc_analysis import *
from core.ptc_helpers import *



#datapath = r"C:\Users\bruno\Programming Projects\Temp Profile Analysis\test_data\dat00002.csv"
datapath = r"C:\Users\s.chen6\Desktop\20161017_105827_P552 MCA DV PTC_02_B4.txt"
#datapath = r"\\Chfile1\ecs_landrive\Automotive_Lighting\LED\P552 MCA Headlamp\P552 MCA Aux\ADVPR\DV Aux\TL A&B\PTC\Cycles 16-30\PTC test\Raw Data\20161022_131458_P552_MCA_DV_PTD_cycs16to30_01_B3.txt"


upper_threshold, lower_threshold = 85, -40
tolerance = 3
rate_adjustment = 10
ambient_channel_number = 1

## DATA IMPORT
date_format = '%m/%d/%Y %I:%M:%S %p'
regex_temp = 'TC[1-4]$'
df, channels, amb, amb_errors = import_data_without_date_index(datapath, ambient_channel_number, regex_temp, sep='\t')

## PLOT
#plot_profile(TITLE, df, channels)

## ANALYSIS
tc_channel_names = {}
for chan in channels:
    tc_channel_names[chan] = ''

ptc_analyze_all_channels(df, channels, amb, amb_errors, tc_channel_names, upper_threshold, lower_threshold, tolerance, rate_adjustment, date_format)

