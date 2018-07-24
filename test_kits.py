import time

class TestKits(object):
    TEST_MAJOR_LOOP_COUNT = 100 #number
    TEST_ASSERT_LOOP_COUNT = 12
    TEST_FRAME_INIT_TIME = 1    #seconds
    #TEST_FRAME_RESET_COMPLETED = 0.3 #seconds
    PWM_PULSE_ASSERT_TIME = 1.5 #second


    (F_ST, F_ODD, F_EVEN) = range(3)

    def __init__(self, **kwargs):
        self.ticks = 0
        self.frame = 0
        self.api = kwargs.get("api")

    def done(self):
        self.ticks = 0
        self.frame += 1

    def timeout(self, interval_timeout):
        return time.time() - self.ticks > interval_timeout

    def fid(self):
        return self.frame %self.TEST_ASSERT_LOOP_COUNT

    def is_frame(self, frame_t):
        frame = self.fid()
        if not frame:
            ftp = self.F_ST
        elif frame & 0x1:
            ftp = self.F_ODD
        else:
            ftp = self.F_EVEN

        return ftp == frame_t

    def get_toggle_interval(self):
        return int((self.frame / 2) % self.TEST_MAJOR_LOOP_COUNT)

    def poll(self):
        if self.is_frame(self.F_ST):
            if not self.ticks:
                raw_data = [0x83, 0x40, 0x40, 0xBF, 0] #RST not assert
                set_raw_command = self.api['set_raw_command']
                set_raw_command(raw_data)
                self.ticks = time.time()
            else:
                if self.timeout(self.TEST_FRAME_INIT_TIME):
                    set_get_chip_info = self.api['set_get_chip_info']
                    set_get_chip_info()
                    self.done()
        elif self.is_frame(self.F_ODD):    #assert time
            if not self.ticks:
                raw_data = [0x73, 0x6, 0x00, 0x0, 0x0, 0x0]  # RST assert
                set_raw_command = self.api['set_raw_command']
                set_raw_command(raw_data)
                self.ticks = time.time()
            else:
                if self.timeout(self.PWM_PULSE_ASSERT_TIME):
                    self.done()
        else: #toggle time
            toggle_time = self.get_toggle_interval()
            raw_data = [0x73, 0x6, 0x01, 0x1, 0x0, 0]  # RST toggle pulse
            set_raw_command = self.api['set_raw_command']
            set_raw_command(raw_data)
            self.ticks = 0
            self.frame += 1

