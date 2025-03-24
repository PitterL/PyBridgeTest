import ctypes
from ctypes.wintypes import BYTE, WORD
import array
import struct
UBYTE = ctypes.c_ubyte

class MemError(Exception):
    "Message error exception class type"
    pass

def BIT(shift_bit):
    return 1 << shift_bit

# 定义支持字典访问的基类
class DictStructure(ctypes.Structure):
    def __getitem__(self, key):
        if key in [field[0] for field in self._fields_]:
            return getattr(self, key)
        else:
            raise KeyError(f"Field '{key}' not found")
    
    def __setitem__(self, key, value):
        if key in [field[0] for field in self._fields_]:
            setattr(self, key, value)
        else:
            raise KeyError(f"Field '{key}' not found")
   

class IdInformation(ctypes.Structure):
    """DEV_BROADCAST_DEVICEINTERFACE ctypes structure wrapper"""
    _fields_ = [
        # size of the members plus the actual length of the dbcc_name string
        ("familiy_id", UBYTE),
        ("variant_id", UBYTE),
        ("version", UBYTE),
        ("build", UBYTE),
        ("maxtrix_xsize", UBYTE),
        ("maxtrix_ysize", UBYTE),
        ("object_num", UBYTE),
    ]
    _pack_ = 1

class ObjectTableElement(ctypes.Structure):
    """DEV_BROADCAST_DEVICEINTERFACE ctypes structure wrapper"""
    _fields_ = [
        # size of the members plus the actual length of the dbcc_name string
        ("type", UBYTE),
        ("start_address", WORD),
        ("size_minus_one", UBYTE),
        ("instances_minus_one", UBYTE),
        ("num_report_ids", UBYTE),
    ]
    _pack_ = 1


class ObjectT6(DictStructure):
    MXT_BOOT_VALUE = 0xa5
    MXT_RESET_VALUE = 0x01
    MXT_BACKUP_VALUE = 0x55
    MXT_BACKUP_STOP_DC = 0x33
    MXT_BACKUP_RESTORE_DC = 0x44

    MXT_DIAGNOSTIC_NONE = 0x0
    MXT_DIAGNOSTIC_PAGEUP = 0x01
    MXT_DIAGNOSTIC_PAGEDOWN = 0x02
    MXT_DIAGNOSTIC_MC_DELTA = 0x10
    MXT_DIAGNOSTIC_MC_REF = 0x11
    MXT_DIAGNOSTIC_MC_SIGNAL = 0x12
    MXT_DIAGNOSTIC_PTC_DELTA = 0x14
    MXT_DIAGNOSTIC_PTC_REF = 0x15
    MXT_DIAGNOSTIC_PTC_SIGNAL = 0x16
    MXT_DIAGNOSTIC_KEY_DELTA = 0x17
    MXT_DIAGNOSTIC_KEY_REF = 0x18
    MXT_DIAGNOSTIC_KEY_SIGNAL = 0x19
    MXT_DIAGNOSTIC_CAL_DATA = 0x33
    MXT_DIAGNOSTIC_SYMBOL_GESTURE = 0x34
    MXT_DIAGNOSTIC_SELF_TEST = 0x35
    MXT_DIAGNOSTIC_DC_DATA = 0x38
    MXT_DIAGNOSTIC_LOW_POWER_MODE = 0x3B
    MXT_DIAGNOSTIC_DEVICE_INFO = 0x80
    MXT_DIAGNOSTIC_PRODUCT_DATA = 0x81
    MXT_DIAGNOSTIC_TOUCHSCREEN = 0xF4
    MXT_DIAGNOSTIC_SC_SIGNAL = 0xF5
    MXT_DIAGNOSTIC_SC_DELTA = 0xF7
    MXT_DIAGNOSTIC_SC_REF = 0xF8

    """DEV_BROADCAST_DEVICEINTERFACE ctypes structure wrapper"""
    _fields_ = [
        # size of the members plus the actual length of the dbcc_name string
        ("reset", UBYTE),
        ("backupnv", UBYTE),
        ("calibrate", UBYTE),
        ("reportall", UBYTE),
        ("rsv", UBYTE),
        ("diagnostic", UBYTE),
    ]
    _pack_ = 1

class ObjectT7(DictStructure):
    """DEV_BROADCAST_DEVICEINTERFACE ctypes structure wrapper"""
    _fields_ = [
        # size of the members plus the actual length of the dbcc_name string
        ("idleacqint", UBYTE),
        ("actvaqint", UBYTE),
        ("actv2idleto", UBYTE),
    ]
    _pack_ = 1


