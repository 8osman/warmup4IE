"""Platform that offers a connection to a warmup device."""
import logging
from typing import Optional, List

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice

from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_HOME,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)

from homeassistant.const import (ATTR_TEMPERATURE, PRECISION_TENTHS, TEMP_CELSIUS, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_ROOM)

from homeassistant.exceptions import PlatformNotReady

import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.entity import async_generate_entity_id

from homeassistant.util.temperature import convert as convert_temperature


_LOGGER = logging.getLogger(__name__)

import voluptuous as vol
	
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_HVAC_HEAT = [HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF]
SUPPORT_PRESET = [PRESET_AWAY, PRESET_HOME]

CONF_LOCATION = 'location'
CONF_TARGET_TEMP = 'target_temp'

DEFAULT_NAME = 'warmup4ie'
DEFAULT_TARGET_TEMP = 20

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_LOCATION): cv.string,
    vol.Required(CONF_ROOM): cv.string,
    vol.Optional(CONF_TARGET_TEMP,
                 default=DEFAULT_TARGET_TEMP): vol.Coerce(float),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo climate devices."""
    _LOGGER.info("Setting up platform for Warmup component")
    name = config.get(CONF_NAME)
    user = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    location = config.get(CONF_LOCATION)
    room = config.get(CONF_ROOM)
    target_temp = config.get(CONF_TARGET_TEMP)

    from warmup4ie import Warmup4IEDevice
    device = Warmup4IEDevice(user, password, location, room,
                             target_temp)
    if device is None or not device.setup_finished:
        raise PlatformNotReady

    add_entities(
            [Warmup(hass, name, device)])


class Warmup(ClimateDevice):
    """Representation of a Warmup device."""

    mode_map = {'prog':HVAC_MODE_AUTO, 'fixed':HVAC_MODE_HEAT, 'off':HVAC_MODE_OFF}

    def __init__(self, hass, name, device):
        """Initialize the climate device."""
        _LOGGER.info("Setting up Warmup component")
        self._name = name
        self._hvac_mode = HVAC_MODE_AUTO
        self._hvac_list = [HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_AUTO]
        self._unit_of_measurement = TEMP_CELSIUS
        self._on = True
        self._away_mode = False
        self._device = device
        self._support_flags = SUPPORT_FLAGS | SUPPORT_PRESET_MODE
        self._awaymodeLastState = HVAC_MODE_OFF

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS
		
    @property
    def hvac_mode(self):
        """Return current HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return available HVAC modes."""
        return self._hvac_list

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.get_current_temmperature()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.get_target_temmperature()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._device.get_target_temperature_low()

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._device.get_target_temperature_high()
		
    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if self._away_mode:
            return PRESET_AWAY
        return PRESET_HOME

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return [PRESET_HOME, PRESET_AWAY]

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away_mode
		
    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._on

    @property
    def current_hvac(self):
        """Return current operation ie. heat, auto, off."""
        return self._current_hvac_mode

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._device.set_new_temperature(kwargs.get(ATTR_TEMPERATURE))

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away_mode = True

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away_mode = False
			
    def set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
            self._device.set_temperature_to_manual()
        elif hvac_mode == HVAC_MODE_AUTO:
            self._hvac_mode = HVAC_MODE_AUTO
            self._device.set_temperature_to_auto()
        elif hvac_mode == HVAC_MODE_OFF:
            self._hvac_mode = HVAC_MODE_OFF
            self._device.set_location_to_off()
        else:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return
        # Ensure we update the current operation after changing the mode
        self.schedule_update_ha_state()
		
		
		
    def set_preset_mode(self, preset_mode):
        if self._on == False: 
            return
        if preset_mode == PRESET_AWAY:
            if self._away_mode == False:
                self._awaymodeLastState = self._hvac_mode
                self._away_mode = True
                self.set_hvac_mode(HVAC_MODE_OFF)
        elif preset_mode == PRESET_HOME:
            if self._away_mode == True:
                self._away_mode = False
                self.set_hvac_mode(self._awaymodeLastState)
        else:
            _LOGGER.error("Unknown mode: %s", preset_mode)
        self.schedule_update_ha_state()
		

    def turn_on(self):
        """Turn on."""
        self._on = True
        self._device.set_temperature_to_manual()

    def turn_off(self):
        """Turn off."""
        self._on = False
        self._device.set_location_to_off()

    def update(self):
        """Fetch new state data for this device.
        This is the only method that should fetch new data for Home Assistant.
        """
        if not self._device.update_room():
            _LOGGER.error("Updating Warmup component failed")

        # set operation mode
        self._current_hvac_mode = self.mode_map.get(
            self._device.get_run_mode())

        # set whether device is in away mode
        if self._device.get_run_mode() == 'away':
            self._away_mode = True
        else:
            self._away_mode = False

        # set whether device is on/off
        if self._device.get_run_mode() == 'off':
            self._on = False
        else:
            self._on = True
