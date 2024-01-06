#!/usr/bin/env python3

import struct
import os
import statistics
import argparse

def extract_prelude(f, filename):
    PRELUDE_OFFSET = 0
    PRELUDE_FORMAT = '<8sIIII'
    PRELUDE_MAGIC = b'\x5FLED\r\n\x1A\n'
    
    f.seek(PRELUDE_OFFSET)
    prelude = f.read(struct.calcsize(PRELUDE_FORMAT))
    
    #[magic, checksum, version, header_offset, size] = struct.unpack(PRELUDE_FORMAT, prelude)
    PRELUDE_FIELDS = [
            'magic',
            'checksum',
            'version',
            'header_offset',
            'size'
            ]
    prelude = dict(zip(PRELUDE_FIELDS, struct.unpack(PRELUDE_FORMAT, prelude)))
    
    print('{:08x} Prelude checksum:{:04x} version:{} header_offset:{:08x} size:{}'.format(
        PRELUDE_OFFSET,
        prelude['checksum'],
        prelude['version'],
        prelude['header_offset'],
        prelude['size']
        ))
    
    if prelude['magic'] != PRELUDE_MAGIC:
        print('bad magic expected:{} got:{}'.format(PRELUDE_MAGIC, prelude['magic']))
        exit(1)
    
    expected_size = os.path.getsize(filename)
    if prelude['size'] != expected_size:
        print('bad size expected:{} got:{}'.format(expected_size, prelude['size']))
        exit(1)

    # todo: checksum
    # todo: version

    return prelude 

def extract_header(f, header_offset):
    """ Extract a file header

    Attempts to read a header from the file, at the given offset. 

    Parameters
    ----------
    name : f
        File to read fromh
    header_offset : int
        Offset from the beginning of the file to read the header from

    Returns
    ----------
    dict
        Dictionary containing the values of each field in the header
    """
    HEADER_FORMAT = '<IIIII'

    f.seek(header_offset)
    header = f.read(struct.calcsize(HEADER_FORMAT))
    
    #[duration_ms, data_offset, data_size, time_index_offset, time_index_size] = struct.unpack(HEADER_FORMAT, header)
    HEADER_FIELDS = [
            'duration_ms',
            'data_offset',
            'data_size',
            'time_index_offset',
            'time_index_size'
            ]
    header = dict(zip(HEADER_FIELDS, struct.unpack(HEADER_FORMAT, header)))
    
    print('{:08x} Header duration_ms:{} data_offset:{:08x} data_size:{} time_index_offset:{:08x} time_index_size:{}'.format(
        header_offset,
        header['duration_ms'],
        header['data_offset'],
        header['data_size'],
        header['time_index_offset'],
        header['time_index_size']
        ))

    return header

def extract_data(f, data_offset, data_size, dump_packets):
    PATTERN_PACKET_FORMAT = '<IHII?'
    PATTERN_PACKET_TYPE_DATA = 0
    PATTERN_PACKET_TYPE_SYNC = 1

    packet_stats = {'data':0, 'sync':0}
    universe_stats = {} 
    packet_offsets = []

    if dump_packets:
        print('')
        print('== PACKET LISTING ==')

    f.seek(data_offset)
    while f.tell() < (data_offset + data_size):

        offset = f.tell()
        packet_offsets.append(offset)

        packet = f.read(struct.calcsize(PATTERN_PACKET_FORMAT))
        [timestamp_ms, size, packet_type, A, B] = struct.unpack(PATTERN_PACKET_FORMAT, packet)

        # TODO: Check that the timestamp is >= previous record


        if packet_type == PATTERN_PACKET_TYPE_DATA:
            [universe, sync] = [A, B]

            packet_stats['data'] += 1
            universe_count = universe_stats.setdefault(universe, [])
            universe_stats[universe].append(timestamp_ms)

            # TODO: Check that size is <= 512?

        elif packet_type == PATTERN_PACKET_TYPE_SYNC:
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
                print('{:08x} Data packet, timestamp:{} universe:{} sync:{} data_size:{}'.format(
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
                print('{:08x} Unknown packet, timestamp:{} type:{} A:{} B:{} data_size:{}'.format(
                    offset,
                    timestamp_ms,
                    packet_type,
                    A,
                    B,
                    size,
                    ))
                pass

    print('')
    print('== PACKET STATISTICS ==')
    print('data_packets:{} sync_packets:{} universes:{}'.format(
        packet_stats['data'],
        packet_stats['sync'],
        len(universe_stats)))

    data = {
            'packet_stats':packet_stats,
            'universe_stats':universe_stats,
            'packet_offsets':packet_offsets
            }

    return data

def calc_universe_stats(universe_stats):
    print('')
    print('== PER-UNIVERSE STATISTICS ==')
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
            universe,
            len(universe_stat),
            fps,
            mean,
            standard_dev
            ))

def extract_time_indexes(
        f,
        time_index_offset,
        time_index_size,
        data_offset,
        data_size,
        packet_offsets,
        dump_time_indexes
        ):
    if dump_time_indexes:
        print('')
        print('== TIME INDEX LISTING ==')
    
    f.seek(time_index_offset)
    
    time_indexes = []
    while f.tell() < (time_index_offset + time_index_size):
        PATTERN_TIME_INDEX_ENTRY_FORMAT = '<I'
    
        entry = f.read(struct.calcsize(PATTERN_TIME_INDEX_ENTRY_FORMAT))
        [offset] = struct.unpack(PATTERN_TIME_INDEX_ENTRY_FORMAT, entry)
        time_indexes.append(offset)
    
    # Add the end of the data section as a final offset, so we can
    # calculate size of all index sections
    time_indexes.append(data_offset + data_size + 1)
    
    time_index = time_indexes[0]
   
    packet_offset_index = 0

    #TODO: Check that first time index points to data_offset

    for next_time_index in time_indexes[1:]:
        err = ''
        size = next_time_index - time_index
    
        # Check that the offsets are increasing
        if time_index > next_time_index:
            err += '(out of order)'
    
        # Check that the offsets point to a valid record
        #if time_index not in packet_offsets:
        if packet_offsets[packet_offset_index] != time_index:
            print("packet_offset:{:08x} time_index:{:08x}".format(
                packet_offsets[packet_offset_index],
                time_index
                ))
            err += '(does not point to packet)'
    
        packets = 0
        while (packet_offset_index < len(packet_offsets)) and (packet_offsets[packet_offset_index] < next_time_index):
            packet_offset_index += 1
            packets += 1

        if dump_time_indexes:
            print('offset:{:08x} span:{} packets:{} {}'.format(
                time_index,
                size,
                packets,
                err
                ))

        time_index = next_time_index

def verify(filename, dump_packets = False, dump_time_indexes = False):
    with open(filename, 'rb') as f:
        prelude = extract_prelude(f, filename)
        header = extract_header(f, prelude['header_offset'])
        data = extract_data(
                f,
                header['data_offset'],
                header['data_size'],
                dump_packets
                )
        time_indexes = extract_time_indexes(
                f,
                header['time_index_offset'],
                header['time_index_size'],
                header['data_offset'],
                header['data_size'],
                data['packet_offsets'],
                dump_time_indexes
                )

        calc_universe_stats(data['universe_stats'])

        #TODO: time index stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', action="store")
    args = parser.parse_args()
    
    f = verify(args.filename, dump_packets=True, dump_time_indexes=True)


