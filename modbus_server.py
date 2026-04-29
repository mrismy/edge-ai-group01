"""
=============================================================================
Modbus TCP Server Simulator – Group 24
=============================================================================
Simulates a Modbus TCP server representing an industrial transformer's
register map. This fulfils the mandatory "Modbus TCP (simulated or real)"
requirement from Section 5.2 of the project guidelines.

Register Map:
    HR 0  – Load Current (x100, e.g. 1250 = 12.50 A)
    HR 1  – Winding Temperature (x10, e.g. 335 = 33.5 °C)
    HR 2  – Anomaly Score (0 or 1)
    HR 3  – Actuator State (0=normal, 1=tripped)
    HR 4  – RUL Estimate (hours, 0xFFFF = stable/learning)

The main simulator (simulator.py) writes to these registers, and Node-RED
can read from them via Modbus TCP to demonstrate OT protocol integration.
=============================================================================
"""

import threading
import time
import struct
from pyModbusTCP.server import ModbusServer, DataBank


class TransformerModbusServer:
    """Modbus TCP server wrapping a simulated transformer's register map."""

    def __init__(self, host="0.0.0.0", port=502):
        self.server = ModbusServer(host=host, port=port, no_block=True)
        self._running = False

    def start(self):
        """Start the Modbus TCP server in a background thread."""
        self.server.start()
        self._running = True
        print(f"[MODBUS] Server started on port {self.server.port}")

    def stop(self):
        """Stop the Modbus TCP server."""
        self._running = False
        self.server.stop()
        print("[MODBUS] Server stopped")

    def update_registers(self, current: float, temperature: float,
                         anomaly: float, actuator_state: int, rul: int = 0xFFFF):
        """
        Write current sensor values to Modbus holding registers.

        Args:
            current:        Load current in Amps (float)
            temperature:    Winding temperature in °C (float)
            anomaly:        Anomaly score (0.0 or 1.0)
            actuator_state: 0=normal, 1=tripped
            rul:            Remaining useful life in hours (0xFFFF = stable)
        """
        data_bank = self.server.data_bank
        data_bank.set_holding_registers(0, [
            int(current * 100),       # HR 0: current x100
            int(temperature * 10),    # HR 1: temperature x10
            int(anomaly),             # HR 2: anomaly score
            int(actuator_state),      # HR 3: actuator state
            int(rul) & 0xFFFF,        # HR 4: RUL hours
        ])

    def read_actuator_state(self) -> int:
        """Read actuator state from HR 3 (may be written by external client)."""
        regs = self.server.data_bank.get_holding_registers(3, 1)
        return regs[0] if regs else 0


if __name__ == "__main__":
    # Stand-alone test mode
    srv = TransformerModbusServer(host="0.0.0.0", port=502)
    srv.start()
    try:
        i = 0
        while True:
            srv.update_registers(
                current=10.0 + (i % 10) * 0.5,
                temperature=30.0 + (i % 10) * 0.3,
                anomaly=0.0,
                actuator_state=0,
            )
            print(f"[MODBUS] Registers updated (iteration {i})")
            time.sleep(2)
            i += 1
    except KeyboardInterrupt:
        srv.stop()
