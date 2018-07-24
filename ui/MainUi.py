import os
from random import random
from multiprocessing import Process
from time import gmtime, strftime

from server.message import Message, MessageServer, UiMessage, ServerMessage, ThreadServer

from test_kits import TestKits

class UiError(Exception):
    "Message error exception class type"
    pass

class LogicDevice(object):
    CMD_STACK_DEPTH = 1000

    [STS_DETACH, STS_ATTACHED, STS_CONNECTED] = range(3)

    def __init__(self, id, logic_phy_pipes):
        self.__id = id
        self.logic_pipe, self.phy_pipe = logic_phy_pipes
        self.cmd_seq = 0
        self.cmd_list = []
        self.msg_list = []
        self.status = self.STS_DETACH
        api_test_kits = {"api": {"set_raw_command": self.set_raw_command, "set_get_chip_info":self.set_get_chip_info}}
        self.kits = TestKits(**api_test_kits)

    def id(self):
        return self.__id

    def next_seq(self, t):
        self.cmd_seq += 1
        token = t.copy()
        token.append(self.cmd_seq)
        return token

    def ready(self):
        return len(self.cmd_list) == 0

    def prepare_command(self, command):
        if len(self.cmd_list) > self.CMD_STACK_DEPTH:   #command may have two in stack, one in prepare, one will be processing and done
            raise ServerError("command still in process {}", self.cmd_list)
            self.cmd_list.pop()

        if isinstance(command, (tuple, list)):
            command = self.group_command(command)

        #self.cmd_list.append(Message(type, self.id(), self.next_seq(seq), **kwargs, pipe=self.pipe()))
        command.set_pipe(self.phy_pipe)
        self.cmd_list.append(command)

    def send_command(self):
        for cmd in self.cmd_list:
            cmd.send()

    def set_bridge_poll(self, kwargs={}):
        command = ServerMessage(Message.CMD_POLL_BRIDGE, self.id(), self.next_seq(Message.seq_root()), **kwargs)
        self.prepare_command(command)

    def set_get_chip_info(self):
        kwargs = {'addr': 0, 'size':7}
        command = ServerMessage(Message.CMD_DEVICE_PAGE_READ, self.id(), self.next_seq(Message.seq_root()), **kwargs)
        self.prepare_command(command)

    def set_raw_command(self, raw_data):
        kwargs = {'value': raw_data}
        command = ServerMessage(Message.CMD_DEVICE_RAW_DATA, self.id(), self.next_seq(Message.seq_root()), **kwargs)
        self.prepare_command(command)

    def poll(self):
        if self.status == self.STS_CONNECTED:
            if self.ready():
                self.kits.poll()

    def handel_bus_detected_msg(self, seq, data):
        kwargs = {'repeat': self.INTERVAL_POLL_DEVICE}
        self.set_bridge_poll(kwargs)

    def handel_bus_detected_msg(self, seq, data):
        print("IRQ:", seq, data)

    def handle_attached_msg(self, seq, data):
        t = strftime("%b-%d %H:%M:%S", gmtime())
        print(t, "Attach:", seq, data)
        if data['value']:
            self.status = self.STS_ATTACHED
            self.set_get_chip_info()
        else:
            self.status = self.STS_DETACH

    def handle_page_read_msg(self, seq, cmd, data):
        t = strftime("%b-%d %H:%M:%S", gmtime())
        print(t, "R:", seq, data)
        if (all(data)):
            self.status = self.STS_CONNECTED

    def handle_page_write_msg(self, seq, cmd, data):
        print("W:", seq, data)

    def handle_raw_data_msg(self, seq, cmd, data):
        #print("Raw:", seq, data)
        pass

    def handle_nak_msg(self, seq, error):
        print("Nak:", seq, error)

    def handle_message(self, msg):
        type = msg.type()
        seq = msg.seq()

        if type == Message.MSG_BUS_FOUND:
            self.handel_bus_detected_msg(seq, msg.extra_info())
        elif type == Message.MSG_DEVICE_INTERRUPT_DATA:
            self.handle_interrupt_data_msg(seq, msg.extra_info())
        else:
            for i, cmd in enumerate(self.cmd_list[:]):
                #print("handle_message: seq msg={} cmd={}".format(seq, cmd.seq()))
                if cmd.seq() == seq:
                    seq.pop()

                    if type == Message.MSG_BRIDGE_ATTACH:
                        self.handle_attached_msg(seq,msg.extra_info())  # only status of attached, since detach will Logici device is removed
                    # elif type == Message.MSG_DEVICE_CONNECTED:
                    #     self.handle_connected_msg(seq, msg.extra_info())
                    elif type == Message.CMD_DEVICE_PAGE_READ:
                        self.handle_page_read_msg(seq, cmd, msg.extra_info())
                    # elif type == Message.MSG_DEVICE_BLOCK_READ:
                    #     self.handle_block_read_msg(seq, cmd, msg.extra_info())
                    elif type == Message.CMD_DEVICE_PAGE_WRITE:
                        self.handle_page_write_msg(seq, cmd, msg.extra_info())
                    elif type == Message.CMD_DEVICE_RAW_DATA:
                        self.handle_raw_data_msg(seq, cmd, msg.extra_info())
                    elif type == Message.CMD_DEVICE_MSG_OUTPUT:
                        self.handle_raw_data_msg(seq, cmd, msg.extra_info())
                    elif type == Message.MSG_DEVICE_NAK:
                        self.handle_nak_msg(seq, error=msg)
                    else:
                        raise ServerError("Logic device id '{}' msg {} seq not match".format(id, msg))
                        self.handle_nak_msg(seq, error="Unknow msg type {}".format(type))

                    del self.cmd_list[i]
                    break

