#!/usr/bin/env python3

import struct
import os
import statistics
import argparse

class LedFile(object):
    PRELUDE_OFFSET = 0
    PRELUDE_FORMAT = '<8sIIII'
    PRELUDE_MAGIC = b'\x5FLED\r\n\x1A\n'
    PRELUDE_VERSION = 0 # TODO
    HEADER_FORMAT = '<IIIII'

    PATTERN_PACKET_FORMAT = '<IHII?'
    PATTERN_PACKET_TYPE_DATA = 0
    PATTERN_PACKET_TYPE_SYNC = 1

    PATTERN_TIME_INDEX_FORMAT = '<I'

    def __init__(self, filename):
        self.init(filename)

    def __del__(self):
        if not self.f.closed:
            self.finalize()

    def init(self, filename):
        self.duration_ms = 0
        self.time_index = bytearray()
        self.next_index_time_ms = 0

        self.f = open(filename, 'wb')

        # 1. Reserve space for the prelude
        #   The prelude includes some fields that are hard to calculate
        #   upfront, so just reserve space for it now.
        self.f.seek(self.PRELUDE_OFFSET)
        self.f.write(bytearray(struct.calcsize(self.PRELUDE_FORMAT)))
        
        # 2. header
        #   The header includes some fields that are hard to calculate
        #   upfront, so just reserve space for it now. Also make a note of
        #   it's offset so that it can be included in the prelude.
        self.header_offset = self.f.tell()
        self.f.write(bytearray(struct.calcsize(self.HEADER_FORMAT)))

        # 3. data
        self.data_offset = self.f.tell()

    def addDataPacket(self, timestamp_ms, universe, sync, data):
        self.updateTimeIndex(timestamp_ms)

        data_packet = struct.pack(self.PATTERN_PACKET_FORMAT,
                timestamp_ms,
                len(data),
                self.PATTERN_PACKET_TYPE_DATA,
                universe,
                sync # TODO
                )
        self.f.write(data_packet)
        self.f.write(data)

        self.duration_ms = max(self.duration_ms, timestamp_ms)

    def addSyncPacket(self, timestamp_ms, channels = 0xFFFFFFFF):
        self.updateTimeIndex(timestamp_ms)

        sync_packet = struct.pack(self.PATTERN_PACKET_FORMAT,
                timestamp_ms,
                0,
                self.PATTERN_PACKET_TYPE_SYNC,
                channels,
                True  # TODO
                )
        self.f.write(sync_packet)

        self.duration_ms = max(self.duration_ms, timestamp_ms)

    def updateTimeIndex(self, timestamp_ms):
        if timestamp_ms >= self.next_index_time_ms:
            self.next_index_time_ms += 1000

            index = struct.pack(self.PATTERN_TIME_INDEX_FORMAT,
                    self.f.tell()
                    )
            self.time_index.extend(index)

    def finalize(self):
        print('finalizing')
        # 4. time index
        self.time_index_offset = self.f.tell()

        self.f.write(self.time_index)

        self.eof_offset = self.f.tell()

        # 5. Fill in header
        self.f.seek(self.header_offset)
        header = struct.pack(self.HEADER_FORMAT,
                self.duration_ms, # duration_ms,
                self.data_offset, # data_offset,
                self.time_index_offset - self.data_offset, # data_size,
                self.time_index_offset, # time_index_offset,
                self.eof_offset - self.time_index_offset # time_index_size
                )
        self.f.write(header)

        # 6. Fill in prelude
        self.f.seek(self.PRELUDE_OFFSET)
        prelude = struct.pack(self.PRELUDE_FORMAT,
                self.PRELUDE_MAGIC, #magic,
                0, # TODO: checksum,
                self.PRELUDE_VERSION, # version,
                self.header_offset, # header_offset,
                self.eof_offset #size
                )
        self.f.write(prelude)

        self.f.close()

if __name__ == "__main__":
    import random

    parser = argparse.ArgumentParser()
    parser.add_argument('filename', action="store")
    args = parser.parse_args()

    led = LedFile(args.filename)

    for time in range(0,10000,33):
        led.addDataPacket(time, 0, False, bytearray(random.randrange(512)))
        led.addDataPacket(time, 1, False, bytearray(random.randrange(512)))
        led.addDataPacket(time, 2, False, bytearray(random.randrange(512)))
        led.addSyncPacket(time)
