"""Pytest fixtures - virtual rig setup shared across the test suite."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

# Make the package importable when running pytest from any cwd.
REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from polaris_bms import Cell, Ekf  # noqa: E402
from polaris_bms.instruments import (  # noqa: E402
    DataLogger,
    ScpiClient,
    SourceMeter,
    TestBench,
    ThermalChamber,
    VirtualScpiServer,
)


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(42)


@pytest.fixture
def cell() -> Cell:
    return Cell(soc0=1.0, temperature_k=298.15)


@pytest.fixture
def bench(cell, rng) -> TestBench:
    return TestBench(cell=cell, dt_s=1.0, rng=rng)


@pytest.fixture
def smu(bench) -> SourceMeter:
    return SourceMeter(bench)


@pytest.fixture
def dlog(bench) -> DataLogger:
    return DataLogger(bench)


@pytest.fixture
def chamber(bench) -> ThermalChamber:
    return ThermalChamber(bench)


@pytest.fixture
def scpi_server(bench):
    srv = VirtualScpiServer(bench, host="127.0.0.1", port=0)
    addr = srv.start()
    yield srv, addr
    srv.stop()


@pytest.fixture
def scpi(scpi_server):
    srv, (host, port) = scpi_server
    client = ScpiClient(host, port)
    yield client
    client.close()
