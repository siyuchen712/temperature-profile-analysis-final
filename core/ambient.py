import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time
import re
from plotly import __version__
from plotly.offline import download_plotlyjs, init_notebook_mode, plot, iplot
import plotly.plotly as py
import plotly.graph_objs as go
from operator import itemgetter
import itertools

from core.re_and_globals import *


def ambient_analysis(df, channels, amb, upper_threshold, lower_threshold):
    #########get the big gap of ambient (channel_1)
    ####Test for one channel
    df_chan_Ambient = df[['Sweep #', 'Time', amb]].sort_values(['Sweep #']).reset_index(drop=True)
    sweep_screen = []
    for i in range(df_chan_Ambient.shape[0]):
        sweep_screen.append(i)
    df_chan_Ambient.insert(0,'Sweep_screen',pd.Series(sweep_screen, index=df_chan_Ambient.index).tolist())
    df_chan_Ambient_loc = get_points_above_and_below_thresholds(df_chan_Ambient, channels[0], upper_threshold, lower_threshold)
    ambient = get_amb_key_points(df_chan_Ambient_loc)
    ambient = calculate_ramp_stats(amb, ambient, df_chan_Ambient_loc)

    ## differentiate profile starting point
    start_index_list = find_starting_point_case(amb, ambient, upper_threshold, lower_threshold)  
    down_i = start_index_list[0]
    up_i = start_index_list[1]
    cold_i = start_index_list[2]
    hot_i = start_index_list[3]

    ls_index_down, ls_index_up, ls_index_cold, ls_index_hot = [], [], [], []
    for i in range(int(ambient.shape[0]/4)):
        ls_index_down.append(i*4 + down_i)
        ls_index_up.append(i*4 + up_i)
        ls_index_cold.append(i*4 + cold_i)
        ls_index_hot.append(i*4 + hot_i)

    ### SOAK ANALYSIS
    df_soak_high, df_soak_low = soak_analysis(amb, amb, ambient, df_chan_Ambient, ls_index_cold, ls_index_hot, start_index_list)

    ### RAMP ANALYSIS
    df_transform_down, df_transform_up = ramp_analysis(ambient, df_chan_Ambient, ls_index_down, ls_index_up)

    ### Create summary
    result_each_cycle, df_summary = create_analysis_summary(amb, amb, df_soak_high, df_soak_low, df_transform_down, df_transform_up)

    return result_each_cycle, df_summary, ambient


#########################
####### HELPERS #########
#########################
def create_analysis_summary(channel, amb, df_soak_high, df_soak_low, df_transform_down, df_transform_up):

    soak_columns_with_cyc = [1,6,9,10,11] ## 'cycle#', 'duration_minutes', 'mean_temp', 'max_temp', 'min_temp'
    soak_columns_wo_cyc = [5,8,9,10]  ## 'duration_minutes', 'mean_temp', 'max_temp', 'min_temp'
    transform_columns_amb = [5,6,7]
    transform_columns_non_amb = [6,7,8]

    if channel == amb:
        ### if ambient, concat and then add cycle# index
        result_each_cycle = pd.concat([df_soak_low[soak_columns_wo_cyc], df_soak_high[soak_columns_wo_cyc],df_transform_down[transform_columns_amb], df_transform_up[transform_columns_amb]], axis=1)
        result_each_cycle.insert(0, 'cycle#', pd.Series(list(range(1,result_each_cycle.shape[0]+1))))
    else:
        result_each_cycle = pd.concat([df_soak_low[soak_columns_with_cyc], df_soak_high[soak_columns_wo_cyc],df_transform_down[transform_columns_non_amb], df_transform_up[transform_columns_non_amb]], axis=1)

    cycles_label = ['cycle#', 
                     'cold_soak_duration_minute', 'cold_soak_mean_temp_c', 'cold_soak_max_temp_c', 'cold_soak_min_temp_c', 
                     'hot_soak_duration_minute', 'hot_soak_mean_temp_c', 'hot_soak_max_temp_c', 'hot_soak_min_temp_c', 
                     'down_recovery_time_minute', 'down_RAMP_temp_c', 'down_RAMP_rate_c/minute', 
                     'up_recovery_time_minute', 'up_RAMP_temp_c', 'up_RAMP_rate_c/minute']

    result_each_cycle.columns = cycles_label
    ls_mean, ls_std, ls_min, ls_min_cid, ls_max, ls_max_cid= [], [], [], [], [], []

    for i in range(1, result_each_cycle.shape[1]):
        ls_mean.append(result_each_cycle.ix[:,i].mean())
        ls_std.append(result_each_cycle.ix[:,i].std())
        ls_max.append(result_each_cycle.ix[:,i].max())
        ls_min.append(result_each_cycle.ix[:,i].min())
        ls_min_cid.append(result_each_cycle.ix[:,i].idxmin())
        ls_max_cid.append(result_each_cycle.ix[:,i].idxmax())

    summary_label = cycles_label[1:]

    df_summary = pd.DataFrame.from_items([('mean', ls_mean), ('min', ls_min),('min_cycle#', ls_min_cid), ('max', ls_max), ('max_cycle#', ls_max_cid),('std_dev', ls_std)],orient='index', columns=summary_label)
    df_summary = df_summary.iloc[:, :14]
    df_summary = df_summary.round(2)
    result_each_cycle = result_each_cycle.round(2)
    result_each_cycle.set_index('cycle#', inplace=True)
    
    return result_each_cycle, df_summary


