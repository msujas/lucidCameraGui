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
	def __init__(self,width, height, ox, oy,monitorx, monitory,manualfps,fps, gainAuto, gain, fmt = 'BGR8'):
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
			nodes['Gain'] = self.gain
	
	
		nodes['PixelFormat'].value = self.fmt
	
	
		num_channels = pixelFormats[nodes['PixelFormat'].value]
	
	
		aspect = nodes['Width'].value/nodes['Height'].value

	
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
	
	
				fps = str(1/(curr_frame_time - prev_frame_time))
				resize = cv2.resize(npndarray,(self.monitorx,self.monitory))

				cv2.putText(resize, fps,textpos, cv2.FONT_HERSHEY_SIMPLEX, textsize, (100, 255, 0), 3, cv2.LINE_AA)
	
				cv2.imshow('lucid (press Esc. to close)',resize)

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
		
	def stop(self):
		self.running = False
		print('stopping process')
		#self.terminate()
		
		
		
class Ui_MainWindow(object):
	def setupUi(self, MainWindow):
		MainWindow.setObjectName("Lucid GUI")
		MainWindow.resize(264, 559)
		self.centralwidget = QtWidgets.QWidget(MainWindow)
		self.centralwidget.setObjectName("centralwidget")
		self.runButton = QtWidgets.QPushButton(self.centralwidget)
		self.runButton.setGeometry(QtCore.QRect(20, 480, 111, 41))
		font = QtGui.QFont()
		font.setPointSize(12)
		self.runButton.setFont(font)
		self.runButton.setObjectName("runButton")
		self.runButton.setShortcut(QtGui.QKeySequence('Shift+Return'))
		self.yOffsetBox = QtWidgets.QSpinBox(self.centralwidget)
		self.yOffsetBox.setGeometry(QtCore.QRect(20, 140, 81, 22))
		self.yOffsetBox.setMaximum(2950)
		self.yOffsetBox.setObjectName("yOffsetBox")
		self.xOffsetBox = QtWidgets.QSpinBox(self.centralwidget)
		self.xOffsetBox.setGeometry(QtCore.QRect(20, 110, 81, 22))
		self.xOffsetBox.setMaximum(4046)
		self.xOffsetBox.setObjectName("xOffsetBox")
		self.yResBox = QtWidgets.QSpinBox(self.centralwidget)
		self.yResBox.setGeometry(QtCore.QRect(20, 80, 81, 22))
		self.yResBox.setMinimum(50)
		self.yResBox.setMaximum(3000)
		self.yResBox.setProperty("value", 3000)
		self.yResBox.setObjectName("yResBox")
		self.xResBox = QtWidgets.QSpinBox(self.centralwidget)
		self.xResBox.setGeometry(QtCore.QRect(20, 40, 81, 22))
		self.xResBox.setMinimum(50)
		self.xResBox.setMaximum(4096)
		self.xResBox.setProperty("value", 4000)
		self.xResBox.setObjectName("xResBox")
		self.monitorxBox = QtWidgets.QSpinBox(self.centralwidget)
		self.monitorxBox.setGeometry(QtCore.QRect(20, 200, 81, 22))
		self.monitorxBox.setMinimum(100)
		self.monitorxBox.setMaximum(2560)
		self.monitorxBox.setStepType(QtWidgets.QAbstractSpinBox.DefaultStepType)
		self.monitorxBox.setProperty("value", 2500)
		self.monitorxBox.setObjectName("monitorxBox")
		self.xResLabel = QtWidgets.QLabel(self.centralwidget)
		self.xResLabel.setGeometry(QtCore.QRect(120, 40, 61, 16))
		self.xResLabel.setObjectName("xResLabel")
		self.yResLabel = QtWidgets.QLabel(self.centralwidget)
		self.yResLabel.setGeometry(QtCore.QRect(120, 80, 71, 16))
		self.yResLabel.setObjectName("yResLabel")
		self.xOffsetLabel = QtWidgets.QLabel(self.centralwidget)
		self.xOffsetLabel.setGeometry(QtCore.QRect(120, 110, 47, 13))
		self.xOffsetLabel.setObjectName("xOffsetLabel")
		self.yOffsetLabel = QtWidgets.QLabel(self.centralwidget)
		self.yOffsetLabel.setGeometry(QtCore.QRect(120, 140, 47, 13))
		self.yOffsetLabel.setObjectName("yOffsetLabel")
		self.monitorxLabel = QtWidgets.QLabel(self.centralwidget)
		self.monitorxLabel.setGeometry(QtCore.QRect(110, 200, 111, 16))
		self.monitorxLabel.setObjectName("monitorxLabel")
		self.monitoryLabel = QtWidgets.QLabel(self.centralwidget)
		self.monitoryLabel.setGeometry(QtCore.QRect(110, 240, 111, 16))
		self.monitoryLabel.setObjectName("monitoryLabel")
		self.monitoryBox = QtWidgets.QSpinBox(self.centralwidget)
		self.monitoryBox.setGeometry(QtCore.QRect(20, 240, 81, 22))
		self.monitoryBox.setMinimum(100)
		self.monitoryBox.setMaximum(950)
		self.monitoryBox.setSingleStep(1)
		self.monitoryBox.setStepType(QtWidgets.QAbstractSpinBox.DefaultStepType)
		self.monitoryBox.setProperty("value", 1300)
		self.monitoryBox.setObjectName("monitoryBox")
		self.aspectInfoLabel = QtWidgets.QLabel(self.centralwidget)
		self.aspectInfoLabel.setGeometry(QtCore.QRect(20, 260, 201, 41))
		font = QtGui.QFont()
		font.setPointSize(7)
		self.aspectInfoLabel.setFont(font)
		self.aspectInfoLabel.setObjectName("aspectInfoLabel")
		self.gainAutoBox = QtWidgets.QComboBox(self.centralwidget)
		self.gainAutoBox.setGeometry(QtCore.QRect(20, 390, 91, 22))
		font = QtGui.QFont()
		font.setPointSize(10)
		self.gainAutoBox.setFont(font)
		self.gainAutoBox.setObjectName("gainAutoBox")
		self.gainAutoBox.addItem('Off')
		self.gainAutoBox.addItem('Once')
		self.gainAutoBox.addItem('Continuous')
		self.gainAutoLabel = QtWidgets.QLabel(self.centralwidget)
		self.gainAutoLabel.setGeometry(QtCore.QRect(120, 390, 61, 16))
		font = QtGui.QFont()
		font.setPointSize(10)
		self.gainAutoLabel.setFont(font)
		self.gainAutoLabel.setObjectName("gainAutoLabel")
		self.gainBox = QtWidgets.QDoubleSpinBox(self.centralwidget)
		self.gainBox.setGeometry(QtCore.QRect(20, 430, 81, 22))
		self.gainBox.setDecimals(1)
		self.gainBox.setMinimum(0.0)
		self.gainBox.setMaximum(48.0)
		self.gainBox.setObjectName("gainBox")
		self.gainBox.setValue(30.0)
		self.gainLabel = QtWidgets.QLabel(self.centralwidget)
		self.gainLabel.setGeometry(QtCore.QRect(110, 420, 81, 31))
		font = QtGui.QFont()
		font.setPointSize(8)
		self.gainLabel.setFont(font)
		self.gainLabel.setObjectName("gainLabel")
		self.manualFPSBox = QtWidgets.QComboBox(self.centralwidget)
		self.manualFPSBox.setGeometry(QtCore.QRect(20, 310, 81, 22))
		self.manualFPSBox.setObjectName("manualFPSBox")
		self.manualFPSBox.addItem('False')
		self.manualFPSBox.addItem('True')
		self.manualFPSLabel = QtWidgets.QLabel(self.centralwidget)
		self.manualFPSLabel.setGeometry(QtCore.QRect(110, 310, 71, 16))
		font = QtGui.QFont()
		font.setPointSize(10)
		self.manualFPSLabel.setFont(font)
		self.manualFPSLabel.setObjectName("manualFPSLabel")
		self.FPSBox = QtWidgets.QSpinBox(self.centralwidget)
		self.FPSBox.setGeometry(QtCore.QRect(20, 350, 81, 22))
		self.FPSBox.setObjectName("FPSBox")
		self.FPSBox.setValue(30)
		self.FPSLabel = QtWidgets.QLabel(self.centralwidget)
		self.FPSLabel.setGeometry(QtCore.QRect(110, 350, 71, 16))

		font = QtGui.QFont()
		font.setPointSize(10)
		self.FPSLabel.setFont(font)
		self.FPSLabel.setObjectName("FPSLabel")
		self.stopButton = QtWidgets.QPushButton(self.centralwidget)
		self.stopButton.setGeometry(QtCore.QRect(160, 490, 75, 23))
		self.stopButton.setObjectName("stopButton")
		MainWindow.setCentralWidget(self.centralwidget)
		self.menubar = QtWidgets.QMenuBar(MainWindow)
		self.menubar.setGeometry(QtCore.QRect(0, 0, 234, 21))
		self.menubar.setObjectName("menubar")
		MainWindow.setMenuBar(self.menubar)
		self.statusbar = QtWidgets.QStatusBar(MainWindow)
		self.statusbar.setObjectName("statusbar")
		MainWindow.setStatusBar(self.statusbar)

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
		self.yOffsetLabel.setText(_translate("MainWindow", "y-offset"))
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
		self.manualFPSLabel.setText(_translate("MainWindow", "Manual FPS"))
		self.manualFPSLabel.adjustSize()
		self.FPSLabel.setText(_translate("MainWindow", "FPS"))
		self.stopButton.setText(_translate("MainWindow", "Stop"))
	def start_worker(self):
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
		self.thread = Worker(width = width,height = height,ox = ox,oy = oy, monitorx = monitorx,monitory = monitory,
		manualfps = manualfps,fps = fps,gainAuto = gainAuto,gain = gain)
		self.thread.start()
		self.runButton.setEnabled(False)
	def stop_worker(self):
		self.thread.stop()
		self.runButton.setEnabled(True)


if __name__ == "__main__":
	import sys
	app = QtWidgets.QApplication(sys.argv)
	MainWindow = QtWidgets.QMainWindow()
	ui = Ui_MainWindow()
	ui.setupUi(MainWindow)
	MainWindow.show()
	sys.exit(app.exec_())
