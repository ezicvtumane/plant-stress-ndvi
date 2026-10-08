from hardware.hal import get_relay_controller

class RelayController:
    def __init__(self):
        self._relay = get_relay_controller()
    def set_850nm(self, active: bool):
        self._relay.set_nir(active)
    def set_660nm(self, active: bool):
        self._relay.set_red(active)
    def all_off(self):
        self._relay.set_nir(False)
        self._relay.set_red(False)
    def cleanup(self):
        self._relay.cleanup()
