"""

"""
import logging
from homeassistant.util import slugify
from homeassistant.helpers.event import track_state_change
from homeassistant.helpers.event import track_time_change
from homeassistant.components import input_boolean
from homeassistant.components import input_number
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

    for config_i in config[DOMAIN]:
        target_entity =  config_i.get('target')
        name =  config_i.get('name', DOMAIN + '_' + slugify(target_entity))
        keep_on = config_i.get('keep_on', False)
        config = _setup(hass, config, target_entity, name, keep_on)

    input_number.async_setup(hass, config)
    input_boolean.async_setup(hass, config)

    return True

def _setup(hass, config, target_entity, name, keep_on):
    """Setup example component."""
    object_id_enable = DOMAIN + '_' + slugify(name) + '_enable'
    object_id_hour = DOMAIN + '_' + slugify(name) + '_hour'
    object_id_temp = DOMAIN + '_' + slugify(name) + '_temp'

    def activate(now):
        if hass.states.get('input_boolean.' + object_id_enable).state == 'off':
            return
        if not str(now.hour) == str(int(float(hass.states.get('input_number.' + object_id_hour).state))):
            return

        climate.set_temperature(hass, hass.states.get('input_number.' + object_id_temp).state, entity_id='climate.'+target_entity)
        if not keep_on:
            hass.states.set('input_boolean.' + object_id_enable, 'off')
        
    _config = config['input_boolean']
    _config[object_id_enable] = {'name': 'Enable', 'initial': False}
    print(config['input_boolean'])
    config['input_boolean'].append(_config)
    print(config['input_boolean'])

    _config = config['input_number']
    _config[object_id_hour] = {'name': 'Hour', 'initial': 15, 'min': 7, 'max': 23, 'step': 1}
    _config[object_id_temp] = {'name': 'Temp', 'initial': 20, 'min': 13, 'max': 22, 'step': 1}
    config['input_number'] = _config

    #_config = {'platform': 'template', 'sensors': { object_id_hour: {'value_template': '{{ states("input_number.' + object_id_hour + '") | round(0) }}'}}}
    #config['sensor'] = _config
    #sensor.setup(hass, config)

    group.Group.create_group(hass,name, ['input_boolean.' + object_id_enable, 'input_number.' + object_id_hour, 'input_number.' + object_id_temp])

    track_time_change(hass, activate, minute=0, second=2)

    def enable(entity_id, old_state, new_state):
        hass.states.set('input_boolean.' + object_id_enable, 'on')

    track_state_change(hass, ['input_number.' + object_id_hour, 'input_number.' + object_id_temp], enable)

    return config
