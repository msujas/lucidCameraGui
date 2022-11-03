# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'guilayout.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!
import lucidLiveStream
from PyQt5 import QtCore, QtGui, QtWidgets

from arena_api.system import system
from arena_api.buffer import *
import arena_api.enums as enums

import ctypes
import numpy as np
import cv2
import time
import matplotlib.pyplot as plt




class Worker(QtCore.QThread):
	def __init__(self,width, height, ox, oy,monitorx, monitory,manualfps,fps, gainAuto, gain, fmt, screenwidth,
	crosssize, crossOffsetH, crossOffsetW, crossCheck):
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
		self.crosssize = crosssize
		self.crossOffsetH = crossOffsetH
		self.crossOffsetW = crossOffsetW
		self.crossCheck = crossCheck
		self.running = True

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
			print(f'No device found! Please connect a device and run '
							f'the example again.')
			return
		nodemap = device.nodemap
		nodes = nodemap.get_node(['Width', 'Height', 'PixelFormat','OffsetX','OffsetY', 'AcquisitionFrameRateEnable', 'AcquisitionFrameRate','GainAuto', 'Gain'])

		pixelFormats =	{'Mono8':1, 'Mono10':1, 'Mono10p':1, 'Mono10Packed':1, 'Mono12':1, 'Mono12p':1,
		'Mono12Packed':1, 'Mono16':1, 'BayerRG8':2, 'BayerRG10':2, 'BayerRG10p':2, 'BayerRG10Packed':2,
		'BayerRG12':2, 'BayerRG12p':2, 'BayerRG12Packed':2, 'BayerRG16':2, 'RGB8':3, 'BGR8':3, 'YCbCr8':3,
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
		if self.gainAuto == 'Off':
			nodes['Gain'].value = self.gain


		nodes['PixelFormat'].value = self.fmt


		num_channels = pixelFormats[nodes['PixelFormat'].value]


		aspect = nodes['Width'].value/nodes['Height'].value

		cross = np.empty(shape = (self.height,self.width,1))

		crossThickness = 10

		cross[self.crossOffsetH + int(self.height/2-(crossThickness-1)/2+1): self.crossOffsetH + int(self.height/2+(crossThickness-1)/2), self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+ int(self.width/2+self.crosssize/2)] = True #middle horizontal
		cross[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2+self.crosssize/2),self.crossOffsetW+ int(self.width/2 - crossThickness/2 +1): self.crossOffsetW+int(self.width/2 + crossThickness/2)] = True #middle vertical
		cross[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2+self.crosssize/2),self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+int(self.width/2-self.crosssize/2 + 1 + crossThickness)] = True #left vertical
		cross[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2+self.crosssize/2),self.crossOffsetW+ int(self.width/2+self.crosssize/2-crossThickness):  self.crossOffsetW+int(self.width/2+self.crosssize/2)] = True #right vertical
		cross[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2-self.crosssize/2 + crossThickness+1),self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+int(self.width/2+self.crosssize/2)] = True #lower horizontal
		cross[self.crossOffsetH + int(self.height/2+self.crosssize/2-crossThickness):  self.crossOffsetH + int(self.height/2+self.crosssize/2), self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+int(self.width/2+self.crosssize/2)] = True #upper horizontal
		if self.monitorx/self.monitory < aspect:
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
		cv2.moveWindow(windowName,self.screenwidth-self.monitorx,0)
		if num_channels == 3:
			crossElement = np.array([0,0,255], dtype = np.uint8)
		elif num_channels == 1:
			crossElement = np.array([255],dtype = np.uint8)
		with device.start_stream():
			"""
			Infinitely fetch and display buffer data until esc is pressed
			"""

			while self.running:
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
				#npndarray = np.where(cross == True, crossElement, npndarray)
				if self.crossCheck:
					npndarray[self.crossOffsetH + int(self.height/2-(crossThickness-1)/2+1): self.crossOffsetH + int(self.height/2+(crossThickness-1)/2),
					self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+ int(self.width/2+self.crosssize/2)] = crossElement #middle horizontal

					npndarray[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2+self.crosssize/2),
					self.crossOffsetW+ int(self.width/2 - crossThickness/2 +1): self.crossOffsetW+int(self.width/2 + crossThickness/2)] = crossElement #middle vertical

					npndarray[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2+self.crosssize/2),
					self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+int(self.width/2-self.crosssize/2 + 1 + crossThickness)] = crossElement #left vertical

					npndarray[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2+self.crosssize/2),
					self.crossOffsetW+ int(self.width/2+self.crosssize/2-crossThickness):  self.crossOffsetW+int(self.width/2+cself.rosssize/2)] = crossElement #right vertical

					npndarray[self.crossOffsetH + int(self.height/2-self.crosssize/2 + 1):self.crossOffsetH + int(self.height/2-self.crosssize/2 + crossThickness+1),
					self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+int(self.width/2+self.crosssize/2)] = crossElement #lower horizontal

					npndarray[self.crossOffsetH + int(self.height/2+self.crosssize/2-crossThickness):  self.crossOffsetH + int(self.height/2+self.crosssize/2),
					self.crossOffsetW+ int(self.width/2-self.crosssize/2 + 1):self.crossOffsetW+int(self.width/2+self.crosssize/2)] = crossElement #upper horizontal
				#fps = str(1/(curr_frame_time - prev_frame_time))
				resize = cv2.resize(npndarray,(self.monitorx,self.monitory))

				#cv2.putText(resize, fps,textpos, cv2.FONT_HERSHEY_SIMPLEX, textsize, (100, 255, 0), 3, cv2.LINE_AA)

				cv2.imshow(windowName,resize)

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
		return

	def stop(self):
		self.running = False
		print('stopping process')
		#self.terminate()



