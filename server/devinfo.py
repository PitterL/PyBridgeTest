import ctypes
from ctypes.wintypes import BYTE, WORD
import array
import struct

UBYTE = ctypes.c_ubyte

class MemError(Exception):
    "Message error exception class type"
    pass

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

class Page(object):
    (ID_INFORMATION, OBJECT_TABLE) = (('I', -1), ('T', -1))  # the value must < 5, which MXT_GEN_MESSAGE_T5 start
    #
    # compond_id is made of OBJECT_ID and INSTANCE_ID
    #
    def __init__(self, compound_id, offset, length, information=None):
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
        self.info = information

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

    def set_info(self, information):
        self.info = information

    def get_info(self):
        return self.info

class MemMapStructure(object):
    """
    ID_INFORMATION = 0,
    OBJECT_TABLE = 1,
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
    """

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

            id_infomation = IdInformation(*struct.unpack_from("B" * ctypes.sizeof(IdInformation), data))
            page.set_info(id_infomation)
            offset = page.addr() + page.size()
            length = id_infomation.object_num * ctypes.sizeof(ObjectTableElement)
            return self.create_page(Page.OBJECT_TABLE, offset, length)
        elif page_id == Page.OBJECT_TABLE:
            page_list = {'id':self.get_page(Page.ID_INFORMATION),
                        'obj':self.get_page(Page.OBJECT_TABLE)}

            if not all(page_list.values()):
                print("{} page value empty".format(self.__class__.__name__))
                return

            esize = ctypes.sizeof(ObjectTableElement)
            object_tables = {}
            for n in range(page_list['id'].get_info().object_num):
                #print(self.__class__.__name__, data[n * esize: (n + 1) * esize])
                element = ObjectTableElement(*struct.unpack_from("<BHBBB", data[n * esize: (n + 1) * esize]))
                offset = element.start_address
                inst = element.instances_minus_one + 1
                for i in range(inst):
                    elem_page_id = (element.type, i)
                    elem_size = element.size_minus_one + 1
                    object_tables[elem_page_id] = element
                    self.create_page(elem_page_id, offset, elem_size)
                    offset += elem_size

            page_list['obj'].set_info(object_tables)
            return self.check_info_crc(page_list)
        else:   #not need parse
            return True