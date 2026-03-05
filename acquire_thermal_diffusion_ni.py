'''
acquire_thermal_diffusion_ni.py

Acquire and save data from IC Thermal Diffusion experiment using National Instruments USB-6215 interface.

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
    python acquire_thermal_diffusion_ni.py pulse_length lag_time duration fname_base

Command line parameters:

    pulse_length (float): Duration of heat pulse in seconds
    lag_time (float): Amount of time to wait in seconds before heater turns on
    duration (float): 
        Amount of time in seconds to measure after heater turns on.
        Total length of measurement in seconds is lag_time + duration.
    fname_base (str): Base for output file name (no extensions needed)

Output file:

    .npy or .txt file containing an array with 7 columns. Column 0 is time, column 1 is analog input CH0,
    column 2 is analog input CH1, etc. 

Author: Jerome Fung (jfung@ithaca.edu)
'''

import nidaqmx

from nidaqmx.system import System
from nidaqmx.stream_readers import AnalogMultiChannelReader
from nidaqmx.stream_writers import AnalogSingleChannelWriter

import numpy as np

'''
Strategy for simultaneous analog input and output relies on using the analog output sample clock to
control the timing of analog reads.

Note that the NI USB-6215 is also a multiplexed device. (See its manual.)
'''

class NIDAQInterface:

    def __init__(self):
        self.system = System.local()

        # autodetect device name assuming only 1 is connected
        self.device_name = self.system.devices[0].name
    
        # measurement setup
        self.n_in_channels = 7
        self.sample_rate = 100. # in Hertz
        self.extra_read_time = 5. # seconds, to extend timeout


    def _create_ao_array(self, pts_per_channel, pulse_length, lag_time):
        output = np.zeros(pts_per_channel)
        start_idx = np.floor(lag_time * self.sample_rate).astype('int')
        stop_idx = start_idx + np.floor(pulse_length * self.sample_rate).astype('int')
        output[start_idx:stop_idx] = 5. # volts
        return output


    def measure(self, pulse_length, lag_time, duration, outfname):
        total_meas_time_sec = lag_time + duration
        pts_per_channel = np.floor(total_meas_time_sec * self.sample_rate).astype('int')
        
        with nidaqmx.Task() as read_task, nidaqmx.Task() as write_task:
            # set up analog input channels as single-ended
            for ch in range(self.n_in_channels):
                read_task.ai_channels.add_ai_voltage_chan(self.device_name + '/ai' + str(ch),
                                                          terminal_config = nidaqmx.constants.TerminalConfiguration.RSE)
            
            # control analog input timing with analog out sample clock
            read_task.timing.cfg_samp_clk_timing(self.sample_rate, samps_per_chan = pts_per_channel,
                                                 source = '/' + self.device_name + '/ao/SampleClock')

            # set up analog output channel
            write_task.ao_channels.add_ao_voltage_chan(self.device_name + '/ao0')
            write_task.timing.cfg_samp_clk_timing(self.sample_rate, samps_per_chan = pts_per_channel)

            # create stream reader/writer objects that can directly access preallocated numpy arrays
            reader = AnalogMultiChannelReader(read_task.in_stream)
            writer = AnalogSingleChannelWriter(write_task.out_stream)

            # preallocate array for analog input data
            # nidaqmx interface expects each row to correspond to a channel
            # add an extra row for time
            input_data = np.zeros((self.n_in_channels + 1, pts_per_channel))
            input_data[0, :] = np.arange(pts_per_channel) / self.sample_rate

            # prepare write, but doesn't actually start until task is started
            writer.write_many_sample(self._create_ao_array(pts_per_channel, pulse_length, lag_time))

            # start tasks
            read_task.start() # waits for AO sample clock
            write_task.start()

            # read data
            reader.read_many_sample(input_data[1:, :], timeout = total_meas_time_sec + self.extra_read_time)

            write_task.wait_until_done()
            read_task.wait_until_done()

            # save
            np.save(outfname + '.npy', input_data.transpose())
            np.savetxt(outfname + '.txt', input_data.transpose())


if __name__ == "__main__":
    interface = NIDAQInterface()
    interface.measure(float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), sys.argv[4])

