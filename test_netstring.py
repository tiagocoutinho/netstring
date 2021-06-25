import pytest
from hypothesis import given, example
from hypothesis.strategies import binary

from netstring import Connection, NetstringError, NEED_DATA


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