def soak_analysis(channel_name, amb, ambient, df_chan_Ambient, ls_index_cold, ls_index_hot, start_index_list):
    
    df_soak_low = ambient.loc[ls_index_cold].sort_values(['Sweep_screen']).reset_index(drop=True)
    df_soak_high = ambient.loc[ls_index_hot].sort_values(['Sweep_screen']).reset_index(drop=True)

    ## replace first keypoint 0 index with 4
    reset_start_index_list = [4 if i==0 else i for i in start_index_list]
    down_i = reset_start_index_list[0]
    up_i = reset_start_index_list[1]
    cold_i = reset_start_index_list[2]
    hot_i = reset_start_index_list[3]

    mean_temp_low, mean_temp_high = [], []
    max_temp_low, max_temp_high = [], []
    min_temp_low, min_temp_high = [], []

    number_of_cycles = int(ambient.shape[0]/4)
    
    if channel_name != amb:
        number_of_cycles -= 1

    for i in range(number_of_cycles):
        df_temp_low, df_temp_high = pd.DataFrame(), pd.DataFrame()
        df_temp_low = df_chan_Ambient.iloc[ambient.iloc[4*i+cold_i]['Sweep_screen']:ambient.iloc[4*i+up_i]['Sweep_screen'],[3]]
        df_temp_high = df_chan_Ambient.iloc[ambient.iloc[4*i+hot_i]['Sweep_screen']:ambient.iloc[4*i+down_i]['Sweep_screen'],[3]]

        mean_temp_low.append(df_temp_low.mean(axis=0).ix[0])
        mean_temp_high.append(df_temp_high.mean(axis=0).ix[0])
        max_temp_low.append(df_temp_low.max(axis=0).ix[0])
        max_temp_high.append(df_temp_high.max(axis=0).ix[0])
        min_temp_low.append(df_temp_low.min(axis=0).ix[0])
        min_temp_high.append(df_temp_high.min(axis=0).ix[0])

    df_soak_low['mean_temp'] = pd.Series(mean_temp_low)
    df_soak_high['mean_temp'] = pd.Series(mean_temp_high)
    df_soak_low['max_temp'] = pd.Series(max_temp_low)
    df_soak_high['max_temp'] = pd.Series(max_temp_high)
    df_soak_low['min_temp'] = pd.Series(min_temp_low)
    df_soak_high['min_temp'] = pd.Series(min_temp_high)

    return df_soak_high, df_soak_low

def ramp_analysis(ambient, df_chan_Ambient, ls_index_down, ls_index_up):
    df_transform_down = ambient.loc[ls_index_down].sort_values(['Sweep_screen']).reset_index(drop=True)
    df_transform_up =ambient.loc[ls_index_up].sort_values(['Sweep_screen']).reset_index(drop=True)
    return df_transform_down, df_transform_up

def get_points_above_and_below_thresholds(df_chan_Ambient, channel, upper_threshold, lower_threshold):
    #The index of all the points of temp out of threshold
    High_index = df_chan_Ambient[channel][df_chan_Ambient[channel] > upper_threshold].index.tolist()
    Low_index = df_chan_Ambient[channel][df_chan_Ambient[channel] < lower_threshold].index.tolist()
    point_index = []
    for i in range(len(Low_index)):
        point_index.append(Low_index[i])
    for i in range(len(High_index)):
        point_index.append(High_index[i]) 
    point_index = np.sort(point_index).tolist()
    return df_chan_Ambient.loc[point_index]

