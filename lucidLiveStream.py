from arena_api.system import system
from arena_api.buffer import *
import arena_api.enums as enums

import ctypes
import numpy as np
import cv2
import time
import matplotlib.pyplot as plt

"""
This function waits for the user to connect a device before raising
an exception
"""




def run(width = 4000, height = 3000, ox = 0, oy = 0,monitorx = 1920, monitory = 1000, fmt = 'BGR8',manualfps = False,fps = 20, gainAuto = 'Off', gain = 34, running = True): #choose Mono8, BayerRG8 or BGR8 for fmt, BGR8 ~30 FPS, BayerRG8 ~45 FPS, Mono8 ~90FPS
    tries = 0
    tries_max = 3
    sleep_time_secs = 10
    while tries < tries_max and running == True:  # Wait for device for 60 seconds
        devices = system.create_device()
        if not devices:
            print(
                f'Try {tries+1} of {tries_max}: waiting for {sleep_time_secs} '
                f'secs for a device to be connected!')
            for sec_count in range(sleep_time_secs):
                time.sleep(1)
                print(f'{sec_count + 1 } seconds passed ',
                    '.' * sec_count, end='\r')
            tries += 1
        else:
            print(f'Created {len(devices)} device(s)\n')
            device = devices[0]
            break

    else:
        print(f'No device found! Please connect a device and run '
                        f'the example again.')
        return
    nodemap = device.nodemap
    nodes = nodemap.get_node(['Width', 'Height', 'PixelFormat','OffsetX','OffsetY', 'AcquisitionFrameRateEnable', 'AcquisitionFrameRate','GainAuto', 'Gain'])

    pixelFormats =  {'Mono8':1, 'Mono10':1, 'Mono10p':1, 'Mono10Packed':1, 'Mono12':1, 'Mono12p':1,
    'Mono12Packed':1, 'Mono16':1, 'BayerRG8':2, 'BayerRG10':2, 'BayerRG10p':2, 'BayerRG10Packed':2,
    'BayerRG12':2, 'BayerRG12p':2, 'BayerRG12Packed':2, 'BayerRG16':2, 'RGB8':3, 'BGR8':3, 'YCbCr8':3,
    'YCbCr8_CbYCr':3, 'YUV422_8':3, 'YUV422_8_UYVY':3, 'YCbCr411_8':3, 'YUV411_8_UYYVYY':3}


    if ox > 4096 - width:
        print('OffsetX is too large for resolution used; it must be less than or equal to\n'
            '4096 (max. res.) - set resolution\n'
            'exiting')
        return

    if oy > 3000 - height:
        print('OffsetY is too large for resolution used; it must be less than or equal to\n'
                '3000 (max. res.) - set resolution\n'
                'exiting')
        return

    ox = ox - ox%nodes['OffsetX'].inc #uses increments of 8
    oy = oy - oy%nodes['OffsetY'].inc #uses increments of 2
    nodes['AcquisitionFrameRateEnable'].value = manualfps
    if nodes['AcquisitionFrameRateEnable'].value:
        nodes['AcquisitionFrameRate'].value = float(fps) #must be float


    nodes['OffsetY'].value = 0
    nodes['OffsetX'].value = 0
    nodes['Width'].value = width
    nodes['Height'].value = height
    print('max. OffsetX = {}'.format(nodes['OffsetX'].max))
    print('max. OffsetX = {}'.format(nodes['OffsetY'].max))
    nodes['OffsetX'].value = ox
    nodes['OffsetY'].value = oy
    nodes['GainAuto'].value = gainAuto
    if not gainAuto:
        nodes['Gain'] = float(gain)


    nodes['PixelFormat'].value = fmt


    num_channels = pixelFormats[nodes['PixelFormat'].value]


    aspect = nodes['Width'].value/nodes['Height'].value
    #monitorx = 300
    #monitory = int(monitorx/aspect)

    if monitorx/monitory < aspect:
        print('y-size doesn\'t fit aspect ratio, resizing')
        monitory = int(monitorx/aspect)
    elif monitorx/monitory > aspect:
        print('x-size doesn\'t fit aspect ratio, resizing' )
        monitorx = int(monitory*aspect)

    # Stream nodemap
    tl_stream_nodemap = device.tl_stream_nodemap

    tl_stream_nodemap["StreamBufferHandlingMode"].value = "NewestOnly"
    tl_stream_nodemap['StreamAutoNegotiatePacketSize'].value = True
    tl_stream_nodemap['StreamPacketResendEnable'].value = True

    curr_frame_time = 0
    prev_frame_time = 0

    buffertimes = np.array([])
    cycletimes = np.array([])
    textpos = (np.uint16(7*monitorx/1920), np.uint16(70*monitory/1080))
    textsize = 3*monitorx/1920
    cv2.namedWindow('lucid')
    cv2.moveWindow('lucid',50,50)
    cv2.namedWindow('lucid2')
    cv2.moveWindow('lucid2',-1500,50)
    with device.start_stream():
        """
        Infinitely fetch and display buffer data until esc is pressed
        """
        if fmt == 'BayerRG8':
            while running:
                # Used to display FPS on stream
                curr_frame_time = time.time()


                """
                Copy buffer and requeue to avoid running out of buffers
                """


                image_buffer = device.get_buffer() #capture image


                #converted_image = BufferFactory.convert(image_buffer, enums.PixelFormat.BGR8) #convert to BGR8 format
                converted_image = BufferFactory.copy(image_buffer)

                device.requeue_buffer(image_buffer)



                nparray = np.ctypeslib.as_array(converted_image.pdata,shape=(converted_image.height, converted_image.width)).reshape(converted_image.height, converted_image.width)
                newarray = cv2.cvtColor(nparray,cv2.COLOR_BayerRG2RGB)

                #buffertime = time.time() - curr_frame_time
                #buffertimes = np.append(buffertimes,buffertime)


                fps = str(1/(curr_frame_time - prev_frame_time))
                resize = cv2.resize(newarray,(monitorx,monitory))



                cv2.putText(resize, fps, textpos, cv2.FONT_HERSHEY_SIMPLEX, textsize, (100, 255, 0), 3, cv2.LINE_AA)

                cv2.imshow('lucid',resize)

                """
                Destroy the copied item to prevent memory leaks
                """
                BufferFactory.destroy(converted_image)

                cycletimes = np.append(cycletimes,curr_frame_time-prev_frame_time)
                prev_frame_time = curr_frame_time


                """
                Break if esc key is pressed
                """
                key = cv2.waitKey(1)
                if key == 27:
                    break
        else:
            while True:
                # Used to display FPS on stream
                curr_frame_time = time.time()

                buffer = device.get_buffer()


                """
                Copy buffer and requeue to avoid running out of buffers
                """
                item = BufferFactory.copy(buffer)
                device.requeue_buffer(buffer)



                #buffer_bytes_per_pixel = int(len(item.data)/(item.width * item.height))
                #print(len(item.data))
                #buffertime = time.time() - curr_frame_time
                #buffertimes = np.append(buffertimes,buffertime)

                """
                Buffer data as cpointers can be accessed using buffer.pbytes
                """
                array = (ctypes.c_ubyte * num_channels * item.width * item.height).from_address(ctypes.addressof(item.pbytes))


                """
                Create a reshaped NumPy array to display using OpenCV
                """
                npndarray = np.ndarray(buffer=array, dtype=np.uint8, shape=(item.height, item.width, num_channels)) # buffer_bytes_per_pixel))


                fps = str(1/(curr_frame_time - prev_frame_time))
                resize = cv2.resize(npndarray,(monitorx,monitory))
                resize2 = cv2.resize(npndarray,(1200,900))
                cv2.putText(resize, fps,textpos, cv2.FONT_HERSHEY_SIMPLEX, textsize, (100, 255, 0), 3, cv2.LINE_AA)

                cv2.imshow('lucid',resize)
                cv2.imshow('lucid2',resize2)
                """
                Destroy the copied item to prevent memory leaks
                """
                BufferFactory.destroy(item)
                cycletimes = np.append(cycletimes,curr_frame_time-prev_frame_time)
                prev_frame_time = curr_frame_time


                """
                Break if esc key is pressed
                """

                key = cv2.waitKey(1)
                if key == 27:
                    break

        device.stop_stream()
        cv2.destroyAllWindows()

    system.destroy_device()
    #print(1/np.average(buffertimes))
    cycletimes = cycletimes[1:]
    print(f'fps = {1/np.average(cycletimes)}, standard deviation = {np.std(1/cycletimes)}')
    plt.plot(1/cycletimes)
    plt.ylabel('fps')
    plt.xlabel('frame')
    plt.show()
if __name__ == '__main__':
    run(monitory = 950)
