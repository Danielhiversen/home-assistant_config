"""light trigger component."""
import logging
import datetime

from homeassistant.util import dt as dt_util
import homeassistant.loader as loader
from homeassistant.components import device_tracker, light, notify
from homeassistant.helpers.event import track_state_change
from homeassistant.helpers.event import track_point_in_time
from homeassistant.const import STATE_ON, STATE_OFF, EVENT_TIME_CHANGED
from homeassistant.components.sun import STATE_ATTR_ELEVATION
from homeassistant.components import light

DOMAIN = "movement_light_gang"

DEPENDENCIES = ['group', 'light']


def setup(hass, config):
    """ Sets up the simple alarms. """
    logger = logging.getLogger(__name__)

    max_sun_elevation = 100
    light_entity_id = "light.gang"
    leave_lights_on_for_min = 1
#    keep_lights_off_for_min = 5
    trigger_sensors = ['binary_sensor.movement3', 'binary_sensor.door_soverom']

    #auto_triggered = False
    turn_off_light_listener = None

    def activate(entity_id, old_state, new_state):
        """ Called when a known person comes home. """
        state_sun = hass.states.get('sun.sun')
        if state_sun.attributes[STATE_ATTR_ELEVATION] > max_sun_elevation:
            return

        nonlocal turn_off_light_listener
        if turn_off_light_listener is not None:
            turn_off_light_listener()
            turn_off_light_listener = None
        turn_off_light_listener = track_point_in_time(hass, deactivate, dt_util.utcnow() + datetime.timedelta(minutes=leave_lights_on_for_min))

        light_state = hass.states.get(light_entity_id)
        if light_state.state == STATE_ON:
            return

        now = dt_util.now()
        if now.hour >= 22 or now.hour < 7:
            light.turn_on(hass, light_entity_id,  rgb_color = [162, 27, 0])
        elif entity_id == 'binary_sensor.movement3':
            light.turn_on(hass, light_entity_id, brightness=225)
        else:
            return

    def deactivate(now):
        light.turn_off(hass, light_entity_id)

    track_state_change(
        hass, trigger_sensors,
        activate, STATE_OFF, STATE_ON)

    return True
