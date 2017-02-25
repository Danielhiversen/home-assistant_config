"""
Support for Xiaomi binary sensors.

Developed by Rave from Lazcad.com
"""
import logging
import asyncio
import pickle
import binascii
import requests

from PIL import Image
import io
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.decomposition import PCA
from subprocess import PIPE, Popen, TimeoutExpired
import os
import shutil
import signal

from homeassistant.const import ATTR_ENTITY_PICTURE, EVENT_HOMEASSISTANT_START
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.config import get_default_config_dir
from homeassistant.loader import get_component
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)
DOMAIN = "ml"
STANDARD_SIZE = (300, 200)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform the setup for Xiaomi devices."""
    add_devices([MlSensor(hass, config.get("name"), config.get("pca_path"), config.get("knn_path"))])


class MlSensor(BinarySensorDevice):
    """Representation of a MlSensor."""

    def __init__(self, hass, name, pca_path, knn_path):
        """Initialize the MlSensor."""
        with open(get_default_config_dir() + pca_path, 'rb') as handle:
            self._pca = pickle.load(handle)
        with open(get_default_config_dir() + knn_path, 'rb') as handle:
            self._knn = pickle.load(handle)
        self._name = name
        self._state = None
        self._running = False
        self._hass = hass
        hass.services.register(DOMAIN, "check_state", self.poll_status)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        print("here", self._state)
        return self._state

    @property
    def should_poll(self):
        return False

    def poll_status(self, service=None):
        img_path = "/home/dahoiv/ml/tmp.jpg"
        cmd = 'avconv -i rtsp://admin:admin@192.168.1.106/11 -vframes 1 -stimeout 0.1 -y -loglevel error ' + img_path
        with Popen(cmd,
                   shell=True,
                   stdout=PIPE,
                   preexec_fn=os.setsid) as process:
            try:
                result = process.communicate(timeout=10)[0]
                _LOGGER.debug("Finished recording")
            except TimeoutExpired:
                # send signal to the process group
                os.killpg(process.pid, signal.SIGINT)
                _LOGGER.error("Killed recording")
                return
        self.process_image(img_path)
        now_str = dt_util.now().strftime("%Y_%b_%d_%H%M%S")
        if self._state:
            shutil.move(img_path, "/home/dahoiv/ml/1/" + now_str + ".jpg")
        else:
            shutil.move(img_path, "/home/dahoiv/ml/0/" + now_str + ".jpg")

    def process_image(self, image):
        if self._running:
            return
        self._running = True
        image = flatten_image(matrix_image(image))
        state = self._knn.predict(self._pca.transform(image))[0]
        self._state = (state == 1)
        print(self._state)
        self._hass.bus.fire('ml', {
            'entity_id': self.entity_id,
            'state': str(state)
        })
        self._running = False
        self.schedule_update_ha_state()

def matrix_image(image):
    "opens image and converts it to a m*n matrix"
    print(image)
    image = Image.open(image)
    crop = 300
    w, h = image.size
    image.crop((0, crop, w, h-crop))
    image = image.resize(STANDARD_SIZE)
    image = list(image.getdata())
    image = np.array(image)
    return image

def flatten_image(image):  
    """
    takes in a n*m numpy array and flattens it to 
    an array of the size (1,m*n)
    """
    s = image.shape[0] * image.shape[1]
    image_wide = image.reshape(1,s)
    return image_wide[0]
