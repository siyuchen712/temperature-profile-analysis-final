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
from core.ambient import *


def single_channel_analysis(df, channel, amb, ambient, upper_threshold, lower_threshold):
    df_summary = pd.DataFrame()
    n_reach_summary = pd.DataFrame()

    ####Test for one channel
    df_chan = df[['Sweep #', 'Time']+[channel]].sort_values(['Sweep #']).reset_index(drop=True)
    sweep_screen = []
    for i in range(df_chan.shape[0]):
        sweep_screen.append(i)
    df_chan.insert(0,'Sweep_screen',pd.Series(sweep_screen, index=df_chan.index).tolist())

    key_point_cycle, cycle_ls, result, n_reach = get_keypoints_for_each_cycle(channel, ambient, df_chan, upper_threshold, lower_threshold)

    #### Cycle Statistics #####
    if len(key_point_cycle) == ambient.shape[0]//4:  ## if all the cycles reached
        selected_channel = pd.concat(key_point_cycle).sort_values(['Sweep_screen']).reset_index(drop=True)
        
        selected_channel = calculate_ramp_stats(channel, selected_channel, df_chan)
        start_index_list = find_starting_point_case(channel, selected_channel, upper_threshold, lower_threshold) 
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
        df_soak_high, df_soak_low = soak_analysis(channel, amb, selected_channel, df_chan, ls_index_cold, ls_index_hot, start_index_list)

        ### RAMP ANALYSIS
        df_transform_down, df_transform_up = ramp_analysis(selected_channel, df_chan, ls_index_down, ls_index_up)

        ## Create summary table
        result_each_cycle, df_summary = create_analysis_summary(channel, amb, df_soak_high, df_soak_low, df_transform_down, df_transform_up)

    elif not cycle_ls:  ##  none of the cycles reached
        df_summary, result_each_cycle = pd.DataFrame(), pd.DataFrame()
        ## pd.DataFrame({1:'NO CYCLES REACH THE THRESHOLDS'}, [0])

    else:  ### only some of the cycles reached the thresholds
        consecutive_cycle = []  ## list of lists --> cycle numbers that reached consecutively
        for k, g in itertools.groupby(enumerate(cycle_ls), lambda x: x[1]-x[0] ) :
            consecutive_cycle.append(list(map(itemgetter(1), g)))
        
        uncontn_cycle = []  ## list of lists of dataframes of keypoints that reached thresholds
        
        ## find consecutive cycle information
        for k in range(len(consecutive_cycle)):
            uncontn_cycle.append([])
            for i in(consecutive_cycle[k]):
                for j in range(len(key_point_cycle)):
                    if key_point_cycle[j]['cycle#'][0] == i+1:
                        #print(key_point_cycle[j]['cycle#'][0])
                        uncontn_cycle[k].append(key_point_cycle[j].iloc[0:4])
                        
        uncontn_result_each_cycle = []  ## list of information for all channels
        uncontn_summary = []  ## list indexed by cycle number ---> data is the partial summary of consecutive periods that reached threshols
        
        period = []  ## created index --> periods of consecutive cycles that reached thresholds
        for x in range(len(uncontn_cycle)):  ## x: period
            uncontn_result_each_cycle.append([])
            uncontn_summary.append([])

            selected_channel = pd.concat(uncontn_cycle[x]).sort_values(['Sweep_screen']).reset_index(drop=True)          
            selected_channel = calculate_ramp_stats(channel, selected_channel, df_chan)
            start_index_list = find_starting_point_case(channel, selected_channel, upper_threshold, lower_threshold) 
            down_i = start_index_list[0]
            up_i = start_index_list[1]
            cold_i = start_index_list[2]
            hot_i = start_index_list[3]

            ls_index_down, ls_index_up, ls_index_cold, ls_index_hot = [], [], [], []
            for i in range(int(selected_channel.shape[0]/4)):
                ls_index_down.append(i*4 + down_i)
                ls_index_up.append(i*4 + up_i)
                ls_index_cold.append(i*4 + cold_i)
                ls_index_hot.append(i*4 + hot_i)
                
            ### SOAK ANALYSIS
            df_soak_high, df_soak_low = soak_analysis(channel, amb, selected_channel, df_chan, ls_index_cold, ls_index_hot, start_index_list)

            ### RAMP ANALYSIS
            df_transform_down, df_transform_up = ramp_analysis(selected_channel, df_chan, ls_index_down, ls_index_up)

            ### Create summary table
            result_each_cycle, df_summary = create_analysis_summary(channel, amb, df_soak_high, df_soak_low, df_transform_down, df_transform_up)

            ## Add tables to period lists
            uncontn_summary[x] = df_summary
            cols_df_summary = df_summary.columns.tolist()
            
            result_each_cycle = result_each_cycle.round(2)
            uncontn_result_each_cycle[x] = result_each_cycle
            cols_result_each_cycle = result_each_cycle.columns.tolist()
            
            period.append(x)

        df_summary = pd.concat(uncontn_summary,axis=0, keys=period)
        result_each_cycle = pd.concat(uncontn_result_each_cycle,axis=0, keys=period)
        df_summary = df_summary[cols_df_summary]
        result_each_cycle = result_each_cycle[cols_result_each_cycle]
        
        nr_period = []
        for i in range(len(n_reach)):
            nr_period.append(i)

        n_reach_summary = pd.concat(n_reach,axis=0, keys=nr_period)
        n_reach_summary = n_reach_summary[['cycle#', 'Sweep #', 'Time', channel]]

    return result_each_cycle, df_summary, n_reach_summary


