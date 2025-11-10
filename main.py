from bus.hid_bus import Hid_Bus, Hid_Device
from bus.message import Message
from bus.device.devinfo import Page, MemMapStructure as Mm, ObjectT6 as T6, ObjectT7 as T7, ObjectT8 as T8, OBJECT_T37 as T37
import time
import array
import queue
import serial
import serial.tools.list_ports
import csv
import os
import sys
import argparse
import msvcrt  # Windows 专用

class AppError(Exception):
    "App error exception class type"
    pass

class MxtStruct(Mm):
    #hid message type
    (MSG_HID_RAW_DATA, MSG_HID_SIMULATED) = range(600, 602)
     # 定义超时时间（秒）
    TIMEOUT_MSG = 0.5
    TIMEOUT_DIAG_COMMAND = 0.1
    TIMEOUT_WAIT_CLEAR_LOOP = 0.1
    TIMEOUT_WRITEBACK = 0.01

    data_queue = queue.Queue()

    def __init__(self, dev: Hid_Device):
        self.dev = dev
        self._seqnum = 0
        super(MxtStruct, self).__init__()

    @staticmethod
    def on_data_received(raw_data):
        # print("Received data:", raw_data)
        msg = Message(MxtStruct.MSG_HID_RAW_DATA, 0, Message.seq_root(), [], 
                            value=array.array('B', raw_data[1:]))
        MxtStruct.data_queue.put(msg)

    def seq(self):
        seq = self._seqnum
        self._seqnum = seq + 1
        return [seq]

    def send_and_receive(self, cmd, timeout=TIMEOUT_MSG):
        # send command
        if cmd:
            cmd.send()

        # wait data back
        try:
            while True:
                msg = MxtStruct.data_queue.get(timeout)
                if cmd:
                    result = self.dev.decode_message(cmd, msg)
                    if not result:
                        print("Drop unexpected message: ", msg)
                    else:
                        return result
                else:
                    return msg
        except Exception as e:
            print("Receive timeout: ", e, cmd)

    def message_receive(self, timeout=TIMEOUT_MSG):
        try:
            # wait data back
            while True:
                msg = MxtStruct.data_queue.get(timeout)
                result = self.dev.decode_auto_repeat_message(msg)
                if not result:
                    print("Not auto repeat message: ", msg)
                else:
                    msg.set_extra_info(value=result)
                    return msg
        except Exception as e:
            print("Receive timeout: ", e, cmd)

    def set_bridge_config(self):
        result = self.send_and_receive(self.dev.enpack_config_command(MxtStruct.MSG_HID_SIMULATED, self.seq()))
        if result:
            return result.value()

    def set_auto_repeat_enable(self, addr, size):
        result = self.send_and_receive(self.dev.enpack_repeat_enable_command(MxtStruct.MSG_HID_SIMULATED, self.seq(), {"addr":addr, "size": size}))
        if result:
            return result.value()

    def save_page_data(self, page_id, addr, size, data):
        data_size = len(data)  #current readout data size
        if data_size == 0 or data_size > size:  #something error
            print(self.__class__.__name__, "save_page_data size invalid", page_id, data)
            return

        page = self.get_page(page_id)
        start = addr - page.addr()
        result = page.save_to_buffer(start, data)
        if not result:
            print(self.__class__.__name__, "save_page_data save_to_buffer failed")
            return

    def parse_page_data(self, page_id):
        page = self.get_page(page_id)
        if not page.buffer_data_valid():
            print(self.__class__.__name__, "parse_page_data data is not enough")
            return
        
        result = self.page_parse(page_id)
        if not result:
            print(self.__class__.__name__, "parse_page_data failed")
            page.clear_buffer()
        
        return page


    def page_read(self, page_id, parse = True):
        page = self.get_page(page_id)
        addr = page.addr()
        size = page.size()

        while (size):
            result = self.send_and_receive(self.dev.enpack_block_read_command(MxtStruct.MSG_HID_SIMULATED, self.seq(), {'addr': addr, 'size': size }))
            if result and result.value():
                data = result.value()
                self.save_page_data(page_id, addr, size, data)
                
                curr_size = len(data)
                addr += curr_size
                size -= curr_size
            else:
                raise AppError(f"read page {page_id} failed: addr {addr} size {size} Failed")
        
        if parse:
            page = self.parse_page_data(page_id)
            
        return page

    def page_write(self, page_id):
        page = self.get_page(page_id)
        data = page.buf()
        addr = page.addr()
        size = page.size()
        off = 0

        while (off < size):
            result = self.send_and_receive(self.dev.enpack_block_write_command(MxtStruct.MSG_HID_SIMULATED, self.seq(), {'addr': addr + off, 'value': data[off:]}))
            if result and result.value():
                curr_size = result.value()
                off += curr_size
            else:
                raise AppError(f"write page {page_id} failed: addr {addr} size {size} off {off}")
        
        return page

    def object_read(self, page_id, field_name):

        page = self.page_read(page_id)
        if not page:
            print(f"Object write: page {page_id} not existed")
            return
        
        obj = page.get_info()
        if not obj:
            print(f"Object write: page {page_id} info not existed")
            return
        
        # read from structure
        return obj[field_name]

    def object_write(self, page_id, field_name, value, check = True):

        page = self.page_read(page_id)
        if not page:
            print(f"Object write: page {page_id} not existed")
            return
        
        obj = page.get_info()
        if not obj:
            print(f"Object write: page {page_id} info not existed")
            return
        
        # write to structure
        obj[field_name] = value

        # Sync to buffer
        page.data_writeback()

        # issue to device
        page = self.page_write(page_id)
        if not page:
            print(f"Object write: page {page_id} write failed")
            return

        # check whether it has been executed
        if check is not False:
            if check is True:
                check_value = value
            elif isinstance(check, int):
                check_value = check
            else:
                check_value = value    
            return self.object_check(page_id, field_name, check_value)

        return True

    def object_check(self, page_id, field_name, value):
        for i in range(16):
            page = self.page_read(page_id)
            if not page:
                print(f"Object check: page {page_id} not existed")
                return
        
            obj = page.get_info()
            if not obj:
                print(f"Object check: page {page_id} info not existed")
                return
            
            if obj[field_name] == value:
                return True

            time.sleep(MxtStruct.TIMEOUT_WRITEBACK if value else MxtStruct.TIMEOUT_WAIT_CLEAR_LOOP)
        
        print(f"object_check page id {page_id} {field_name} {value} failed: ", self.page_read(page_id).buf())

    def read_info_block(self):
        page_id_list = (Page.ID_INFORMATION, Page.OBJECT_TABLE)
        for page_id in page_id_list:
            page = self.page_read(page_id)
            
            if not page.buffer_data_valid():
                raise AppError("<{}> get page {} failed".format(self.__class__.__name__, page_id))
            
        return True
    
    def object_t37_read(self):
        page_id = (Mm.MXT_DEBUG_DIAGNOSTIC_T37, 0)
        page = self.page_read(page_id, False)
        if page:
            return T37(page)

    def diagnostic(self, diag, next_page = 0, wait = True):
        t6_page_id = (Mm.MXT_GEN_COMMAND_T6, 0)

        result = self.object_write(t6_page_id, "diagnostic", diag, 0)
        if not result:
            print(f"Diagnostic command {diag} failed")
            return
        
        if next_page:
            curr = 0
            while curr != next_page:
                page_cmd = T6.MXT_DIAGNOSTIC_PAGEDOWN if curr < next_page else T6.MXT_DIAGNOSTIC_PAGEUP
                result = self.object_write(t6_page_id, "diagnostic", page_cmd, False)
                if not result:
                    print(f"Diagnostic command {diag} failed")
                    return
                
                # for old firmware compatible 
                time.sleep(MxtStruct.TIMEOUT_DIAG_COMMAND)

                obj = self.object_t37_read()
                if obj:
                    if obj.mode() == diag:
                        curr = obj.page()
                    else:
                        print(f"Diagnostic command {diag} mode {obj.mode()} failed")
                        return
                else:
                    print(f"Diagnostic command {diag} page {next_page} curr {page} failed")
                    return
        else:
            # for old firmware compatible 
            if wait:
                time.sleep(MxtStruct.TIMEOUT_DIAG_COMMAND)

        obj = self.object_t37_read()
        if obj:
            def switch_case(obj, value):
                switcher = {
                    T6.MXT_DIAGNOSTIC_PTC_DELTA: obj.buff_s16,
                    T6.MXT_DIAGNOSTIC_KEY_DELTA: obj.buff_s16,
                    T6.MXT_DIAGNOSTIC_SC_DELTA: obj.buff_s16,

                    T6.MXT_DIAGNOSTIC_PTC_REF: obj.buff_u16,
                    T6.MXT_DIAGNOSTIC_KEY_REF: obj.buff_u16,
                    T6.MXT_DIAGNOSTIC_MC_REF: obj.buff_u16,
                    T6.MXT_DIAGNOSTIC_SC_REF: obj.buff_u16,

                    T6.MXT_DIAGNOSTIC_PTC_SIGNAL: obj.buff_u16,
                    T6.MXT_DIAGNOSTIC_MC_SIGNAL: obj.buff_u16,
                    T6.MXT_DIAGNOSTIC_KEY_SIGNAL: obj.buff_u16,
                    T6.MXT_DIAGNOSTIC_SC_SIGNAL: obj.buff_u16,
                }

                # 使用 get 方法获取对应的函数，如果没有找到则返回 common_case
                func = switcher.get(value, obj.buff_raw)
                return func()
		
            if obj.mode() == diag and obj.page() == 0:
                return switch_case(obj, diag)


