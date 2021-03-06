#!/usr/bin/python3

import PyIndi
import time
import sys
import numpy as np
import io
import os
import logging
from astropy.io import fits
from PIL import Image
import cv2
from datetime import datetime

import config

binning  = 1
exposure = 0.01 # init exposure
logging.basicConfig(filename='/var/log/allsky.log',level=logging.DEBUG)

minute   = datetime.now().strftime("%Y-%m-%d_%H-%M")

class IndiClient(PyIndi.BaseClient):
	device = None

	def __init__(self):
		super(IndiClient, self).__init__()
	def newDevice(self, d):
		logging.debug('Новое устройство: '+ d.getDeviceName());
		self.device = d
		pass
	def newProperty(self, p):
		pass
	def removeProperty(self, p):
		pass
	def newBLOB(self, bp):
		global exposure

		fit = fits.open( io.BytesIO( bp.getblobdata() ) )
		hdu = fit[0]

		# avg only center (30 - 70% for x and y)
		avg = np.mean(hdu.data[int(hdu.header['NAXIS1'] * 0.3):int(hdu.header['NAXIS1'] * .7),
			int(hdu.header['NAXIS2'] * 0.3):int(hdu.header['NAXIS2'] * .7)])

		logging.info('Получил кадр выдержкой {} сек. со средним {}'.format(exposure, avg))

		if (avg > config.ccd['avgMin'] and avg < config.ccd['avgMax']) or ( (exposure == config.ccd['expMin']) and (avg > config.ccd['avgMin']) ) or ( (exposure == config.ccd['expMax']) and (avg < config.ccd['avgMax']) ):
			# запись
			rgb = cv2.cvtColor(hdu.data, cv2.COLOR_BayerGB2BGR)
			img = Image.fromarray(rgb, 'RGB')
#			if binning == 1:
#				img = Image.fromarray(rgb, 'RGB')
#			else:
#				img = Image.fromarray(hdu.data)

			global minute

			img.save('/var/www/html/snap/'+ minute +'.jpg')
			logging.info('Файл '+ minute +' записан. Жду следующей минуты')
			
			if os.path.exists('/var/www/html/current.jpg'):
				os.remove('/var/www/html/current.jpg')
			os.symlink('/var/www/html/snap/'+ minute +'.jpg', '/var/www/html/current.jpg')

			while True:
				now = datetime.now().strftime("%Y-%m-%d_%H-%M")
				if now != minute:
					break;
				time.sleep(1)

			minute = now

		else:
			# подбор выдержки
			if avg > 250:
				exposure = config.ccd['expMin']
			else:
				if avg > config.ccd['avgMax']:
					exposure /= 1.1
				else:
					exposure *= 1.1

				if exposure < config.ccd['expMin']:
					exposure = config.ccd['expMin']
				if exposure > config.ccd['expMax']:
					exposure = config.ccd['expMax']

		global ccd_exposure

		ccd_exposure[0].value = exposure
		self.sendNewNumber(ccd_exposure)

		pass
	def newSwitch(self, svp):
		pass
	def newNumber(self, nvp):
#		print("newNumber ", nvp.name)
		pass
	def newText(self, tvp):
		pass
	def newLight(self, lvp):
		pass
	def newMessage(self, d, m):
		pass
	def serverConnected(self):
		pass
	def serverDisconnected(self, code):
		pass

# connect the server
indiclient = IndiClient()
indiclient.setServer("localhost", 7624)

if (not(indiclient.connectServer())):
	logging.warning('Не найден INDI-сервер камеры')
	sys.exit(1)

logging.debug('INDI нашёл')

ccd = indiclient.getDevice(config.ccd['name'])
while not(ccd):
	time.sleep(0.5)
	ccd = indiclient.getDevice(config.ccd['name'])

logging.debug('CCD нашёл')

ccd_connect = ccd.getSwitch("CONNECTION")
while not(ccd_connect):
	time.sleep(0.5)
	ccd_connect = ccd.getSwitch("CONNECTION")

logging.debug('CCD подключил')

if not(ccd.isConnected()):
	ccd_connect[0].s=PyIndi.ISS_ON  # the "CONNECT" switch
	ccd_connect[1].s=PyIndi.ISS_OFF # the "DISCONNECT" switch
	indiclient.sendNewSwitch(ccd_connect)

#ccd_frame = ccd.getNumber("CCD_FRAME")
#while not(ccd_frame):
#	time.sleep(0.5)
#	ccd_frame = ccd.getNumber("CCD_FRAME")
#
#width  = int(ccd_frame[2].value)
#height = int(ccd_frame[3].value)
#print("Нашёл размер кадра: {}x{}".format(width, height))

ccd_exposure = ccd.getNumber("CCD_EXPOSURE")
while not(ccd_exposure):
	time.sleep(0.5)
	ccd_exposure = ccd.getNumber("CCD_EXPOSURE")

logging.debug('EXPOSURE нашёл')

ccd_temp = ccd.getNumber("CCD_TEMPERATURE")
while not(ccd_temp):
	time.sleep(0.5)
	ccd_temp = ccd.getNumber("CCD_TEMPERATURE")

logging.debug('TEMPERATURE нашёл')

ccd_binning = ccd.getNumber("CCD_BINNING")
while not(ccd_binning):
	time.sleep(0.5)
	ccd_binning = ccd.getNumber("CCD_BINNING")

logging.debug('BINNING нашёл')

ccd_binning[0].value = binning
ccd_binning[1].value = binning
indiclient.sendNewNumber(ccd_binning)

logging.info('BINNING {} отправил'.format(binning))

ccd_exposure[0].value = exposure
indiclient.sendNewNumber(ccd_exposure)

logging.info('EXPOSURE отправил')

indiclient.setBLOBMode(PyIndi.B_ALSO, config.ccd['name'], "CCD1")

while ccd:
	time.sleep(10)