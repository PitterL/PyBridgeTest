#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
"""
Show all HID devices information
"""

from multiprocessing import RLock
#from multiprocessing import Process, Pipe, RLock
#from multiprocessing.connection import wait
import sys
import array
import time

#from bus.manage import Bus, BusManager
from bus.manage import PhyDevice, Bus
from server.message import BaseMessage, Message, HidMessage, MessageServer, ThreadServer
from dotdict import Dotdict

import bus.pywinusb.hid as usbhid
from bus.pywinusb.hid import tools

class HidCommand(Message):
    NAME = 'HID cmd'

    """
    :param data:
    :return:

    ======================================
    Read Register:
    CMD0	LenW	LenR	ADD_L	ADD_H
    0x51    0x2
    Response:
    TAG     LenR    [Data]
    0x0

    =============================================================
    Write Register
    CMD0	LenW	LenR	ADD_L	ADD_H	DATA0	DATA1	DATA2
    Response:
    TAG     TAG2    TAG3
    0x4     0       0
    """
    (CMD_TEST, CMD_IRQ, CMD_WRITE_READ, CMD_RAW) = (0x80, (0x88, 0x58), 0x51,  None)

    TIMEOUT = 1 #second
    SIZE_MAX = {'r': 63, 'w': 59}
    #SIZE_PROPER = {'r': 64, 'w': 48}

    R = Dotdict({'RESPONSE_OK': 0})
    W = Dotdict({'RESPONSE_OK': 4})

    def __init__(self, type, seq, **kwargs):
        #print(self.__class__.__name__, "init", type, seq, kwargs)
        self.usage = kwargs.pop('usage')

        self._repeat_value = kwargs.pop('repeat', None)
        if self.repeatable():
            #self._repeat = True
            self.repeat_count = 0
        # else:
        #     self._repeat = False

        #self.__timeout = kwargs.pop('timeout', 0)

        super(HidCommand, self).__init__(HidCommand.NAME, type, 0, seq, **kwargs)

        value = []
        if type == HidCommand.CMD_TEST:
            #[type, 0, value]
            value = array.array('B', [type, 0, kwargs['value']])
            self.trans_size = 0
            self.op = 'w'
        elif type == HidCommand.CMD_WRITE_READ:
            addr_l, addr_h = kwargs['addr'].to_bytes(2, byteorder='little')
            if 'size' in kwargs.keys(): #only read need explicit size
                #[type, LenW=2, LenR, AddrL, AddrH]
                trans_size = self.to_trans_size(kwargs['size'], 'r')
                value = [type, 2, trans_size, addr_l, addr_h]
                self.op = 'r'
            else:
                #write #[type, LenW, LenR=0, AddrL, AddrH, Data0, Data1, ...]
                #addr_l, addr_h = kwargs['addr'].to_bytes(2, byteorder='little')
                data = kwargs['value']
                trans_size = self.to_trans_size(len(data), 'w')
                value = [type, trans_size + 2, 0, addr_l, addr_h]
                value.extend(data[:trans_size])
                self.op = 'w'
            self.trans_size = trans_size
        elif type == HidCommand.CMD_RAW:
            value = kwargs['value']
            self.trans_size = self.to_trans_size(len(value), 'w')
            self.op = 'w'
        elif type == HidCommand.CMD_IRQ:
            addr_l, addr_h = kwargs['addr'].to_bytes(2, byteorder='little')
            value = type + (2, kwargs['size'], addr_l, addr_h)
            self.trans_size = self.to_trans_size(len(value), 'w')
            self.op = 'w'
        else:
            print("Unsuport hid command {}".format(type))

        try:
            self.__raw_data = array.array('B', value)
        except Exception as e:
            print(self.__class__.__name__, "hid corrupted data", value, e)
            self.__raw_data = None

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.__class__.__name__ + " " + super().__str__() + \
               " op={} len={} timeout={} repeat={}".format(
                   self.op, self.transfered_size(), self.timeout(), self._repeat_value)

    def is_read(self):
        return 'size_r' in self.kwargs.keys()

    def to_trans_size(self, size, op):
        "for HID protocal, there is read/write limit, so we may couldn't write through one time"
        max_size = HidCommand.SIZE_MAX[op]
        if size > max_size:
            return max_size

        return size

    def to_trans_format(self, data, size):
        raw_data = array.array('B', [0])
        raw_data.extend(data)
        raw_data.extend([0]*(size - len(data) + 1))

        return raw_data

    # def proper_size(self, op):
    #     if op not in HidCommand.SIZE_PROPER.keys():
    #         BusError('Unknow proper_size op {}'.format(op))
    #     return HidCommand.SIZE_MAX[op]

    def transfered_size(self):
        return self.trans_size

    # def delay(self):
    #     return self._delay

    # def delayed(self, delay=None):
    #     if delay is None:
    #         delay = self.delay()
    #     return time.time() >= self.time() + delay

    def delay_time(self):  #how long message could be send
        status = self.status()
        if status == Message.INIT:
            return 0
        elif status == Message.SEND:
            return self.time_left()
        elif status == Message.REPEAT:
            return self.time_left(self._repeat_value)

    def repeatable(self):
        return self._repeat_value is not None

    def reset_repeat(self, status):
        if status == Message.REPEAT:
            self.repeat_count += 1
        else:
            self.repeat_count = 0

        self.set_status(status)

    def ready(self):
        return self.is_status(Message.INIT) or (self.is_status(Message.REPEAT) and self.timeout(self._repeat_value))

    def raw_data(self):
        return self.__raw_data

    def parent_type(self):
        info = self.extra_info()
        if 'parent_type' in info.keys():
            return info['parent_type']

    def send_to(self, pipe):
        if not pipe:
            print("Pipe is None")
            return False

        status = self.status()

        if self.ready():
            self.set_status(Message.SEND)
            if self.raw_data():
                #print(self.__class__.__name__, "send:", self.msg_data(), list(map(hex, self.raw_data())))
                raw_data = self.to_trans_format(self.raw_data(), len(pipe[Hid_Device.USAGE_ID_OUTPUT]))
                #print(list(map(hex, raw_data)))
                try:
                    pipe.set_raw_data(raw_data)
                    pipe.send()
                    return True
                except:
                    print(self.__class__.__name__, "Send HID Message: Failed")

            self.set_status(Message.ERROR)

        return False

