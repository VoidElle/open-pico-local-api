"""Tests for all model classes."""
import unittest

from open_pico_local_api.enums.device_mode_enum import DeviceModeEnum
from open_pico_local_api.enums.on_off_state_enum import OnOffStateEnum
from open_pico_local_api.enums.target_humidity_enum import TargetHumidityEnum
from open_pico_local_api.models.command_response_model import CommandResponseModel
from open_pico_local_api.models.pico_device_model import PicoDeviceModel
from open_pico_local_api.models.sensor_readings_model import SensorReadingsModel
from open_pico_local_api.models.operating_parameters_model import OperatingParametersModel


# Minimal realistic device payload
_FULL_PAYLOAD = {
    "idp": 42,
    "frm": "app",
    "cmd": "stato_sync",
    "res": 1,
    "ip": "192.168.1.10",
    "fw_ver": "3.2.1",
    "fw_note": "stable",
    "vr": 5,
    "modello": 2,
    "BaseTop": 1,
    "Grd_DM": "ABC123",
    "config_mod": 0,
    "id_slave": 0,
    "name": "TestPico",
    "has_slave": 0,
    "bmp_slave": 0,
    "man": [],
    "v_tmpr": 22.5,
    "v_umd": 45.0,
    "v_AirQ": 10,
    "v_Tvoc": 5,
    "v_ECo2": 600,
    "umd_raw": 450,
    "s_umd": 2,
    "s_co2": 800,
    "par_rt": [1, 2, 3],
    "par_mm": [],
    "par_amb": [],
    "par_ext": [],
    "err": [],
    "mod": 1,
    "step_mod": 0,
    "on_off": 1,
    "speed": 3,
    "spd_rich": 3,
    "spd_row": 0,
    "fan_dir": 0,
    "verso": 0,
    "Delta_tmprCiclo": 0,
    "Delta_umdCiclo": 0,
    "night_mod": 0,
    "led_on_off": 1,
    "led_on_off_breve": 0,
    "led_color": 2,
    "m_crono": 0,
    "tw_active": 0,
    "cntr": 100,
    "memfree": 50000,
    "up_time": 3600,
    "date": "2025-01-01",
    "time": "12:00:00",
    "week": 3,
}


class TestCommandResponseModel(unittest.TestCase):

    def test_from_dict_full(self):
        data = {"idp": 7, "frm": "pico", "cmd": "stato_sync"}
        model = CommandResponseModel.from_dict(data)
        self.assertEqual(model.idp, 7)
        self.assertEqual(model.frame_from, "pico")
        self.assertEqual(model.command, "stato_sync")

    def test_from_dict_defaults(self):
        model = CommandResponseModel.from_dict({})
        self.assertEqual(model.idp, 0)
        self.assertEqual(model.frame_from, "")
        self.assertEqual(model.command, "")


