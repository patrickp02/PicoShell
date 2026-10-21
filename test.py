import time
import micropython

SIZE = 4096
ROUNDS = 200

data = bytearray(SIZE)

for i in range(SIZE):
    data[i] = (i * 17 + 23) & 0xFF


def crc_python(buf, rounds):
    crc = 0xFFFFFFFF

    for _ in range(rounds):
        for b in buf:
            crc ^= b

            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1

                crc &= 0xFFFFFFFF

    return crc ^ 0xFFFFFFFF


@micropython.native
def crc_native(buf, rounds):
    crc = 0xFFFFFFFF

    for _ in range(rounds):
        for b in buf:
            crc ^= b

            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1

                crc &= 0xFFFFFFFF

    return crc ^ 0xFFFFFFFF


@micropython.viper
def crc_viper(buf, rounds: int) -> int:
    p = ptr8(buf)
    length: int = int(len(buf))
    crc: uint = uint(0xFFFFFFFF)

    r: int = 0
    i: int = 0
    bit: int = 0
    b: uint = uint(0)

    while r < rounds:
        i = 0

        while i < length:
            b = uint(p[i])
            crc ^= b

            bit = 0
            while bit < 8:
                if crc & 1:
                    crc = (crc >> 1) ^ uint(0xEDB88320)
                else:
                    crc >>= 1

                bit += 1

            i += 1

        r += 1

    return int(crc ^ uint(0xFFFFFFFF))


def bench(name, fn):
    start = time.ticks_us()
    result = fn(data, ROUNDS)
    elapsed_us = time.ticks_diff(time.ticks_us(), start)

    seconds = elapsed_us / 1_000_000
    bytes_processed = SIZE * ROUNDS
    throughput = bytes_processed / seconds

    print()
    print(name)
    print("Result:     0x{:08X}".format(result))
    print("Time:       {:.6f} sec".format(seconds))
    print("Throughput: {:.0f} bytes/sec".format(throughput))

    return result, seconds


print("CPU:", __import__("machine").freq() // 1_000_000, "MHz")
print("Buffer:", SIZE, "bytes")
print("Rounds:", ROUNDS)
print("Total:", SIZE * ROUNDS, "bytes")

r1, t1 = bench("Python", crc_python)
r2, t2 = bench("Native", crc_native)
r3, t3 = bench("Viper", crc_viper)

print()
print("Python -> Native: {:.2f}x".format(t1 / t2))
print("Python -> Viper:  {:.2f}x".format(t1 / t3))
print("Native -> Viper:  {:.2f}x".format(t2 / t3))

print()
if r1 == r2 == r3:
    print("All results match.")
else:
    print("RESULT MISMATCH!")