class ObjectT8(DictStructure):
    """DEV_BROADCAST_DEVICEINTERFACE ctypes structure wrapper"""

    MXT_T8_MEASALLOW_MUTUALTCH = BIT(0)
    MXT_T8_MEASALLOW_SELFTCH = BIT(1)
    MXT_T8_MEASALLOW_HOVER = BIT(2)
    MXT_T8_MEASALLOW_SELFPROX = BIT(3)

    _fields_ = [
        # size of the members plus the actual length of the dbcc_name string
        ("chrgtime", UBYTE),
        ("atchdrift", UBYTE),
        ("tchdrift", UBYTE),
        ("driftst", UBYTE),
        ("tchautocal", UBYTE),
        ("sync", UBYTE),
        ("atchcalst", UBYTE),
        ("atchcalsthr", UBYTE),
        ("atchfrccalthr", UBYTE),
        ("atchfrccalratio", UBYTE),
        ("measallow", UBYTE),
        ("measidledef", UBYTE),
        ("measactvdef", UBYTE),
        ("refmode", UBYTE),
        ("cfg", UBYTE),
    ]
    _pack_ = 1

class ObjectT15(DictStructure):
    """DEV_BROADCAST_DEVICEINTERFACE ctypes structure wrapper"""
    _fields_ = [
        # size of the members plus the actual length of the dbcc_name string
        ("ctrl", UBYTE),
        ("xorigin", UBYTE),
        ("yorigin", UBYTE),
        ("xsize", UBYTE),
        ("ysize", UBYTE),
        ("akscfg", UBYTE),
        ("blen", UBYTE),
        ("tchthr", UBYTE),
        ("tchdi", UBYTE),
        ("tchhyst", UBYTE),
        ("antchdi", UBYTE),
    ]
    _pack_ = 1

class ObjectT15(DictStructure):
    """DEV_BROADCAST_DEVICEINTERFACE ctypes structure wrapper"""
    _fields_ = [
        # size of the members plus the actual length of the dbcc_name string
        ("ctrl", UBYTE),
        ("xorigin", UBYTE),
        ("yorigin", UBYTE),
        ("xsize", UBYTE),
        ("ysize", UBYTE),
        ("akscfg", UBYTE),
        ("blen", UBYTE),
        ("tchthr", UBYTE),
        ("tchdi", UBYTE),
        ("tchhyst", UBYTE),
        ("antchdi", UBYTE),
    ]
    _pack_ = 1


class Page(object):
    (ID_INFORMATION, OBJECT_TABLE) = (('I', -1), ('T', -1))  # the value must < 5, which MXT_GEN_MESSAGE_T5 start
    #
    # compond_id is made of OBJECT_ID and INSTANCE_ID
    #
    def __init__(self, compound_id, offset, length, info=None):
        if isinstance(compound_id, (list, tuple)):
            major, minor = compound_id
        else:
            major = compound_id
            minor = -1  # valid minor must >=0

        self.major = major
        self.minor = minor
        self.offset = offset  # page data offset in mem map
        self.length = length  # page data len
        # self.cache = array.array('B', [])   #use to store data in split reading
        self.__buffer = array.array('B', [])  # copy from cache data if split reading complete
        self.info = info

        #print(self.__class__.__name__, self.__str__())

    def __str__(self):
        return "Page {}: addr {start}\tlen {len},\tdata {data}".format(self.id(), start=self.addr(), len=self.size(), data=self.buf())

    def __repr__(self):
        return super(Page, self).__repr__() + '(' + self.__str__() + ')'

    def __iter__(self):
        return iter(self.__buffer)

    def __getitem__(self, key):
        if key < len(self.__buffer):
            return self.__buffer[key]

    # def compound(self):
    #     return self.sub_id() >= 0

    # def id(self):
    #     if self.compound():
    #         return (self.major_id(), self.sub_id())
    #     else:
    #         return self.major_id()

    def id(self):
        return (self.major, self.minor)

    def major_id(self):
        return self.major

    def sub_id(self):
        return self.minor

    def addr(self):
        return self.offset

    def size(self):
        return self.length

    def clear_buffer(self):
        # self.set_info(None)
        del self.__buffer[:]

    def save_to_buffer(self, start, data):
        if not isinstance(data, type(self.__buffer)):
            MemError("save data type not support {}".format(type(data)))
            return

        if not len(data):
            MemError("save data length zero {}".format(type(data)))
            return

        # if start != len(self.__buffer):
        #     MemError("save data offset not support start={} buffer len={}".format(start, len(self.__buffer)))
        #     return
        # if start != len(self.__buffer):
        #     MemError("save data offset not support start={} buffer len={}".format(start, len(self.__buffer)))

        if start + len(data) > self.length:
            MemError("save data lenght over start+data {} buffer max len={}".format(start + len(data), self.length))
            return
        else:
            self.__buffer[start: start + len(data)] = data
            return len(self.__buffer)
    """
    def clear_cache(self):
        del self.cache[:]

    def copy_to_cache(self, start, data):
        if not isinstance(data, type(self.cache)):
            ServerError("copyt to cache data type not support {}".format(type(data)))

        if len(data) and start + len(data) <= self.length:
            self.cache[start: start + len(data)] = data
    """

    def buffer_data_valid(self):
        return self.length and len(self.__buffer) == self.length

    def data_length(self):
        return len(self.__buffer)

    """
    def save(self):
        if len(self.cache) == self.length:
            self.buffer[:] = self.cache[:]
    """

    def buf(self):
        #return self.__buffer[:]  # array('B')
        return self.__buffer

    def set_info(self, info):
        self.info = info

    def get_info(self):
        return self.info

    def data_writeback(self):
        if not isinstance(self.major, int):
            raise MemError(f"{self.major} not support write back")
        
        if self.info:
            data = array.array('B', ctypes.string_at(ctypes.addressof(self.info), ctypes.sizeof(self.info)))
            self.save_to_buffer(0, data)
        else:
            print(f"Page id {self.id()} no data writeback")

        return self