class HidApp(object):

    time_last = 0 
    tick = 0

    def mxt_proc_t16_message(self, msg):
        MXT_T61_STATUS_RUNNING = 1 << 0    # BIT(0) = 1
        MXT_T61_STATUS_FORCERPT = 1 << 4   # BIT(4) = 16
        MXT_T61_STATUS_STOP = 1 << 5       # BIT(5) = 32
        MXT_T61_STATUS_START = 1 << 6      # BIT(6) = 64
        MXT_T61_STATUS_ELAPSED = 1 << 7    # BIT(7) = 128

        timestamp = msg.time()
        interval = timestamp - self.time_last
        if not self.time_last:
            local_time = time.localtime(timestamp)
            formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
            result = f"Test starting time: {formatted_time}"
        else:
            data = msg.value()
            status = data[0]
            parts = [
                f"{self.tick} T61 Status {status:02X} Interval {interval:.3f}",
                " RUNNING" if status & MXT_T61_STATUS_RUNNING else "",
                " FORCE" if status & MXT_T61_STATUS_FORCERPT else "",
                " STOP" if status & MXT_T61_STATUS_STOP else "",
                " START" if status & MXT_T61_STATUS_START else "",
                " ELAPSED" if status & MXT_T61_STATUS_ELAPSED else "",
                " Timeout" if interval < 5.5 or interval > 6.5 else ""
            ]

            result = "".join(parts)

        print(result)

        self.time_last = timestamp
        self.tick = self.tick + 1

        return result

    def run(self, file):
        # Hid Bus
        bus = Hid_Bus()

        phy = None
        while not phy:
            phy = bus.refresh()
            if not phy:
                print("Please connect bridge board")
                time.sleep(2)

        
        output = []
        if phy:
            # creat Hid device
            dev = bus.create_new_device(phy)

            # create queue for message recieving
            data_queue = queue.Queue()

            # set receiving callback
            phy.set_raw_data_handler(MxtStruct.on_data_received)

            mxt = MxtStruct(dev)
            if not mxt.set_bridge_config():
                print("Mxt Device is not conneced")
                # time.sleep(2)
            else:
                if not mxt.read_info_block():
                    raise AppError("Mxt Information table is not readable")
                else:
                    
                    # Get ID Information
                    page = mxt.get_page(Page.ID_INFORMATION)
                    id_info = page.get_info()
                    if not id_info:
                        raise AppError("Mxt ID information table is found")
                    
                    # Get Object table
                    page = mxt.get_page(Page.OBJECT_TABLE)
                    obj_table = page.get_info()
                    if not obj_table:
                        raise AppError("Mxt Object table is found")

                    # T5 message
                    obj_info = obj_table[Mm.MXT_GEN_MESSAGE_T5]
                    addr = obj_info.start_address
                    size = obj_info.size_minus_one + 1

                    # enable message report
                    mxt.set_auto_repeat_enable(addr, size)

                    # T61
                    page_id = (Mm.MXT_SPT_TIMER_T61, 0)
                    t16_page = mxt.get_page(page_id)
                    print("T61[0] report id is ", t16_page.get_report_id())

                    # output.append(arr)
                    # print(arr)
                    

                    print("Press 's' to exit...")
                    while True:
                        if msvcrt.kbhit():  # 检查是否有按键
                            key = msvcrt.getch().decode('utf-8').lower()  # 获取按键并转换为小写
                            if key == 's':
                                print("Detected 's' button, exiting")
                                break
                        
                        timeout = 10
                        line = None
                        msg = mxt.message_receive(timeout)
                        if msg and msg.size():
                            data = msg.value()
                            if data[0] == t16_page.get_report_id():
                                line = self.mxt_proc_t16_message(msg)
                        else:
                            line = f"timeout {timeout} at {time.time()}"
                        
                        if line:
                            file.write(line + "\n")
                            file.flush()
                            output.append(line)
        
            phy.close()

            return output