class TestPicoDeviceModel(unittest.TestCase):

    def setUp(self):
        self.model = PicoDeviceModel.from_dict(_FULL_PAYLOAD)

    def test_protocol_fields(self):
        self.assertEqual(self.model.idp, 42)
        self.assertEqual(self.model.frame_from, "app")
        self.assertEqual(self.model.command, "stato_sync")
        self.assertEqual(self.model.response, 1)

    def test_device_info(self):
        self.assertEqual(self.model.device_info.ip, "192.168.1.10")
        self.assertEqual(self.model.device_info.firmware_version, "3.2.1")
        self.assertEqual(self.model.device_info.name, "TestPico")

    def test_sensors_temperature(self):
        self.assertAlmostEqual(self.model.sensors.temperature, 22.5)
        self.assertEqual(self.model.sensors.temperature_celsius, 22.5)

    def test_sensors_humidity(self):
        self.assertAlmostEqual(self.model.sensors.humidity, 45.0)
        self.assertEqual(self.model.sensors.humidity_percent, 45.0)

    def test_sensors_setpoint_enum(self):
        self.assertEqual(self.model.sensors.humidity_setpoint, TargetHumidityEnum.FIFTY_PERCENT)

    def test_sensors_air_quality(self):
        self.assertTrue(self.model.sensors.has_air_quality)

    def test_sensors_temperature_type_is_float(self):
        self.assertIsInstance(self.model.sensors.temperature, float)

    def test_sensors_humidity_type_is_float(self):
        self.assertIsInstance(self.model.sensors.humidity, float)

    def test_operating_mode_enum(self):
        self.assertEqual(self.model.operating.mode, DeviceModeEnum.HEAT_RECOVERY)

    def test_operating_on_off_enum(self):
        self.assertEqual(self.model.operating.on_off, OnOffStateEnum.ON)

    def test_is_on(self):
        self.assertTrue(self.model.is_on)

    def test_is_healthy(self):
        self.assertTrue(self.model.is_healthy)

    def test_support_fan_speed_control_heat_recovery(self):
        self.assertTrue(self.model.support_fan_speed_control)

    def test_support_target_humidity_not_in_heat_recovery(self):
        self.assertFalse(self.model.support_target_humidity_selection)

    def test_support_night_mode_toggle_heat_recovery(self):
        self.assertTrue(self.model.support_night_mode_toggle)

    def test_raw_data_preserved(self):
        self.assertEqual(self.model.raw_data["idp"], 42)

    def test_to_dict_roundtrip(self):
        d = self.model.to_dict()
        self.assertEqual(d["idp"], 42)
        self.assertEqual(d["v_tmpr"], 22.5)

    def test_from_dict_defaults(self):
        # s_umd must be a valid TargetHumidityEnum value (1-3); use minimal valid payload
        minimal = {"s_umd": 1, "mod": 1, "on_off": 2}
        model = PicoDeviceModel.from_dict(minimal)
        self.assertEqual(model.idp, 0)
        self.assertAlmostEqual(model.sensors.temperature, 0.0)
        self.assertAlmostEqual(model.sensors.humidity, 0.0)
        self.assertFalse(model.is_on)

    def test_unhealthy_when_errors_present(self):
        payload = dict(_FULL_PAYLOAD)
        # errors are List[List[int]] — a non-empty inner list signals an error
        payload["err"] = [[1, 2]]
        model = PicoDeviceModel.from_dict(payload)
        self.assertFalse(model.is_healthy)

    def test_humidity_mode_support(self):
        payload = dict(_FULL_PAYLOAD)
        payload["mod"] = DeviceModeEnum.HUMIDITY_RECOVERY
        model = PicoDeviceModel.from_dict(payload)
        self.assertTrue(model.support_target_humidity_selection)
        self.assertFalse(model.support_fan_speed_control)


class TestSensorReadingsModel(unittest.TestCase):

    @staticmethod
    def _make(**kwargs):
        defaults = dict(
            temperature=21.0, humidity=50.0, air_quality=0,
            tvoc=0, eco2=0, humidity_raw=500,
            humidity_setpoint=TargetHumidityEnum.FIFTY_PERCENT,
            co2_setpoint=600,
        )
        defaults.update(kwargs)
        return SensorReadingsModel(**defaults)

    def test_temperature_celsius_rounded(self):
        m = self._make(temperature=21.456)
        self.assertEqual(m.temperature_celsius, 21.5)

    def test_humidity_percent_rounded(self):
        m = self._make(humidity=49.999)
        self.assertEqual(m.humidity_percent, 50.0)

    def test_has_air_quality_false_when_zero(self):
        m = self._make(air_quality=0, tvoc=0, eco2=0)
        self.assertFalse(m.has_air_quality)

    def test_has_air_quality_true_when_tvoc_nonzero(self):
        m = self._make(tvoc=10)
        self.assertTrue(m.has_air_quality)


class TestOperatingParametersModel(unittest.TestCase):

    @staticmethod
    def _make(**kwargs):
        defaults = dict(
            mode=DeviceModeEnum.HEAT_RECOVERY, step_mode=0,
            on_off=OnOffStateEnum.ON, speed=2, speed_requested=2,
            speed_row=0, fan_direction=0, direction=0,
            delta_temp_cycle=0, delta_humidity_cycle=0,
            night_mode=0, led_on_off=1, led_on_off_short=0,
            led_color=0, chrono_mode=0, timer_active=0,
        )
        defaults.update(kwargs)
        return OperatingParametersModel(**defaults)

    def test_is_on_true(self):
        m = self._make(on_off=OnOffStateEnum.ON)
        self.assertTrue(m.is_on)

    def test_is_on_false(self):
        m = self._make(on_off=OnOffStateEnum.OFF)
        self.assertFalse(m.is_on)

    def test_fan_running_true(self):
        m = self._make(speed=3)
        self.assertTrue(m.fan_running)

    def test_fan_running_false(self):
        m = self._make(speed=0)
        self.assertFalse(m.fan_running)

    def test_night_mode_active(self):
        m = self._make(night_mode=1)
        self.assertTrue(m.is_night_mode_active)

    def test_night_mode_inactive(self):
        m = self._make(night_mode=0)
        self.assertFalse(m.is_night_mode_active)

    def test_led_state_on(self):
        m = self._make(led_on_off=1)
        self.assertTrue(m.is_led_state_on())

    def test_led_state_off(self):
        m = self._make(led_on_off=0)
        self.assertFalse(m.is_led_state_on())


if __name__ == "__main__":
    unittest.main()
