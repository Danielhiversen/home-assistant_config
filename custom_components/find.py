# encoding=utf8
"""
"""
import logging

from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_START
from homeassistant.util import dt as dt_util
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import track_state_change, track_time_change
from homeassistant.helpers.event import track_point_in_utc_time, async_track_point_in_utc_time
from homeassistant.components.sensor.rest import RestData


# The domain of your component. Should be equal to the name of your component.
DOMAIN = "find"

# List of component names (string) your component depends upon.
# We depend on group because group will be loaded after all the components that
# initialize devices have been setup.
DEPENDENCIES = ['group', ]

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup component."""

    def daniel(service):
    
        print(hass.states.get('zone.home'))
        print(hass.states.get('zone.jobb').state)
        print(hass.states.get('device_tracker.daniel'))
        print(hass.states.get('sensor.phone_speed'))
        print(hass.states.get('sensor.phone_to_home').state)
        print(hass.states.get('sensor.phone_to_home_car').state)
        print(hass.states.get('binary_sensor.daniel_position').state)
     #   try:
        if hass.states.get('device_tracker.daniel').state == 'home' or float(hass.states.get('sensor.phone_to_home').state) < 2:
            msg = "Daniel er hjemme."
        elif hass.states.get('device_tracker.daniel').state.lower() == 'jobb':
            msg = "Daniel er på jobb."
        elif float(hass.states.get('sensor.phone_to_home').state) < 60:
            if hass.states.get('binary_sensor.daniel_position').state == 'off':
                msg = "Daniel er på vei hjem og kommer til å bruke {} minutter dersom han sykler".format(hass.states.get('sensor.phone_to_home').state)
            else:
                msg = "Daniel er {} kilometer unna".format(str(round(float(hass.states.get('sensor.phone_to_home_car').distance) / 1000), 2))
        else:
            msg = "Daniel er et stykke unna, og kommer til å bruke {} minutter hit med bil.".format(hass.states.get('sensor.phone_to_home').state)
      #  except:
      #      msg = "Jeg vet ikke hvor Daniel er. Beklager"

        msg = str(msg)#.encode('utf-8')
        data = {}
        data[ATTR_ENTITY_ID] = "media_player.stue"
        data['message'] = msg
        data['cache'] = False
        
        #_LOGGER.error(msg)
        print(msg.encode("utf-8"))
        hass.services.call('tts', 'google_say', data)


    hass.services.register(DOMAIN, "daniel", daniel)
    return True
