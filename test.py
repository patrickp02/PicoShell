import time
import machine
import micropython

SIZE = 1024
ROUNDS = 50

data = bytearray(SIZE)

for i in range(SIZE):
    data[i] = (i * 17 + 23) & 255


def crc_python(buf, rounds):
    crc = 0xFFFFFFFF

    for r in range(rounds):
        for b in buf:
            crc ^= b

            for bit in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1

                crc &= 0xFFFFFFFF

    return crc ^ 0xFFFFFFFF


@micropython.viper
def crc_viper(buf, rounds: int) -> uint:
    p = ptr8(buf)
    length = int(len(buf))
    crc = uint(0xFFFFFFFF)

    r = 0

    while r < rounds:
        i = 0

        while i < length:
            crc ^= uint(p[i])

            bit = 0
            while bit < 8:
                if crc & 1:
                    crc = (crc >> 1) ^ uint(0xEDB88320)
                else:
                    crc >>= 1

                bit += 1

            i += 1

        r += 1

    return crc ^ uint(0xFFFFFFFF)


print("CPU:", machine.freq() // 1000000, "MHz")

##
start = time.ticks_ms()
a = crc_python(data, ROUNDS)
python_ms = time.ticks_diff(time.ticks_ms(), start)

print("Python:", python_ms, "ms")
print("Python result:", hex(a))


start = time.ticks_us()
b = crc_viper(data, ROUNDS)
viper_us = time.ticks_diff(time.ticks_us(), start)

print("Viper:", viper_us, "us")
print("Viper result:", hex(b))


if a == b:
    print("Results match")
else:
    print("RESULT MISMATCH")

python_us = python_ms * 1000

if viper_us:
    print("Speedup:", python_us / viper_us, "x")
