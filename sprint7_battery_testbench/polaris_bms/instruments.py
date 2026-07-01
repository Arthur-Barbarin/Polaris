"""Virtual lab instruments wrapped over the C++ cell model.

The goal is to make the pytest test framework drive the simulated cell
through the same kind of interface that talks to real Keysight / Arbin /
Chroma equipment in an Apple-style validation lab.

Three layers:

  PowerSupply / SourceMeter / DataLogger - object-style "drivers" that look
    like vendor SDKs (similar to PyVISA wrappers).
  VirtualScpiServer - exposes the same drivers over a TCP socket using a
    minimal SCPI-flavoured command set. This is what makes the test
    framework "talk to hardware" without any hardware present.
  ScpiClient - the client side, mirrors the API a real test rig would use.
"""
from __future__ import annotations

import socket
import socketserver
import threading
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

from .native import Cell, Fault
from .signals import inject_current_noise, inject_voltage_noise


# --------------------------------------------------------------------------- #
# Driver-level wrappers
# --------------------------------------------------------------------------- #

@dataclass
class TestBench:
    """A virtual rig: one cell + the instruments wired to it.

    The bench steps in fixed dt increments. Calls to source / measure on
    its instruments are expected to be sandwiched by `tick(dt)`.

    A single re-entrant lock serialises access to the underlying cell -
    important when the bench is wrapped by the multi-threaded SCPI server.
    """

    cell: Cell
    dt_s: float = 1.0
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng(0))
    voltage_noise_std: float = 0.0015      # 1.5 mV - representative of 16-bit ADC
    current_noise_std: float = 0.005       # 5 mA shunt
    current_setpoint_a: float = 0.0
    last_voltage: float = 0.0
    lock: threading.RLock = field(default_factory=threading.RLock)

    def tick(self) -> Tuple[float, float]:
        """Advance one dt; returns (current_applied, terminal_voltage_true)."""
        with self.lock:
            v_true = self.cell.step(self.current_setpoint_a, self.dt_s)
            self.last_voltage = v_true
            return self.current_setpoint_a, v_true


@dataclass
class SourceMeter:
    """SMU-style: sources current, can also enforce voltage limits (CC-CV)."""

    bench: TestBench

    def source_current(self, amps: float) -> None:
        with self.bench.lock:
            self.bench.current_setpoint_a = float(amps)

    def output_off(self) -> None:
        with self.bench.lock:
            self.bench.current_setpoint_a = 0.0

    def measure_current(self) -> float:
        with self.bench.lock:
            return inject_current_noise(
                self.bench.current_setpoint_a,
                self.bench.rng,
                std_a=self.bench.current_noise_std,
            )


@dataclass
class DataLogger:
    """High-impedance voltmeter / DAQ."""

    bench: TestBench

    def measure_voltage(self) -> float:
        with self.bench.lock:
            return inject_voltage_noise(
                self.bench.last_voltage,
                self.bench.rng,
                std_v=self.bench.voltage_noise_std,
            )

    def measure_temperature_k(self) -> float:
        with self.bench.lock:
            return float(self.bench.cell.snapshot().T_k)


@dataclass
class ThermalChamber:
    bench: TestBench

    def setpoint_k(self, T_k: float) -> None:
        self.bench.cell.set_temperature(float(T_k))


# --------------------------------------------------------------------------- #
# SCPI server / client
# --------------------------------------------------------------------------- #

_SCPI_HELP = """\
Polaris virtual SCPI - supported commands:
  *IDN?                      -> identification
  SOUR:CURR <amps>           -> set discharge current (positive = discharge)
  SOUR:OUTP OFF              -> disable output
  MEAS:VOLT?                 -> measured terminal voltage (V)
  MEAS:CURR?                 -> measured current (A)
  MEAS:TEMP?                 -> measured cell temperature (K)
  TIME:STEP <dt>             -> change tick interval
  TIME:TICK <n>              -> advance simulation by n ticks
  CELL:STATE?                -> JSON-like state dump: soc,vrc1,vrc2,T,cyc,t,q,r0
  CELL:RESET <soc> <T_k>     -> reset cell state
  CHAM:TEMP <K>              -> set thermal-chamber set-point
  CELL:FAULT <code> <sev>    -> inject fault (0..4)
"""


