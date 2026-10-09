"""md v1.2 superblock + internal write-intent bitmap writer (authoring only).

Layouts follow include/uapi/linux/raid/md_p.h (struct mdp_superblock_1) and
drivers/md/md-bitmap.h (bitmap_super_t). Checksum is mdadm's calc_sb_1_csum.
"""
import struct

SB_MAGIC = 0xA92B4EFC
BITMAP_MAGIC = 0x6D746962
FEAT_BITMAP = 1
FEAT_RECOVERY = 2
ROLE_SPARE = 0xFFFF
ROLE_FAULTY = 0xFFFE
LEFT_SYMMETRIC = 2
MAX_SECTOR = 0xFFFFFFFFFFFFFFFF


def md_time(sec, usec=0):
    return (sec & 0xFFFFFFFFFF) | (usec << 40)


def sb_csum(buf, max_dev):
    size = 256 + max_dev * 2
    total = 0
    for i in range(0, size - size % 4, 4):
        total += struct.unpack_from("<I", buf, i)[0]
    if size % 4 == 2:
        total += struct.unpack_from("<H", buf, size - 2)[0]
    return ((total & 0xFFFFFFFF) + (total >> 32)) & 0xFFFFFFFF


def superblock(*, set_uuid, name, ctime, level, layout, size, chunk_sectors,
               raid_disks, bitmap_offset, data_offset, data_size, super_offset,
               recovery_offset, dev_number, device_uuid, utime, events,
               resync_offset, roles, feature_map):
    max_dev = len(roles)
    buf = bytearray(4096)
    struct.pack_into("<IIII", buf, 0, SB_MAGIC, 1, feature_map, 0)
    buf[16:32] = set_uuid
    nb = name.encode()
    buf[32:32 + len(nb)] = nb
    struct.pack_into("<QIIQII", buf, 64, ctime, level, layout, size,
                     chunk_sectors, raid_disks)
    struct.pack_into("<i", buf, 96, bitmap_offset)
    # reshape fields 100..127 stay zero
    struct.pack_into("<QQQQII", buf, 128, data_offset, data_size, super_offset,
                     recovery_offset, dev_number, 0)
    buf[168:184] = device_uuid
    # devflags, bblog_shift, bblog_size, bblog_offset zero
    struct.pack_into("<QQQII", buf, 192, utime, events, resync_offset, 0, max_dev)
    for i, r in enumerate(roles):
        struct.pack_into("<H", buf, 256 + 2 * i, r)
    struct.pack_into("<I", buf, 216, sb_csum(buf, max_dev))
    return bytes(buf)


def bitmap(*, set_uuid, events, events_cleared, sync_size, chunksize,
           sectors_reserved, bits, nbits):
    hdr = bytearray(256)
    struct.pack_into("<II", hdr, 0, BITMAP_MAGIC, 4)
    hdr[8:24] = set_uuid
    struct.pack_into("<QQQIIIIII", hdr, 24, events, events_cleared, sync_size,
                     0, chunksize, 5, 0, sectors_reserved, 0)
    body = bytearray((nbits + 7) // 8)
    for b in bits:
        body[b // 8] |= 1 << (b % 8)
    return bytes(hdr) + bytes(body)


def ls_locate(chunk_no, n):
    """array data chunk number -> (stripe, member role) for raid5 left-symmetric."""
    s, i = divmod(chunk_no, n - 1)
    pd = (n - 1) - (s % n)
    return s, (pd + 1 + i) % n


def ls_parity(stripe, n):
    return (n - 1) - (stripe % n)
