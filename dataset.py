import torch
import torch.nn as nn
import torch.utils.data as data

import os
import numpy as np
import gdal
from urllib import request
from PIL import Image
import geohash2
from tqdm import tqdm as tqdm

from common import *


def download_per_pic(lng, lat, zoom_level, size, api_key, save_path, saveAs=None):
    base_url = 'https://maps.googleapis.com/maps/api/staticmap?center={y},{x}&zoom={z}&size={s}x{s}&maptype={t}&key={k}&format=png8'
    url = base_url.format(x = lng, y = lat, z=zoom_level, s=size+42, t='satellite', k=api_key)
    request.urlretrieve(url, '{}.png'.format(save_path))
    
    # remove water mark
    img = Image.open('{}.png'.format(save_path)).convert('RGB')
    img = np.asarray(img)[21:-21, 21:-21, :]
    os.remove('{}.png'.format(save_path))

    # save
    img = Image.fromarray(img)
    img.save('{}.png'.format(save_path))
    
    return np.array(img, dtype=np.float)

        
class lonlatDataset(data.Dataset):
    def __init__(self, lonlatList, imgSavePath, APIKEY):
        self.coordList = lonlatList
        self.imgSavePath = imgSavePath
        self.APIKEY = APIKEY

    def __len__(self):
        return len(self.coordList)

    def __getitem__(self, index):     
        lon, lat = self.coordList[index][0], self.coordList[index][1]
        ghash = geohash2.encode(lon, lat, precision=12)
        
        if self.imgSavePath is not None:
            savePath = self.imgSavePath + "/" + ghash
        else:
            savePath = "./" + ghash
        
        if os.path.exists(savePath+".png"):
            img = np.array(Image.open(savePath+".png"), dtype=np.float)
        else:
            img = download_per_pic(lon, lat, zoom_level=18, size=320, api_key=self.APIKEY, save_path=savePath)
        
        img /= img.max()
        return torch.as_tensor(img.transpose(2, 0, 1), dtype=torch.float)


class lonlatDataset_local(data.Dataset):
    def __init__(self, lonlatList, imgPath, patchSize=320):
        self.coordList = lonlatList

        self.patchSize = patchSize
        self.imgDS = gdal.Open(imgPath)
        self.imgW, self.imgH = self.imgDS.RasterXSize, self.imgDS.RasterYSize
        # self.imgArray = self.imgDS.ReadAsArray(0, 0, self.imgW, self.imgH)

    def __len__(self):
        return len(self.coordList)

    def __getitem__(self, index):     
        lon, lat = self.coordList[index][0], self.coordList[index][1]
        geox, geoy = lonlat2geo(self.imgDS, lon, lat)
        imgx, imgy = geo2imagexy(self.imgDS, geox, geoy)
        ulx, uly = int(imgx - (self.patchSize//2)), int(imgy - (self.patchSize//2))

        img = self.imgDS.ReadAsArray(ulx, uly, self.patchSize, self.patchSize)
        # img = self.imgArray[:, ulx:ulx+self.patchSize, uly:uly+self.patchSize]
        return torch.as_tensor(img/max(img.max(), 0.1), dtype=torch.float)

    
def getLonLatDataLoader(lonlatList, APIKEY, local=False, imgSavePath=r"./imgTemp", BSize=4, nWorkers=4, pinMem=True):
    if local:
        data_set = lonlatDataset_local(lonlatList, imgPath=imgSavePath, patchSize=320)
    else:
        data_set = lonlatDataset(lonlatList, imgSavePath=imgSavePath, APIKEY=APIKEY)
        if not os.path.exists(imgSavePath):
            os.mkdir(imgSavePath)
    return data.DataLoader(data_set, batch_size=BSize, shuffle=False, num_workers=nWorkers, pin_memory=pinMem)

