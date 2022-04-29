#!/usr/bin/python3
import struct
import os
import statistics
import argparse

def dumpFile(filename):
    dump_packets = False

    print('== FILE DUMP ==')
    with open(filename, 'rb') as f:
    # Prelude
        PRELUDE_OFFSET = 0
        PRELUDE_FORMAT = '<8sIIII'
        PRELUDE_MAGIC = b'\x5FLED\r\n\x1A\n'
    
        f.seek(PRELUDE_OFFSET)
        prelude = f.read(struct.calcsize(PRELUDE_FORMAT))
    
        [magic, checksum, version, header_offset, size] = struct.unpack(PRELUDE_FORMAT, prelude)
    
        print('{:08x} Prelude checksum:{:04x} version:{} header_offset:{:08x} size:{}'.format(
            PRELUDE_OFFSET,
            checksum,
            version,
            header_offset,
            size
            ))
    
        if magic != PRELUDE_MAGIC:
            print('bad magic expected:{} got:{}'.format(PRELUDE_MAGIC, magic))
            exit(1)
    
        expected_size = os.path.getsize(filename)
        if expected_size != size:
            print('bad size expected:{} got:{}'.format(expected_size, size))
            exit(1)
    
        # todo: checksum
        # todo: version

    
    # Header
        HEADER_FORMAT = '<IIIII'
        f.seek(header_offset)
        header = f.read(struct.calcsize(HEADER_FORMAT))
    
        [duration_ms, data_offset, data_size, time_index_offset, time_index_size] = struct.unpack(HEADER_FORMAT, header)
    
        print('{:08x} Header duration_ms:{} data_offset:{:08x} data_size:{} time_index_offset:{:08x} time_index_size:{}'.format(
            header_offset,
            duration_ms,
            data_offset,
            data_size,
            time_index_offset,
            time_index_size
            ))
    
        # TODO: check that time index is correct length
        # TODO: check that data section fits in file and doesn't overlap prelude, header, or time index
        # TODO: check that time index section fits in file and doesn't overlap prelude, header, or data
    
    # Analyze data
    
        packet_stats = {'data':0, 'sync':0}
        universe_stats = {} 
        packet_offsets = []
    
        f.seek(data_offset)
        while f.tell() < (data_offset + data_size):
            PATTERN_PACKET_FORMAT = '<IHII?'
            PATTERN_PACKET_TYPE_DATA = 0
            PATTERN_PACKET_TYPE_SYNC = 1
   
            offset = f.tell()
            packet_offsets.append(offset)
    
            packet = f.read(struct.calcsize(PATTERN_PACKET_FORMAT))
            [timestamp_ms, size, packet_type, A, B] = struct.unpack(PATTERN_PACKET_FORMAT, packet)
    
    
            # TODO: Check that the timestamp is >= previous record
    
    
            if packet_type == PATTERN_PACKET_TYPE_DATA:
                [universe, sync] = [A, B]
    #            print('  universe:{} sync:{}'.format(universe, sync))
    
                packet_stats['data'] += 1
                universe_count = universe_stats.setdefault(universe, [])
                universe_stats[universe].append(timestamp_ms)
    
                # TODO: Check that size is <= 512?
    
            elif packet_type == PATTERN_PACKET_TYPE_SYNC:
    #            print('  output_flags:{:08x}'.format(A))
    
                packet_stats['sync'] += 1

                # TODO: Check that size == 0?
            else:
                #print('bad type:{}'.format(packet_type))
                #exit(1)
                pass
    
            # discard the data portion
            data = f.read(size)

            if dump_packets:
                if packet_type == PATTERN_PACKET_TYPE_DATA:
                    print('{:08x} Data packet, timestamp:{} universe:{} sync:{} data size:{}'.format(
                        offset,
                        timestamp_ms,
                        A,
                        B,
                        size
                        ))
                elif packet_type == PATTERN_PACKET_TYPE_SYNC:
                    print('{:08x} Sync packet, timestamp:{} A:{:08x} B:{}'.format(
                        offset,
                        timestamp_ms,
                        A,
                        B,
                        ))
                else:
                    print('{:08x} Unknown packet, timestamp:{} type:{} A:{} B:{} size:{}'.format(
                        offset,
                        timestamp_ms,
                        packet_type,
                        A,
                        B,
                        size,
                        ))
                    pass
   
        print('')
        print('== STATISTICS ==')
        print('data_packets:{} sync_packets:{}: universes:{}'.format(packet_stats['data'],
            packet_stats['sync'],
            len(universe_stats)))
    
        print('')
        print('== PER-UNIVERSE STATS ==')
        for universe in sorted(universe_stats):
            universe_stat = universe_stats[universe]
    
            time_deltas = []
            last_time = universe_stat[0]
            for time in universe_stat[1:]:
                time_deltas.append(time - last_time)
                last_time = time
    
            mean = statistics.mean(time_deltas)
            fps = 1000/mean
            standard_dev = statistics.stdev(time_deltas)
    
            print('universe:{} count:{} fps:{:0.2f} mean:{:0.2f} standard_deviation:{:0.2f}'.format(
                universe, len(universe_stat), fps, mean, standard_dev))
    
    # Analyze time index
    
        f.seek(time_index_offset)
    
        time_indexes = []
        while f.tell() < (time_index_offset + time_index_size):
            PATTERN_TIME_INDEX_ENTRY_FORMAT = '<I'
    
            entry = f.read(struct.calcsize(PATTERN_TIME_INDEX_ENTRY_FORMAT))
            [offset] = struct.unpack(PATTERN_TIME_INDEX_ENTRY_FORMAT, entry)
            time_indexes.append(offset)
    
        # Add the end of the data section as a final offset, so we can calculate size of all index sections
        time_indexes.append(data_offset+data_size+1)
    
        time_index = time_indexes[0]
    
        for next_time_index in time_indexes[1:]:
            err = ''
            size = next_time_index - time_index
    
            # Check that the offsets are increasing
            if time_index > next_time_index:
                err += '(out of order)'
    
            # Check that the offsets point to a valid record
            if time_index not in packet_offsets:
                err += '(does not point to packet)'
    
            packets = 0
            for packet_offset in packet_offsets:
                if packet_offset >= time_index and packet_offset < next_time_index:
                    packets += 1
    
            print('offset:{:08x} size:{} packets:{} '.format(time_index, size, packets) + err)
    
            time_index = next_time_index


parser = argparse.ArgumentParser()
parser.add_argument('filename', action="store")
args = parser.parse_args()

filename = args.filename

f = dumpFile(filename)


