"""
"""
import datetime
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from dateutil import tz

from homeassistant.const import CONF_ACCESS_TOKEN, EVENT_HOMEASSISTANT_START, ATTR_ENTITY_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

# The domain of your component. Should be equal to the name of your component.
DOMAIN = "heating"

# List of component names (string) your component depends upon.
# We depend on group because group will be loaded after all the components that
# initialize devices have been setup.
DEPENDENCIES = ['group', ]

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup component."""

    import tibber
    tibber_home = None

    last_update = dt_util.now() - datetime.timedelta(hours=50)
    prices = []
    dates = []
    time_disable = None

    async def load_data(now=None):
        nonlocal last_update, tibber_home, prices, dates
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
        dates = []
        for key, price_total in tibber_home.price_total.items():
            prices.append(price_total*100)
            dates.append(dt_util.as_local(dt_util.parse_datetime(key)))

        if len(dates) > 24 or dt_util.now().hour < 12:
            last_update = dt_util.now()
            await heating()

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

    async def heating(_=None):
        if time_disable and (dt_util.now() - time_disable).hour < 3:
            return
        set_temp = new_set_temp = float(hass.states.get('input_number.set_temp').state)

        next_state, next_time_diff = finding_next_state([hass.states.get('input_datetime.stop_time_1'),
                                                         hass.states.get('input_datetime.stop_time_2'),
                                                         hass.states.get('input_datetime.start_time_1'),
                                                         hass.states.get('input_datetime.start_time_2')
                                                         ])
        if '_1' in next_state.entity_id:
            comf_temp = float(hass.states.get('input_number.comfort_temp_1').state)
        elif '_2' in next_state.entity_id:
            comf_temp = float(hass.states.get('input_number.comfort_temp_2').state)
        else:
            _LOGGER.error("Unknown entity")
            return

        print(next_state, next_time_diff, prices.index(max(prices)))

        if 'stop_time' in next_state.entity_id:
            if next_time_diff < 30:
                new_set_temp = comf_temp - 1
            elif next_time_diff < 60:
                new_set_temp = comf_temp - 0.5
            elif dates[prices.index(max(prices))] == dt_util.now().hour:
                new_set_temp = comf_temp - 1
            else:
                new_set_temp = comf_temp
        elif 'start_time' in next_state.entity_id:
            new_set_temp = comf_temp - min(5,  round(next_time_diff / 60 * 2) / 2)
        if hass.states.get('input_boolean.away').state:
            new_set_temp = 10

        if new_set_temp == set_temp:
            return

        print(new_set_temp)
        data = {ATTR_ENTITY_ID: 'input_number.set_temp', 'value': new_set_temp}
        hass.async_add_job(hass.services.async_call('input_number', 'set_value', data))

    def temp_disable(service):
        nonlocal time_disable
        time_disable = dt_util.now()
        data = {ATTR_ENTITY_ID: 'input_number.set_temp', 'value': 12}
        hass.async_add_job(hass.services.async_call('input_number', 'set_value', data))

    async_track_time_change(hass, heating, second=12)
    async_track_time_change(hass, load_data, hour=[0], minute=range(0, 60, 5), second=8)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, load_data)
    hass.services.register(DOMAIN, "temporarly_disable", temp_disable)

    return True
