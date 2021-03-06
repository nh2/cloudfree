import matplotlib.pyplot as plt
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import io
import binascii
import urllib

import numpy as np
import datetime
import os
import os.path

DATADIR = "data"
OUTPUTDIR = "output"
MAXDAYS = 100

if not os.path.exists(DATADIR):
  os.makedirs(DATADIR)
if not os.path.exists(OUTPUTDIR):
  os.makedirs(OUTPUTDIR)

def dayDeltaBack(day, delta):
  return (day + datetime.timedelta(days=delta)).strftime("%Y-%m-%d")


def getPhoto(day, zoom, tile):
  zoom = str(zoom)
  fileName = os.path.join(DATADIR, day) +"-" + zoom + "-" + str(tile[0]) + str(tile[1]) + "photo.jpg"
  tile = "/" + str(tile[0]) + "/" + str(tile[1])

  if not os.path.isfile(fileName):
    content = urllib.urlopen("http://map1.vis.earthdata.nasa.gov/wmts-geo/MODIS_Terra_CorrectedReflectance_TrueColor/default/" + day + "/EPSG4326_250m/"+ zoom + tile + ".jpg").read()
    with open(fileName, "wb") as f:
      f.write(content)

  return Image.open(fileName)

def getCloud(day, zoom, tile):
  zoom = str(zoom)
  fileName = os.path.join(DATADIR, day) +"-" + zoom + "-" + str(tile[0]) + str(tile[1]) + "cloud.png"
  tile = "/" + str(tile[0]) + "/" + str(tile[1])

  if not os.path.isfile(fileName):
    url = "http://map1.vis.earthdata.nasa.gov/wmts-geo/MODIS_Terra_Cloud_Top_Temp_Day/default/" + day + "/EPSG4326_2km/"+ zoom + tile + ".png"
    content = urllib.urlopen(url).read()
    with open(fileName, "wb") as f:
      f.write(content)

  return Image.open(fileName)

def getNoData(day, zoom, tile):
  zoom = str(zoom)
  fileName = os.path.join(DATADIR, day) +"-" + zoom + "-" + str(tile[0]) + str(tile[1]) + "nodata.png"
  tile = "/" + str(tile[0]) + "/" + str(tile[1])

  if not os.path.isfile(fileName):
    content = urllib.urlopen("http://map1.vis.earthdata.nasa.gov/wmts-geo/MODIS_Terra_Data_No_Data/default/" + day + "/EPSG4326_250m/"+ zoom + tile + ".png").read()
    with open(fileName, "wb") as f:
      f.write(content)

  return Image.open(fileName)


# Saves the images
def getImageData(startDay, nrDays, zoom, tile):
  days = [dayDeltaBack(startDay, x) for x in xrange(nrDays)]
  photo = lambda x: getPhoto(x, zoom, tile)
  cloud = lambda x: getCloud(x, zoom, tile)
  noData = lambda x: getNoData(x, zoom, tile)
  return map(photo, days), map(cloud, days), map(noData, days)

def growMask(mask, leftRight, upDown):
  maskBuffer = np.array(mask)

  # res = np.roll(maskBuffer, -5, axis=1) # right
  # maskBuffer |= res

  for x in xrange(-leftRight, 0):
    res = np.roll(maskBuffer, x, axis=1) # left
    res[:, x:] = 0
    maskBuffer |= res

  for x in xrange(1, leftRight+1):
    res = np.roll(maskBuffer, x, axis=1) # right
    res[:, :x] = 0
    maskBuffer |= res

  for y in xrange(-upDown, 0):
    res = np.roll(maskBuffer, y, axis=0) # up
    res[y:,:] = 0
    maskBuffer |= res

  for y in xrange(0, upDown+1):
    res = np.roll(maskBuffer, y, axis=0) # down
    res[:y,:] = 0
    maskBuffer |= res

  return maskBuffer

"""
  tile: tuple of ints (a,b)
  zoom level: 1 to 6
  date: the date from which to start the pictures
"""

