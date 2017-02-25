"""
"""
import asyncio
import logging
import time
import feedparser
from html.parser import HTMLParser
from endomondo import MobileApi
# pip install git+https://github.com/Danielhiversen/sports-tracker-liberator
from bs4 import BeautifulSoup
from xml.parsers.expat import ExpatError
import requests
import xmltodict
from datetime import timedelta

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.util import dt as dt_util
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import track_state_change, track_time_change
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.components.sensor.rest import RestData


# The domain of your component. Should be equal to the name of your component.
DOMAIN = "news"

# List of component names (string) your component depends upon.
# We depend on group because group will be loaded after all the components that
# initialize devices have been setup.
DEPENDENCIES = ['group', ]

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)

class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.strict = False
        self.convert_charrefs= True
        self.fed = []
    def handle_data(self, d):
        self.fed = d
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

def num2str(num):
  num = float(num)
  if (num - int(num)) == 0:
      num = int(num)
  return str(round(num, 1)).replace("."," komma ")


def setup(hass, config):
    """Setup component."""

    yr_precipitation = {}
    nowcast_precipitation = None
    news_rss = []
    workout_text = None
    last_workout_time = None
    auth_token=config[DOMAIN].get("token")
    endomondo = MobileApi(auth_token=auth_token)

    def _get_text(message_type=None):
        news = ""
        now = dt_util.now()
        if message_type == 2:
            news = news + "Sov godt "
        elif now.hour < 4:
            news = news + "God natt "
        elif now.hour < 10:
            news = news + "God morgen "
        elif now.hour < 18:
            news = news + "Hei "
        else:
            news = news + "God kveld "

        persons= []
        state = hass.states.get('group.tracker')
        if state:
            tracker = state.attributes.get('entity_id')
            for person in tracker:
                person = hass.states.get(person)
                if not person:
                    continue
                if not person.state == 'home':
                    continue
                persons.append(person.attributes.get('friendly_name'))
        if len(persons) > 1:
            persons.insert(-1,"og")
        news = news + ' '.join(persons) + '. '

        if message_type == 0:
            news = news + "Velkommen hjem. "

        nonlocal workout_text
        if workout_text and 'daniel' in news.lower():
            news = news + workout_text
            workout_text = None

        if yr_precipitation:
            res = 0
            for time, value in yr_precipitation.items():
