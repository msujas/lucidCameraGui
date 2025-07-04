from PyQt6 import QtCore
import time
import numpy as np
import cv2
from arena_api.system import system
from arena_api.buffer import *
import ctypes
from datetime import datetime

def shrinkImageSave(filename, array, factor):
	leny = array.shape[0]
	lenx = array.shape[1]
	newy = int(leny/(factor**0.5))
	newx = int(lenx/(factor**0.5))
	resize = cv2.resize(array,(newx,newy))
	cv2.imwrite(filename, resize)

class Worker(QtCore.QObject):
	output = QtCore.pyqtSignal(tuple)
	imagesizeoutput = QtCore.pyqtSignal(tuple)
	imageoutput = QtCore.pyqtSignal(np.ndarray)
	nodevice = QtCore.pyqtSignal()
	def __init__(self,width: int, height: int, ox: int, oy: int,monitorx: int, monitory: int,manualfps: bool,fps: int, gainAuto: str, 
	gain: float, fmt: str, screenwidth: int, screenheight: int, crosssize: int, crossOffsetH: int, crossOffsetW: int, crossCheck: bool, linePosition: int, 
	imageTime: int, imageDir: str, totalImageTime : int,  lineCheck: bool = True, imageSaveFactor = 1):
		super(Worker,self).__init__()
		self.width = width
		self.height = height
		self.ox = ox
		self.oy = oy
		self.monitorx = monitorx
		self.monitory = monitory
		self.fmt = fmt
		self.manualfps = manualfps
		self.fps = fps
		self.gainAuto = gainAuto
		self.gain = gain
		self.screenwidth = screenwidth
		self.screenheight = screenheight
		self.crosssize = crosssize
		self.crossOffsetH = crossOffsetH
		self.crossOffsetW = crossOffsetW
		self.crossCheck = crossCheck
		self.running = True
		self.snapshot = False
		self.imageTime = imageTime
		self.imageSeries = False
		self.imageDir = imageDir
		self.linePosition = linePosition
		self.lineCheck = lineCheck
		self.saveImageFactor = imageSaveFactor
		self.totalImageTime = totalImageTime

	def run(self):
		tries = 0
		tries_max = 2
		sleep_time_secs = 5
		while tries < tries_max and self.running == True:  # Wait for device for 60 seconds
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
			print(f'No device found! Please connect a device and run again')
			self.nodevice.emit()
			return
		nodemap = device.nodemap
		nodes = nodemap.get_node(['Width', 'Height', 'PixelFormat','OffsetX','OffsetY', 'AcquisitionFrameRateEnable', 'AcquisitionFrameRate','GainAuto', 'Gain'])

		pixelFormats =	{'Mono8':1, 'Mono10':1, 'Mono10p':1, 'Mono10Packed':1, 'Mono12':1, 'Mono12p':1,
		'Mono12Packed':1, 'Mono16':1, 'BayerRG8':1, 'BayerRG10':1, 'BayerRG10p':1, 'BayerRG10Packed':1,
		'BayerRG12':1, 'BayerRG12p':1, 'BayerRG12Packed':1, 'BayerRG16':1, 'RGB8':3, 'BGR8':3, 'YCbCr8':3,
		'YCbCr8_CbYCr':3, 'YUV422_8':3, 'YUV422_8_UYVY':3, 'YCbCr411_8':3, 'YUV411_8_UYYVYY':3}


		if self.ox > 4096 - self.width:
			print('OffsetX is too large for resolution used; it must be less than or equal to\n'
				'4096 (max. res.) - set resolution\n'
				'exiting')
			return

		if self.oy > 3000 - self.height:
			print('OffsetY is too large for resolution used; it must be less than or equal to\n'
					'3000 (max. res.) - set resolution\n'
					'exiting')
			return

		self.ox = self.ox - self.ox%nodes['OffsetX'].inc #uses increments of 8
		self.oy = self.oy - self.oy%nodes['OffsetY'].inc #uses increments of 2
		nodes['AcquisitionFrameRateEnable'].value = self.manualfps
		if nodes['AcquisitionFrameRateEnable'].value:
			nodes['AcquisitionFrameRate'].value = float(self.fps) #must be float


		nodes['OffsetY'].value = 0
		nodes['OffsetX'].value = 0
		nodes['Width'].value = self.width
		nodes['Height'].value = self.height
		print('max. OffsetX = {}'.format(nodes['OffsetX'].max))
		print('max. OffsetX = {}'.format(nodes['OffsetY'].max))
		nodes['OffsetX'].value = self.ox
		nodes['OffsetY'].value = self.oy
		nodes['GainAuto'].value = self.gainAuto
		if nodes['GainAuto'].value == 'Off':
			nodes['Gain'].value = self.gain


		nodes['PixelFormat'].value = self.fmt


		num_channels = pixelFormats[nodes['PixelFormat'].value]


		aspect = nodes['Width'].value/nodes['Height'].value

		crossThickness = 4
		lineSize = 300
		lineThickness = 3


		if self.monitorx/self.monitory < aspect: #adjusting the monitor x or y values based on the aspect ratio
			print('y-size doesn\'t fit aspect ratio, resizing')
			self.monitory = int(self.monitorx/aspect)
		elif self.monitorx/self.monitory > aspect:
			print('x-size doesn\'t fit aspect ratio, resizing' )
			self.monitorx = int(self.monitory*aspect)
		self.imagesizeoutput.emit((self.monitorx, self.monitory))
		# Stream nodemap
		tl_stream_nodemap = device.tl_stream_nodemap

		tl_stream_nodemap["StreamBufferHandlingMode"].value = "NewestOnly"
		tl_stream_nodemap['StreamAutoNegotiatePacketSize'].value = True
		tl_stream_nodemap['StreamPacketResendEnable'].value = True

		curr_frame_time = 0
		prev_frame_time = 0

		buffertimes = np.array([])
		cycletimes = np.array([])
		textpos = (np.uint16(7*self.monitorx/1920), np.uint16(70*self.monitory/1080))
		textsize = 3*self.monitorx/1920
		print(f'monitorx {self.monitorx}, monitory {self.monitory}')
		windowName = 'Lucid (press stop to close)'
		#cv2.namedWindow(windowName)
		#cv2.moveWindow(windowName,self.screenwidth-self.monitorx - 20,self.screenheight - self.monitory-100)
		if num_channels == 3:
			crossElement = np.array([0,0,255], dtype = np.uint8)
		elif num_channels == 1:
			crossElement = np.array([255],dtype = np.uint8)
		self.gaincheck = False
		self.imageCountDown = 0
		with device.start_stream():
			"""
			Infinitely fetch and display buffer data until esc is pressed
			"""
			frameCount = 0
			fpsCheckCount = 0
			t0 = time.time()
			totalFPS = 0
			fpsCheckFreq = 10
			while self.running:
				# Used to display FPS on stream
				curr_frame_time = time.time()
				if self.gaincheck:
					nodes['Gain'].value = self.gain
					self.gaincheck = False
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
				#npndarray = np.where(cross == True, crossElement, npndarray)
				if self.crossCheck:
					npndarray[self.crossOffsetH + int(self.height/2-(crossThickness-1)/2+1): self.crossOffsetH + int(self.height/2+(crossThickness-1)/2),
					self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+ int(self.width/2+self.crosssize/2)] = crossElement #middle horizontal

					npndarray[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2+self.crosssize/2),
					self.crossOffsetW+ int(self.width/2 - crossThickness/2 +1): self.crossOffsetW+int(self.width/2 + crossThickness/2)] = crossElement #middle vertical

					npndarray[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2+self.crosssize/2),
					self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+int(self.width/2-self.crosssize/2 + 1 + crossThickness)] = crossElement #left vertical

					npndarray[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2+self.crosssize/2),
					self.crossOffsetW+ int(self.width/2+self.crosssize/2-crossThickness):  self.crossOffsetW+int(self.width/2+self.crosssize/2)] = crossElement #right vertical

					npndarray[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2-self.crosssize/2 + crossThickness+1),
					self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+int(self.width/2+self.crosssize/2)] = crossElement #lower horizontal

					npndarray[self.crossOffsetH + int(self.height/2+self.crosssize/2-crossThickness):  self.crossOffsetH + int(self.height/2+self.crosssize/2),
					self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+int(self.width/2+self.crosssize/2)] = crossElement #upper horizontal
				if self.lineCheck:
					npndarray[self.linePosition:self.linePosition+lineThickness,self.crossOffsetW+ int(self.width/2-lineSize/2 + 1):self.crossOffsetW+ int(self.width/2+lineSize/2)] = crossElement
				#fps = str(1/(curr_frame_time - prev_frame_time))
				resize = cv2.resize(npndarray,(self.monitorx,self.monitory))

				#cv2.putText(resize, fps,textpos, cv2.FONT_HERSHEY_SIMPLEX, textsize, (100, 255, 0), 3, cv2.LINE_AA)
				if self.snapshot:
					self.saveImage(resize)
					self.snapshot = False
				if self.imageSeries and self.totalImageTime > 0:
					currentTime = time.time()
					if currentTime - self.imageCountDown >= self.imageTime:
						self.saveImage(resize)
						self.totalImageTime -= self.imageTime/60
						if self.totalImageTime <= 0:
							self.totalImageTime = 0
							self.imageSeries = False
						self.output.emit((int(self.totalImageTime), self.imageSeries))
						self.imageCountDown = time.time()
					

						
				self.imageoutput.emit(resize)
				#cv2.imshow(windowName,resize)

				"""
				Destroy the copied item to prevent memory leaks
				"""
				BufferFactory.destroy(item)
				#cycletimes = np.append(cycletimes,curr_frame_time-prev_frame_time)
				if frameCount >= fpsCheckFreq:
					timeCheck = time.time() - t0
					fps = fpsCheckFreq/timeCheck
					if fpsCheckCount == 0:
						totalFPS = fps
					else:
						totalFPS = (fps*fpsCheckCount+fps)/(fpsCheckCount+1)
					frameCount = 0
					t0 = time.time()
					fpsCheckCount += 1
				prev_frame_time = curr_frame_time
				frameCount += 1

				"""
				Break if esc key is pressed
				"""


			device.stop_stream()
			#cv2.destroyAllWindows()

		system.destroy_device()
		#print(1/np.average(buffertimes))
		#cycletimes = cycletimes[1:]
		#print(f'fps = {1/np.average(cycletimes)}, standard deviation = {np.std(1/cycletimes)}')
		print(f'fps = {totalFPS}')
		return

	def stop(self):
		self.running = False
		print('stopping process')
		#self.terminate()

	def saveImage(self, array):
		dt = datetime.fromtimestamp(time.time())
		filename = f'{self.imageDir}/{dt.year}_{dt.month:02d}_{dt.day:02d}_{dt.hour:02d}{dt.minute:02d}{dt.second:02d}.png'
		if self.saveImageFactor > 1:
			shrinkImageSave(filename, array,self.saveImageFactor)
		else:
			cv2.imwrite(filename, array)