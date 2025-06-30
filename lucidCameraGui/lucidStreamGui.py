# Created by: PyQt5 UI code generator 5.9.2


from PyQt6 import QtCore, QtGui, QtWidgets

from arena_api.system import system
from arena_api.buffer import *
import arena_api.enums as enums
from arena_api.__future__.save import Recorder

import ctypes
import numpy as np
import cv2
import time
from datetime import datetime
from pathlib import Path
import os, sys


def stringToBool(string):
	if string == 'True':
		return True
	else:
		return False
	
def shrinkImageSave(filename, array, factor):
	leny = array.shape[0]
	lenx = array.shape[1]
	newy = int(leny/(factor**0.5))
	newx = int(lenx/(factor**0.5))
	resize = cv2.resize(array,(newx,newy))
	cv2.imwrite(filename, resize)




class parAttributes():
	def __init__(self, param):
		self.param = param
	def name(self):
		return self.objectName()
	def parValue(self):
		if type(self.param) == QtWidgets.QSpinBox or type(self.param) == QtWidgets.QDoubleSpinBox:
			return self.param.value()
		elif type(self.param) == QtWidgets.QComboBox:
			return self.param.currentText()
		elif type(self.param) == QtWidgets.QLineEdit:
			return self.param.text()

		

class Worker(QtCore.QThread):
	output = QtCore.pyqtSignal(tuple)
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
		cv2.namedWindow(windowName)
		cv2.moveWindow(windowName,self.screenwidth-self.monitorx - 20,self.screenheight - self.monitory-100)
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
						self.totalImageTime -= (currentTime - self.imageCountDown)/60
						if self.totalImageTime <= 0:
							self.totalImageTime = 0
							self.imageSeries = False
						self.output.emit((int(self.totalImageTime), self.imageSeries))
						self.imageCountDown = time.time()
					

						
					
				cv2.imshow(windowName,resize)

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

				key = cv2.waitKey(1)
				if key == 27:
					break

			device.stop_stream()
			cv2.destroyAllWindows()

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



