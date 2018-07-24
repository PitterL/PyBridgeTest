#from multiprocessing import Pipe
from bus.manage import BusManager
from bus.hid_bus import Hid_Bus
#from server.message import ThreadServer
from ui.MainUi import MainUi

BusManager.register_bus(Hid_Bus())

if __name__ == '__main__':
    BusManager()
    ui = MainUi()
    ui.run()
