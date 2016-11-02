"""

"""
import logging

from homeassistant.helpers.event import track_state_change
from homeassistant.helpers.event import track_time_change
from homeassistant.components import input_boolean
from homeassistant.components import input_slider
from homeassistant.components import group
from homeassistant.components import climate
from homeassistant.components import sensor



# The domain of your component. Should be equal to the name of your component.
DOMAIN = "temp_control"

# List of component names (string) your component depends upon.
# We depend on group because group will be loaded after all the components that
# initialize devices have been setup.
DEPENDENCIES = ['group', ]

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup example component."""
    target_entity =  config[DOMAIN].get('target')
    name =  config[DOMAIN].get('name', DOMAIN + ' ' + target_entity)

    object_id_enable = DOMAIN + '_' + target_entity + '_enable'
    object_id_hour = DOMAIN + '_' + target_entity + '_hour'
    object_id_temp = DOMAIN + '_' + target_entity + '_temp'

    def activate(now):
        if hass.states.get('input_boolean.' + object_id_enable).state == 'off':
            return
        if not str(now.hour) == str(int(float(hass.states.get('input_slider.' + object_id_hour).state))):
            return

        climate.set_temperature(hass, hass.states.get('input_slider.' + object_id_temp).state, entity_id='climate.'+target_entity)
        hass.states.set('input_boolean.' + object_id_enable, 'off')
        
    _config = config['input_boolean']
    _config[object_id_enable] = {'name': 'Enable', 'initial': False}
    config['input_boolean'] = _config
    input_boolean.setup(hass, config)

    _config = config['input_slider']
    _config[object_id_hour] = {'name': 'Hour', 'initial': 15, 'min': 7, 'max': 23, 'step': 1}
    _config[object_id_temp] = {'name': 'Temp', 'initial': 20, 'min': 17, 'max': 22, 'step': 0.5}
    config['input_slider'] = _config
    input_slider.setup(hass, config)

    #_config = {'platform': 'template', 'sensors': { object_id_hour: {'value_template': '{{ states("input_slider.' + object_id_hour + '") | round(0) }}'}}}
    #config['sensor'] = _config
    #sensor.setup(hass, config)

    group.Group(hass,name, ['input_boolean.' + object_id_enable, 'input_slider.' + object_id_hour, 'input_slider.' + object_id_temp])

    track_time_change(hass, activate, minute=0, second=2)

    def enable(entity_id, old_state, new_state):
        hass.states.set('input_boolean.' + object_id_enable, 'on')

    track_state_change(hass, ['input_slider.' + object_id_hour, 'input_slider.' + object_id_temp], enable)

    return True

