#!/usr/bin/env python3
"""
    Simple command line pyupdi utility
"""

from .pyupdi.device.device import Device
from .pyupdi.updi.nvm import UpdiNvmProgrammer

class Updi_Device(object):

    def __init__(self, comport, baud, device):
        self.comport = comport
        self.baud = baud
        self.device = device
        self._nvm = None

    def start(self, program = False):
        nvm = UpdiNvmProgrammer(self.comport, self.baud, self.device)
        if nvm:
            if program:
                nvm.enter_progmode()
        
        self._nvm = nvm

    def stop(self):
        if self._nvm:
            self._nvm.leave_progmode()
            self._nvm = None
    
    def device_info(self):
        return self._nvm.get_device_info()

