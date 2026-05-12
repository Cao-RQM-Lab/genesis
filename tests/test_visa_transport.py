from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch


class VisaTransportTests(unittest.TestCase):
    @patch("genesis.core.transport.visa_transport.pyvisa")
    def test_open_sets_message_terminators_and_timeout(self, mock_pyvisa: MagicMock):
        from genesis.core.transport.visa_transport import VisaTransport

        resource = MagicMock()
        rm = MagicMock()
        rm.open_resource.return_value = resource
        mock_pyvisa.ResourceManager.return_value = rm

        transport = VisaTransport("GPIB0::22::INSTR")
        transport.open()

        self.assertEqual(resource.timeout, 10000)
        self.assertEqual(resource.write_termination, "\n")
        self.assertEqual(resource.read_termination, "\n")
        resource.clear.assert_called_once()
        rm.open_resource.assert_called_once_with("GPIB0::22::INSTR")

    @patch("genesis.core.transport.visa_transport.pyvisa")
    def test_open_respects_explicit_settings_overrides(self, mock_pyvisa: MagicMock):
        from genesis.core.transport.visa_transport import VisaTransport

        resource = MagicMock()
        rm = MagicMock()
        rm.open_resource.return_value = resource
        mock_pyvisa.ResourceManager.return_value = rm

        transport = VisaTransport(
            "GPIB0::7::INSTR",
            settings={
                "visaTimeoutMs": 1500,
                "writeTermination": "\r\n",
                "readTermination": "\r\n",
                "visaClearOnOpen": False,
            },
        )
        transport.open()

        self.assertEqual(resource.timeout, 1500)
        self.assertEqual(resource.write_termination, "\r\n")
        self.assertEqual(resource.read_termination, "\r\n")
        resource.clear.assert_not_called()

    @patch("genesis.core.transport.visa_transport.pyvisa")
    def test_query_passes_through_with_delay_when_set(self, mock_pyvisa: MagicMock):
        from genesis.core.transport.visa_transport import VisaTransport

        resource = MagicMock()
        resource.query.return_value = "1.23"
        rm = MagicMock()
        rm.open_resource.return_value = resource
        mock_pyvisa.ResourceManager.return_value = rm

        transport = VisaTransport(
            "GPIB::1::INSTR",
            settings={"visaQueryDelay": 0.01, "visaClearOnOpen": False},
        )
        transport.open()

        reply = transport.query("FIELD:MAG?")
        self.assertEqual(reply, "1.23")
        resource.query.assert_called_once_with("FIELD:MAG?", delay=0.01)

    @patch.dict(os.environ, {"GENESIS_VISA_IO_LOG": "1"})
    @patch("genesis.core.transport.visa_transport.pyvisa")
    @patch("builtins.print")
    def test_logging_env_writes_show_repr_with_escapes_and_timestamp(
        self, mock_print: MagicMock, mock_pyvisa: MagicMock
    ) -> None:
        from genesis.core.transport.visa_transport import VisaTransport

        resource = MagicMock()
        rm = MagicMock()
        rm.open_resource.return_value = resource
        mock_pyvisa.ResourceManager.return_value = rm

        transport = VisaTransport(
            "GPIB0::22::INSTR",
            settings={"visaClearOnOpen": False},
        )
        transport.open()
        transport.write("CONF:FIELD:UNITS 1")

        mock_print.assert_called_once()
        logged = mock_print.call_args[0][0]
        self.assertIn("[visa-io ", logged)
        self.assertIn("[GPIB0::22::INSTR]", logged)
        self.assertIn("WRITE >>", logged)
        self.assertIn(r"\n", logged)

    @patch.dict(os.environ, {"GENESIS_VISA_IO_LOG": "0"})
    @patch("genesis.core.transport.visa_transport.pyvisa")
    @patch("builtins.print")
    def test_logging_env_force_off_overrides_job_flag(
        self, mock_print: MagicMock, mock_pyvisa: MagicMock
    ) -> None:
        from genesis.core.transport.visa_transport import VisaTransport

        resource = MagicMock()
        rm = MagicMock()
        rm.open_resource.return_value = resource
        mock_pyvisa.ResourceManager.return_value = rm

        transport = VisaTransport(
            "GPIB0::22::INSTR",
            settings={"visaClearOnOpen": False, "visaLogIoStdout": True},
        )
        transport.open()
        transport.query("FIELD:MAG?")

        mock_print.assert_not_called()


if __name__ == "__main__":
    unittest.main()
