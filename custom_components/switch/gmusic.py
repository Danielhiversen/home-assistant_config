"""
"""
import asyncio
import logging
import time
import random
from datetime import timedelta

from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, EVENT_HOMEASSISTANT_START
from homeassistant.util import dt as dt_util
from homeassistant.components.switch import (
    ENTITY_ID_FORMAT, SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import track_state_change
from homeassistant.components.sensor.rest import RestData
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, MEDIA_TYPE_MUSIC, ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE, DOMAIN as DOMAIN_MP)

import homeassistant.components.input_select as input_select


# The domain of your component. Should be equal to the name of your component.
DOMAIN = "gmusic"

DEPENDENCIES = ['group', ]

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)

def setup(hass, config):
    """Setup example component."""


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Gmusic switch."""
    add_devices([GmusicComponent(hass, config)])
    return True

    
class GmusicComponent(SwitchDevice):
    def __init__(self, hass, config):
        from gmusicapi import Mobileclient

        self.hass = hass
        self._api = Mobileclient()
        logged_in = self._api.login(config['user'],config['password'], config['device_id'])
        if not logged_in:
            _LOGGER.error("Failed to log in")	
            return False
        self._input_select_entity = "input_select." + config["input_select"]
        self._media_player = "input_select." + config["media_player"]
        self._entity_ids = []
        self._playing = False
        self._playlists = []
        self._tracks = []
        self._next_track_no = 0
        self._playlist_to_index = {}
        self._unsub_tracker = None
        self._name = "Google music"
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, self._update_playlist)

    @property
    def icon(self):
        return ' mdi:music-note'

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._playing

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def turn_on(self, **kwargs):
        """Fire the on action."""
        self._play()

    def turn_off(self, **kwargs):
        """Fire the off action."""
        self._turn_off_media_player()

    def _update_playlist(self, now=None):
        self._playlists = self._api.get_all_user_playlist_contents()
        self._playlist_to_index = {}
        idx = -1
        for playlist in self._playlists:
            idx = idx + 1
            name = playlist.get('name','')
            if len(name) < 1:
                continue
            self._playlist_to_index[name] = idx
        data = {"options": list(self._playlist_to_index.keys()), "entity_id": self._input_select_entity}
        self.hass.services.call(input_select.DOMAIN, input_select.SERVICE_SET_OPTIONS, data)

    def _turn_off_media_player(self):
        #if self._entity_ids:
        data = {ATTR_ENTITY_ID: self._entity_ids}
        self.hass.services.call(DOMAIN_MP, SERVICE_TURN_OFF, data, blocking=True)
        self._playing = False
        self.update_ha_state()
        if self._unsub_tracker is not None:
            self._unsub_tracker()
            self._unsub_tracker = None

    def _update_entity_ids(self):
        new_state = self.hass.states.get(self._media_player).state
        _entity_ids = "media_player." + new_state
        if self.hass.states.get(_entity_ids) is None:
            _LOGGER.error("%s is not a valid media player.", new_state)
            return False
        self._entity_ids = _entity_ids 
        return True

    def _next_track(self, entity_id=None, old_state=None, new_state=None):
        if not self._playing:
            return
        if self._next_track_no >= len(self._tracks):
            self._next_track_no = 0
        track = self._tracks[self._next_track_no]
        if track is None:
            self._turn_off_media_player() 
            return
        try:
            url = self._api.get_stream_url(track['trackId'])
        except:
            track_no = track_no + 1
            _LOGGER.error("Faield to get track")	
            return _next_track()
        data = {
            ATTR_MEDIA_CONTENT_ID: url,
            ATTR_MEDIA_CONTENT_TYPE: "audio/mp3",
        }

        data[ATTR_ENTITY_ID] = self._entity_ids
        self.hass.services.call(DOMAIN_MP, SERVICE_PLAY_MEDIA, data)
        self._next_track_no = self._next_track_no + 1
        self._playing = True
        self.update_ha_state()
        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_START, self._next_track)

    def _play(self):
        option = self.hass.states.get(self._input_select_entity).state
        if not self._update_entity_ids():
            return
        idx = self._playlist_to_index.get(option)
        if idx is None:
            self._turn_off_media_player()
            return

        self._tracks = self._playlists[idx]['tracks']
        random.shuffle(self._tracks)
        self._next_track_no = 0
        self._playing = True
        self._unsub_tracker = track_state_change(self.hass, self._entity_ids, self._next_track, from_state='playing', to_state='idle')
        self._next_track()

