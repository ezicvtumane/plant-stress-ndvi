# Copilot & AI Agent Instructions
See complete canonical project rules in [SYSTEM_RULES.md](../SYSTEM_RULES.md).

Key Invariants:
1. Cohorts order: K1 Control (A0) -> K2 Osmosis (100 mM NaCl, separate tray, A1) -> K3 Terminal Drought (A2) -> K4 Prevention (Watering at dT > +0.8C, high NDVI 0.75-0.80, scales, no soil sensor) -> K5 Reaction (Watering on turgor loss, scales, no soil sensor).
2. Salt: Strictly 100 mM NaCl. Glycophyte pea (Pisum sativum). Never use 150 mM.
3. Soil: Capacitive sensors on K1, K2, K3 only. K4 and K5 have no sensor: output '--' or 'N/A', never '0.0%'.
4. Server: web_station.py listens on 0.0.0.0:8000. All I2C calls via i2c_executor (max_workers=1). Strict None checks for windowsill climate data.
5. Verification: Before finishing, run python3 -m py_compile web_station.py, verify systemctl is-active plant-station.service, clean 0-byte git objects, and git push to main.
