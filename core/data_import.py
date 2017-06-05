import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time
import re
import plotly.plotly as py
import plotly.graph_objs as go
from operator import itemgetter
import itertools

from core.plot import *
from core.tshock_analysis import *
from core.ptc_analysis import *


py.sign_in('sjbrun','v1jdPUhNoRgRBpAOOx7Y')

#### TSHOCK
def import_data_with_date_index(datapath, ambient_channel_number, regex_temp, sep=','):
    ''' Main import function with date index (for plotting) '''
    df = read_data_for_plot(datapath, sep=sep)
    channels = get_channels(df, regex_temp)
    amb = set_ambient(channels, ambient_channel_number)
    df, errors = drop_errors(df, channels)
    return df, channels, amb, errors

def import_data_without_date_index(datapath, ambient_channel_number, regex_temp, sep=','):
    ''' Main import function without date index (for analysis using sweep #) '''
    df = read_data_for_analysis(datapath, sep=sep)
    channels = get_channels(df, regex_temp)
    amb = set_ambient(channels, ambient_channel_number)
    df, errors = drop_errors(df, channels)
    return df, channels, amb, errors



################################################
############### Helper functions ###############
################################################
def read_data_for_plot(datapath, sep=','):
    ''' Returns a dataframe of the agilent temperature data '''
    date_parser = lambda x: pd.datetime.strptime(x, DATE_FORMAT)
    return pd.read_csv(datapath, parse_dates={'Date Time': [1]}, date_parser=date_parser, 
                       index_col='Date Time', engine='python', sep=sep)

def read_data_for_analysis(datapath, sep=','):
    ''' Returns a dataframe of the agilent temperature data '''
    return pd.read_csv(datapath, sep=sep)

def get_channels(df, regular_expression):
    ''' Find valid TC channel headers in dataframe '''
    return [df.columns[i] for i in range(len(df.columns)) if re.search(regular_expression, df.columns[i])]

def set_ambient(channels, ambient_channel_number):
    ''' Sets the ambient TC from user input integer '''
    return channels[ambient_channel_number-1]

def drop_errors(df, channels):
    ''' Get rid of outrage data and output error list '''
    df_copy = df
    for channel in channels:
        df = df[df[channel] < 150]
        df = df[df[channel] > -100]
    errors = df_copy[~df_copy.index.isin(df.index.tolist())]
    return df, errors


