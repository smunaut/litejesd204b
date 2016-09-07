import unittest
import random
from collections import namedtuple

from litex.gen import *

from litejesd204b.core import line_coding

from test.model.line_coding import encode_lane

Control = namedtuple("Control", "value")


def encode_sequence(seq):
    output = []

    dut = line_coding.Encoder()
    def pump():
        for w in seq:
            if isinstance(w, Control):
                yield dut.k[0].eq(1)
                yield dut.d[0].eq(w.value)
            else:
                yield dut.k[0].eq(0)
                yield dut.d[0].eq(w)
            yield
            output.append((yield dut.output[0]))
        for _ in range(2):
            yield
            output.append((yield dut.output[0]))
    run_simulation(dut, pump())

    return output[2:]


def decode_sequence(seq):
    output = []

    dut = line_coding.Decoder()
    def pump():
        for w in seq:
            yield dut.input.eq(w)
            yield
            if (yield dut.k):
                output.append(Control((yield dut.d)))
            else:
                output.append((yield dut.d))
        yield
        if (yield dut.k):
            output.append(Control((yield dut.d)))
        else:
            output.append((yield dut.d))
    run_simulation(dut, pump())
    return output[1:]


class TestLineCoding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prng = random.Random(42)
        cls.input_sequence = []
        for i in range(8):
            cls.input_sequence += [Control((i << 5) | 28)]*2
        cls.input_sequence += [prng.randrange(256) for _ in range(10000)]
        cls.output_sequence = encode_sequence(cls.input_sequence)

    def test_coding(self):
        prng = random.Random(42)
        input_sequence = [prng.randrange(256) for _ in range(10000)]
        reference_sequence = encode_lane([input_sequence])[0]
        output_sequence = encode_sequence(input_sequence)
        self.assertEqual(reference_sequence,
                         output_sequence)

    def test_comma(self):
        control_chars = [
            0b0011110100,
            0b0011111001,
            0b0011110101,
            0b0011110011,
            0b0011110010,
            0b0011111010,
            0b0011110110,
            0b0011111000,
        ]
        for i, c in enumerate(control_chars):
            ok = {c, ~c & 0b1111111111}
            with self.subTest(i=i):
                self.assertIn(self.output_sequence[2*i], ok)
                self.assertIn(self.output_sequence[2*i+1], ok)

    def test_running_disparity(self):
        rd = -1
        for w in self.output_sequence:
            rd += line_coding.disparity(w, 10)
            self.assertIn(rd, {-1, 1})

    def test_no_spurious_commas(self):
        for w1, w2 in zip(self.output_sequence[16:], self.output_sequence[17:]):
            for shift in range(10):
                cw = (w1 << shift) | (w2 >> (10-shift))
                self.assertNotIn(cw, {0b0011111001, 0b1100000110,   # K28.1
                                      0b0011111010, 0b1100000101,   # K28.5
                                      0b0011111000, 0b1100000111})  # K28.7

    def test_roundtrip(self):
        self.assertEqual(self.input_sequence,
                         decode_sequence(self.output_sequence))