class Ui_MainWindow(object):
	def setupUi(self, MainWindow):
		MainWindow.setObjectName("Lucid GUI")

		self.screen = QtWidgets.QApplication.primaryScreen().size()
		self.screenwidth = self.screen.width()

		scaling = (self.screenwidth/1920)**0.5
		windowsize = [int(280*scaling),int(670*scaling)]
		MainWindow.resize(*windowsize)
		MainWindow.move(0,self.screen.height() - windowsize[1] - 75)
		box1pos = [int(20*scaling), int(40*scaling)]
		boxDimensions = [int(80*scaling),int(22*scaling)]
		boxOffset = boxDimensions[1] + int(18*scaling)
		labelxpos = 20 + boxDimensions[0] + 10

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




		self.yOffsetBox = QtWidgets.QSpinBox(self.centralwidget)
		self.yOffsetBox.setGeometry(QtCore.QRect(20, 3*boxOffset + box1pos[1],*boxDimensions))
		self.yOffsetBox.setMaximum(2950)
		self.yOffsetBox.setObjectName("yOffsetBox")
		self.yOffsetBox.setFont(boxfont)

		self.xOffsetBox = QtWidgets.QSpinBox(self.centralwidget)
		self.xOffsetBox.setGeometry(QtCore.QRect(20, 2*boxOffset + box1pos[1],*boxDimensions))
		self.xOffsetBox.setMaximum(4046)
		self.xOffsetBox.setObjectName("xOffsetBox")
		self.xOffsetBox.setFont(boxfont)

		self.yResBox = QtWidgets.QSpinBox(self.centralwidget)
		self.yResBox.setGeometry(QtCore.QRect(20, boxOffset + box1pos[1],*boxDimensions))
		self.yResBox.setMinimum(50)
		self.yResBox.setMaximum(3000)
		self.yResBox.setProperty("value", 3000)
		self.yResBox.setObjectName("yResBox")
		self.yResBox.setFont(boxfont)

		self.xResBox = QtWidgets.QSpinBox(self.centralwidget)
		self.xResBox.setGeometry(QtCore.QRect(20, 40,*boxDimensions))
		self.xResBox.setMinimum(50)
		self.xResBox.setMaximum(4096)
		self.xResBox.setProperty("value", 4000)
		self.xResBox.setObjectName("xResBox")
		self.xResBox.setFont(boxfont)

		self.xResLabel = QtWidgets.QLabel(self.centralwidget)
		self.xResLabel.setGeometry(QtCore.QRect(labelxpos, 40, 61, 16))
		self.xResLabel.setObjectName("xResLabel")
		self.xResLabel.setFont(labelfont)

		self.yResLabel = QtWidgets.QLabel(self.centralwidget)
		self.yResLabel.setGeometry(QtCore.QRect(labelxpos, boxOffset + box1pos[1], 71, 16))
		self.yResLabel.setObjectName("yResLabel")
		self.yResLabel.setFont(labelfont)

		self.monitorxBox = QtWidgets.QSpinBox(self.centralwidget)
		self.monitorxBox.setGeometry(QtCore.QRect(20, 4*boxOffset + box1pos[1],*boxDimensions))
		self.monitorxBox.setMinimum(100)
		self.monitorxBox.setMaximum(3840)
		self.monitorxBox.setStepType(QtWidgets.QAbstractSpinBox.DefaultStepType)
		self.monitorxBox.setProperty("value", 2500)
		self.monitorxBox.setObjectName("monitorxBox")
		self.monitorxBox.setFont(boxfont)

		self.xOffsetLabel = QtWidgets.QLabel(self.centralwidget)
		self.xOffsetLabel.setGeometry(QtCore.QRect(labelxpos, 2*boxOffset + box1pos[1], 47, 13))
		self.xOffsetLabel.setObjectName("xOffsetLabel")
		self.xOffsetLabel.setFont(labelfont)


		self.yOffsetLabel = QtWidgets.QLabel(self.centralwidget)
		self.yOffsetLabel.setGeometry(QtCore.QRect(labelxpos, 3*boxOffset + box1pos[1], 47, 20))
		self.yOffsetLabel.setObjectName("yOffsetLabel")
		self.yOffsetLabel.setFont(labelfont)


		self.monitorxLabel = QtWidgets.QLabel(self.centralwidget)
		self.monitorxLabel.setGeometry(QtCore.QRect(labelxpos, 4*boxOffset + box1pos[1], 111, 16))
		self.monitorxLabel.setObjectName("monitorxLabel")
		self.monitorxLabel.setFont(labelfont)

		self.monitoryLabel = QtWidgets.QLabel(self.centralwidget)
		self.monitoryLabel.setGeometry(QtCore.QRect(labelxpos, 5*boxOffset + box1pos[1], 111, 16))
		self.monitoryLabel.setObjectName("monitoryLabel")
		self.monitoryLabel.setFont(labelfont)

		self.monitoryBox = QtWidgets.QSpinBox(self.centralwidget)
		self.monitoryBox.setGeometry(QtCore.QRect(20, 5*boxOffset + box1pos[1],*boxDimensions))
		self.monitoryBox.setMinimum(100)
		self.monitoryBox.setMaximum(3000)
		self.monitoryBox.setSingleStep(1)
		self.monitoryBox.setStepType(QtWidgets.QAbstractSpinBox.DefaultStepType)
		self.monitoryBox.setProperty("value", 1600)
		self.monitoryBox.setObjectName("monitoryBox")
		self.monitoryBox.setFont(boxfont)

		self.aspectInfoLabel = QtWidgets.QLabel(self.centralwidget)
		self.aspectInfoLabel.setGeometry(QtCore.QRect(20, int(5.7*boxOffset + box1pos[1]), 201, 41))
		self.aspectInfoLabel.setFont(smallLabelfont)
		self.aspectInfoLabel.setObjectName("aspectInfoLabel")

		self.colourBox = QtWidgets.QComboBox(self.centralwidget)
		self.colourBox.setGeometry(QtCore.QRect(20, 7*boxOffset + box1pos[1],*boxDimensions))
		self.colourBox.setObjectName("colourBox")
		self.colourBox.setFont(boxfont)

		self.colourBoxLabel = QtWidgets.QLabel(self.centralwidget)
		self.colourBoxLabel.setFont(labelfont)
		self.colourBoxLabel.setObjectName("colourBoxLabel")
		self.colourBoxLabel.setGeometry(QtCore.QRect(labelxpos, 7*boxOffset + box1pos[1], 91, 16))

		self.manualFPSBox = QtWidgets.QComboBox(self.centralwidget)
		self.manualFPSBox.setGeometry(QtCore.QRect(20, 8*boxOffset + box1pos[1],*boxDimensions))
		self.manualFPSBox.setObjectName("manualFPSBox")
		self.manualFPSBox.setFont(boxfont)

		self.manualFPSLabel = QtWidgets.QLabel(self.centralwidget)
		self.manualFPSLabel.setGeometry(QtCore.QRect(labelxpos, 8*boxOffset + box1pos[1], 71, 16))
		self.manualFPSLabel.setFont(labelfont)
		self.manualFPSLabel.setObjectName("manualFPSLabel")

		self.FPSBox = QtWidgets.QSpinBox(self.centralwidget)
		self.FPSBox.setGeometry(QtCore.QRect(20, 9*boxOffset + box1pos[1],*boxDimensions))
		self.FPSBox.setObjectName("FPSBox")
		self.FPSBox.setFont(boxfont)

		self.FPSLabel = QtWidgets.QLabel(self.centralwidget)
		self.FPSLabel.setGeometry(QtCore.QRect(labelxpos, 9*boxOffset + box1pos[1], 71, 16))
		self.FPSLabel.setFont(labelfont)
		self.FPSLabel.setObjectName("FPSLabel")

		self.gainAutoBox = QtWidgets.QComboBox(self.centralwidget)
		self.gainAutoBox.setGeometry(QtCore.QRect(20, 10*boxOffset + box1pos[1], boxDimensions[0] + int(10*scaling), boxDimensions[1]))
		self.gainAutoBox.setObjectName("gainAutoBox")
		self.gainAutoBox.setFont(boxfont)

		self.gainAutoLabel = QtWidgets.QLabel(self.centralwidget)
		self.gainAutoLabel.setGeometry(QtCore.QRect(int(labelxpos+10*scaling), 10*boxOffset + box1pos[1], 61, 16))
		self.gainAutoLabel.setObjectName("gainAutoLabel")
		self.gainAutoLabel.setFont(labelfont)

		self.gainBox = QtWidgets.QDoubleSpinBox(self.centralwidget)
		self.gainBox.setGeometry(QtCore.QRect(20, 11*boxOffset + box1pos[1],*boxDimensions))
		self.gainBox.setDecimals(1)
		self.gainBox.setMaximum(48.0)
		self.gainBox.setObjectName("gainBox")
		self.gainBox.setFont(boxfont)

		self.gainLabel = QtWidgets.QLabel(self.centralwidget)
		self.gainLabel.setGeometry(QtCore.QRect(labelxpos, 11*boxOffset + box1pos[1], 81, 31))
		self.gainLabel.setObjectName("gainLabel")
		self.gainLabel.setFont(labelfont)

		self.crossSizeBox =  QtWidgets.QSpinBox(self.centralwidget)
		self.crossSizeBox.setGeometry(QtCore.QRect(20, 12*boxOffset + box1pos[1],*boxDimensions))
		self.crossSizeBox.setObjectName("crossSizeBox")
		self.crossSizeBox.setFont(boxfont)
		self.crossSizeBox.setMinimum(100)
		self.crossSizeBox.setMaximum(2000)
		self.crossSizeBox.setValue(700)

		self.crossSizeLabel = QtWidgets.QLabel(self.centralwidget)
		self.crossSizeLabel.setGeometry(QtCore.QRect(labelxpos, int(12*boxOffset + box1pos[1]), 81, 31))
		self.crossSizeLabel.setObjectName("crossSizeLabel")
		self.crossSizeLabel.setText('cross size')
		self.crossSizeLabel.setFont(labelfont)
		self.crossSizeLabel.adjustSize()

		self.crossCheckBox =  QtWidgets.QCheckBox(self.centralwidget)
		self.crossCheckBox.setGeometry(QtCore.QRect(labelxpos + int(60*scaling), 12*boxOffset + box1pos[1],int(10*scaling),int(10*scaling)))
		self.crossCheckBox.setObjectName('crossCheckBox')
		self.crossCheckBox.setText('display cross?')
		self.crossCheckBox.setChecked(True)
		self.crossCheckBox.adjustSize()

		self.crossHLabel = QtWidgets.QLabel(self.centralwidget)
		self.crossHLabel.setGeometry(QtCore.QRect(20, int(12.6*boxOffset + box1pos[1]), 81, 31))
		self.crossHLabel.setObjectName("crossHLabel")
		self.crossHLabel.setText('cross y offset')
		self.crossHLabel.setFont(labelfont)
		self.crossHLabel.adjustSize()

		self.crossOffsetHBox =  QtWidgets.QSpinBox(self.centralwidget)
		self.crossOffsetHBox.setGeometry(QtCore.QRect(20, 13*boxOffset + box1pos[1],*boxDimensions))
		self.crossOffsetHBox.setObjectName("crossOffsetHBox")
		self.crossOffsetHBox.setFont(boxfont)
		self.crossOffsetHBox.setMinimum(-1500)
		self.crossOffsetHBox.setMaximum(1500)
		self.crossOffsetHBox.setValue(0)

		self.crossWLabel = QtWidgets.QLabel(self.centralwidget)
		self.crossWLabel.setGeometry(QtCore.QRect(20 + boxDimensions[0] + 20, int(12.6*boxOffset + box1pos[1]), 81, 31))
		self.crossWLabel.setObjectName("crossWLabel")
		self.crossWLabel.setText('cross x offset')
		self.crossWLabel.setFont(labelfont)
		self.crossWLabel.adjustSize()

		self.crossOffsetWBox =  QtWidgets.QSpinBox(self.centralwidget)
		self.crossOffsetWBox.setGeometry(QtCore.QRect(20 + boxDimensions[0] + 20, 13*boxOffset + box1pos[1],*boxDimensions))
		self.crossOffsetWBox.setObjectName("crossOffsetWBox")
		self.crossOffsetWBox.setFont(boxfont)
		self.crossOffsetWBox.setMinimum(-1500)
		self.crossOffsetWBox.setMaximum(1500)
		self.crossOffsetWBox.setValue(0)

		self.runButton = QtWidgets.QPushButton(self.centralwidget)
		self.runButton.setGeometry(QtCore.QRect(20, 14*boxOffset + box1pos[1], int(130*scaling), int(40*scaling)))
		self.runButton.setFont(font)
		self.runButton.setObjectName("runButton")

		self.stopButton = QtWidgets.QPushButton(self.centralwidget)
		self.stopButton.setGeometry(QtCore.QRect(20 + int(130*scaling) + 10, 14*boxOffset + box1pos[1], 75, 23))
		self.stopButton.setObjectName("stopButton")
		self.stopButton.setFont(font)
		self.stopButton.adjustSize()
		self.stopButton.setEnabled(False)

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
		self.retranslateUi(MainWindow)
		QtCore.QMetaObject.connectSlotsByName(MainWindow)

		self.runButton.clicked.connect(self.start_worker)
		self.stopButton.clicked.connect(self.stop_worker)
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
		self.stopButton.setEnabled(True)
		width = self.xResBox.value()
		height = self.yResBox.value()
		ox = self.xOffsetBox.value()
		oy = self.yOffsetBox.value()
		monitorx = self.monitorxBox.value()
		monitory = self.monitoryBox.value()
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

		self.thread = Worker(width = width,height = height,ox = ox,oy = oy, monitorx = monitorx,monitory = monitory,
		manualfps = manualfps,fps = fps,gainAuto = gainAuto,gain = gain, fmt = colourFormat, screenwidth = self.screenwidth,crosssize = crosssize,
		crossOffsetH = crossOffsetH, crossOffsetW = crossOffsetW, crossCheck = crossCheck)

		self.thread.start()
		self.runButton.setEnabled(False)

	def stop_worker(self):
		self.thread.stop()
		self.runButton.setEnabled(True)
		self.stopButton.setEnabled(False)

if __name__ == "__main__":
	import sys
	app = QtWidgets.QApplication(sys.argv)
	MainWindow = QtWidgets.QMainWindow()
	ui = Ui_MainWindow()
	ui.setupUi(MainWindow)
	MainWindow.show()
	sys.exit(app.exec_())