class PhyMessage(Message):
    #hid message type
    (MSG_HID_RAW_DATA, MSG_HID_SIMULATED) = range(600, 602)
    HID_DEVICE = 'HID Device'

    def __init__(self, *args, **kwargs):
        super(PhyMessage, self).__init__(PhyMessage.HID_DEVICE, *args, **kwargs)
        self.report_lock = RLock()

    def send(self):
        #print("PhyMessage send")
        self.report_lock.acquire()

        result = super(PhyMessage, self).send()
        self.report_lock.release()

        return result

class Hid_Device(PhyDevice):

    VID_PID_LIST = [(0x03eb, 0x6123)]  #vid/pid
    (HID_EVENT_ID, HID_EVENT_SIMULATED_ID) = (1, 999)   #True is return from hid.core if there is event

    USAGE_ID_INPUT = usbhid.get_full_usage_id(0xffff, 0x03)
    USAGE_ID_OUTPUT = usbhid.get_full_usage_id(0xffff, 0x05)
    CMD_STACK_DEPTH = 2
    CMD_TIMEOUT = 0.5 #timeout of command

    def __init__(self, *args, **kwargs):
        super(Hid_Device, self).__init__(*args, **kwargs)
        self.report_in = None
        self.report_out = None
        self.hid_cmd = []   #only support 1 command depth by hardware
        # parent, client = Pipe(duplex=False)
        # self.pipe_hid_event = client
        # self.pipe_hid_recv = parent

    # def __del__(self):
    #     print("<{}> del".format(self.__class__.__name__))
        # self.pipe_hid_event.close()
        # self.pipe_hid_recv.close()
        #super(Hid_Device, self).__del__()

    def start(self, default_pipe):
        super(Hid_Device, self).start(default_pipe)
        self.open_dev()

    def stop(self, default_pipe):
        self.close_dev()
        super(Hid_Device, self).stop(default_pipe)

    def open_dev(self):
        self.phy.open()

        for report in self.phy.find_output_reports():
            #print(report)
            if self.USAGE_ID_OUTPUT in report:
                self.report_out = report
                break

        for report in self.phy.find_input_reports():
            if self.USAGE_ID_INPUT in report:
                self.report_in = report
                break

        # self.phy.add_event_handler(self.USAGE_ID_INPUT,
        #                            self.phy_event_handler, usbhid.HID_EVT_ALL)  # level usage

        self.phy.set_raw_data_handler(self.phy_raw_data_handler)

        print("HID report out: {}".format(self.report_out))
        print("HID report in: {}".format(self.report_in))

    def close_dev(self):
        self.phy.close()

    def handle_phy_test_message(self, cmd, msg):
        print(self.__class__.__name__, "handle_phy_test_message", msg)
        seq = cmd.seq()  # to parent seq
        seq.pop()

        cmd_data = cmd.raw_data()
        value = msg.value()

        attached = cmd_data[0] == value[0]
        return HidMessage(Message.MSG_BRIDGE_ATTACH, self.id(), seq, value=attached,
                pipe=self.logic_pipe())

    def handle_phy_rw_message(self, cmd, msg):
        #print("handle_hid_read_message")
        type = cmd.parent_type()
        seq = cmd.seq()  # to parent seq
        seq.pop()
        (RW_OK, NAK_W, NAK_ADDR, W_ONLY_OK) = range(4)

        cmd_data = cmd.raw_data()
        op = cmd.op
        value = msg.value()
        status = value[0]
        size = value[1]

        if (not status and not size):
            return

        if op == 'r' and cmd_data[2]:   # command data[2] is readsize
            if status == RW_OK and size <= cmd.transfered_size():
                result = value[2: size + 2]
            else:
                result = []
            return HidMessage(type, self.id(), seq, value=result,
                    pipe=self.logic_pipe())
        elif op == 'w':
            if status == W_ONLY_OK and cmd.transfered_size() >= size:
                result = size
            else:
                result = 0
            return HidMessage(type, self.id(), seq, value=result,
                    pipe=self.logic_pipe())

    def handle_phy_raw_message(self, cmd, msg):
        type = cmd.parent_type()
        seq = cmd.seq()  # to parent seq
        seq.pop()

        value = msg.value()
        return HidMessage(type, self.id(), seq, value=value,
                      pipe=self.logic_pipe())

    def handle_phy_ouput_message(self, cmd, msg):
        cmd_data = cmd.raw_data()
        type = cmd.parent_type()
        seq = cmd.seq()  # to parent seq
        seq.pop()

        (OK, FAILED) = range(2)

        value = msg.value()
        if cmd_data[0] == value[0] and value[1] == OK:
            result = True
        else:
            result = False

        return HidMessage(type, self.id(), seq, value=result,
                      pipe=self.logic_pipe())

    def handle_phy_interrupt_message(self, msg):
        type = Message.MSG_DEVICE_INTERRUPT_DATA
        seq = Message.seq_root()

        (RW_OK, NAK_W, NAK_ADDR, W_ONLY_OK) = range(4)
        #print(self.__class__.__name__, "int", msg)
        value = msg.value()
        if value[0] == 0x9A and value[1] == RW_OK:
            return HidMessage(type, self.id(), seq, value=value[2:],
                          pipe=self.logic_pipe()).send()
        else:
            print(self.__class__.__name__, "Invalid irq message:", value)

    def handle_phy_nak_message(self, cmd):
        seq = cmd.seq()  # to parent seq
        seq.pop()
        HidMessage(Message.MSG_DEVICE_NAK, self.id(), seq, pipe=self.logic_pipe()).send()

    def handle_phy_message(self, msg):
        #print(self.__class__.__name__, "handle_phy_message")



        result = None
        for i, cmd in enumerate(self.hid_cmd[:]):
            if cmd.is_status(Message.SEND): # PhyMessage.MSG_HID_RAW_DATA
                #print(self.__class__.__name__, "cmd:", cmd)
                #print(self.__class__.__name__, "msg:", msg)

                if cmd.type() == HidCommand.CMD_TEST:
                    result = self.handle_phy_test_message(cmd, msg)
                elif cmd.type() == HidCommand.CMD_WRITE_READ:
                    result = self.handle_phy_rw_message(cmd, msg)
                elif cmd.type() == HidCommand.CMD_RAW:
                    result = self.handle_phy_raw_message(cmd, msg)
                elif cmd.type() == HidCommand.CMD_IRQ:
                    result = self.handle_phy_ouput_message(cmd, msg)
                else:
                    print(self.__class__.__name__, "Unhandled cmd message", cmd, msg)

                if result:
                    self.hid_cmd.pop(i)
                    result.send()

                break

            elif cmd.is_status(Message.ERROR): # PhyMessage.MSG_HID_SIMULATED
                print(self.__class__.__name__, "cmd error:", cmd)
                self.hid_cmd.pop(i)
                result = False
                break

        if result:
            if cmd.repeatable():  # repeatable message added in
                cmd.reset_repeat(Message.REPEAT)
                self.hid_cmd.append(cmd)
        else:
            if result is None:
                self.handle_phy_interrupt_message(msg)
            else:
                print(self.__class__.__name__, "Unknow phy msg:", msg)
                self.handle_phy_nak_message(cmd)

    def phy_event_handler(self, raw_data, event_type):  # this may be a asyn thread/process, need lock report pipe
        "simple usage control handler"

        #print("HID PHY EVENT:", event_type, raw_data)

        msg = PhyMessage(PhyMessage.MSG_HID_RAW_DATA, self.id(), Message.seq_root(), event=event_type,
                         value=array.array('B', raw_data[1:]))
        self.handle_phy_message(msg)

    def phy_raw_data_handler(self, raw_data):
        self.phy_event_handler(raw_data, usbhid.HID_EVT_ALL)

    def hid_proc_poll_command(self, type, seq, extra_info):
        "Test command 1"

        command = HidCommand(HidCommand.CMD_TEST, self.next_seq(seq),
                         value=0xca, parent_type=type, **extra_info,
                         pipe=self.report_out, usage=Hid_Device.USAGE_ID_OUTPUT)

        self.prepare_command(command)

    def hid_proc_block_read_command(self, type, seq, data):
        cmd = HidCommand(HidCommand.CMD_WRITE_READ, self.next_seq(seq),
                         addr=data['addr'], size=data['size'], parent_type=type,
                         pipe=self.report_out, usage=Hid_Device.USAGE_ID_OUTPUT)
        self.prepare_command(cmd)

    def hid_proc_block_write_command(self, type, seq, data):
        cmd = HidCommand(HidCommand.CMD_WRITE_READ, self.next_seq(seq),
                         addr=data['addr'], value=data['value'], parent_type=type,
                         pipe=self.report_out, usage=Hid_Device.USAGE_ID_OUTPUT)
        self.prepare_command(cmd)

    def hid_proc_raw_data_command(self, type, seq, data):
        cmd = HidCommand(HidCommand.CMD_RAW, self.next_seq(seq),
                         value=data['value'], parent_type=type,
                         pipe=self.report_out, usage=Hid_Device.USAGE_ID_OUTPUT)
        self.prepare_command(cmd)

    def hid_proc_msg_output_command(self, type, seq, data):
        cmd = HidCommand(HidCommand.CMD_IRQ, self.next_seq(seq),
                         addr=data['addr'], size=data['size'], parent_type=type,
                         pipe=self.report_out, usage=Hid_Device.USAGE_ID_OUTPUT)
        self.prepare_command(cmd)

    def prepare_command(self, command):
        if len(self.hid_cmd) >= Hid_Device.CMD_STACK_DEPTH:
            print("Hid has command in list: {}".format(self.hid_cmd))
            cmd = self.hid_cmd.pop()
            self.handle_phy_nak_message(cmd)

        #print(self.__class__.__name__, "prepare_command", command)
        self.hid_cmd.append(command)

    def handle_timeout_command(self):
        for cmd in self.hid_cmd[:]:
            if cmd.is_status(Message.SEND):
                if cmd.timeout(Hid_Device.CMD_TIMEOUT):
                    print("HID command timeout: {}".format(cmd))
                    self.hid_cmd.remove(cmd)
                    self.handle_phy_nak_message(cmd)

    def send_command(self):
        #print("{} send command (has {} cmd in list)".format(self.__class__.__name__, len(self.hid_cmd)))

        pending = any(map(lambda c: c.is_status(Message.SEND), self.hid_cmd))
        if pending:
            #print(self.__class__,__name__, "pending {} command".format(len(self.hid_cmd)), self.hid_cmd)
            pass
        else:
            for cmd in self.hid_cmd:
                if cmd.ready():
                    cmd.send() #send 1 only each time
                    break

    def handle_bus_command(self, msg):
        type = msg.type()
        seq = msg.seq()
        extra_info = msg.extra_info()

        if type == Message.CMD_POLL_BRIDGE:
            self.hid_proc_poll_command(type, seq, extra_info)
        # elif type == Message.CMD_POLL_DEVICE:
        #     self.hid_proc_poll_command(type, seq, extra_info)
        elif type == Message.CMD_DEVICE_BLOCK_READ or type == Message.CMD_DEVICE_PAGE_READ:
            self.hid_proc_block_read_command(type, seq, extra_info)
        elif type == Message.CMD_DEVICE_BLOCK_WRITE or type == Message.CMD_DEVICE_PAGE_WRITE:
            self.hid_proc_block_write_command(type, seq, extra_info)
        elif type == Message.CMD_DEVICE_RAW_DATA:
            self.hid_proc_raw_data_command(type, seq, extra_info)
        elif type == Message.CMD_DEVICE_MSG_OUTPUT:
            self.hid_proc_msg_output_command(type, seq, extra_info)
        else:
            print("Unknown message type {}".format(type))

    def poll_interval(self):
        wait_list = []
        if len(self.hid_cmd):
            wait_list.append(Hid_Device.CMD_TIMEOUT)   #command timeout

            for cmd in self.hid_cmd:
                t = cmd.delay_time()
                if t is not None:
                    wait_list.append(t)

        if len(wait_list):
            interval = min(wait_list)
            #print(self.__class__.__name__, "Polling interval {:0.2} [{}]".format(interval, wait_list))
            return interval

        #print(self.__class__.__name__, "Pause")
        #return None for infinite

    def process(self):
        super(Hid_Device, self).process()

        all_pipes = [self.phy_pipe()]
        close_handle = False
        if not close_handle:
            #try:
            for r in MessageServer.wait(all_pipes, timeout=self.poll_interval()):
                if r:
                    try:
                        msg = r.recv()
                    except EOFError:
                        print("Process EOF: {}".format(self.__class__.__name__))
                        close_handle = True
                        self.close_dev()
                        # self.pipe_hid_event.close()
                        # self.pipe_hid_recv.close()
                        return

                    #print("Process<{}> get: {}".format(self.__class__.__name__, msg))

                    self.handle_bus_command(msg)
                    # location = msg.loc()
                    # if location == PhyMessage.HID_DEVICE:
                    #     #self.handle_phy_message(msg)
                    # elif location == PhyMessage.SERVER:
                    #     self.handle_bus_command(msg)
                    # else:
                    #     pass

            self.send_command()
            self.handle_timeout_command()