class MainScreen(object):
    "Main Screen"

    def __init__(self, **kwargs):
        #self.pipe_to_server = MessageServer.get('ui_to_server')
        #self.pipe_from_server = MessageServer.get('server_to_ui')
        self.pipe_from_bus = MessageServer.open('bus_to_server')
        self.devices = dict()
        super(MainScreen, self).__init__(**kwargs)

    def handle_bus_detected_msg(self, id, msg):
        ext_info = msg.extra_info()
        val = ext_info['value']

        #remove device
        if id in self.devices.keys():
            if not val:
                del self.devices[id]
        else:
            if val:
                dev = LogicDevice(id, val)
                self.devices[id] = dev
                dev.set_bridge_poll()

    def dispatch(self):
        for dev in self.devices.values():
            has_msg = dev.logic_pipe.poll(0)
            if has_msg:
                msg = dev.logic_pipe.recv()
                type = msg.type()
                id = msg.id()

                dev.handle_message(msg)

    def recv(self):
        has_msg = self.pipe_from_bus.poll(0)
        if has_msg:
            msg = self.pipe_from_bus.recv()
            type = msg.type()
            id = msg.id()
            #print("Process<{}> recv message: {}".format(self.__class__.__name__, msg))
            #create or remove device window, root window only process this message

            if type == Message.MSG_BUS_FOUND:
                self.handle_bus_detected_msg(id, msg)


        self.dispatch()

    def send(self):
        for dev in self.devices.values():
            dev.send_command()

    def poll(self):
        for dev in self.devices.values():
            dev.poll()

    def update(self):
        while True:
            ThreadServer.process()

            self.recv()
            self.send()
            self.poll()

class MainUi(object):
    "Main Ui"

    def __init__(self, **kwargs):
        self.screen = MainScreen()
        super(MainUi, self).__init__(**kwargs)

    def run(self):
        p = Process(target=self.screen.update(), args=())
        p.start()

if __name__ == '__main__':
    parent, client = Pipe()
    MainUi(parent).run()