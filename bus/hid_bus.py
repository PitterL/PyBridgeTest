#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
"""
Show all HID devices information
"""

from bus.message import Message, HidMessage
import bus.pywinusb.hid as usbhid
from bus.pywinusb.hid import tools

import sys
import array
from bus.common.dotdict import Dotdict

class HidError(Exception):
    "Hid error exception class type"
    pass

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
    (CMD_CONFIG, CMD_REPEAT, CMD_WRITE_READ, CMD_RAW, CMD_AUTO) = (0x80, (0x88, 0x58), 0x51,  "Raw", "Auto")

    TIMEOUT = 1 #second
    SIZE_MAX = {'r': 63, 'w': 59}
    #SIZE_PROPER = {'r': 64, 'w': 48}

    R = Dotdict({'RESPONSE_OK': 0})
    W = Dotdict({'RESPONSE_OK': 4})

    def __init__(self, type, seq, **kwargs):
        #print(self.__class__.__name__, "init", type, seq, kwargs)

        self._repeat_value = kwargs.pop('repeat', None)
        if self.repeatable():
            #self._repeat = True
            self.repeat_count = 0
        # else:
        #     self._repeat = False

        #self.__timeout = kwargs.pop('timeout', 0)

        super(HidCommand, self).__init__(HidCommand.NAME, type, 0, seq, **kwargs)

        value = []
        if type == HidCommand.CMD_CONFIG:
            #[type, 0, value]
            value = array.array('B', [type, 0x30, kwargs['value']])
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
        elif type == HidCommand.CMD_REPEAT:
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

    def to_trans_format(self, data, id, size):
        raw_data = array.array('B', [id])
        raw_data.extend(data)
        raw_data.extend([0]*(size - len(data) - 1))

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

    def repeatable(self):
        return self._repeat_value is not None

    def raw_data(self):
        return self.__raw_data

    def parent_type(self):
        info = self.extra_info()
        if 'parent_type' in info.keys():
            return info['parent_type']

    def send_to(self, pipe):
        if not pipe:
            raise HidError("Pipe is None", self.__str__())

        report_id = pipe.report_id
        report_length = pipe.report_size

        status = self.status()

        if self.ready():
            self.set_status(Message.SEND)
            data = self.to_trans_format(self.raw_data(), report_id, report_length)
            #print(self.__class__.__name__, "send: {}".format(data))
            pipe.send(data)
            return True

        return False
    
