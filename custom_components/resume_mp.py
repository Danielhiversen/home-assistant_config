"""

"""
import logging
import time

from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, EVENT_HOMEASSISTANT_START
from homeassistant.util import dt as dt_util
from homeassistant.helpers import extract_domain_configs
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import track_state_change, track_time_change
from homeassistant.components.sensor.rest import RestData
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA, MEDIA_TYPE_MUSIC, ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE, DOMAIN as DOMAIN_MP)
from homeassistant.config import get_default_config_dir

import homeassistant.components.input_select as input_select


# The domain of your component. Should be equal to the name of your component.
DOMAIN = "resume_mp"

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)

def setup(hass, config):
    """Setup the ."""
    def _resume_mp(config):    
        media_player = "media_player." + config.get("media_player","")
        resume_state = None
        resume = False

        def _state_change(entity_id=None, old_state=None, new_state=None):
            nonlocal resume_state, resume
            content_id = hass.states.get(media_player).attributes.get("media_content_id", [])
            if resume_state and new_state.state != 'playing' and resume:
                print(resume_state)
                data = {
                    ATTR_MEDIA_CONTENT_ID: resume_state.attributes.get("media_content_id", ""),
                    ATTR_MEDIA_CONTENT_TYPE: "audio/mp3",
                    ATTR_ENTITY_ID: media_player,
                }
                resume_state = None
                resume = True
                hass.services.call(DOMAIN_MP, SERVICE_PLAY_MEDIA, data)
            elif (new_state.state == 'playing' and
                  ("nrk.no" in content_id or "nrk-mms-live.online.no" in content_id)):
                resume_state = new_state
            elif (resume_state and new_state.state == 'playing' and
                  "tts_proxy"  in content_id):
                resume = True
            else:
                resume_state = None
                resume = False
        track_state_change(hass, media_player, _state_change)

    for config_key in extract_domain_configs(config, DOMAIN):
        _resume_mp(config[config_key])
    return True
