import array

# CRC-24 多项式（根据 C 代码中的定义）
CRC24_POLY = 0x864CFB

def crc24(crc, firstbyte, secondbyte):
    """
    计算两个字节的 CRC-24 值。
    :param crc: 当前的 CRC 值
    :param firstbyte: 第一个字节
    :param secondbyte: 第二个字节
    :return: 更新后的 CRC 值
    """
    # 将两个字节组合成一个 16 位值
    data = (firstbyte << 8) | secondbyte

    # 更新 CRC 值
    crc ^= data << 16
    for _ in range(8):
        if crc & 0x800000:
            crc = (crc << 1) ^ CRC24_POLY
        else:
            crc <<= 1
        crc &= 0xFFFFFF  # 确保 CRC 是 24 位

    return crc

def calc_blocks_crc24(blocks):
    """
    计算多个数据块的 CRC-24 值。
    :param blocks: 数据块列表，每个数据块是一个 (base, size) 的元组
    :return: 计算出的 CRC-24 值
    """
    crc = 0
    odd = 0
    sum_size = 0

    for block in blocks:
        base, size = block
        ptr = 0

        # 处理两个字节的数据
        while ptr + 1 < size:
            if sum_size & 0x1:
                firstbyte = odd
                secondbyte = base[ptr]
                ptr += 1
                odd = base[ptr]
                ptr += 1
            else:
                firstbyte = base[ptr]
                ptr += 1
                secondbyte = base[ptr]
                ptr += 1

            crc = crc24(crc, firstbyte, secondbyte)

        # 处理剩余的一个字节（如果 size 是奇数）
        if (size + sum_size) & 0x1:
            if size & 0x1:
                odd = base[ptr]

            if block == blocks[-1]:  # 最后一个块
                crc = crc24(crc, odd, 0)
        else:
            if sum_size & 0x1:
                crc = crc24(crc, odd, base[ptr])

        sum_size += size

    # 确保 CRC 是 24 位
    return crc & 0xFFFFFF

def calc_crc24(base):
    """
    计算单个数据块的 CRC-24 值。
    :param base: 数据块（array.array('B')）
    :return: 计算出的 CRC-24 值
    """
    block = (base, len(base))
    return calc_blocks_crc24([block])

# 测试
if __name__ == "__main__":
    # 示例数据
    data = array.array('B', [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])

    # 计算 CRC-24
    crc_value = calc_crc24(data)
    print(f"CRC-24: {crc_value:06X}")