class Writer(object):

    def __init__(self, filename = "output.csv"):
        # 指定要写入的 CSV 文件名
        self.filename = filename

    def run(self, info, data):
        # 打开文件并创建一个 csv.writer 对象
        with open(self.filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)

            print("Write chip infomation")
            for name, value in info.items():
                if isinstance(value, list) and all(isinstance(x, int) for x in value):
                    value = ",".join(f"{v:02X}" for v in value)

                file.write(f"{name}:, {value}\n")  
            
            # 写入数据
            print("Write data")
            for row in data:
                writer.writerow(row)

        print(f"Write to file: {self.filename}")


#cmd = ["-f", r"out\message.csv"]
cmd = None
if __name__ == '__main__':
    def parse_args(args=None):

        parser = argparse.ArgumentParser(
            prog='xparse',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description='Tools for log Graphic debugview data and UPDI information')

        parser.add_argument('--version',
                            action='version', version='%(prog)s v1.0.1',
                            help='show version')

        parser.add_argument('-f', '--filename', 
                            required=False,
                            nargs='?',
                            default='output.txt',
                            metavar='LOG_FILE',
                            help='where the the data will be stored')

        return parser


    def runstat(args=None):
        parser = parse_args(args)
        aargs = args if args is not None else sys.argv[1:]
        args = parser.parse_args(aargs)
        print(args)

        if not args.filename and not args.scan:
            parser.print_help()
            return

        #if os.path.exists(args.filename):
        #    print(f"output file existed {args.filename}")
            #return
        
        return args

    args = runstat(cmd)
    if not args:
        raise AppError("args invalid")

    local_time = time.localtime(time.time())
    formatted_time = time.strftime("%Y%m%d_%H%M%S", local_time)
    
    if args.filename.endswith('.txt'):
        filename = args.filename.replace('.txt', f'_{formatted_time}.txt')
    else:
        filename = f"{args.filename}_{formatted_time}.txt"

    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        app = HidApp()
        data = app.run(file)

        local_time = time.localtime(time.time())
        formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
    
        file.write(f"finished at {formatted_time}" + "\n")
        file.flush()



   