#                print(time, value)
                if time < now and time > now - timedelta(hours=3):
                    res += value
            precipitation = num2str(res)
            news = news + "De siste 3 timene har det kommet " + precipitation + " mm nedbør "

        temp = hass.states.get('sensor.ute_veranda_temperature')
        if temp and temp.state != "unknown":
            news = news + "og temperaturen er nå " + num2str(temp.state) + " grader ute. "
        if nowcast_precipitation > 0:
            news = news + "Den neste timen er det ventet " + num2str(nowcast_precipitation) + " mm nedbør. "

        if message_type == 2:
            alarm_state = hass.states.get('automation.wake_me_up')
            if alarm_state and alarm_state.state == "on":
                time_to_alarm = float(hass.states.get('sensor.relative_alarm_time').state)
                alarm_time_hour = int(time_to_alarm / 60)
                alarm_time_min = int(time_to_alarm - alarm_time_hour*60)
                news = news + "Vekkerklokken ringer om " + str(alarm_time_hour) + " timer og " + str(alarm_time_min) + " minutter."

        if message_type in [1, 2]:
            return news

        news = news + "Her kommer siste nytt:  "
        if False:
            _news_rss = news_rss
        else:
            _news_rss = news_rss[:2]
        for case in _news_rss:
            news = news + case + " "
        return news
            
    @asyncio.coroutine
    def _read_news(service):
        message_type = int(service.data.get("message_type", -1))
        news = _get_text(message_type)

        data = {}
        if service and service.data.get(ATTR_ENTITY_ID):
            data[ATTR_ENTITY_ID] = service.data.get(ATTR_ENTITY_ID)
        data['message'] = news
        data['cache'] = False

        autoradio = True if service.data.get("entity_id_radio") else False
        yield from hass.services.async_call('tts', 'google_say', data, blocking=autoradio)
        return
        if not autoradio:
            return
        # if vekking:

        data = {}
        data[ATTR_ENTITY_ID] = service.data.get("entity_id_radio")
        if service.data.get("radio_option"):
            data['option'] = service.data.get("radio_option")
        else:
            data['option'] = "P3"
        hass.services.call('input_select', 'select_option', data)

    def _rss_news(time=None):
        nonlocal news_rss
        resource = "https://www.nrk.no/nyheter/"
        method = 'GET'
        payload = auth = headers = None
        rest = RestData(method, resource, auth, headers, payload, verify_ssl=True)
        rest.update()
        news_rss = []
        if rest.data is None:
            return
        raw_data = BeautifulSoup(rest.data, 'html.parser')
        prew_text = ""
        for raw_text in raw_data.select("p"):
            text = strip_tags(str(raw_text))
            if text == prew_text:
                continue
            prew_text = text
            news_rss.append(text)
            if len(news_rss) > 2:
                break
        _feed = feedparser.parse("http://www.yr.no/sted/Norge/S%C3%B8r-Tr%C3%B8ndelag/Trondheim/Trondheim/varsel.xml")
        summary = _feed.feed.get("summary")
        if summary is None:
            return
        news_rss.append("Værvarsel " + strip_tags(summary).replace("<strong>","").replace("</strong>",""))

    def _yr_precipitation(now=None):
        url = "http://api.met.no/weatherapi/nowcast/0.9/"
        urlparams = {'lat': str(hass.config.latitude),
                    'lon': str(hass.config.longitude)}

        if not now:
            now = dt_util.utcnow()

        try:
            with requests.Session() as sess:
                response = sess.get(url, params=urlparams)
        except requests.RequestException:
            track_point_in_utc_time(hass, _yr_precipitation, now + timedelta(minutes=2))
            return
        if response.status_code != 200:
            track_point_in_utc_time(hass, _yr_precipitation, now + timedelta(minutes=2))
            return
        text = response.text

        nonlocal nowcast_precipitation
        nonlocal yr_precipitation
        nowcast_precipitation = 0
        try:
            data = xmltodict.parse(text)['weatherdata']
            model = data['meta']['model']
            if '@nextrun' not in model:
                model = model[0]
            nextrun = dt_util.parse_datetime(model['@nextrun'])
            nextrun = nextrun if (nextrun > now) else now + timedelta(minutes=2)
            for time_entry in data['product']['time']:
                loc_data = time_entry['location']
                time = dt_util.parse_datetime(time_entry['@to'])
                #print(loc_data['precipitation']['@value'])
                #print(dt_util.as_local(time))

                value = float(loc_data['precipitation']['@value'])
                if time > now and time < now + timedelta(hours=1):
                    nowcast_precipitation += value
                yr_precipitation[time] = value

            for time in yr_precipitation.copy().keys():
                if time < now - timedelta(hours=3):
                    del yr_precipitation[time]

        except (ExpatError, IndexError) as err:
            track_point_in_utc_time(hass, _yr_precipitation, now + timedelta(minutes=2))       
            return
        track_point_in_utc_time(hass, _yr_precipitation, nextrun + timedelta(seconds=2))

    def _workout_text(now=None):
        nonlocal workout_text
        nonlocal last_workout_time
        last_workout = endomondo.get_workouts()[0]
        if not now:
            now = dt_util.utcnow()
        now = dt_util.as_local(now)

        if (now - dt_util.as_local(last_workout.start_time)).total_seconds() > 3600*24:
            workout_text = None
            return

        last_workout_time = last_workout.start_time
        workout_text = "Bra jobbet Daniel! I dag har du trent i " + str(int(last_workout.duration/3600)) + " timer og "  + str(int((last_workout.duration - int(last_workout.duration/3600)*3600)/60)) + " minutter. Distanse " + num2str(last_workout.distance) + " kilometer. Du har forbrent " + num2str(last_workout.burgers_burned) + " burgere. \n"
        if last_workout.live:
            track_point_in_utc_time(hass, _workout_text, now + timedelta(seconds=30))

    _rss_news()
    _workout_text()
    _yr_precipitation()
    track_time_change(hass, _yr_precipitation, minute=[31], second=0)
    track_time_change(hass, _rss_news, minute=[10, 26, 41, 56], second=0)
    track_time_change(hass, _workout_text, minute=[11, 26, 41, 56], second=0)

    hass.services.register(DOMAIN, "read_news", _read_news)
    print(_get_text())
    workout_text = None

    return True
