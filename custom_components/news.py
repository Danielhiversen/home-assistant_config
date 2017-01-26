"""
"""
import logging
import time
import feedparser
from html.parser import HTMLParser
from endomondo import MobileApi
# pip install git+https://github.com/Danielhiversen/sports-tracker-liberator
from bs4 import BeautifulSoup
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
    """Setup example component."""

    yr_precipitation = []
    nowcast_precipitation = None
    news_rss = []
    workout_text = None
    last_workout_time = None
    auth_token=config[DOMAIN].get("token")
    endomondo = MobileApi(auth_token=auth_token)

    def _get_text(message_type=None):
        news = ""
        now = dt_util.now()
        if now.hour < 10:
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

        if message_type == "0":
            news = news + "Velkommen hjem. "

        nonlocal workout_text
        if workout_text and 'daniel' in news.lower():
            news = news + workout_text
            workout_text = None

        if yr_precipitation:
            precipitation = num2str(sum(yr_precipitation))
            news = news + "De siste 3 timene har det kommet " + precipitation + " mm nedbør "
        temp = hass.states.get('sensor.ute_veranda_temperature')
        if temp and temp.state != "unknown":
            news = news + "og temperaturen er nå " + num2str(temp.state) + " grader ute. "
        if nowcast_precipitation:
            precipitation = num2str(nowcast_precipitation)
            news = news + "Den neste timen er det ventet " + precipitation + " mm nedbør. "

        news = news + "Her kommer siste nytt:  "
        for case in news_rss:
            news = news + case + " "
        return news
            
    def _read_news(service=None):
        message_type = None
        if service:
            message_type = service.data.get("message_type")
        news = _get_text(message_type)
        data = {}
        if service and service.data.get(ATTR_ENTITY_ID):
            data[ATTR_ENTITY_ID] = service.data.get(ATTR_ENTITY_ID)
        data['message'] = news
        data['cache'] = False
        print(data)
        hass.services.call('tts', 'google_say', data)

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
        news_rss.append("Værvarsel " + strip_tags(_feed.feed.summary).replace("<strong>","").replace("</strong>",""))

    def _yr_precipitation(now=None):
        state = hass.states.get('sensor.yr_precipitation').state
        nonlocal yr_precipitation
        yr_precipitation.append(float(state))
        if len(yr_precipitation) > 3:
            yr_precipitation.pop(0)

    def _yr_precipitation2(now=None):
        url = "http://api.met.no/weatherapi/nowcast/0.9/"
        urlparams = {'lat': str(hass.config.latitude),
                    'lon': str(hass.config.longitude)}

        try:
            with requests.Session() as sess:
                response = sess.get(url, params=urlparams)
        except requests.RequestException:
            return
        if response.status_code != 200:
            return
        text = response.text

        nonlocal nowcast_precipitation
        try:
            data = xmltodict.parse(text)['weatherdata']
            model = data['meta']['model']
            if '@nextrun' not in model:
                model = model[0]
            nextrun = dt_util.parse_datetime(model['@nextrun'])
            for time_entry in data['product']['time']:
                loc_data = time_entry['location']
                nowcast_precipitation = float(loc_data['precipitation']['@value'])
        except (ExpatError, IndexError) as err:
            track_point_in_utc_time(hass, _workout_text, now + timedelta(minutes=2))       
            return
        track_point_in_utc_time(hass, _workout_text, nextrun + timedelta(seconds=2))

    def _workout_text(now=None):
        nonlocal workout_text
        nonlocal last_workout_time
        last_workout = endomondo.get_workouts()[0]
        if not now:
            now = dt_util.utcnow()
        now = dt_util.as_local(now)
        if last_workout_time == last_workout.start_time:
            return
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
    _yr_precipitation2()
    track_time_change(hass, _yr_precipitation, minute=[31], second=0)
    track_time_change(hass, _rss_news, minute=[10, 26, 41, 56], second=0)
    track_time_change(hass, _workout_text, minute=[11, 26, 41, 56], second=0)

    hass.services.register(DOMAIN, "read_news", _read_news)
    print(_get_text())
    workout_text = None

    return True
