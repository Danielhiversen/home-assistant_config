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

from collections import deque

DOMAIN = "effect_control"
MAX_CONS = 3000

DEPENDENCIES = ['group']


def setup(hass, config):
    """ Sets up the simple alarms. """
    logger = logging.getLogger(__name__)
    effect = deque(maxlen=5)
    effect_usage = [("vvb", 1000, 'switch.vvb'), ("varmepumpe", 1000, 'switch.sensibo')]

    def keep_effects(entity_id, old_state, new_state):
        print(new_state.state)
        effect.append(float(new_state.state))

    def activate(entity_id, old_state, new_state):
        now = dt_util.now()
        if len(effect) < 2 or now.minute < 5:
            return

        print(effect)
        print(sum(effect)/ len(effect), new_state.state, now.minute)

        avg_effect = 0 if len(effect) < 1 else sum(effect) / len(effect)
        est_total_cons = float(new_state.state)*1000 + avg_effect * (60 - now.minute) * 60/3.6
        print("est total cons, ", est_total_cons)
        def _update_est_cons():
            print('est_total_cons', est_total_cons)
            hass.states.set('sensor.est_cons', est_total_cons, {'unit_of_measurement': 'Wh'})
        
        if now.minute < 5:
            _update_est_cons()
            return

        if est_total_cons < 0.9 * MAX_CONS:
            print(effect_usage)
            for name, dev_effect, entity_id in reversed(effect_usage):
                # if entity_id is off
                # est_total_cons += dev_effect * (60 - now.minute) / 60
                print("turn on ", name)
                if est_total_cons > 0.9 * MAX_CONS:
                    # _update_est_cons()
                    # print('est_total_cons', est_total_cons)
                    # effect.clear()
                    return
                # call tur on

        if est_total_cons < MAX_CONS:
            _update_est_cons()
            return

        for name, dev_effect, entity_id in effect_usage:
            # if entity_id is on
            # check if we need to turn off device imediately or if we can wait
            print("turn off ", name)
            est_total_cons -= dev_effect * (60 - now.minute) / 60
            if est_total_cons < MAX_CONS:
                print('est_total_cons', est_total_cons)
                # _update_est_cons()
                # effect.clear()
                return

        #

    track_state_change(hass, 'sensor.houtly_cons', activate)
    track_state_change(hass, 'sensor.total_effect', keep_effects)

    return True
