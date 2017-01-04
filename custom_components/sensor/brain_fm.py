"""
Support for brain.fm.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.brainfm/
"""
from datetime import timedelta
from random import shuffle
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import (ATTR_ATTRIBUTION, CONF_EMAIL, CONF_PASSWORD)
from homeassistant.util import Throttle

REQUIREMENTS = ['brainfm==0.1.2']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=2)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor."""
    import brainfm
    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    client = brainfm.Connection(email, password)

    dev = []
    for sensor_type in ["sleep", "relax", "focus"]:
        dev.append(BrainfmSensor(sensor_type, client))
    add_devices(dev)

class BrainfmSensor(Entity):
    """Representation of a brain.fm sensor."""

    def __init__(self, sensor_type, client):
        """Initialize the sensor."""
        self._sensor_type = sensor_type
        self._client = client
        self._state = None
        self._channel_name = None
        # self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'brainfm {}'.format(self._sensor_type)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            "Channel name": self._channel_name,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from brain_fm."""
        stations = self._client.get_stations()
        shuffle(stations)
        for station in stations:
            if self._sensor_type in station["canonical_name"]:
                station_id = int(station["station_id"])
                self._client.get_station(station_id=station_id)
                try:
                    token_data = self._client.get_token(station_id=station_id)
                    self._state = "https://stream.brain.fm/?tkn" + token_data["session_token"]
                    self._channel_name = token_data["name"]
                    return
                except:
                    continue
