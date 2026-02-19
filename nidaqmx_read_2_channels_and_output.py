import nidaqmx
from nidaqmx.system import System
from nidaqmx.stream_readers import AnalogMultiChannelReader
from nidaqmx.stream_writers import AnalogSingleChannelWriter

import numpy as np

system = System.local()

# autodetect device name assuming only 1 is connected
device_name = system.devices[0].name
print(device_name)

# configuration
sample_rate = 100 # Hz, use this for both analog in and out
# run for 30 s
run_time = 30
n_samples_channel = sample_rate * run_time
output = np.zeros(n_samples_channel)
output[100:200] = 5.
output[300:400] = 5.
output[600:800] = 5.
output[900:910] = 5.


with nidaqmx.Task() as read_task, nidaqmx.Task() as write_task:
    read_task.ai_channels.add_ai_voltage_chan(device_name + '/ai0',
                                              terminal_config = nidaqmx.constants.TerminalConfiguration.RSE)
    read_task.ai_channels.add_ai_voltage_chan(device_name + '/ai1',
                                              terminal_config = nidaqmx.constants.TerminalConfiguration.RSE)
    write_task.ao_channels.add_ao_voltage_chan(device_name + '/ao0')

    # Use analog out sample clock to control analog in
    read_task.timing.cfg_samp_clk_timing(sample_rate, #source = device_name + '/ao0',
                                         samps_per_chan = n_samples_channel)
    write_task.timing.cfg_samp_clk_timing(sample_rate, samps_per_chan = n_samples_channel)

    # set analog in to trigger the analog out
    #write_task.triggers.start_trigger.cfg_dig_edge_start_trig(trigger_source = device_name + '/ai0/StartTrigger')

    # create stream reader/writer object
    reader = AnalogMultiChannelReader(read_task.in_stream)
    writer = AnalogSingleChannelWriter(write_task.out_stream)

    input_data = np.zeros((2, n_samples_channel))
    # documentation says each row corresponds to a channel

    writer.write_many_sample(output)
    
    # start tasks
    write_task.start()
    read_task.start()
    reader.read_many_sample(input_data, timeout = 40)

    write_task.wait_until_done()
    read_task.wait_until_done()

    np.save('test_read.npy', input_data)