class Hid_Bus(Bus):

    def __init__(self):
        super(Hid_Bus, self).__init__()

    def create_new_device(self, *args, **kwargs):
        #super(Hid_Bus, self).create_new_device(args, kwargs)
        return Hid_Device(*args, **kwargs)

    def refresh(self):
        phys = []
        for vid_pid in Hid_Device.VID_PID_LIST:
            phys.extend(self.show_hids(*vid_pid))

        #print(phys)
        return phys

    def show_hids(self, target_vid=0, target_pid=0, output=None):
        """Check all HID devices conected to PC hosts."""
        # first be kind with local encodings
        if not output:
            # beware your script should manage encodings
            output = sys.stdout
        # then the big cheese...
        #from hid.core import tools
        all_hids = None
        if target_vid:
            if target_pid:
                # both vendor and product Id provided
                device_filter = usbhid.core.HidDeviceFilter(vendor_id=target_vid,
                        product_id=target_pid)
            else:
                # only vendor id
                device_filter = usbhid.core.HidDeviceFilter(vendor_id=target_vid)

            all_hids = device_filter.get_devices()
        else:
            all_hids = usbhid.core.find_all_hid_devices()
        # if all_hids:
        #     print("Found HID class devices!, writting details...")
        #     for dev in all_hids:
        #         device_name = str(dev)
        #         output.write(device_name)
        #         output.write('\n\n  Path:      %s\n' % dev.device_path)
        #         output.write('\n  Instance:  %s\n' % dev.instance_id)
        #         output.write('\n  Port (ID): %s\n' % dev.get_parent_instance_id())
        #         output.write('\n  Port (str):%s\n' % str(dev.get_parent_device()))
        #         #
        #         try:
        #             dev.open()
        #             tools.write_documentation(dev, output)
        #         finally:
        #             dev.close()
        #     print("done!")
        # else:
        #     print("There's not any non system HID class device available")

        return all_hids

