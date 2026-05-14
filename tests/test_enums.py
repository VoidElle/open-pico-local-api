"""Tests for all enum classes."""
import unittest

from enums.device_mode_enum import DeviceModeEnum
from enums.on_off_state_enum import OnOffStateEnum
from enums.target_humidity_enum import TargetHumidityEnum


class TestDeviceModeEnum(unittest.TestCase):

    def test_all_modes_defined(self):
        modes = [
            DeviceModeEnum.HEAT_RECOVERY,
            DeviceModeEnum.EXTRACTION,
            DeviceModeEnum.IMMISSION,
            DeviceModeEnum.HUMIDITY_RECOVERY,
            DeviceModeEnum.HUMIDITY_EXTRACTION,
            DeviceModeEnum.COMFORT_SUMMER,
            DeviceModeEnum.COMFORT_WINTER,
            DeviceModeEnum.CO2_RECOVERY,
            DeviceModeEnum.CO2_EXTRACTION,
            DeviceModeEnum.HUMIDITY_CO2_RECOVERY,
            DeviceModeEnum.HUMIDITY_CO2_EXTRACTION,
            DeviceModeEnum.NATURAL_VENTILATION,
        ]
        self.assertEqual(len(modes), 12)

    def test_int_values(self):
        self.assertEqual(DeviceModeEnum.HEAT_RECOVERY, 1)
        self.assertEqual(DeviceModeEnum.EXTRACTION, 2)
        self.assertEqual(DeviceModeEnum.NATURAL_VENTILATION, 12)

    def test_from_int(self):
        self.assertEqual(DeviceModeEnum(1), DeviceModeEnum.HEAT_RECOVERY)
        self.assertEqual(DeviceModeEnum(6), DeviceModeEnum.COMFORT_SUMMER)


class TestOnOffStateEnum(unittest.TestCase):

    def test_on_value(self):
        self.assertEqual(OnOffStateEnum.ON, 1)

    def test_off_value(self):
        self.assertEqual(OnOffStateEnum.OFF, 2)

    def test_from_int(self):
        self.assertEqual(OnOffStateEnum(1), OnOffStateEnum.ON)
        self.assertEqual(OnOffStateEnum(2), OnOffStateEnum.OFF)


class TestTargetHumidityEnum(unittest.TestCase):

    def test_values(self):
        self.assertEqual(TargetHumidityEnum.FORTY_PERCENT, 1)
        self.assertEqual(TargetHumidityEnum.FIFTY_PERCENT, 2)
        self.assertEqual(TargetHumidityEnum.SIXTY_PERCENT, 3)

    def test_from_int(self):
        self.assertEqual(TargetHumidityEnum(2), TargetHumidityEnum.FIFTY_PERCENT)


if __name__ == "__main__":
    unittest.main()