#########################
####### HELPERS #########
#########################

def get_keypoints_for_each_cycle(channel, ambient, df_chan, upper_threshold, lower_threshold):
    ls_cycle_bound = [] ## bounds rand to search each cycle for key points
    high_index = []  ## all poitns above high threshold
    low_index = []  ## all points below low threshold
    ls_cycle = [] ## list of lists --> nested list is search bounds of sweep screen
    cycle_ls = []  ## list of integers - cycles that DID reach threhold(s)
    point_cycle_index = [] ## merged low and high key points for each cycle
    key_point_cycle = []  ## list holding dataframes of key cycle points
    n_reach = []  ## list of the "not-reach" cycles' keypoint dataframes
    n_reach_cycle = []  ## list of integers - cycles that DID NOT reach threhold(s)

    number_of_ambient_cycles = ambient.shape[0]//4
    for i in range(number_of_ambient_cycles): 
        cycle_ls.append(i)
        ## find boundary to search
        if i != number_of_ambient_cycles - 1:  ## last cycle in loop
            ls_cycle_bound.append(ambient.iloc[[4*i,4*i+6]].Sweep_screen.tolist())
        else:  ## not last cycle in loop 
            ls_cycle_bound.append(ambient.iloc[[4*i,ambient.shape[0]-1]].Sweep_screen.tolist())

        if ls_cycle_bound[i][0] < 5: ## at beginning of profile (sweep screen smaller than 5)
            ls_cycle_bound[i][0] = 0
        else: ## not at beginning
            ls_cycle_bound[i][0] = ls_cycle_bound[i][0] - 5

        if ls_cycle_bound[i][1] > ambient.Sweep_screen[ambient.shape[0]-1] - 5: ## at end
            ls_cycle_bound[i][1] = ambient.Sweep_screen[ambient.shape[0]-1]
        else:  ## not at end
            ls_cycle_bound[i][1] = ls_cycle_bound[i][1] + 5

        ls_cycle_component = df_chan.iloc[ls_cycle_bound[i][0]:ls_cycle_bound[i][1]]
        ls_cycle_component.insert(0,'cycle#',i+1)
        ls_cycle.append(ls_cycle_component)

        #The index of all the points of temp out of threshold
        high_index = ls_cycle[i][channel][ls_cycle[i][channel]> upper_threshold].index.tolist()
        low_index = ls_cycle[i][channel][ls_cycle[i][channel]< lower_threshold].index.tolist()
        point_index = []
        for m in range(int(len(low_index))):
            point_index.append(low_index[m])
        for n in range(int(len(high_index))):
            point_index.append(high_index[n])   

        point_index = np.sort(point_index)
        point_index = point_index.tolist()
        point_cycle_index.append(point_index)
        ls_cycle[i] = ls_cycle[i].loc[point_cycle_index[i]]
    
        ## Gap point
        result = ls_cycle[i]
        result['diff_1_sweep#'] = ls_cycle[i][[1]].shift(-1) - ls_cycle[i][[1]]
        result['diff_2_sweep#'] = ls_cycle[i][[1]] - ls_cycle[i][[1]].shift(1)
        result = result.sort_values(['Sweep_screen'])
        result = result.reset_index(drop=True)

        ## Get the threshold of gap length
        result_index_1 = result['diff_1_sweep#'][result['diff_1_sweep#'] >1].index.tolist()
        result_index_2 = result['diff_2_sweep#'][result['diff_2_sweep#'] >1].index.tolist()
        result_index = list(set(result_index_1) | set(result_index_2))
        result = result.loc[result_index]
        result = result.sort_values(['Sweep_screen'])
        result = result.reset_index(drop=True)
        
        if result.shape[0]< 5 and i!=ambient.shape[0]//4-1:
            n_reach.append(result)
            n_reach_cycle.append(i)
        elif result.shape[0]< 4 and i ==ambient.shape[0]//4-1:
            n_reach.append(result)
            n_reach_cycle.append(i)
        else:
            result_points = result[[0,1,2,3,4]]
            result_points = result_points.iloc[0:4]
            key_point_cycle.append(result_points)

    for cycle in n_reach_cycle:  ## remove cycles that DID NOT reach from cycle list 
        cycle_ls.remove(cycle)

    return key_point_cycle, cycle_ls, result, n_reach