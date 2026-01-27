'''
Read 4 analog input channels and use an analog output channel simultaneously.

Analog output: delay 1 s, HIGH 1 s, LOW 1 s, HIGH 1s, LOW thereafter
'''

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
        self.in_high_channel = 3
        self.out_low_channel = 0
        self.out_high_channel = 0

        self.device_info = DaqDeviceInfo(self.board_number)
        self.ai_info = self.device_info.get_ai_info()
        self.ai_range = self.ai_info.supported_ranges[0]
        self.ao_info = self.device_info.get_ao_info()
        self.ao_range = self.ao_info.supported_ranges[0]

        # configure single-ended input
        ul.a_input_mode(self.board_number, AnalogInputMode.SINGLE_ENDED) 

    def measure(self, outfname):
        ain_rate = 10000 # per channel
        points_per_channel = 300000 # per channel
        total_count = points_per_channel * 4

        # allocate memory buffer for input
        memhandle = ul.win_buf_alloc(total_count)
        data_array = ctypes.cast(memhandle, ctypes.POINTER(ctypes.c_ushort))

        # set up ouput
        aout_rate = 100
        aout_duration = 30 # seconds
        aout_pts = aout_rate * aout_duration
        output_data = np.zeros(aout_pts, dtype = np.float64)
        output_data[100:200] = 5. # actual volts
        output_data[300:400] = 5. # actual volts
        # allocate a buffer for the output
        output_handle = ul.scaled_win_buf_alloc(aout_pts)
        # Get the pointer to the output data
        output_ptr = output_data.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        ul.scaled_win_array_to_buf(output_ptr, output_handle, 0, aout_pts)

        # Start analog output in background mode.
        # There will almost certainly be some timing offset, hopefully not too much
        ao_options = ScanOptions.BACKGROUND | ScanOptions.SCALEDATA
        ul.a_out_scan(self.board_number, self.out_low_channel, self.out_high_channel,
                      aout_pts, aout_rate, self.ao_range, output_handle, ao_options)

        # scan
        ul.a_in_scan(self.board_number, self.in_low_channel, self.in_high_channel,
                     total_count, ain_rate, self.ai_range, memhandle, 0)

        # convert to numpy array
        np_data_array = np.ctypeslib.as_array(data_array, (total_count,))

        # convert from integer to volts
        voltage_array = np.zeros(len(np_data_array))
        for i in np.arange(len(np_data_array)):
            voltage_array[i] = ul.to_eng_units(self.board_number, self.ai_range, 
                                               np_data_array[i])

        # reshape
        voltage_array = voltage_array.reshape(-1, self.in_high_channel - self.in_low_channel + 1)
        np.save(outfname, voltage_array)

        # free memory and clean up
        ul.win_buf_free(memhandle)
        data_array = None
        ul.stop_background(self.board_number, FunctionType.AOFUNCTION)



