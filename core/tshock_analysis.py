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
import xlsxwriter

from core.tshock_helpers import *


def tshock_analyze_all_channels(df, channels, amb, amb_errors, tc_channel_names, upper_threshold, lower_threshold, tolerance, rate_adjustment, date_format):
    writer = create_wb() ## create workbook
    
    ## analyze ambient
    amb_upper_threshold = upper_threshold - tolerance
    amb_lower_threshold = lower_threshold + tolerance
    result_each_cycle_amb, df_summary_amb, ambient, content_instruction_ambient = ambient_analysis(df, channels, amb, amb_upper_threshold, amb_lower_threshold, date_format)
    
    write_multiple_dfs(writer, [amb_errors, df_summary_amb, result_each_cycle_amb], 'Amb '+str(amb), 3, content_instruction_ambient)

    ### all other channels
    if rate_adjustment or rate_adjustment != 0:  ## apply rate adjustment if supplied and not zero
        temp_adjustment = rate_adjustment*(float(upper_threshold) - float(lower_threshold))/100
        upper_threshold = upper_threshold - temp_adjustment
        lower_threshold = lower_threshold + temp_adjustment

    else: ## otherwise use tolerance used for ambient
        upper_threshold = amb_upper_threshold
        lower_threshold = amb_lower_threshold
    for channel in channels:
        print(channel)
        if channel != amb:
            result_each_cycle, df_summary_tc, n_reach_summary = pd.DataFrame(), pd.DataFrame(), pd.DataFrame() ## ensure reset
            result_each_cycle, df_summary_tc, n_reach_summary, content_instruction = single_channel_analysis(df, channel, amb, ambient, upper_threshold, lower_threshold, date_format)
            if tc_channel_names[channel]:
                tc_name = tc_channel_names[channel] + ' (' + channel.split(' ')[1] + ')'
            else:
                tc_name = channel
            write_multiple_dfs(writer, [df_summary_tc, result_each_cycle, n_reach_summary], tc_name, 3, content_instruction)
    writer.save()


def ambient_analysis(df, channels, amb, upper_threshold, lower_threshold, date_format):
    ''' Analysis for ambient channel '''

    ## get the big gap of ambient (channel_1)
    df_chan_Ambient = df[['Sweep #', 'Time', amb]].sort_values(['Sweep #']).reset_index(drop=True)
    sweep_screen = []
    for i in range(df_chan_Ambient.shape[0]):
        sweep_screen.append(i)
    df_chan_Ambient.insert(0,'Sweep_screen',pd.Series(sweep_screen, index=df_chan_Ambient.index).tolist())
    df_chan_Ambient_loc = get_points_above_and_below_thresholds(df_chan_Ambient, channels[0], upper_threshold, lower_threshold)
    ambient = get_amb_key_points(df_chan_Ambient_loc)
    ambient = calculate_ramp_stats(amb, ambient, df_chan_Ambient_loc, date_format)

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

    cycle_amount = len(result_each_cycle)

    content_instruction = ['In this test file, there are '+ str(cycle_amount) +' cycles.\n\nThe First Table: List out the test data that have reading error.', 'The Second Table: Summary table for the ambient.', 'The Third Table: List out the calculation result for each cycle of ambient.']

    return result_each_cycle, df_summary, ambient, content_instruction


def single_channel_analysis(df, channel, amb, ambient, upper_threshold, lower_threshold, date_format):
    ''' Analysis for non-ambient channels '''

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
        
        selected_channel = calculate_ramp_stats(channel, selected_channel, df_chan, date_format)
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

        content_instruction = ['Every cycle of this channel can reach the threshold!\n\nThe First Table: List out the summary table.', 'The Second Table: Summary table for this channel.', ' ']


    elif not cycle_ls:  ##  none of the cycles reached
        df_summary, result_each_cycle = pd.DataFrame(), pd.DataFrame()
        content_instruction = ['No cycle of this channel can reach the threshold!', ' ', ' ']

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
            selected_channel = calculate_ramp_stats(channel, selected_channel, df_chan, date_format)
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
        df_summary.index.names = ['period #', 'value']
        result_each_cycle = pd.concat(uncontn_result_each_cycle,axis=0, keys=period)
        result_each_cycle.index.names = ['period #', 'cycle #']
        df_summary = df_summary[cols_df_summary]
        result_each_cycle = result_each_cycle[cols_result_each_cycle]
        
        
        nr_period = []
        for i in range(len(n_reach)):
            nr_period.append(i)

        n_reach_summary = pd.concat(n_reach,axis=0, keys=nr_period)
        n_reach_summary = n_reach_summary[['cycle#', 'Sweep #', 'Time', channel]]
        content_instruction = ['Only some cycles of this channel can reach the threshold!\n\nThe First Table: List out the summary table based on the period, where some of the cycles are consequtive.', 'The Second Table: List out the calculation result for each cycle of the consequtive period.', 'These cycles cannot reach the threshold: '+str(nr_period)+ '\n\nThe Third Table: List out the key points, which can touch the threshold.']

    return result_each_cycle, df_summary, n_reach_summary, content_instruction