if __name__ == '__main__':
    if sys.version_info < (3,):
        import codecs
        output = codecs.getwriter('mbcs')(sys.stdout)
    else:
        # python3, you have to deal with encodings, try redirecting to any file
        output = sys.stdout
    try:
        hid_bus = Hid_Bus()
        check_list = []
        check_list.extend(Hid_Device.VID_PID_LIST)
        check_list.append((0, 0))
        for vid, pid in check_list:
            print("check vid=%x pid=%x" % (vid, pid))
            devices = hid_bus.show_hids(vid, pid, output = output)
            if devices:
                print("Found HID class devices!, writting details...")
                for dev in devices:
                    device_name = str(dev)
                    output.write(device_name)
                    output.write('\n\n  Path:      %s\n' % dev.device_path)
                    output.write('\n  Instance:  %s\n' % dev.instance_id)
                    output.write('\n  Port (ID): %s\n' % dev.get_parent_instance_id())
                    output.write('\n  Port (str):%s\n' % str(dev.get_parent_device()))
                    #
                    try:
                        dev.open()
                        tools.write_documentation(dev, output)
                    finally:
                        dev.close()
                print("done!")
                break
            else:
                print("There's not any non system HID class device available")

    except UnicodeEncodeError:
        print("\nError: Can't manage encodings on terminal, try to run the script on PyScripter or IDLE")

