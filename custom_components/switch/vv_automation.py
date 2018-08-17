import asyncio
import aiohttp

from homeassistant.helpers.event import track_state_change, track_time_change, async_track_time_change
from homeassistant.util import dt as dt_util
from homeassistant.const import CONF_ACCESS_TOKEN, SERVICE_TURN_OFF, SERVICE_TURN_ON, ATTR_ENTITY_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import PlatformNotReady

import numpy as np
import logging
import voluptuous as vol

from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string
})


async def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup component."""
    print("aa")
    import tibber
    tibber_connection = tibber.Tibber(config.get(CONF_ACCESS_TOKEN),
                                      websession=async_get_clientsession(hass))
    try:
        await tibber_connection.update_info()
        dev = []
        for tibber_home in tibber_connection.get_homes():
            await tibber_home.update_info()
            if 'hamretunet' in tibber_home.info['viewer']['home']['appNickname'].lower():
                break
    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise PlatformNotReady()
    add_devices([vv(tibber_home, hass)])


class vv(SwitchDevice):
    def __init__(self, tibber_home, hass):
        self.tibber_home = tibber_home
        self.turn_ons = []
        self.turn_offs = []
        self._state = True
        self.hass = hass
        async_track_time_change(hass, self.set_state, hour=range(24), minute=[0,15], second=6)
        async_track_time_change(hass, self._fetch_data, hour=[0], minute=[0,12], second=1)

    async def _fetch_data(self, args=None):
        print("aav")
        try:
            await self.tibber_home.update_price_info()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return

        now = dt_util.now()
        prices = np.zeros(24) + 1000
        for key, price_total in self.tibber_home.price_total.items():
            price_time = dt_util.as_local(dt_util.parse_datetime(key))
            if now.date() == price_time.date():
                prices[price_time.hour] = price_total

        min_price = 1000
        time = 6
        for k in range(6):
            price = prices[k]
            if k > 4:
                price += 1/100.0
            if price < min_price:
                min_price = price
                time = k
        turn_ons = [time]
        turn_offs = []

        time += 2
        min_price = 1000
        _time = time
        for k in range(time, 16):
            price = prices[k]
            if price < min_price:
                min_price = price
                _time = k
        print(_time, "-----aaaaa")
        if _time > 8:
            print("h2")
            time = _time
            turn_ons.append(time)
            turn_offs.append(6)
            time += 2
        print("----", turn_ons, turn_offs, time)

        large_change = False
        for rate in [1.10, 1.04, 1.03, 1.02]:
            print("rate", rate)
            for d in range(8, 1, -1):
                print(d)
                temp_turn_on = None
                temp_turn_off = None
                for _time in range(time + d, 19):
                    print(_time-d, _time)
                    if prices[_time-d] < prices[_time]:
                        continue
                    _sum = np.sum(prices[(_time - d):_time])
                    if _sum/d > rate * prices[_time]:
                        large_change = True
                        break
                if not large_change:
                    continue

                diff = 0
                for _time in range(time + d, 19):
                    _sum = np.sum(prices[(_time - d):_time])
                    print(_time, _sum/d, 1.04 * prices[_time], d, (_sum/d) / prices[_time], _sum/d - prices[_time])
                    if _sum/d - prices[_time] > diff:
                        diff = _sum/d - prices[_time]
                        temp_turn_off = _time - max(d, 3)
                        temp_turn_on = _time
                        print("time", _time)
                if temp_turn_on and temp_turn_off:
                    turn_ons.append(temp_turn_on)
                    turn_offs.append(temp_turn_off)
                    time = temp_turn_on
                    time += 2
                    print("break")
                    break
            if temp_turn_on and temp_turn_off:
                break

        print(3, turn_ons, turn_offs)

        if (len(turn_offs) < 2 and time < 17):
            max_price = 0
            _time = None
            for k in range(time, 17):
                print(k, max_price, _time)
                price = prices[k] + prices[k+1]
                if price > max_price:
                    max_price = price
                    _time = k
            if _time and prices[_time + 2] + 1/100 < prices[_time]:
                turn_offs.append(_time)
                turn_ons.append(_time + 2)
                time = _time + 3
        print(4, turn_ons, turn_offs)

        if (len(turn_offs) < 2 and time < 20) or time < 18:
            time = np.argmax(prices[time:20]) + time
            if prices[time + 1] + 1/100  < prices[time]:
                turn_offs.append(time)
                if time + 1 < 20:
                    print("---dfaf")
                    turn_ons.append(time + 1)

        turn_offs.append(20)


        print(prices)
        print(turn_ons, turn_offs)
        self.turn_ons = turn_ons
        self.turn_offs = turn_offs
        self.schedule_update_ha_state()

    async def set_state(self, args=None):
        if not self.is_on:
            return
        print(self.turn_ons, self.turn_offs)
        now = dt_util.now()
        service_data = {}
        service_data[ATTR_ENTITY_ID] = "switch.vv"
        if now.hour in self.turn_ons:
            print("turn on")
            await self.hass.services.async_call("switch", SERVICE_TURN_ON, service_data)
            return
        if now.hour in self.turn_offs:
            await self.hass.services.async_call("switch", SERVICE_TURN_OFF, service_data)
            print("turn off")

    async def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        self.hass.loop.create_task(self._fetch_data())

    @property
    def is_on(self):
        """Return true if it is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return {'turn_ons': str(self.turn_ons), 'turn_offs': str(self.turn_offs)}

    @property
    def name(self):
        """Return the name of the switch."""
        return "vv automation"

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    def turn_on(self, **kwargs):
        print(self.turn_ons, self.turn_offs)
        """Turn the switch on."""
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._state = False
        self.schedule_update_ha_state()