class OBJECT_T37(object):
    UINT16_T = 'H'
    INT16_T = 'h'

    (MODE, PAGE, DATA) = range(3)

    def __init__(self, page):
        self.__page = page

    def __buff_covert(self, buf, sign):
        format = '<' + sign * (len(buf) // 2)
        return array.array(sign, struct.unpack(format, buf))

    def mode(self):
        if self.__page.data_length() > OBJECT_T37.MODE:
            return self.__page.buf()[OBJECT_T37.MODE]

    def page(self):
        if self.__page.data_length() > OBJECT_T37.PAGE:
            return self.__page.buf()[OBJECT_T37.PAGE]

    def buff_u16(self):
        if self.__page.buffer_data_valid():
            return self.__buff_covert(self.__page.buf()[OBJECT_T37.DATA:], OBJECT_T37.UINT16_T)

    def buff_s16(self):
        if self.__page.buffer_data_valid():
            return self.__buff_covert(self.__page.buf()[OBJECT_T37.DATA:], OBJECT_T37.INT16_T)

    def buff_raw(self):
        if self.__page.data_length() > OBJECT_T37.PAGE:
            return self.__page.buf()[OBJECT_T37.DATA:]

class MemMapStructure(object):

    MXT_DEBUG_DIAGNOSTIC_T37 = 37
    MXT_GEN_MESSAGE_T5 = 5
    MXT_GEN_COMMAND_T6 = 6
    MXT_GEN_POWER_T7 = 7
    MXT_GEN_ACQUIRE_T8 = 8
    MXT_GEN_DATASOURCE_T53 = 53
    MXT_TOUCH_MULTI_T9 = 9
    MXT_TOUCH_KEYARRAY_T15 = 15
    MXT_TOUCH_PROXIMITY_T23 = 23
    MXT_TOUCH_PROXKEY_T52 = 52
    MXT_PROCI_GRIPFACE_T20 = 20
    MXT_PROCG_NOISE_T22 = 22
    MXT_PROCI_ONETOUCH_T24 = 24
    MXT_PROCI_TWOTOUCH_T27 = 27
    MXT_PROCI_GRIP_T40 = 40
    MXT_PROCI_PALM_T41 = 41
    MXT_PROCI_TOUCHSUPPRESSION_T42 = 42
    MXT_PROCI_STYLUS_T47 = 47
    MXT_PROCG_NOISESUPPRESSION_T48 = 48
    MXT_SPT_COMMSCONFIG_T18 = 18
    MXT_SPT_GPIOPWM_T19 = 19
    MXT_SPT_SELFTEST_T25 = 25
    MXT_SPT_CTECONFIG_T28 = 28
    MXT_SPT_USERDATA_T38 = 38
    MXT_SPT_DIGITIZER_T43 = 43
    MXT_SPT_MESSAGECOUNT_T44 = 44
    MXT_SPT_CTECONFIG_T46 = 46
    MXT_SPT_DYNAMICCONFIGURATIONCONTAINER_T71 = 71
    MXT_PROCI_SYMBOLGESTUREPROCESSOR = 92
    MXT_PROCI_TOUCHSEQUENCELOGGER = 93
    MXT_TOUCH_MULTITOUCHSCREEN_T100 = 100
    MXT_PROCI_ACTIVESTYLUS_T107 = 107

    OBJECT_ELEMENTS = { 
        MXT_TOUCH_KEYARRAY_T15: ObjectT15,
        MXT_GEN_COMMAND_T6: ObjectT6,
        MXT_GEN_POWER_T7: ObjectT7,
        MXT_GEN_ACQUIRE_T8: ObjectT8
    }

    def __init__(self):
        self.__pages = {} #buffer to store each object instance
        self.__pages[Page.ID_INFORMATION] = Page(Page.ID_INFORMATION, 0, len(IdInformation._fields_))

    def __str__(self):
        result = []
        for i, page in self.__pages.items():
            result.append(str(page))
        return '\n'.join(result)

    def __iter__(self):
        return self.__pages

    def __getitem__(self, key):
        if key in self.__pages.keys():
            return self.__pages[key]

    def create_page(self, page_id, offset, length):
        if length <= 0:
            print(self.__class__.__name__, "create_page size zero", page_id)
            return

        if page_id in self.__pages.keys():
            del self.__pages[page_id]
        self.__pages[page_id] = Page(page_id, offset, length)
        return self.get_page(page_id)

    def delete_page(self, page_id):
        if page_id in self.__pages.keys():
            del self.__pages[page_id]

    def has_page(self, page_id):
        return page_id in self.__pages.keys()

    def get_page(self, page_id):
        return self.__pages.get(page_id, None)

    def to_page_name(self, offset):
        for page in self.__pages.values():
            if offset > page.offset and offset < page.offset + page.length:
                return page.name

        return None

    def page_valid(self, page_id):
        page = self.get_page(page_id)
        if page:
            return page.buffer_data_valid()

    """
    def get_page_data(self, page_id):
        if page_id in self.__pages.keys():
            page = self.__pages[page_id]
            if page.buffer_data_valid():
                return page.buf()   #array('B')

        return array.array('B', [])
 

    def update_page(self, page_id, start, data, discard):
        if page_id in self.__pages.keys():
            page = self.__pages[page_id]
            if discard:
                page.clear_cache()
            page.copy_to_cache(start, data)
            page.save_to_buffer()
    """

    def check_info_crc(self, page_list):
        #FIXME: need achieve
        return True

    def page_parse(self, page_id):

        if not self.has_page(page_id):
            print("{} page {} not exist".format(self.__class__.__name__, page_id))
            return

        page = self.get_page(page_id)
        if not page.buffer_data_valid():
            print("{} page {} data length {}, not ready".format(self.__class__.__name__, page_id, page.data_length()))
            return

        data = page.buf()
        if page_id == Page.ID_INFORMATION:
            if not all(data):
                print(self.__class__.__name__, 'Invalid data', page_id, data)
                return

            print(self.__class__.__name__, "Parse ID information:")
            print(" ".join("{:02x}".format(v) for v in data))

            id_infomation = IdInformation(*struct.unpack_from("B" * ctypes.sizeof(IdInformation), data))
            page.set_info(id_infomation)
            offset = page.addr() + page.size()
            length = id_infomation.object_num * ctypes.sizeof(ObjectTableElement)
            self.create_page(Page.OBJECT_TABLE, offset, length)
        elif page_id == Page.OBJECT_TABLE:
            page_list = {'id':self.get_page(Page.ID_INFORMATION),
                        'obj':self.get_page(Page.OBJECT_TABLE)}

            if not all(page_list.values()):
                print("{} page value empty".format(self.__class__.__name__))
                return

            esize = ctypes.sizeof(ObjectTableElement)
            object_tables = {}
            print(self.__class__.__name__, "Parse Object Table:")
            for n in range(page_list['id'].get_info().object_num):
                #print(self.__class__.__name__, data[n * esize: (n + 1) * esize])
                print(" ".join("{:02x}".format(v) for v in data[n * esize: (n + 1) * esize]))
                element = ObjectTableElement(*struct.unpack_from("<BHBBB", data[n * esize: (n + 1) * esize]))
                offset = element.start_address
                inst = element.instances_minus_one + 1
                for i in range(inst):
                    elem_page_id = (element.type, i)
                    elem_size = element.size_minus_one + 1
                    self.create_page(elem_page_id, offset, elem_size)
                    offset += elem_size
                
                object_tables[element.type] = element

            page_list['obj'].set_info(object_tables)

            if not self.check_info_crc(page_list):
                return
        else:   #not need parse
            major, _ = page_id
            if major in self.OBJECT_ELEMENTS.keys():
                cls = self.OBJECT_ELEMENTS[major]
                esize = ctypes.sizeof(cls)
                if len(data) != esize:
                    if (len(data) > esize):
                        print(f"Parse T{major} with short object definition")
                    else:
                        raise MemError("object size mismatch:".format(esize, len(data)))
                obj_data = cls.from_buffer_copy(data)
                page.set_info(obj_data)

        return page