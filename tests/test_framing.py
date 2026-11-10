import pytest

from ledger_rig.framing import REPORT_SIZE, Decoder, FramingError, encode


@pytest.mark.parametrize(
    ("size", "count"),
    [(0, 1), (1, 1), (57, 1), (58, 2), (59, 2), (64, 2), (300, 6)],
)
def test_round_trip(size, count):
    message = b"\xab" * size
    reports = encode(message)
    assert len(reports) == count
    assert all(len(report) == REPORT_SIZE for report in reports)
    decoder = Decoder()
    decoded = [decoder.feed(report) for report in reports]
    assert decoded == [None] * (count - 1) + [message]


def test_bad_channel_raises():
    report = encode(b"x")[0]
    with pytest.raises(FramingError):
        Decoder().feed(b"\x02" + report[1:])


def test_bad_tag_raises():
    report = encode(b"x")[0]
    with pytest.raises(FramingError):
        Decoder().feed(report[:2] + b"\x06" + report[3:])


def test_first_sequence_not_zero_raises():
    with pytest.raises(FramingError):
        Decoder().feed(encode(b"x" * 100)[1])


@pytest.mark.parametrize("next_index", [0, 2], ids=["repeated", "skipped"])
def test_skipped_sequence_raises(next_index):
    reports = encode(b"x" * 300)
    decoder = Decoder()
    decoder.feed(reports[0])
    with pytest.raises(FramingError):
        decoder.feed(reports[next_index])


def test_decodes_consecutive_messages():
    decoder = Decoder()
    for message in (b"\x01" * 100, b"\x02" * 3):
        assert [decoder.feed(report) for report in encode(message)][-1] == message
