"""
"""
import datetime
import logging
import pickle
import os

from homeassistant.const import CONF_ACCESS_TOKEN, EVENT_HOMEASSISTANT_START, ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change, track_state_change, track_time_change, track_state_change
from homeassistant.util import dt as dt_util

# The domain of your component. Should be equal to the name of your component.
DOMAIN = "heating_bedroom"

# List of component names (string) your component depends upon.
# We depend on group because group will be loaded after all the components that
# initialize devices have been setup.
DEPENDENCIES = ['group', ]

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)

DATA_PATH = 'heat_time_soverom.pickle'

def setup(hass, config):
    """Setup component."""

    import tibber

    tibber_home = None

    start_time = dt_util.now()
    last_update = dt_util.now() - datetime.timedelta(hours=50)
    prices = []
    cheap_hours = []
    heat_time = {}
    heater_start_time = None
    curr_temp_start = None

    if os.path.isfile(hass.config.path(DATA_PATH)):
        with open(hass.config.path(DATA_PATH), 'rb') as f:
            heat_time = pickle.load(f)

    async def load_data(now=None):
        nonlocal last_update, tibber_home, prices, cheap_hours
        if dt_util.now() - last_update < datetime.timedelta(hours=10):
            return

        if tibber_home is None:
            tibber_connection = tibber.Tibber(config[DOMAIN].get(CONF_ACCESS_TOKEN),
                                              websession=async_get_clientsession(hass))
            await tibber_connection.update_info()
            for tibber_home in tibber_connection.get_homes():
                await tibber_home.update_info()
                if 'hamretunet' in tibber_home.info['viewer']['home']['appNickname'].lower():
                    break

        await tibber_home.update_price_info()
        prices = []
        for key, price_total in tibber_home.price_total.items():
            prices.append(price_total*100)

        cheap_hours = []
        for k in range(1, 24-1):
            if (prices[k - 1] > prices[k] + 1 and prices[k]*1.15 < prices[k+1]) or prices[k]*1.23 < prices[k+1]:
                cheap_hours.append(k)
        
        print("cheap soverom", cheap_hours)

    def finding_next_state(states):

        now = dt_util.now()
        next_state = None
        next_time_diff = 24*60
        
        for state in states:
            time_diff = (state.attributes['hour'] - now.hour) * 60 + (state.attributes['minute'] - now.minute)                  
            if time_diff <= 0:
                time_diff = 24*60 + time_diff
            if time_diff < next_time_diff:
                next_state = state
                next_time_diff = time_diff

        return next_state, next_time_diff
    
    def save_heat_time(entity_id, old_state, new_state):
        nonlocal heat_time, heater_start_time, curr_temp_start
        now = dt_util.now()
        try:
            if now - hass.states.get('sensor.soverom_temperature').last_updated < datetime.timedelta(minutes=15):
                curr_temp = float(hass.states.get('sensor.soverom_temperature').state)
            else:
                heater_start_time = None
                return
        except (ValueError, AttributeError):
            heater_start_time = None
            return

        try:
            if float(old_state.state) < 15 and float(new_state.state) > 15:
                heater_start_time = now
                curr_temp_start = curr_temp
                return
        except ValueError:
            return

        if heater_start_time is None or curr_temp - curr_temp_start < 1 or (now - heater_start_time).total_seconds()/60 < 15:
            return

        key = 'heat_time1' if now.hour > 8 else 'heat_time2'

        new_heat_time = ((now - heater_start_time).total_seconds()/60) / (curr_temp - curr_temp_start)
        all_heat_time = heat_time.get(key, [])
        all_heat_time = all_heat_time[-min(len(all_heat_time), 10):]
        all_heat_time.append(new_heat_time)
        heat_time[key] = all_heat_time
        heater_start_time = None

        with open(hass.config.path(DATA_PATH), 'wb') as f:
            pickle.dump(heat_time, f)
    
    async def heating(_=None):
        nonlocal heat_time, heater_start_time, curr_temp_start
        turn_on_fan = False
        now = dt_util.now()

        if hass.states.get('input_boolean.heating_soverom').state == 'off':
            print("off soverom", hass.states.get('input_boolean.heating_soverom').state)
            return
            
        set_temp = new_set_temp = float(hass.states.get('climate.ovn2').attributes.get('temperature'))
        print(set_temp, "-----")

        states = [hass.states.get('input_datetime.sovetid')]
        spare_modus = hass.states.get('input_boolean.spare_modus')
        if spare_modus is None or spare_modus.state == 'off': 
            states.append(hass.states.get('input_datetime.wakeup'))

        next_state, next_time_diff = finding_next_state(states)
        comf_temp = float(hass.states.get('input_number.comfort_temp_soverom').state)

        curr_temp = None
        try:
            if now - hass.states.get('sensor.soverom_temperature').last_updated < datetime.timedelta(minutes=15):
                curr_temp = float(hass.states.get('sensor.soverom_temperature').state)
        except (ValueError, AttributeError):
            pass
        if curr_temp is None:
            try:
                curr_temp = float(hass.states.get('climate.ovn2').attributes.get('current_temperature'))
            except (ValueError, AttributeError):
                return
        if curr_temp is None:
            data = { "entity_id": "climate.soverom"}
            await hass.services.async_call('climate', 'turn_off', data)
            return

        if now.hour > 15:
            key = 'heat_time1'
            min_time = 25
        else:
            key = 'heat_time2'
            min_time = 25
        print(heat_time)
        all_heat_time = heat_time.get(key, [20])
        current_heat_time = sum(all_heat_time) / len(all_heat_time)

        print("soverom", new_set_temp)
        
        if next_time_diff < (comf_temp - curr_temp) * current_heat_time or next_time_diff < min_time or (new_set_temp == comf_temp and next_time_diff < 3*60):
            new_set_temp = comf_temp
        elif (now.hour in cheap_hours or prices[now.hour] < 10/100) and now.minute > 30 and (comf_temp - curr_temp) * current_heat_time > 90:
            new_set_temp = max(min(curr_temp + 1 , new_set_temp), comf_temp)
        elif prices[now.hour] in [min(prices), min(prices[7:21])] and now.minute > 25:
            new_set_temp = max(min(curr_temp + 1 , new_set_temp), comf_temp - 2)    
        else:
            new_set_temp = comf_temp - 4

        print("soverom", new_set_temp, set_temp, curr_temp, comf_temp, next_time_diff, (comf_temp - curr_temp) * current_heat_time)
        if new_set_temp >= comf_temp and now.hour > 16 and 5 < next_time_diff < 50:
                turn_on_fan = True

        if new_set_temp != set_temp:
            print("soverom ----")
            data = { "entity_id": "climate.ovn2", "temperature": new_set_temp}
            await hass.services.async_call('climate', 'set_temperature', data)
            data = { "entity_id": "climate.ovn2"}
            await hass.services.async_call('climate', 'turn_on', data)
            
        fan_mode = hass.states.get('climate.stue').attributes.get('fan_mode')
        if turn_on_fan:
            if fan_mode != 'on':
                data = { "entity_id": "climate.ovn2", "fan_mode": 'on'}
                await hass.services.async_call('climate', 'set_fan_mode', data)
        else:
            if fan_mode != 'off':
                data = { "entity_id": "climate.ovn2", "fan_mode": 'off'}
                await hass.services.async_call('climate', 'set_fan_mode', data)
        data = { "entity_id": "climate.soverom"}
        await hass.services.async_call('climate', 'turn_on', data)
        if next_time_diff < 40:
            new_set_temp = comf_temp
        if new_set_temp == (comf_temp - 4):
            new_set_temp = comf_temp - 3

        data = { "entity_id": "climate.soverom", "temperature": new_set_temp+0.5}
        await hass.services.async_call('climate', 'set_temperature', data)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, load_data)
    async_track_time_change(hass, heating, second=12, minute=range(0, 60, 1))
    async_track_time_change(hass, load_data, hour=[0, 5, 20], minute=range(0, 60, 12), second=8)
    track_state_change(hass, 'sensor.soverom_ovn_heating', save_heat_time)

    return True
