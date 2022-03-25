import pytest
from hypothesis import given, example
from hypothesis.strategies import binary

from netstring import Connection, NetstringError, NEED_DATA


DATA_EVENTS = [
    (b'bad', [], NetstringError),
    (b'10:almost good,', [], NetstringError),
    (b'12:almost good,', [], None),
    (b'4:good,bad', [b'good'], NetstringError),
    (b'13:13:recursive1,', [b'13:recursive1'], None),
    (b'14:14:recursive2,,', [b'14:recursive2,'], None),
    (b'3:foo,', [b"foo"], None),
    (b'46:{"id": 0, "method": "hello", "jsonrpc": "2.0"},', [b'{"id": 0, "method": "hello", "jsonrpc": "2.0"}'], None),
]


@given(binary())
def test_netstring(payload):
    conn = Connection()

    assert conn.trailing_data == (b"", False)
    assert conn.next_event() == NEED_DATA
    assert conn.trailing_data == (b"", False)
    data = conn.send_data(payload)
    assert conn.trailing_data == (b"", False)
    conn.receive_data(data)
    assert conn.trailing_data == (data, False)
    assert conn.next_event() == payload
    assert conn.trailing_data == (b"", False)
    assert conn.next_event() == NEED_DATA
    assert conn.trailing_data == (b"", False)

    data = conn.send_data(payload)
    assert conn.trailing_data == (b"", False)
    conn.receive_data(data)
    assert conn.trailing_data == (data, False)
    assert conn.next_event() == payload
    assert conn.trailing_data == (b"", False)

    conn.receive_data(b"")
    assert conn.trailing_data == (b"", True)
    with pytest.raises(NetstringError):
        conn.receive_data(b"Hello, world!")


@pytest.mark.parametrize("data, events, error", DATA_EVENTS)
def test_concrete(data, events, error):
    conn = Connection()
    if error:
        evts = []
        with pytest.raises(error):
            for evt in stream_data(conn, data):
                evts.append(evt)
    else:
        evts = list(stream_data(conn, data))
    assert evts == events


@given(binary())
@example(b"Hello, world!")
def test_incomplete(payload):
    conn = Connection()

    assert conn.trailing_data == (b"", False)
    assert conn.next_event() == NEED_DATA
    data = conn.send_data(payload)
    assert conn.trailing_data == (b"", False)
    if len(payload) > 4:
        conn.receive_data(data[0:1])
        assert conn.trailing_data == (data[0:1], False)
        assert conn.next_event() == NEED_DATA
        assert conn.trailing_data == (data[0:1], False)
        conn.receive_data(data[1:3])
        assert conn.trailing_data == (data[0:3], False)
        assert conn.next_event() == NEED_DATA
        assert conn.trailing_data == (data[0:3], False)
        conn.receive_data(data[3:-1])
        assert conn.trailing_data == (data[0:-1], False)
        assert conn.next_event() == NEED_DATA
        assert conn.trailing_data == (data[0:-1], False)
        conn.receive_data(data[-1:])
        assert conn.trailing_data == (data, False)
        assert conn.next_event() == payload
        assert conn.trailing_data == (b"", False)
        assert conn.next_event() == NEED_DATA
        assert conn.trailing_data == (b"", False)


def test_close():
    conn = Connection()

    assert conn.next_event() == NEED_DATA
    conn.receive_data(b"")
    with pytest.raises(NetstringError):
        conn.receive_data(b"Hello, world!")