class _ScpiHandler(socketserver.StreamRequestHandler):
    timeout = 5

    def handle(self) -> None:
        srv: VirtualScpiServer = self.server  # type: ignore[assignment]
        while True:
            try:
                line = self.rfile.readline()
            except OSError:
                return
            if not line:
                return
            cmd = line.decode("utf-8", errors="ignore").strip()
            if not cmd:
                continue
            try:
                reply = srv.dispatch(cmd)
            except Exception as exc:  # noqa: BLE001
                reply = f"ERR {exc}"
            if reply is not None:
                self.wfile.write((reply + "\n").encode("utf-8"))


class VirtualScpiServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, bench: TestBench, host: str = "127.0.0.1", port: int = 0):
        super().__init__((host, port), _ScpiHandler)
        self.bench = bench
        self.smu = SourceMeter(bench)
        self.dlog = DataLogger(bench)
        self.chamber = ThermalChamber(bench)
        self._thread: Optional[threading.Thread] = None

    @property
    def address(self) -> Tuple[str, int]:
        return self.server_address  # type: ignore[return-value]

    def start(self) -> Tuple[str, int]:
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()
        return self.address

    def stop(self) -> None:
        self.shutdown()
        self.server_close()
        if self._thread:
            self._thread.join(timeout=2)

    # ----------------------------------------------------------------- dispatch
    def dispatch(self, cmd: str) -> Optional[str]:
        u = cmd.upper()
        if u == "*IDN?":
            return "Polaris Virtual Bench, model VTB-1, firmware 0.1"
        if u == "?HELP" or u == "HELP?":
            return _SCPI_HELP
        if u.startswith("SOUR:CURR "):
            self.smu.source_current(float(cmd.split(maxsplit=1)[1]))
            return None
        if u == "SOUR:OUTP OFF":
            self.smu.output_off()
            return None
        if u == "MEAS:VOLT?":
            return f"{self.dlog.measure_voltage():.6f}"
        if u == "MEAS:CURR?":
            return f"{self.smu.measure_current():.6f}"
        if u == "MEAS:TEMP?":
            return f"{self.dlog.measure_temperature_k():.4f}"
        if u.startswith("TIME:STEP "):
            self.bench.dt_s = float(cmd.split(maxsplit=1)[1])
            return None
        if u.startswith("TIME:TICK "):
            n = int(cmd.split(maxsplit=1)[1])
            for _ in range(n):
                self.bench.tick()
            return None
        if u == "CELL:STATE?":
            s = self.bench.cell.snapshot()
            return ",".join(f"{getattr(s, f):.6f}" for f in [
                "soc", "v_rc1", "v_rc2", "T_k", "cycles_eq", "time_s", "q_now_ah", "r0_now",
            ])
        if u.startswith("CELL:RESET "):
            _, soc, T = cmd.split()
            self.bench.cell.reset(float(soc), float(T))
            return None
        if u.startswith("CHAM:TEMP "):
            self.chamber.setpoint_k(float(cmd.split(maxsplit=1)[1]))
            return None
        if u.startswith("CELL:FAULT "):
            _, code, sev = cmd.split()
            self.bench.cell.set_fault(Fault(int(code)), float(sev))
            return None
        raise ValueError(f"unknown command: {cmd!r}")


class ScpiClient:
    """Minimal SCPI client - matches what a real Apple test-stand wrapper looks like."""

    def __init__(self, host: str, port: int, timeout: float = 2.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.file = self.sock.makefile("rwb", buffering=0)

    def close(self) -> None:
        try:
            self.file.close()
        finally:
            self.sock.close()

    def write(self, cmd: str) -> None:
        self.file.write((cmd + "\n").encode("utf-8"))

    def query(self, cmd: str) -> str:
        self.write(cmd)
        line = self.file.readline()
        if not line:
            raise ConnectionError("instrument closed connection")
        return line.decode("utf-8").strip()

    # convenience helpers
    def set_current(self, amps: float) -> None:
        self.write(f"SOUR:CURR {amps:.6f}")

    def measure_voltage(self) -> float:
        return float(self.query("MEAS:VOLT?"))

    def measure_current(self) -> float:
        return float(self.query("MEAS:CURR?"))

    def measure_temperature(self) -> float:
        return float(self.query("MEAS:TEMP?"))

    def tick(self, n: int = 1) -> None:
        self.write(f"TIME:TICK {n}")