def getData(tile, date, zoom):
  # get all the data at once
  photos, clouds, noDatas = getImageData(date, MAXDAYS, zoom, tile)
  print tile
  workingBuffer = np.zeros(shape=(512, 512, 3), dtype=np.uint8)

  for i in xrange(MAXDAYS):
    print i
    photo = photos[i]
    cloud = clouds[i]
    noData = noDatas[i]

    rgb = np.asarray(photo.convert('RGB'))
    a = np.asarray(cloud.convert('RGBA').split()[3]) # 0 -> transparent, 0xff -> cloud

    # TODO: once the bug in PIL is fixed, use RGBA and transparent instead of black
    # https://mail.python.org/pipermail/image-sig/2011-February/006693.html
    # noDataMask = np.asarray(noData.convert('RGBA').split()[3]) # 0 -> transparent, 0xff -> noData

    noDataMask = (np.asarray(noData.convert('RGB').split()[0]) != 0) * 0xff # 0 -> transparent, 0xff -> noData

    # Due to difference in resolution in the cloud image and the mask and photo images
    # we need to increase the size of the masks by 2 pixels in each direction
    # We do this by replicating the mask to the left and right and create a slightly
    # bigger mask

    # print a
    gapMask = growMask(noDataMask, 2, 4)   # 0xff -> gap pixels
    aMask = a
    # aMask = growMask(a, 1, 1)

    # print gapMask.shape
    # print type(gapMask[0,0])
    # bla = gapMask.astype(np.uint8)
    # xx = bla[:, np.newaxis] + np.zeros((512, 512, 3))
    # print xx.shape
    # print type(xx[0,0,0])
    # print "xx.tobytes"
    # print xx.tobytes
    # Image.fromarray(xx).save('gap.jpg')
    # Image.fromarray(np.uint8(bla)).save('gap%d.jpg' % i)

    workingBuffer = np.where(((a | aMask | gapMask) == 0)[:, :, np.newaxis], rgb, workingBuffer)
    # print workingBuffer.shape
    # print type(workingBuffer[0,0,0])

    # save output
    fileName = os.path.join(OUTPUTDIR, "output") + "-" + dayDeltaBack(date, i) + "-" + str(zoom) + "-" + str(tile[0]) + "-" + str(tile[1]) + ".jpg"
    Image.fromarray(workingBuffer).save(fileName)


import subprocess
# Copy data to make the video

# This will not work if you do not pass the zoom index and how many days to take
def copyData(date):

  if not os.path.exists('output/video'):
    os.makedirs('output/video')

  for i in xrange(365):
    fileName = os.path.join(OUTPUTDIR, "output") + "-" + dayDeltaBack(date, i) +".jpg"
    bashCommand = "cp " + fileName + " " + os.path.join(OUTPUTDIR, "video")
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output = process.communicate()[0]
    print output

def copyDataFull(date, zoom, tile):
  import shutil
  if os.path.exists('output/video'):
    shutil.rmtree('output/video')

  os.makedirs('output/video')

  for i in xrange(MAXDAYS):
    fileName = os.path.join(OUTPUTDIR, "output") + "-" + dayDeltaBack(date, i) + "-" + str(zoom) + "-" + str(tile[0]) + "-" + str(tile[1]) + ".jpg"
    bashCommand = "cp " + fileName + " " + os.path.join(OUTPUTDIR, "video")
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output = process.communicate()[0]
    print output


def makeVideoAfterCopy():
  import shutil
  if os.path.exists('gen'):
    shutil.rmtree('gen')
  if not os.path.exists('gen'):
    os.makedirs('gen')
  symLinksCommand = "x=0; for i in $(find output/video -name '*.jpg' | sort); do counter=$(printf %04d $x); (cd gen && ln -s ../\"$i\" \"$counter\".jpg); x=$(($x+1)); done"
  process = subprocess.Popen(["bash", "-c", symLinksCommand])
  output = process.communicate()[0]
  print output

  if os.path.exists('test.mp4'):
    os.remove('test.mp4')
  makeVideoCommand = "avconv -r 3 -i gen/%04d.jpg -b:v 1000k test.mp4"
  print makeVideoCommand
  process = subprocess.Popen(makeVideoCommand.split())
  output = process.communicate()[0]
  print output
  os.chdir('..')



def makeVideo(date, zoom, tile):
  getData(tile, date, zoom)
  copyDataFull(date, zoom, tile)
  makeVideoAfterCopy()

date = datetime.datetime(year=2013, month=01, day=01)
# date = datetime.datetime.today() - 100
# The maximum number of days used to get the cloud free images

# getData((1,1), date, 2)

# copyData(date)
# makeVideo()

zoom = 2
tile = (1,1)

makeVideo(date, zoom, tile)