class Hid_Device(object):
    (HID_EVENT_ID, HID_EVENT_SIMULATED_ID) = (1, 999)   #True is return from hid.core if there is event

    CMD_STACK_DEPTH = 2
    CMD_TIMEOUT = 0.5 #timeout of command

    def __init__(self, phy, report):
        self.report_out = report
        self.phy = phy
        self.cmd_seq = 0

    def id(self):
        return Hid_Device.HID_EVENT_ID
    
    def next_seq(self, t):
        self.cmd_seq += 1
        token = t.copy()
        token.append(self.cmd_seq)
        #print(self.__class__.__name__, "next seq {}".format(token))
        return token
    
    def decode_test_message(self, cmd, msg):
        # print(self.__class__.__name__, "handle_phy_test_message", msg)
        id = cmd.id()
        seq = cmd.seq()  # to parent seq
        seq.pop()

        cmd_data = cmd.raw_data()
        value = msg.value()

        attached = cmd_data[0] == value[0]
        return HidMessage(Message.MSG_BRIDGE_ATTACH, id, seq, value=attached)

    def decode_rw_message(self, cmd, msg):
        #print("handle_hid_read_message")
        type = cmd.parent_type()
        seq = cmd.seq()  # to parent seq
        seq.pop()
        (RW_OK, NAK_W, NAK_RSV, NAK_ADDR, W_ONLY_OK) = range(5)

        cmd_data = cmd.raw_data()
        op = cmd.op
        value = msg.value()
        status = value[0]
        rsize = value[1]

        if (not status and not rsize):
            return

        if op == 'r' and cmd_data[2]:   # command data[2] is readsize
            if status == RW_OK and rsize <= cmd.transfered_size():
                result = value[2: rsize + 2]
            else:
                result = []
            return HidMessage(type, self.id(), seq, value=result)
        elif op == 'w':
            if status == W_ONLY_OK:
                result = cmd.transfered_size()
            else:
                result = 0
            return HidMessage(type, self.id(), seq, value=result)

    def decode_raw_message(self, cmd, msg):
        type = cmd.parent_type()
        seq = cmd.seq()  # to parent seq
        seq.pop()

        value = msg.value()
        return HidMessage(type, self.id(), seq, value=value)

    def decode_repeat_ack_message(self, cmd, msg):
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


    def decode_auto_repeat_message(self, msg):
        (RW_OK, NAK_W, NAK_ADDR, W_ONLY_OK) = range(4)
        value = msg.value()
        if value[0] == 0x9A and value[1] == RW_OK:
            return value[2:]
        else:
            print(self.__class__.__name__, "Invalid irq message:", value)

    def decode_message(self, cmd, msg):

        if cmd.type() == HidCommand.CMD_CONFIG:
            result = self.decode_test_message(cmd, msg)
        elif cmd.type() == HidCommand.CMD_WRITE_READ:
            result = self.decode_rw_message(cmd, msg)
        elif cmd.type() == HidCommand.CMD_RAW:
            result = self.decode_raw_message(cmd, msg)
        elif cmd.type() == HidCommand.CMD_REPEAT:
            result = self.decode_repeat_ack_message(cmd, msg)

        if not result:
            print(self.__class__.__name__, "Unhandled cmd message", cmd, msg)

        return result

    def enpack_config_command(self, type, seq, extra_info = {}):
        "config bridge parameter"

        return HidCommand(HidCommand.CMD_CONFIG, self.next_seq(seq),
                         value=0xca, parent_type=type, **extra_info,
                         pipe=self.report_out)


    def enpack_block_read_command(self, type, seq, data):
        return HidCommand(HidCommand.CMD_WRITE_READ, self.next_seq(seq),
                         addr=data['addr'], size=data['size'], parent_type=type,
                         pipe=self.report_out)


    def enpack_block_write_command(self, type, seq, data):
        return HidCommand(HidCommand.CMD_WRITE_READ, self.next_seq(seq),
                         addr=data['addr'], value=data['value'], parent_type=type,
                         pipe=self.report_out)
        

    def enpack_raw_data_command(self, type, seq, data):
        return HidCommand(HidCommand.CMD_RAW, self.next_seq(seq),
                         value=data['value'], parent_type=type,
                         pipe=self.report_out)
        

    def enpack_repeat_enable_command(self, type, seq, data):
        return HidCommand(HidCommand.CMD_REPEAT, self.next_seq(seq),
                         addr=data['addr'], size=data['size'], parent_type=type,
                         pipe=self.report_out)
    

class Hid_Bus(object):

    VID_PID_LIST = [(0x03eb, 0x6123)]  #vid/pid
    USAGE_IDS = [
        (usbhid.get_full_usage_id(0xff00, 0x02), usbhid.get_full_usage_id(0xff00, 0x03)),
        (usbhid.get_full_usage_id(0xffff, 0x02), usbhid.get_full_usage_id(0xffff, 0x04))
    ]


    def __init__(self):
        super(Hid_Bus, self).__init__()
        self.report_out = None
        self.report_in = None

    def create_new_device(self, phy):
        return Hid_Device(phy, self.report_out)

    def outpipe(self):
        return self.report_out
    
    def inpipe(self):
        return self.report_in

    def refresh(self):
        phys = []
        for vid_pid in Hid_Bus.VID_PID_LIST:
            phys.extend(self._show_hids(*vid_pid))

        for phy in phys:
            phy.open()

            for usage_in, usage_out in Hid_Bus.USAGE_IDS:
                for report_out in phy.find_output_reports():
                    if usage_out in report_out:
                        for report_in in phy.find_input_reports():
                            if usage_in in report_in:
                                self.report_out = report_out
                                self.report_in = report_in

                                # self.phy.set_raw_data_handler(self._phy_raw_data_handler)
                                return phy
                            else:
                                for item in report_in.items():
                                    print(f"in - Page ID: {item[1].page_id:04X}, Usage ID: {item[1].usage_id:04X}")
                    else:
                        for item in report_out.items():
                            print(f"Out - Page ID: {item[1].page_id:04X}, Usage ID: {item[1].usage_id:04X}")
            
            phy.close()

        #print(phy)


    def _show_hids(self, target_vid=0, target_pid=0, output=None):
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

