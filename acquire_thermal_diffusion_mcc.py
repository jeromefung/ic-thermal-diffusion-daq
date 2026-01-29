'''
acquire_thermal_diffusion_mcc.py

Acquire and save data from IC Thermal Diffusion experiment using MCC USB-234 interface.

Hardware connections: (See pinout for single-ended analog input)

    Analog output CH0: heater MOSFET gate 
    Analog input CH0: V_htr (LOW when heater on)
    Analog input CH1: V_0 for thermistor voltage divider
    Analog input CH2: V_A1 (output of thermistor 1 op amp)
    Analog input CH3: V_A2
    Analog input CH4: V_A3
    Analog input CH5: V_A4
    Analog input CH6: V_0 for heater circuit

Command line usage:
    python acquire_thermal_diffusion_mcc.py pulse_length lag_time duration fname_base

Command line parameters:

    pulse_length (float): Duration of heat pulse in seconds
    lag_time (float): Amount of time to wait in seconds before heater turns on
    duration (float): 
        Amount of time in seconds to measure after heater turns on.
        Total length of measurement in seconds is lag_time + duration.
    fname_base (str): Base for output file name (no extensions needed)

Author: Jerome Fung (jfung@ithaca.edu)
'''

import sys
import numpy as np 
from mcculw import ul
from mcculw.device_info import DaqDeviceInfo
from mcculw.enums import InterfaceType, AnalogInputMode, ScanOptions, FunctionType

import ctypes


class MCCInterface:
    def __init__(self):
        ul.ignore_instacal()
        devices = ul.get_daq_device_inventory(InterfaceType.ANY)
        self.board_number = 0
        ul.create_daq_device(self.board_number, devices[0])

        self.in_low_channel = 0
        self.in_high_channel = 6
        self.n_in_channels - self.in_high_channel - self.in_low_channel + 1
        self.out_low_channel = 0
        self.out_high_channel = 0

        self.device_info = DaqDeviceInfo(self.board_number)
        self.ai_info = self.device_info.get_ai_info()
        self.ai_range = self.ai_info.supported_ranges[0]
        self.ao_info = self.device_info.get_ao_info()
        self.ao_range = self.ao_info.supported_ranges[0]

        # configure ADC and DAC rates in hertz
        self.adc_rate_per_channel = 10000
        self.dac_rate = 100
        self.downsampled_rate = 100

        # configure single-ended input
        ul.a_input_mode(self.board_number, AnalogInputMode.SINGLE_ENDED) 

    def measure(self, pulse_length, lag_time, duration, outfname):
        total_meas_time_sec = lag_time + duration
        ain_pts_per_channel = np.floor(total_meas_time_sec * self.adc_rate_per_channel).astype('int')
        aout_pts = np.floor(total_meas_time_sec * self.dac_rate).astype('int')

        total_input_pts = ain_pts_per_channel * self.n_in_channels
         
        # allocate memory buffer for input
        input_memhandle = ul.win_buf_alloc(total_count)
        data_array = ctypes.cast(input_memhandle, ctypes.POINTER(ctypes.c_ushort))

        # set up output
        output_data = np.zeros(aout_pts, dtype = np.float64)
        start_idx = np.floor(lag_time * self.dac_rate).astype('int')
        stop_idx = start_idx + np.floor(pulse_length * self.dac_rate).astype('int')
        output_data[start_idx:stop_idx] = 5. # actual volts

        # allocate a buffer for the output
        output_memhandle = ul.scaled_win_buf_alloc(aout_pts)
        # Get the pointer to the output data
        output_ptr = output_data.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        ul.scaled_win_array_to_buf(output_ptr, output_memhandle, 0, aout_pts)

        # Start analog output in background mode.
        # There will almost certainly be some timing offset, hopefully not too much
        ao_options = ScanOptions.BACKGROUND | ScanOptions.SCALEDATA
        ul.a_out_scan(self.board_number, self.out_low_channel, self.out_high_channel,
                      aout_pts, self.dac_rate, self.ao_range, output_memhandle, ao_options)

        # start analog input scan
        actual_rate = ul.a_in_scan(self.board_number, self.in_low_channel, self.in_high_channel,
                                   total_input_pts, self.adc_rate_per_channel, self.ai_range, input_memhandle, 
                                   0)

        # convert to numpy array
        np_data_array = np.ctypeslib.as_array(data_array, (total_input_pts,))

        # convert from integer values to volts
        # want to include times in the output data
        # to avoid a concatenate/copy, initialize the entire array
        voltage_array = np.zeros(total_input_pts + ain_pts_per_channel)
        # interleave the times
        voltage_array[::self.n_in_channels] = np.arange(ain_pts_per_channel)/actual_rate
        for i in np.arange(len(np_data_array)):
            voltage_array[i + 1 + np.floor(i/self.n_in_channels).astype('int')] = ul.to_eng_units(self.board_number, 
                                                                                                  self.ai_range, 
                                                                                                  np_data_array[i])
        # reshape
        voltage_array = voltage_array.reshape(-1, self.n_in_channels + 1)

        # save
        np.save(outfname + '.npy', voltage_array)
        np.save(outfname + '_100Hz.npy', voltage_array[::100])
        np.savetxt(outfname + '_100Hz.txt', voltage_array[::100])

        # free memory and clean up
        ul.win_buf_free(input_memhandle)
        #ul.win_buf_free(output_handle)
        data_array = None
        ul.stop_background(self.board_number, FunctionType.AOFUNCTION)



if __name__ == "__main__":
    interface = MCCInterface()
    interface.measure(float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), sys.argv[4])


