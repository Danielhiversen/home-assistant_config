"""
Support for brain.fm.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.brainfm/
"""
from datetime import timedelta
from random import shuffle
from urllib.request import urlopen
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_change
from homeassistant.const import (ATTR_ATTRIBUTION, CONF_EMAIL, CONF_PASSWORD)
from homeassistant.util import Throttle

REQUIREMENTS = ['brainfm==0.2.1']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=24)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor."""
    import brainfm
    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    client = brainfm.Connection(email, password)

    dev = []
    for sensor_type in ["sleep"]:#, "relax", "focus"]:
        dev.append(BrainfmSensor(sensor_type, client, hass))
    add_devices(dev)

class BrainfmSensor(Entity):
    """Representation of a brain.fm sensor."""

    def __init__(self, sensor_type, client, hass):
        """Initialize the sensor."""
        self._sensor_type = sensor_type
        self._client = client
        self._state = None
        self._channel_name = None
        self._web_adress = None

        def _update(now=None):
            stations = client.get_stations()
            shuffle(stations)
            for station in stations:
                print(station)
                if self._sensor_type in station["canonical_name"]:
                    station_id = station["station_id"]
                    print(client.get_station(station_id=station_id))
                    while client.get_station(station_id=station_id)['playable'] == 0:
                        sub_stations = client.get_stations_by_id(parent_id=station_id)
                        shuffle(sub_stations)
                        station_id = sub_stations[0]['station_id']
                        for sub_station in sub_stations:
                            if '8hours' in station["canonical_name"]:
                                station_id = sub_station['station_id']
                                break
                    try:
                        token_data = client.get_token(station_id=station_id)
                        self._web_adress = "https://stream.brain.fm/?tkn=" + token_data["session_token"]
                        mp3file = urlopen(self._web_adress)
                        with open('/home/dahoiv/.homeassistant/www/sleep.mp3','wb') as output:
                            output.write(mp3file.read())
                        self._state = token_data["name"]
                        break
                    except:
                        continue
        _update(now=None)
        track_time_change(hass, _update, hour=9, minute=14, second=36)
        
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
            "Web adress": self._web_adress,
        }


