"""
Event parser and human readable log generator.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/resotre_states/
"""
import logging

import voluptuous as vol

import homeassistant.util.dt as dt_util
from homeassistant.components import recorder
from homeassistant.const import (EVENT_HOMEASSISTANT_START, ATTR_ENTITY_ID,
                                 STATE_OFF, STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF)
from homeassistant.components import (input_boolean, input_select, group, climate,
                                      input_slider, automation, switch, light)

DOMAIN = "restore_states"
DEPENDENCIES = ['recorder', 'frontend']

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {}
}, extra=vol.ALLOW_EXTRA)

EVENT_LOGBOOK_ENTRY = 'logbook_entry'

GROUP_BY_MINUTES = 15


def setup(hass, config):
    """Restore states from database."""

    def _restore_states(service):
        """Restore states."""
        run = recorder.run_information(dt_util.utcnow())
        if run is None:
            return

        from sqlalchemy import and_, func

        states = recorder.get_model('States')
        most_recent_state_ids = recorder.query(
            func.max(states.state_id).label('max_state_id')
        )

        most_recent_state_ids = most_recent_state_ids.group_by(
            states.entity_id).subquery()

        query = recorder.query('States').join(most_recent_state_ids, and_(
            states.state_id == most_recent_state_ids.c.max_state_id))

        states = recorder.execute(query)

        data = {ATTR_ENTITY_ID: 'group.all_automations'}
        hass.services.call('homeassistant', SERVICE_TURN_OFF, data, True)

        last_services = []
        for state in states:
            if state.domain == group.DOMAIN:
                continue
            if state.domain == input_slider.DOMAIN:
                data = {ATTR_ENTITY_ID: state.entity_id,
                        input_slider.ATTR_VALUE: state.state}
                service = input_slider.SERVICE_SELECT_VALUE
            elif state.domain == input_select.DOMAIN:
                data = {ATTR_ENTITY_ID: state.entity_id,
                        input_select.ATTR_OPTION: state.state}
                service = input_select.SERVICE_SELECT_OPTION
            elif state.domain == climate.DOMAIN:
                data = {ATTR_ENTITY_ID: state.entity_id,
                        climate.ATTR_TEMPERATURE: state.attributes.get('temperature')}
                service = climate.SERVICE_SET_TEMPERATURE
            elif (state.domain in [input_boolean.DOMAIN, automation.DOMAIN]):
                  #or state.attributes.get('assumed_state')):
                data = {ATTR_ENTITY_ID: state.entity_id}
                if state.state == STATE_OFF:
                    service = SERVICE_TURN_OFF
                if state.state == STATE_ON:
                    service = SERVICE_TURN_ON
                else:
                    continue
                if state.domain == light.DOMAIN:
                   continue
                if state.domain == automation.DOMAIN:
                   last_services.append((state.domain, service, data))
                   continue
            elif (state.domain in [switch.DOMAIN]):
                   continue
            else:
                continue
            if hass.states.get(state.entity_id) is None:
                continue
            hass.services.call(state.domain, service, data, True)

        for (domain, service, data) in last_services:
            hass.services.call(domain, service, data, True)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _restore_states)
    return True
