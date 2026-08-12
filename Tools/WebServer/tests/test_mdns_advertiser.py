#!/usr/bin/env python3
"""Test cases for services.mdns_advertiser.MdnsAdvertiser.

The advertiser owns its own Zeroconf instance; tests patch it at the import
boundary so no real multicast socket is opened.
"""

import os
import signal
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _import_advertiser():
    """Lazy import so RED phase fails with ImportError, not module-load error."""
    from fpbinject.services.mdns_advertiser import MdnsAdvertiser  # noqa: E402

    return MdnsAdvertiser


def _make_advertiser(**overrides):
    """Construct an advertiser with sane defaults for tests."""
    Cls = _import_advertiser()
    kwargs = {
        "port": 5500,
        "version": "1.6.6",
        "auth_mode": "token",
        "path": "/api",
        "install_signal_handlers": False,
    }
    kwargs.update(overrides)
    return Cls(**kwargs)


def _txt_dict_from_register_call(mock_zc):
    """Pull the TXT-properties dict out of register_service(info) call."""
    register_call = mock_zc.register_service.call_args
    assert register_call is not None, "register_service was not called"
    info = register_call.args[0]
    return info.properties


class TestMdnsAdvertiserRegister(unittest.TestCase):
    """Service registration with correct TXT records."""

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    def test_register_uses_fpbinject_service_type(self, MockZeroconf):
        zc = MockZeroconf.return_value
        adv = _make_advertiser()
        adv.register()
        info = zc.register_service.call_args.args[0]
        self.assertEqual(info.type, "_fpbinject._tcp.local.")
        self.assertTrue(info.name.endswith("._fpbinject._tcp.local."))

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    def test_register_publishes_required_txt_keys(self, MockZeroconf):
        adv = _make_advertiser()
        adv.register()
        txt = _txt_dict_from_register_call(MockZeroconf.return_value)
        keys = {k.decode() if isinstance(k, bytes) else k for k in txt.keys()}
        self.assertIn("txtvers", keys)
        self.assertIn("version", keys)
        self.assertIn("auth", keys)
        self.assertIn("device", keys)
        self.assertIn("path", keys)

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    def test_register_advertises_port(self, MockZeroconf):
        adv = _make_advertiser(port=8080)
        adv.register()
        info = MockZeroconf.return_value.register_service.call_args.args[0]
        self.assertEqual(info.port, 8080)


class TestMdnsAdvertiserAuthIntent(unittest.TestCase):
    """auth TXT reflects advertised intent, not effective state."""

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    def test_auth_token_when_auth_mode_token(self, MockZeroconf):
        adv = _make_advertiser(auth_mode="token")
        adv.register()
        txt = _txt_dict_from_register_call(MockZeroconf.return_value)
        auth_val = txt[b"auth"] if b"auth" in txt else txt["auth"]
        self.assertEqual(
            auth_val.decode() if isinstance(auth_val, bytes) else auth_val,
            "token",
        )

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    def test_auth_none_when_auth_mode_none(self, MockZeroconf):
        adv = _make_advertiser(auth_mode="none")
        adv.register()
        txt = _txt_dict_from_register_call(MockZeroconf.return_value)
        auth_val = txt[b"auth"] if b"auth" in txt else txt["auth"]
        self.assertEqual(
            auth_val.decode() if isinstance(auth_val, bytes) else auth_val,
            "none",
        )


class TestMdnsAdvertiserNoTokenLeak(unittest.TestCase):
    """The actual auth token must never appear in TXT records."""

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    def test_txt_never_contains_token_key(self, MockZeroconf):
        adv = _make_advertiser()
        adv.register()
        txt = _txt_dict_from_register_call(MockZeroconf.return_value)
        keys_lower = {
            (k.decode() if isinstance(k, bytes) else k).lower() for k in txt.keys()
        }
        self.assertNotIn("token", keys_lower)
        self.assertNotIn("secret", keys_lower)
        self.assertNotIn("apikey", keys_lower)
        self.assertNotIn("api_key", keys_lower)


