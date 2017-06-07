
from core.tshock_analysis import *
from core.tshock_helpers import *
from core.data_import import *



datapath = r"C:\Users\s.chen6\Desktop\dat00002.csv"
upper_threshold, lower_threshold = 95, -40
tolerance = 3
rate_adjustment = 0
ambient_channel_number = 1

## DATA IMPORT
date_format = '%m/%d/%Y %H:%M:%S:%f'
regex_temp = '^Chan\s[0-9][0-9][0-9]'
df, channels, amb, amb_errors = import_data_without_date_index(datapath, ambient_channel_number, regex_temp, sep=',')




## PLOT
#plot_profile(TITLE, df, channels)

## ANALYSIS
## ANALYSIS
tc_channel_names = {}
for chan in channels:
    tc_channel_names[chan] = ''
#analyze_all_channels(df, channels, amb)
tshock_analyze_all_channels(df, channels, amb, amb_errors, tc_channel_names, upper_threshold, lower_threshold, tolerance, rate_adjustment, date_format)
    
