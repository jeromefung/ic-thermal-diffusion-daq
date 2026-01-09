import numpy as np 
from mcculw import ul
from mcculw.device_info import DaqDeviceInfo
from mcculw.enums import InterfaceType, AnalogInputMode  

import ctypes

class MCCInterface:

    def __init__(self):
        ul.ignore_instacal()
        devices = ul.get_daq_device_inventory(InterfaceType.ANY)
        self.board_number = 0
        ul.create_daq_device(self.board_number, devices[0])

        self.low_channel = 0
        self.high_channel = 1
        self.device_info = DaqDeviceInfo(self.board_number)
        self.ai_info = self.device_info.get_ai_info()
        self.ai_range = self.ai_info.supported_ranges[0]

        # configure single-ended input
        ul.a_input_mode(self.board_number, AnalogInputMode.SINGLE_ENDED) 

    def measure(self, outfname):
        rate = 10000 # per channel
        points_per_channel = 20000 # per channel
        total_count = points_per_channel * 2

        # allocate memory buffer
        memhandle = ul.win_buf_alloc(total_count)
        data_array = ctypes.cast(memhandle, ctypes.POINTER(ctypes.c_ushort))

        # scan
        ul.a_in_scan(self.board_number, self.low_channel, self.high_channel,
                     total_count, rate, self.ai_range, memhandle, 0)

        # convert to numpy array
        np_data_array = np.ctypeslib.as_array(data_array, (total_count,))

        # convert from integer to volts
        voltage_array = np.zeros(len(np_data_array))
        for i in np.arange(len(np_data_array)):
            voltage_array[i] = ul.to_eng_units(self.board_number, self.ai_range, 
                                               np_data_array[i])

        np.save(outfname, voltage_array)

        # free memory
        ul.win_buf_free(memhandle)
        data_array = None



