
from core.ambient import *
from core.data_import import *



datapath = r"C:\Users\bruno\Programming Projects\Temp Profile Analysis\test_data\dat00002.csv"
upper_threshold, lower_threshold = 95, -40
tolerance = 3
rate_adjustment = 0
ambient_channel_number = 1

## DATA IMPORT
df, channels, amb, amb_errors = import_data_without_date_index(datapath, ambient_channel_number)

## PLOT
#plot_profile(TITLE, df, channels)

## ANALYSIS
tc_channel_names = {}
for chan in channels:
    tc_channel_names[chan] = ''

analyze_all_channels(df, channels, amb, amb_errors, tc_channel_names, upper_threshold, lower_threshold, tolerance, rate_adjustment)