class Ui_MainWindow(object):
	def setupUi(self, MainWindow):
		MainWindow.setObjectName("Lucid GUI")

		self.screen = QtWidgets.QApplication.primaryScreen().size()
		self.screenwidth = self.screen.width()
		self.screenheight = self.screen.height()

		self.gridLayout = QtWidgets.QGridLayout()


		if self.screenheight > 2000:
			monydefault = 2000
		elif self.screenheight > 1400:
			monydefault = 1300
		else:
			monydefault = 900
		scaling = (self.screenwidth/1920)**0.5 #scaling box and font sizes for different screen resolutions
		windowsize = [int(280*scaling),int(700*scaling)]
		MainWindow.resize(*windowsize)
		MainWindow.move(0,self.screenheight - windowsize[1] - 75)
		box1pos = [int(20*scaling), int(35*scaling)]
		boxDimensions = [int(80*scaling),int(22*scaling)]
		boxOffset = boxDimensions[1] + int(18*scaling)
		labelxpos = 20 + boxDimensions[0] + 10
		box2x = int(20 + boxDimensions[0] + 10*scaling)
		box1x = 20
		homepath = str(Path.home())
		endpath = 'Documents/lucidSnapShots'
		self.snapshotDir = f'{homepath}/{endpath}/'
		if not os.path.exists(self.snapshotDir):
			os.makedirs(self.snapshotDir)
		
		basefont = int(12*scaling)

		self.centralwidget = QtWidgets.QWidget(MainWindow)
		self.centralwidget.setObjectName("centralwidget")


		font = QtGui.QFont()
		font.setPointSize(basefont)
		boxfont = QtGui.QFont()
		boxfont.setPointSize(basefont-4)
		labelfont = QtGui.QFont()
		labelfont.setPointSize(basefont-4)
		smallLabelfont = QtGui.QFont()
		smallLabelfont.setPointSize(basefont-5)


		self.xResBox = QtWidgets.QSpinBox() #select x resolution of camera
		self.xResBox.setGeometry(QtCore.QRect(box1x, box1pos[1],*boxDimensions))
		self.xResBox.setMinimum(50)
		self.xResBox.setMaximum(4096)
		self.xResBox.setProperty("value", 4000)
		self.xResBox.setObjectName("xResBox")
		self.xResBox.setFont(boxfont)
		self.gridLayout.addWidget(self.xResBox, 1, 0)

		self.xResLabel = QtWidgets.QLabel()
		self.xResLabel.setGeometry(QtCore.QRect(box1x, int(box1pos[1] - 0.35*boxOffset), 61, 16))
		self.xResLabel.setObjectName("xResLabel")
		self.xResLabel.setFont(labelfont)
		self.gridLayout.addWidget(self.xResLabel, 0, 0)

		self.yResBox = QtWidgets.QSpinBox() #select y resolution of camera
		self.yResBox.setGeometry(QtCore.QRect(box2x, box1pos[1],*boxDimensions))
		self.yResBox.setMinimum(50)
		self.yResBox.setMaximum(3000)
		self.yResBox.setProperty("value", 3000)
		self.yResBox.setObjectName("yResBox")
		self.yResBox.setFont(boxfont)
		self.gridLayout.addWidget(self.yResBox, 1, 1)

		self.yResLabel = QtWidgets.QLabel()
		self.yResLabel.setGeometry(QtCore.QRect(box2x, int(box1pos[1] - 0.35*boxOffset), 71, 16))
		self.yResLabel.setObjectName("yResLabel")
		self.yResLabel.setFont(labelfont)
		self.gridLayout.addWidget(self.yResLabel, 0,1)

		self.xOffsetBox = QtWidgets.QSpinBox() #select x pixel offset of camera (if not using max. resoution)
		self.xOffsetBox.setGeometry(QtCore.QRect(box1x, boxOffset + box1pos[1],*boxDimensions))
		self.xOffsetBox.setMaximum(4046)
		self.xOffsetBox.setObjectName("xOffsetBox")
		self.xOffsetBox.setFont(boxfont)
		self.gridLayout.addWidget(self.xOffsetBox, 3,0)

		self.xOffsetLabel = QtWidgets.QLabel()
		self.xOffsetLabel.setGeometry(QtCore.QRect(box1x, int(0.65*boxOffset + box1pos[1]), 47, 13))
		self.xOffsetLabel.setObjectName("xOffsetLabel")
		self.xOffsetLabel.setFont(labelfont)
		self.gridLayout.addWidget(self.xOffsetLabel, 2,0)

		self.yOffsetBox = QtWidgets.QSpinBox() #select y pixel offset of camera
		self.yOffsetBox.setGeometry(QtCore.QRect(box2x, boxOffset + box1pos[1],*boxDimensions))
		self.yOffsetBox.setMaximum(2950)
		self.yOffsetBox.setObjectName("yOffsetBox")
		self.yOffsetBox.setFont(boxfont)
		self.gridLayout.addWidget(self.yOffsetBox, 3,1)

		self.yOffsetLabel = QtWidgets.QLabel()
		self.yOffsetLabel.setGeometry(QtCore.QRect(box2x, int(0.65*boxOffset + box1pos[1]), 47, 20))
		self.yOffsetLabel.setObjectName("yOffsetLabel")
		self.yOffsetLabel.setFont(labelfont)
		self.gridLayout.addWidget(self.yOffsetLabel, 2,1)

		self.monitorxBox = QtWidgets.QSpinBox() #select x size of image on screen (in pixels)
		#self.monitorxBox.setGeometry(QtCore.QRect(box1x, 2*boxOffset + box1pos[1],*boxDimensions))
		self.monitorxBox.setMinimum(100)
		self.monitorxBox.setMaximum(3840)
		#self.monitorxBox.setStepType(QtWidgets.QAbstractSpinBox.DefaultStepType)
		self.monitorxBox.setProperty("value", 3000)
		self.monitorxBox.setObjectName("monitorxBox")
		self.monitorxBox.setFont(boxfont)
		self.gridLayout.addWidget(self.monitorxBox, 5,0)

		self.monitorxLabel = QtWidgets.QLabel()
		#self.monitorxLabel.setGeometry(QtCore.QRect(10, int(1.65*boxOffset + box1pos[1]), 111, 16))
		self.monitorxLabel.setObjectName("monitorxLabel")
		self.monitorxLabel.setFont(labelfont)
		self.gridLayout.addWidget(self.monitorxLabel, 4,0)

		self.monitoryBox = QtWidgets.QSpinBox() #select y size of image on screen (in pixels)
		#self.monitoryBox.setGeometry(QtCore.QRect(int(box2x+20*scaling), 2*boxOffset + box1pos[1],*boxDimensions))
		self.monitoryBox.setMinimum(100)
		self.monitoryBox.setMaximum(3000)
		self.monitoryBox.setSingleStep(1)
		#self.monitoryBox.setStepType(QtWidgets.QAbstractSpinBox.DefaultStepType)
		self.monitoryBox.setProperty("value", monydefault)
		self.monitoryBox.setObjectName("monitoryBox")
		self.monitoryBox.setFont(boxfont)
		self.gridLayout.addWidget(self.monitoryBox, 5,1)

		self.monitoryLabel = QtWidgets.QLabel()
		#self.monitoryLabel.setGeometry(QtCore.QRect(int(box2x+20*scaling), int(1.65*boxOffset + box1pos[1]), 111, 16))
		self.monitoryLabel.setObjectName("monitoryLabel")
		self.monitoryLabel.setFont(labelfont)
		self.gridLayout.addWidget(self.monitoryLabel, 4,1)

		self.aspectInfoLabel = QtWidgets.QLabel()
		#self.aspectInfoLabel.setGeometry(QtCore.QRect(box1x, int(2.7*boxOffset + box1pos[1]), 201, 41))
		self.aspectInfoLabel.setFont(smallLabelfont)
		self.aspectInfoLabel.setObjectName("aspectInfoLabel")
		self.gridLayout.addWidget(self.aspectInfoLabel, 6,0)

		self.colourBox = QtWidgets.QComboBox() #select colour format
		#self.colourBox.setGeometry(QtCore.QRect(box1x, int(3.5*boxOffset + box1pos[1]),*boxDimensions))
		self.colourBox.setObjectName("colourBox")
		self.colourBox.setFont(boxfont)
		self.gridLayout.addWidget(self.colourBox, 7,0)

		self.colourBoxLabel = QtWidgets.QLabel()
		self.colourBoxLabel.setFont(labelfont)
		self.colourBoxLabel.setObjectName("colourBoxLabel")
		#self.colourBoxLabel.setGeometry(QtCore.QRect(labelxpos, int(3.5*boxOffset + box1pos[1]), 91, 16))
		self.gridLayout.addWidget(self.colourBoxLabel, 7,1)

		self.manualFPSBox = QtWidgets.QComboBox() #whether to set FPS manually or automatically
		#self.manualFPSBox.setGeometry(QtCore.QRect(box1x, 5*boxOffset + box1pos[1],*boxDimensions))
		self.manualFPSBox.setObjectName("manualFPSBox")
		self.manualFPSBox.setFont(boxfont)
		self.gridLayout.addWidget(self.manualFPSBox, 9,0)

		self.manualFPSLabel = QtWidgets.QLabel()
		#self.manualFPSLabel.setGeometry(QtCore.QRect(box1x, int(4.5*boxOffset + box1pos[1]), 71, 16))
		self.manualFPSLabel.setFont(labelfont)
		self.manualFPSLabel.setObjectName("manualFPSLabel")
		self.gridLayout.addWidget(self.manualFPSLabel, 8,0)

		self.FPSBox = QtWidgets.QSpinBox() #select FPS (if manual selected)
		self.FPSBox.setGeometry(QtCore.QRect(box2x, 5*boxOffset + box1pos[1],*boxDimensions))
		self.FPSBox.setObjectName("FPSBox")
		self.FPSBox.setFont(boxfont)
		self.gridLayout.addWidget(self.FPSBox, 9,1)

		self.FPSLabel = QtWidgets.QLabel()
		self.FPSLabel.setGeometry(QtCore.QRect(box2x, int(4.5*boxOffset + box1pos[1]), 71, 16))
		self.FPSLabel.setFont(labelfont)
		self.FPSLabel.setObjectName("FPSLabel")
		self.gridLayout.addWidget(self.FPSLabel, 8,1)

		self.gainAutoBox = QtWidgets.QComboBox() #choose whether to have gain chosen automatically or manually
		#self.gainAutoBox.setGeometry(QtCore.QRect(box1x, 6*boxOffset + box1pos[1], boxDimensions[0] + int(10*scaling), boxDimensions[1]))
		self.gainAutoBox.setObjectName("gainAutoBox")
		self.gainAutoBox.setFont(boxfont)
		self.gridLayout.addWidget(self.gainAutoBox, 10,0)

		self.gainAutoLabel = QtWidgets.QLabel()
		#self.gainAutoLabel.setGeometry(QtCore.QRect(int(labelxpos+10*scaling), 6*boxOffset + box1pos[1], 61, 16))
		self.gainAutoLabel.setObjectName("gainAutoLabel")
		self.gainAutoLabel.setFont(labelfont)
		self.gridLayout.addWidget(self.gainAutoLabel, 10,1)

		self.gainBox = QtWidgets.QDoubleSpinBox() #select gain (if gainAuto is off)
		#self.gainBox.setGeometry(QtCore.QRect(box1x, 7*boxOffset + box1pos[1],*boxDimensions))
		self.gainBox.setDecimals(1)
		self.gainBox.setMaximum(48.0)
		self.gainBox.setObjectName("gainBox")
		self.gainBox.setFont(boxfont)
		self.gridLayout.addWidget(self.gainBox, 11,0)

		self.gainLabel = QtWidgets.QLabel()
		#self.gainLabel.setGeometry(QtCore.QRect(labelxpos, 7*boxOffset + box1pos[1], 81, 31))
		self.gainLabel.setObjectName("gainLabel")
		self.gainLabel.setFont(labelfont)
		self.gridLayout.addWidget(self.gainLabel, 11,1)

		self.crossSizeBox =	 QtWidgets.QSpinBox() #select the size of the cross that is overlayed on the image
		#self.crossSizeBox.setGeometry(QtCore.QRect(box1x, 8*boxOffset + box1pos[1],*boxDimensions))
		self.crossSizeBox.setObjectName("crossSizeBox")
		self.crossSizeBox.setFont(boxfont)
		self.crossSizeBox.setMinimum(100)
		self.crossSizeBox.setMaximum(2500)
		self.crossSizeBox.setValue(700)
		self.crossSizeBox.setSingleStep(10)
		self.gridLayout.addWidget(self.crossSizeBox, 13,0)

		self.crossSizeLabel = QtWidgets.QLabel()
		#self.crossSizeLabel.setGeometry(QtCore.QRect(box1x, int(7.65*boxOffset + box1pos[1]), 81, 31))
		self.crossSizeLabel.setObjectName("crossSizeLabel")
		self.crossSizeLabel.setText('cross size')
		self.crossSizeLabel.setFont(labelfont)
		self.crossSizeLabel.adjustSize()
		self.gridLayout.addWidget(self.crossSizeLabel, 12,0)

		self.crossCheckBox =  QtWidgets.QCheckBox() #select whether or not to display the cross
		#self.crossCheckBox.setGeometry(QtCore.QRect(labelxpos, 8*boxOffset + box1pos[1],int(10*scaling),int(10*scaling)))
		self.crossCheckBox.setObjectName('crossCheckBox')
		self.crossCheckBox.setText('display cross?')
		self.crossCheckBox.setFont(labelfont)
		self.crossCheckBox.setChecked(True)
		self.crossCheckBox.adjustSize()
		self.gridLayout.addWidget(self.crossCheckBox, 13,1)

		self.crossOffsetHBox =	QtWidgets.QSpinBox() #choose center position of cross in y
		#self.crossOffsetHBox.setGeometry(QtCore.QRect(box1x, 9*boxOffset + box1pos[1],*boxDimensions))
		self.crossOffsetHBox.setObjectName("crossOffsetHBox")
		self.crossOffsetHBox.setFont(boxfont)
		self.crossOffsetHBox.setMinimum(-1500)
		self.crossOffsetHBox.setMaximum(1500)
		self.crossOffsetHBox.setValue(0)
		self.gridLayout.addWidget(self.crossOffsetHBox, 15,0)

		self.crossHLabel = QtWidgets.QLabel()
		#self.crossHLabel.setGeometry(QtCore.QRect(box1x, int(8.6*boxOffset + box1pos[1]), 81, 31))
		self.crossHLabel.setObjectName("crossHLabel")
		self.crossHLabel.setText('cross y offset')
		self.crossHLabel.setFont(labelfont)
		self.crossHLabel.adjustSize()
		self.gridLayout.addWidget(self.crossHLabel, 14,0)

		self.crossOffsetWBox =	QtWidgets.QSpinBox() #choose center position of cross in x
		#self.crossOffsetWBox.setGeometry(QtCore.QRect(30 + boxDimensions[0], 9*boxOffset + box1pos[1],*boxDimensions))
		self.crossOffsetWBox.setObjectName("crossOffsetWBox")
		self.crossOffsetWBox.setFont(boxfont)
		self.crossOffsetWBox.setMinimum(-1500)
		self.crossOffsetWBox.setMaximum(1500)
		self.crossOffsetWBox.setValue(0)
		self.gridLayout.addWidget(self.crossOffsetWBox, 15,1)

		self.crossWLabel = QtWidgets.QLabel()
		#self.crossWLabel.setGeometry(QtCore.QRect(30 + boxDimensions[0], int(8.6*boxOffset + box1pos[1]), 81, 31))
		self.crossWLabel.setObjectName("crossWLabel")
		self.crossWLabel.setText('cross x offset')
		self.crossWLabel.setFont(labelfont)
		self.crossWLabel.adjustSize()
		self.gridLayout.addWidget(self.crossWLabel, 14,1)

		self.lockCrossPositionBox =  QtWidgets.QCheckBox() #select whether or not to display the cross
		#self.lockCrossPositionBox.setGeometry(QtCore.QRect(2*boxDimensions[0] + 40, int(8.9*boxOffset + box1pos[1]),int(10*scaling),int(10*scaling)))
		self.lockCrossPositionBox.setObjectName('lockCrossPositionBox')
		self.lockCrossPositionBox.setText('lock cross\nposition')
		self.lockCrossPositionBox.setFont(labelfont)
		self.lockCrossPositionBox.setChecked(True)
		self.lockCrossPositionBox.adjustSize()
		self.gridLayout.addWidget(self.lockCrossPositionBox, 15,2)

		if self.lockCrossPositionBox.isChecked():
			self.crossOffsetWBox.setEnabled(False)
			self.crossOffsetHBox.setEnabled(False)

		self.runButton = QtWidgets.QPushButton()
		#self.runButton.setGeometry(QtCore.QRect(box1x, 10*boxOffset + box1pos[1], int(130*scaling), int(40*scaling)))
		self.runButton.setFont(font)
		self.runButton.setObjectName("runButton")
		self.runButton.setMinimumHeight(int(50*scaling))
		self.gridLayout.addWidget(self.runButton, 16,0, 1,2)

		self.stopButton = QtWidgets.QPushButton()
		#self.stopButton.setGeometry(QtCore.QRect(box1x + int(130*scaling) + 10, 10*boxOffset + box1pos[1], 75, 23))
		self.stopButton.setObjectName("stopButton")
		self.stopButton.setFont(font)
		self.stopButton.adjustSize()
		self.stopButton.setEnabled(False)
		self.gridLayout.addWidget(self.stopButton, 16,2)

		self.snapShotButton = QtWidgets.QPushButton()
		self.snapShotButton.setGeometry(QtCore.QRect(box1x, int(11.2*boxOffset + box1pos[1]), int(130*scaling), int(40*scaling)))
		self.snapShotButton.setFont(labelfont)
		self.snapShotButton.setObjectName("snapShotButton")
		self.snapShotButton.setText('take single image')
		self.snapShotButton.adjustSize()
		self.snapShotButton.setEnabled(False)
		self.gridLayout.addWidget(self.snapShotButton, 17,0)

		self.imageSeriesButton = QtWidgets.QPushButton()
		self.imageSeriesButton.setGeometry(QtCore.QRect(box1x, int(12*boxOffset + box1pos[1]), int(130*scaling), int(40*scaling)))
		self.imageSeriesButton.setFont(labelfont)
		self.imageSeriesButton.setObjectName("imageSeriesButton")
		self.imageSeriesButton.setText('take image series')
		self.imageSeriesButton.adjustSize()
		self.imageSeriesButton.setEnabled(False)
		self.gridLayout.addWidget(self.imageSeriesButton, 18,0)

		self.imageSeriesTime = QtWidgets.QSpinBox()
		self.imageSeriesTime.setGeometry(QtCore.QRect(int(box2x + 10*scaling), int(12*boxOffset + box1pos[1]), int(50*scaling), boxDimensions[1]))
		self.imageSeriesTime.setFont(labelfont)
		self.imageSeriesTime.setObjectName("imageSeriesTime")
		self.imageSeriesTime.setMinimum(1)
		self.imageSeriesTime.setMaximum(3600)
		self.imageSeriesTime.setValue(1800)
		self.imageSeriesTime.setSingleStep(60)
		self.gridLayout.addWidget(self.imageSeriesTime, 18,1)

		self.imageSeriesTimeLabel = QtWidgets.QLabel()
		self.imageSeriesTimeLabel.setGeometry(QtCore.QRect(int(box2x + 70*scaling), int(12*boxOffset + box1pos[1]), int(60*scaling), int(40*scaling)))
		self.imageSeriesTimeLabel.setFont(labelfont)
		self.imageSeriesTimeLabel.setObjectName("imageSeriesTimeLabel")
		self.imageSeriesTimeLabel.setText('series time period\n(seconds)')
		self.imageSeriesTimeLabel.adjustSize()
		self.gridLayout.addWidget(self.imageSeriesTimeLabel, 17,1)

		self.imageSeriesTotalTime = QtWidgets.QSpinBox()
		self.imageSeriesTotalTime.setObjectName('imageSeriesTotalTime')
		self.imageSeriesTotalTime.setMaximum(24*60*7)
		self.imageSeriesTotalTime.setSingleStep(60)
		self.imageSeriesTotalTime.setMinimum(0)
		self.imageSeriesTotalTime.setValue(24*60)
		self.gridLayout.addWidget(self.imageSeriesTotalTime, 18,2)

		self.imageSeriesTotalTimeLabel = QtWidgets.QLabel()
		self.imageSeriesTotalTimeLabel.setObjectName('imageSeriesTotalTimeLabel')
		self.imageSeriesTotalTimeLabel.setText('total time for image\nseries (mins)')
		self.gridLayout.addWidget(self.imageSeriesTotalTimeLabel, 17,2)


		self.saveImageShrinkBox = QtWidgets.QSpinBox()
		#self.saveImageShrinkBox.setGeometry(QtCore.QRect(int(box2x + 10*scaling), int(12.8*boxOffset + box1pos[1]), int(50*scaling), boxDimensions[1]))
		self.saveImageShrinkBox.setFont(labelfont)
		self.saveImageShrinkBox.setObjectName("saveImageShrinkBox")
		self.saveImageShrinkBox.setProperty('value',1)
		self.saveImageShrinkBox.setMinimum(1)
		self.saveImageShrinkBox.setMaximum(10)
		self.gridLayout.addWidget(self.saveImageShrinkBox, 19,1)
		
		self.saveImageShrinkLabel = QtWidgets.QLabel()
		#self.saveImageShrinkLabel.setGeometry(QtCore.QRect(int(box2x + 70*scaling), int(12.8*boxOffset + box1pos[1]), int(60*scaling), int(40*scaling)))
		self.saveImageShrinkLabel.setFont(labelfont)
		self.saveImageShrinkLabel.setObjectName("saveImageShrinkLabel")
		self.saveImageShrinkLabel.setText('save image\nshrink factor')
		self.saveImageShrinkLabel.adjustSize()
		self.gridLayout.addWidget(self.saveImageShrinkLabel, 19,2)

		self.imageSeriesStopButton = QtWidgets.QPushButton()
		#self.imageSeriesStopButton.setGeometry(QtCore.QRect(box1x, int(12.8*boxOffset + box1pos[1]), int(130*scaling), int(40*scaling)))
		self.imageSeriesStopButton.setFont(labelfont)
		self.imageSeriesStopButton.setObjectName("imageSeriesStopButton")
		self.imageSeriesStopButton.setText('stop image series')
		self.imageSeriesStopButton.adjustSize()
		self.imageSeriesStopButton.setEnabled(False)
		self.gridLayout.addWidget(self.imageSeriesStopButton, 19,0)

		self.directoryBox = QtWidgets.QLineEdit()
		#self.directoryBox.setGeometry(QtCore.QRect(box1x, int(box1pos[1]+14*boxOffset),int(boxDimensions[0]*2),boxDimensions[1]))
		self.directoryBox.setObjectName("directoryBox")
		self.directoryBox.setFont(boxfont)
		self.directoryBox.setText(self.snapshotDir)
		self.gridLayout.addWidget(self.directoryBox, 21,0, 1,2)

		self.openDirectoryButton = QtWidgets.QPushButton(self.centralwidget)
		#self.openDirectoryButton.setGeometry(QtCore.QRect(int(box1x + 10*scaling + boxDimensions[0]*2), int(box1pos[1]+14*boxOffset),boxDimensions[1],boxDimensions[1]))
		self.openDirectoryButton.setObjectName("openDirectoryButton")
		self.openDirectoryButton.setFont(boxfont)
		self.openDirectoryButton.setText('...')
		self.openDirectoryButton.setMaximumWidth(int(30*scaling))
		self.gridLayout.addWidget(self.openDirectoryButton, 21,2)

		self.directoryLabel = QtWidgets.QLabel(self.centralwidget)
		#self.directoryLabel.setGeometry(QtCore.QRect(box1x, int(box1pos[1]+13.65*boxOffset),int(boxDimensions[0]*2),boxDimensions[1]))
		self.directoryLabel.setObjectName('directoryLabel')
		self.directoryLabel.setText('image directory')
		self.directoryLabel.setFont(labelfont)
		self.directoryLabel.adjustSize()
		self.gridLayout.addWidget(self.directoryLabel, 20,0)

		self.linePositionLabel = QtWidgets.QLabel(self.centralwidget)
		#self.linePositionLabel.setGeometry(QtCore.QRect(box1x, int(14.7*boxOffset + box1pos[1]),*boxDimensions))
		self.linePositionLabel.setObjectName('linePositionLabel')
		self.linePositionLabel.setText('line position')
		self.linePositionLabel.setFont(labelfont)
		self.linePositionLabel.adjustSize()
		self.gridLayout.addWidget(self.linePositionLabel, 22,0)

		self.linePositionBox =	 QtWidgets.QSpinBox() #select the size of the cross that is overlayed on the image
		#self.linePositionBox.setGeometry(QtCore.QRect(box1x, 15*boxOffset + box1pos[1],*boxDimensions))
		self.linePositionBox.setObjectName("linePositionBox")
		self.linePositionBox.setFont(boxfont)
		self.linePositionBox.setMinimum(0)
		self.linePositionBox.setMaximum(3000)
		self.linePositionBox.setValue(1800)
		self.linePositionBox.setSingleStep(1)
		self.linePositionBox.setKeyboardTracking(False)
		self.linePositionBox.valueChanged.connect(self.linePositionChange)
		self.linePositionBox.valueChanged.connect(self.updateConfigLog)
		self.gridLayout.addWidget(self.linePositionBox, 23,0)

		self.lineCheckBox =  QtWidgets.QCheckBox(self.centralwidget) #select whether or not to display the cross
		#self.lineCheckBox.setGeometry(QtCore.QRect(labelxpos, 15*boxOffset + box1pos[1],int(10*scaling),int(10*scaling)))
		self.lineCheckBox.setObjectName('lineCheckBox')
		self.lineCheckBox.setText('display line?')
		self.lineCheckBox.setFont(labelfont)
		self.lineCheckBox.setChecked(True)
		self.lineCheckBox.adjustSize()
		self.lineCheckBox.stateChanged.connect(self.lineCheckChange)
		self.lineCheckBox.stateChanged.connect(self.updateConfigLog)
		self.gridLayout.addWidget(self.lineCheckBox, 23,1)

		MainWindow.setCentralWidget(self.centralwidget)
		MainWindow.setCentralWidget(self.centralwidget)
		self.menubar = QtWidgets.QMenuBar(MainWindow)
		self.menubar.setGeometry(QtCore.QRect(0, 0, 234, 21))
		self.menubar.setObjectName("menubar")
		MainWindow.setMenuBar(self.menubar)
		self.statusbar = QtWidgets.QStatusBar(MainWindow)
		self.statusbar.setObjectName("statusbar")
		MainWindow.setStatusBar(self.statusbar)


		self.manualFPSBox.addItem('False')
		self.manualFPSBox.addItem('True')
		self.FPSBox.setValue(30)
		self.gainBox.setValue(30.0)
		self.gainAutoBox.addItem('Off')
		self.gainAutoBox.addItem('Once')
		self.gainAutoBox.addItem('Continuous')
		self.colourBox.addItem('BGR8')
		self.colourBox.addItem('Mono8')

		self.centralwidget.setLayout(self.gridLayout)
		self.retranslateUi(MainWindow)
		QtCore.QMetaObject.connectSlotsByName(MainWindow)

		self.running = False
		self.monitorxBox.setKeyboardTracking(False)
		self.monitoryBox.setKeyboardTracking(False)
		self.xResBox.setKeyboardTracking(False)
		self.yResBox.setKeyboardTracking(False)
		self.FPSBox.setKeyboardTracking(False)
		self.gainBox.setKeyboardTracking(False)
		self.crossSizeBox.setKeyboardTracking(False)
		self.crossOffsetHBox.setKeyboardTracking(False)
		self.crossOffsetWBox.setKeyboardTracking(False)
		self.monitorxBox.valueChanged.connect(self.updateConfigLog)
		self.monitoryBox.valueChanged.connect(self.updateConfigLog)
		self.xResBox.valueChanged.connect(self.updateConfigLog)
		self.yResBox.valueChanged.connect(self.updateConfigLog)
		self.FPSBox.valueChanged.connect(self.updateConfigLog)
		self.gainBox.valueChanged.connect(self.updateConfigLog)
		self.crossSizeBox.valueChanged.connect(self.updateConfigLog)
		self.crossOffsetHBox.valueChanged.connect(self.updateConfigLog)
		self.crossOffsetWBox.valueChanged.connect(self.updateConfigLog)
		self.colourBox.currentTextChanged.connect(self.updateConfigLog)
		self.manualFPSBox.currentTextChanged.connect(self.updateConfigLog)
		self.runButton.clicked.connect(self.start_worker)
		self.stopButton.clicked.connect(self.stop_worker)
		self.snapShotButton.clicked.connect(self.takeSingleImage)
		self.imageSeriesButton.clicked.connect(self.takeImageSeries)
		self.imageSeriesStopButton.clicked.connect(self.stopImageSeries)
		self.gainBox.valueChanged.connect(self.changeGain)
		self.crossSizeBox.valueChanged.connect(self.crossSizeChange)
		self.crossOffsetHBox.valueChanged.connect(self.crossHChange)
		self.crossOffsetHBox.valueChanged.connect(self.updateConfigLog)
		self.crossOffsetWBox.valueChanged.connect(self.crossWChange)
		self.crossOffsetWBox.valueChanged.connect(self.updateConfigLog)
		self.lockCrossPositionBox.stateChanged.connect(self.crossDisplayCheck)
		self.lockCrossPositionBox.stateChanged.connect(self.updateConfigLog)
		self.openDirectoryButton.clicked.connect(self.folderDialogue)
		self.crossCheckBox.stateChanged.connect(self.changeCrossDisplay)
		self.saveImageShrinkBox.valueChanged.connect(self.changeImageSaveFactor)
		
		#self.paramConfigList = [self.crossOffsetHBox, self.crossOffsetWBox,self.monitorxBox,self.monitoryBox,self.colourBox,
		#	   self.manualFPSBox,self.FPSBox,self.xResBox,self.yResBox,self.xOffsetBox,self.yOffsetBox,self.directoryBox]
		
		self.updateParamDct()
		self.settingsLog = f'{homepath}/lucidGUIConfig/lucidGUIconfiguration.log'
		if not os.path.exists(os.path.dirname(self.settingsLog)):
			os.makedirs(os.path.dirname(self.settingsLog))
		if os.path.exists(self.settingsLog):
			self.readConfigLog()

	def retranslateUi(self, MainWindow):
		_translate = QtCore.QCoreApplication.translate
		MainWindow.setWindowTitle(_translate("MainWindow", "Lucid GUI"))
		self.runButton.setText(_translate("MainWindow", "Let\'s gooooo!"))

		self.xResLabel.setText(_translate("MainWindow", "x-resolution"))
		self.xResLabel.adjustSize()
		self.yResLabel.setText(_translate("MainWindow", "y-resolution"))
		self.yResLabel.adjustSize()
		self.xOffsetLabel.setText(_translate("MainWindow", "x-offset"))
		self.xOffsetLabel.adjustSize()
		self.yOffsetLabel.setText(_translate("MainWindow", "y-offset"))
		self.yOffsetLabel.adjustSize()
		self.monitorxLabel.setText(_translate("MainWindow", "x image size on screen"))
		self.monitorxLabel.adjustSize()
		self.monitoryLabel.setText(_translate("MainWindow", "y image size on screen"))
		self.monitoryLabel.adjustSize()
		self.aspectInfoLabel.setText(_translate("MainWindow", "aspect ratio of image on screen will be\n"
"scaled automatically"))
		self.aspectInfoLabel.adjustSize()
		self.gainAutoLabel.setText(_translate("MainWindow", "Gain Auto"))
		self.gainAutoLabel.adjustSize()
		self.gainLabel.setText(_translate("MainWindow", "Gain (set Gain\n"
"Auto to \'Off\')"))
		self.gainLabel.adjustSize()
		self.manualFPSLabel.setText(_translate("MainWindow", "Manual FPS"))
		self.manualFPSLabel.adjustSize()
		self.colourBoxLabel.setText(_translate("MainWindow","colour format"))
		self.colourBoxLabel.adjustSize()
		self.FPSLabel.setText(_translate("MainWindow", "FPS"))
		self.FPSLabel.adjustSize()
		self.stopButton.setText(_translate("MainWindow", "Stop"))

	def start_worker(self):
		self.updateConfigLog()
		self.running = True
		self.stopButton.setEnabled(True)
		self.snapShotButton.setEnabled(True)
		self.imageSeriesButton.setEnabled(True)
		width = self.xResBox.value()
		height = self.yResBox.value()
		ox = self.xOffsetBox.value()
		oy = self.yOffsetBox.value()
		monitorx = self.monitorxBox.value()
		monitory = self.monitoryBox.value()
		totalImageTime = self.imageSeriesTotalTime.value()
		if self.manualFPSBox.currentText() == 'True':		
			manualfps = True		
		elif self.manualFPSBox.currentText() == 'False':
			manualfps = False		
		fps = self.FPSBox.value()		
		gainAuto = self.gainAutoBox.currentText()		
		gain = self.gainBox.value()		
		colourFormat = self.colourBox.currentText()	
		
		crosssize = self.crossSizeBox.value()		
		crossOffsetH = self.crossOffsetHBox.value()		
		crossOffsetW = self.crossOffsetWBox.value()
		crossCheck = self.crossCheckBox.isChecked()
		imageTime = self.imageSeriesTime.value()

		self.thread = Worker(width = width,height = height,ox = ox,oy = oy, monitorx = monitorx,monitory = monitory,
		manualfps = manualfps,fps = fps,gainAuto = gainAuto,gain = gain, fmt = colourFormat, screenwidth = self.screenwidth, screenheight=self.screenheight,
		crosssize = crosssize,crossOffsetH = crossOffsetH, crossOffsetW = crossOffsetW, crossCheck = crossCheck, imageTime = imageTime, 
		imageDir = self.snapshotDir, totalImageTime=totalImageTime,lineCheck=self.lineCheckBox.isChecked(), linePosition=self.linePositionBox.value(), 
		imageSaveFactor=self.saveImageShrinkBox.value())

		self.thread.start()
		self.runButton.setEnabled(False)
		self.thread.output.connect(self.imageTimer)

	def imageTimer(self, values):
		newtime = values[0]
		seriesState = values[1]
		self.imageSeriesTotalTime.setValue(newtime)
		self.imageSeriesButton.setEnabled(not seriesState)
		self.imageSeriesStopButton.setEnabled(seriesState)


	def stop_worker(self):
		self.thread.stop()
		self.runButton.setEnabled(True)
		self.stopButton.setEnabled(False)
		self.snapShotButton.setEnabled(False)
		self.imageSeriesButton.setEnabled(False)
		self.imageSeriesStopButton.setEnabled(False)
		self.running = False

	def updateParamDct(self):
		self.paramDct = {self.crossOffsetHBox.objectName(): [self.crossOffsetHBox,self.crossOffsetHBox.value()],
						self.crossOffsetWBox.objectName(): [self.crossOffsetWBox,self.crossOffsetWBox.value()],
						self.monitorxBox.objectName(): [self.monitorxBox,self.monitorxBox.value()],
						self.monitoryBox.objectName(): [self.monitoryBox,self.monitoryBox.value()],
						self.gainBox.objectName(): [self.gainBox,self.gainBox.value()],
						self.crossSizeBox.objectName(): [self.crossSizeBox, self.crossSizeBox.value()] ,
						self.colourBox.objectName():[self.colourBox,self.colourBox.currentText()],
						self.manualFPSBox.objectName():[self.manualFPSBox,self.manualFPSBox.currentText()],
						self.FPSBox.objectName():[self.FPSBox,self.FPSBox.value()],
						self.xResBox.objectName():[self.xResBox,self.xResBox.value()],
						self.yResBox.objectName():[self.yResBox,self.yResBox.value()],
						self.xOffsetBox.objectName():[self.xOffsetBox,self.xOffsetBox.value()],
						self.yOffsetBox.objectName():[self.yOffsetBox,self.yOffsetBox.value()],
						self.directoryBox.objectName():[self.directoryBox,self.directoryBox.text()],
						self.linePositionBox.objectName():[self.linePositionBox,self.linePositionBox.value()],
						self.lineCheckBox.objectName():[self.lineCheckBox,self.lineCheckBox.isChecked()]}
		
	def changeImageSaveFactor(self):
		if self.running:
			self.thread.saveImageFactor = self.saveImageShrinkBox.value()

	def changeGain(self):
		if self.running:
			self.thread.gain = self.gainBox.value()
			self.thread.gaincheck = True
	def crossSizeChange(self):
		if self.running:
			self.thread.crosssize = self.crossSizeBox.value()
	def crossHChange(self):
		if self.running:
			self.thread.crossOffsetH = self.crossOffsetHBox.value()

	def crossWChange(self):
		if self.running:
			self.thread.crossOffsetW = self.crossOffsetWBox.value()
	
	def linePositionChange(self):
		if self.running:
			self.thread.linePosition = self.linePositionBox.value()
	
	def lineCheckChange(self):
		if self.running:
			self.thread.lineCheck = self.lineCheckBox.isChecked()

	def takeSingleImage(self):
		if self.running:
			self.thread.snapshot = True

	def takeImageSeries(self):
		if self.running:
			self.thread.imageSeries = True
			self.thread.imageTime = self.imageSeriesTime.value()
			self.thread.imageCountDown = 0
			self.imageSeriesButton.setEnabled(False)
			self.imageSeriesStopButton.setEnabled(True)

	def stopImageSeries(self):
		if self.running:
			self.thread.imageSeries = False
			self.imageSeriesButton.setEnabled(True)
			self.imageSeriesStopButton.setEnabled(False)
	def crossDisplayCheck(self):
		if self.lockCrossPositionBox.isChecked():
			self.crossOffsetHBox.setEnabled(False)
			self.crossOffsetWBox.setEnabled(False)
		else:
			self.crossOffsetHBox.setEnabled(True)
			self.crossOffsetWBox.setEnabled(True)

	def changeCrossDisplay(self):
		if self.running:
			self.thread.crossCheck = self.crossCheckBox.isChecked()



	def folderDialogue(self):
		folder = str(QtWidgets.QFileDialog.getExistingDirectory(None, "Select Directory",self.directoryBox.text()))
		if folder != '':
			self.directoryBox.setText(folder)
			self.snapshotDir = folder
			#f = open(logFile,'w')
			#f.write(folder)
			#f.close()
			self.updateConfigLog()
			if self.running:
				self.thread.imageDir = folder
	def updateConfigLog(self):
		self.updateParamDct()
		logUpdate = ''
		for par in self.paramDct:
			logUpdate += f'{par};{self.paramDct[par][1]}\n'
		f = open(self.settingsLog,'w')
		f.write(logUpdate)
		f.close()
	def readConfigLog(self):
		f = open(self.settingsLog,'r')
		lines = f.readlines()
		f.close()
		for line in lines:
			parname = line.split(';')[0]
			parvalue = line.split(';')[1].replace('\n','')
			if type(self.paramDct[parname][0]) == QtWidgets.QSpinBox:
				self.paramDct[parname][0].setValue(int(parvalue))
			elif type(self.paramDct[parname][0]) == QtWidgets.QDoubleSpinBox:
				self.paramDct[parname][0].setValue(float(parvalue))
			elif type(self.paramDct[parname][0]) == QtWidgets.QLineEdit:
				self.paramDct[parname][0].setText(parvalue)
			elif type(self.paramDct[parname][0]) == QtWidgets.QComboBox:
				self.paramDct[parname][0].setCurrentText(parvalue)
			elif type(self.paramDct[parname][0]) == QtWidgets.QCheckBox:
				self.paramDct[parname][0].setChecked(stringToBool(parvalue))
		self.updateParamDct()

def main():
	app = QtWidgets.QApplication(sys.argv)
	MainWindow = QtWidgets.QMainWindow()
	ui = Ui_MainWindow()
	ui.setupUi(MainWindow)
	MainWindow.show()
	sys.exit(app.exec())
if __name__ == "__main__":
	main()

