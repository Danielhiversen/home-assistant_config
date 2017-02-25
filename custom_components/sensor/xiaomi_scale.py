"""
Install PyBluez as described here: https://home-assistant.io/components/device_tracker.bluetooth_le_tracker/
sudo setcap cap_net_raw,cap_net_admin+eip /home/dahoiv/home-assistant/venv/bin/python3


"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_MAC

import struct

REQUIREMENTS = ['pybluez==0.22']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=""): cv.string,
})

BLE_TEMP_UUID = '01c80f10a14d180d161d18'
BLE_TEMP_HANDLE = 0x24
SKIP_HANDLE_LOOKUP = True
CONNECT_TIMEOUT = 30


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sensor."""
    import bluetooth._bluetooth as bluez # low level bluetooth wrappers.

    name = config.get(CONF_NAME)
    mac = config.get(CONF_MAC)
    dev_id = 0

    try:
        sock = bluez.hci_open_dev(dev_id)
    except:
        return False

    old_filter = sock.getsockopt(bluez.SOL_HCI, bluez.HCI_FILTER, 14)
    SCAN_RANDOM = 0x01
    OWN_TYPE = SCAN_RANDOM
    SCAN_TYPE = 0x01

    cmd_pkt = struct.pack("<BB", 0x01, 0x00)
    bluez.hci_send_cmd(sock, 0x08, 0x000C, cmd_pkt)
    print("----")
    add_devices([XiaomiScale(name, mac, sock)])
    print("----2")


class XiaomiScale(Entity):
    """Representation of a scale sensor."""

    def __init__(self, name, mac, sock):
        """Initialize the scale."""
        self._mac = mac.lower()
        self._name = name
        self._sock = sock
        self._state = None
        self._unit_of_measurement = None

    @property
    def name(self):
        """Return the name of the scale."""
        return self._name

    @property
    def state(self):
        """Return the state of the scale."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from the scale."""
        import bluetooth._bluetooth as bluez # low level bluetooth wrappers.
        old_filter = self._sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)

        flt = bluez.hci_filter_new()
        bluez.hci_filter_all_events(flt)
        bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
        self._sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, flt)
        for i in range(100):
            pkt = self._sock.recv(255)
            ptype, event, plen = struct.unpack("BBB", pkt[:3])
            subevent, = struct.unpack("B", pkt[3:4])
            pkt = pkt[4:]
            if event == 0x3e and subevent == 0x02:
                mac = ':'.join('%02x'%i for i in struct.unpack("<BBBBBB", pkt[3:9][::-1]))
                print(i, mac)
                if mac.lower() == self._mac:
                    uuid = ''.join('%02x'%i for i in struct.unpack("B"*16, pkt[-22: -6]))
                    print(mac, uuid, ptype)
                    if self._validate_data(uuid): break
        self._sock.setsockopt(bluez.SOL_HCI, bluez.HCI_FILTER, old_filter)

    def _validate_data(self, uuid):
        measunit = uuid[22:24]	
        measured = int((uuid[26:28] + uuid[24:26]), 16) * 0.01
        unit = None
        if measunit.startswith(('03', 'b3')): unit = 'lbs'
        if measunit.startswith(('12', 'b2')): unit = 'jin'  
        if measunit.startswith(('22', 'a2')): unit = 'Kg' ; measured = measured / 2

        if unit is None: return False

        self._unit_of_measurement = unit
        self._state = round(measured, 1)
        print(measured)
        return True
