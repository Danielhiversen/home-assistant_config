"""
"""
import datetime
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from dateutil import tz

from homeassistant.const import CONF_ACCESS_TOKEN, EVENT_HOMEASSISTANT_START
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

# The domain of your component. Should be equal to the name of your component.
DOMAIN = "tibber_prices"

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

    prices = []
    dates = []

    async def load_data(now=None):
        nonlocal tibber_home, prices, dates

        def skip():
            if not dates:
                return False
            for _date in dates:
                if (dt_util.now() - datetime.timedelta(days=1)).date == _date.date:
                    return False
            for _date in dates:
                if (dt_util.now() + datetime.timedelta(days=1)).date == _date.date and dt_util.now().hour >= 12:
                    return True
            return False

        if skip():
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

        if len(dates) > 24 or dt_util.utcnow().hour < 12:
            await generate_fig_call()

    async def generate_fig_call(_=None):
        hass.add_job(generate_fig)

    def generate_fig(_=None):
        now = dt_util.now()

        hour = now.hour
        dt = datetime.timedelta(minutes=now.minute)

        plt.style.use('ggplot')
        xFmt = mdates.DateFormatter('%H', tz=tz.gettz('Europe/Berlin'))
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.grid(which='major', axis='x', linestyle='-', color='gray', alpha=0.25)
        plt.tick_params(axis="both", which="both", bottom=False, top=False,
                        labelbottom=True, left=False, right=False, labelleft=True)
        ax.plot([dates[hour]+dt, dates[hour]+dt], [min(prices)-3, max(prices)+3], 'r', alpha=0.35, linestyle='-')
        ax.plot(dates, prices, '#039be5')

        ax.fill_between(dates, 0, prices, facecolor='#039be5', alpha=0.25)
        plt.text(dates[hour]+dt, prices[hour], str(round(prices[hour], 1)), fontsize=14)
        min_length = 5 if len(dates) > 24 else 3
        last_hour = -1 * min_length
        for _hour in range(1, len(prices)-1):
            if abs(_hour - last_hour) < min_length or abs(_hour - hour) < min_length:
                continue
            if (prices[_hour - 1] > prices[_hour] < prices[_hour + 1]) \
                    or (prices[_hour - 1] < prices[_hour] > prices[_hour + 1]):
                last_hour = _hour
                plt.text(dates[_hour], prices[_hour],
                         str(round(prices[_hour], 1)) + "\n{:02}".format(_hour%24),
                         fontsize=14, va='bottom')

        ax.set_xlim((dates[0] - datetime.timedelta(minutes=3), dates[-1] + datetime.timedelta(minutes=3)))
        ax.set_ylim((min(prices)-0.5, max(prices)+0.5))
        ax.set_facecolor('white')
        # import plotly.plotly as py
        ax.xaxis.set_major_formatter(xFmt)
        fig.autofmt_xdate()
        fig.savefig('/tmp/prices.png')  # file name in your local system
        plt.close(fig)
        plt.close('all')

    async_track_time_change(hass, generate_fig_call, minute=[1, 11, 21, 31, 41, 51], second=15)
    async_track_time_change(hass, load_data, hour=[12, 13, 14, 0, 8], minute=range(0, 60, 5), second=8)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, load_data)
    return True