class TestMdnsAdvertiserDeviceTxtV1(unittest.TestCase):
    """v1 contract: device TXT is published once at startup as 'none'."""

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    def test_device_is_none_at_register(self, MockZeroconf):
        adv = _make_advertiser()
        adv.register()
        txt = _txt_dict_from_register_call(MockZeroconf.return_value)
        device_val = txt[b"device"] if b"device" in txt else txt["device"]
        self.assertEqual(
            device_val.decode() if isinstance(device_val, bytes) else device_val,
            "none",
        )


class TestMdnsAdvertiserUpdateDeviceState(unittest.TestCase):
    """update_device_state() shipped + tested for forward compat (unused in v1)."""

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    def test_update_device_state_calls_update_service(self, MockZeroconf):
        zc = MockZeroconf.return_value
        adv = _make_advertiser()
        adv.register()
        adv.update_device_state("connected")
        self.assertTrue(zc.update_service.called)

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    def test_update_device_state_preserves_id_and_all_txt_keys(self, MockZeroconf):
        adv = _make_advertiser()
        adv.register()
        register_keys = set(adv._build_txt("none").keys())

        connected_props = adv._build_txt("connected")
        self.assertEqual(set(connected_props.keys()), register_keys)
        self.assertEqual(connected_props["id"], adv._server_id)
        self.assertEqual(connected_props["device"], "connected")
        self.assertNotEqual(connected_props["id"], "")


class TestMdnsAdvertiserIdempotentUnregister(unittest.TestCase):
    """unregister() is safe to call repeatedly."""

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    def test_double_unregister_calls_unregister_service_once(self, MockZeroconf):
        zc = MockZeroconf.return_value
        adv = _make_advertiser()
        adv.register()
        adv.unregister()
        adv.unregister()
        self.assertEqual(zc.unregister_service.call_count, 1)

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    def test_unregister_without_register_is_noop(self, MockZeroconf):
        zc = MockZeroconf.return_value
        adv = _make_advertiser()
        adv.unregister()
        self.assertEqual(zc.unregister_service.call_count, 0)


class TestMdnsAdvertiserSignalHandlers(unittest.TestCase):
    """Signal-handler install policy.

    Default (install_signal_handlers=None): install unless PYTEST_CURRENT_TEST is set.
    Explicit True: install always.
    Explicit False: never install.
    """

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    @patch("fpbinject.services.mdns_advertiser.signal.signal")
    def test_signal_handlers_skipped_when_explicitly_disabled(
        self, mock_signal, MockZeroconf
    ):
        adv = _make_advertiser(install_signal_handlers=False)
        adv.register()
        self.assertFalse(mock_signal.called)

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    @patch("fpbinject.services.mdns_advertiser.signal.signal")
    def test_signal_handlers_installed_when_explicitly_enabled(
        self, mock_signal, MockZeroconf
    ):
        adv = _make_advertiser(install_signal_handlers=True)
        adv.register()
        installed = {call.args[0] for call in mock_signal.call_args_list}
        self.assertIn(signal.SIGINT, installed)
        self.assertIn(signal.SIGTERM, installed)

    @patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "test_x"}, clear=False)
    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    @patch("fpbinject.services.mdns_advertiser.signal.signal")
    def test_signal_handlers_default_skipped_under_pytest(
        self, mock_signal, MockZeroconf
    ):
        Cls = _import_advertiser()
        adv = Cls(port=5500, version="1", auth_mode="none")
        adv.register()
        self.assertFalse(mock_signal.called)


class TestMdnsAdvertiserAtexitHook(unittest.TestCase):
    """atexit handler is registered so graceful exits unregister."""

    @patch("fpbinject.services.mdns_advertiser.Zeroconf")
    @patch("fpbinject.services.mdns_advertiser.atexit.register")
    def test_register_installs_atexit_unregister(self, mock_atexit, MockZeroconf):
        adv = _make_advertiser()
        adv.register()
        self.assertTrue(mock_atexit.called)
        cb = mock_atexit.call_args.args[0]
        self.assertEqual(cb, adv.unregister)


if __name__ == "__main__":
    unittest.main()