#####
def get_amb_key_points(df_chan_Ambient_loc):
    ####Gap point
    result = df_chan_Ambient_loc
    result['diff_1_sweep#'] = df_chan_Ambient_loc[[0]].shift(-1) - df_chan_Ambient_loc[[0]]
    result['diff_2_sweep#'] = df_chan_Ambient_loc[[0]] - df_chan_Ambient_loc[[0]].shift(1)
    result = result.sort_values(['Sweep_screen'])
    result = result.reset_index(drop=True)

    #Get the threshold of gap length
    result_index_1 = result['diff_1_sweep#'][result['diff_1_sweep#'] >1].index.tolist()
    result_index_2 = result['diff_2_sweep#'][result['diff_2_sweep#'] >1].index.tolist()
    result_index = list(set(result_index_1) | set(result_index_2))
    result = result.loc[result_index]
    result = result.sort_values(['Sweep_screen'])
    result = result.reset_index(drop=True)

    result_points_1 = result[[0,1,2,3]]
    result_points_1.insert(0,'diff_1_sweep#',(result_points_1[[0]].shift(-1) - result_points_1[[0]]).Sweep_screen.values.tolist())
    result_points_1.insert(0,'diff_2_sweep#',(result_points_1[[1]] - result_points_1[[1]].shift(1)).Sweep_screen.values.tolist())

    ripple_gap = (result_points_1['diff_1_sweep#'] + result_points_1['diff_2_sweep#']).mean()*0.5  ## TO DO --> set valid ratio
    cycle_index = result_points_1['diff_1_sweep#'][result_points_1['diff_1_sweep#'] + result_points_1['diff_2_sweep#']>ripple_gap].index.tolist()
    cycle_index.append(0)
    
    result_points_1 = result_points_1.loc[cycle_index]
    result_points_1 = result_points_1.sort_values(['Sweep_screen'])
    result_points_1 = result_points_1.reset_index(drop=True)
    result_points_1 = result_points_1[[2,3,4,5]]

    ambient = result_points_1  ## ambient --> dataframe of key points and later has all calculations
    return ambient

####
def calculate_ramp_stats(channel_name, ambient, df_chan_Ambient_loc):
    ### Adds time duration
    time = []
    for m in range(ambient.shape[0]-1):
        a1 = ambient['Time'][m+1]
        a2 = ambient['Time'][m]
        time.append((datetime.strptime(a1, DATE_FORMAT) - datetime.strptime(a2, DATE_FORMAT)).total_seconds())

    time.append(0)
    ambient.insert(0,'duration',time)
    ambient['duration_minutes'] = ambient['duration']/60 ## translate duration to minutes

    # temp range difference of consecutive rows
    ambient['ramp_temp'] = pd.Series(0, index=df_chan_Ambient_loc.index)
    ambient['ramp_temp'] = ambient[channel_name].shift(-1) - ambient[channel_name]
    
    # Find ramp rates
    ambient['ramp_rate'] = pd.Series(0, index=df_chan_Ambient_loc.index)
    ambient['ramp_rate'] = ambient['ramp_temp']*60/ambient['duration']

    return ambient


def find_starting_point_case(amb, ambient, upper_threshold, lower_threshold):
    starting_temp = ambient.iloc[0][amb] ## temp of first key point
    temp_diff_between_first_two_key_pts = starting_temp - ambient.iloc[1][amb]

    if abs((starting_temp - upper_threshold)) < abs((starting_temp - lower_threshold)):
        ### starts at upper thresh
        if abs(temp_diff_between_first_two_key_pts) < (upper_threshold-lower_threshold)*.5:
            ### is a hot soak
            ls_index_down, ls_index_up, ls_index_cold, ls_index_hot = set_high_soak(ambient)
        else:
            ### hot to cold ramp
            ls_index_down, ls_index_up, ls_index_cold, ls_index_hot = set_transform_down(ambient)
    else:
        ### starts at lower thresh 
        if abs(temp_diff_between_first_two_key_pts) < (upper_threshold-lower_threshold)*.5:
            ## is a cold soak
            ls_index_down, ls_index_up, ls_index_cold, ls_index_hot = set_low_soak(ambient)
        else: 
            ### cold to hot ramp
            ls_index_down, ls_index_up, ls_index_cold, ls_index_hot = set_transform_up(ambient)
    return ls_index_down, ls_index_up, ls_index_cold, ls_index_hot

def set_transform_down(ambient):
    print('STARTING POINT: TRANSFORM DOWN')
    down_i, up_i, cold_i, hot_i = 0, 2, 1, 3
    return [down_i, up_i, cold_i, hot_i]

def set_transform_up(ambient):
    print('STARTING POINT: TRANSFORM UP')
    down_i, up_i, cold_i, hot_i = 2, 0, 3, 1
    return [down_i, up_i, cold_i, hot_i]

def set_high_soak(ambient):
    print('STARTING POINT: HIGH SOAK')
    down_i, up_i, cold_i, hot_i = 1, 3, 2, 0
    return [down_i, up_i, cold_i, hot_i]

def set_low_soak(ambient):
    print('STARTING POINT: LOW SOAK')
    down_i, up_i, cold_i, hot_i = 3, 1, 0, 2
    return [down_i, up_i, cold_i, hot_i]

