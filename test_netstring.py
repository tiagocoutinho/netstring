# -*- coding: utf-8 -*-
#
# This file is part of the python-netstring project
#
# Copyright (c) 2021-2022 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import io

import pytest
from hypothesis import given, example
from hypothesis.strategies import binary

from netstring import Connection, decode, encode, NEED_DATA, CONNECTION_CLOSED
from netstring import reads, async_reads, stream_data, stream, async_stream


DATA_EVENTS = [
    (b'bad', [], ValueError),
    (b'10:almost good,', [], ValueError),
    (b'11:       good,', [b'       good'], None),
    (b'12:almost good,', [], None),
    (b'4:good,bad', [b'good'], ValueError),
    (b'13:13:recursive1,', [b'13:recursive1'], None),
    (b'14:14:recursive2,,', [b'14:recursive2,'], None),
    (b'3:foo,', [b"foo"], None),
    (b'46:{"id": 0, "method": "hello", "jsonrpc": "2.0"},',
     [b'{"id": 0, "method": "hello", "jsonrpc": "2.0"}'], None),
    (2*(b'1000000:'+1000000*b'$'+b','), 2*[1000000*b'$'], None),
]

def idfn(v):
    if isinstance(v, bytes):
        return v[:15] + b'[...]' if len(v) > 20 else v[:20]


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
    with pytest.raises(ValueError):
        conn.receive_data(b"Hello, world!")


@given(binary())
def test_encode(payload):
    assert f'{len(payload)}:'.encode() + payload + b',' == encode(payload)


@pytest.mark.parametrize(
    "data, value",
    [
        (b'bad', ValueError),
        (b'10:almost good,', ValueError),
        (b'14:incomplete', ValueError),
        (b'11:       good,', b'       good'),
        (b'46:{"id": 0, "method": "hello", "jsonrpc": "2.0"},',
         b'{"id": 0, "method": "hello", "jsonrpc": "2.0"}'),
        (b'1000000:'+1_000_000*b'$'+b',', 1_000_000*b'$')
    ],
    ids=idfn)
def test_decode(data, value):
    if isinstance(value, bytes):
        assert decode(data) == value
    else:
        with pytest.raises(value):
            decode(data)


@pytest.mark.parametrize("data, events, error", DATA_EVENTS, ids=idfn)
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
    assert conn.closed
    with pytest.raises(ValueError):
        conn.receive_data(b"Hello, world!")

    conn = Connection()
    conn.close()
    assert conn.closed
    assert conn.next_event() == CONNECTION_CLOSED
    with pytest.raises(ValueError):
        conn.receive_data(b"5:Hello,")
    assert conn.next_event() == CONNECTION_CLOSED

    conn = Connection()
    conn.receive_data(b"5:Hello,")
    conn.close()
    assert conn.closed
    assert conn.next_event() == CONNECTION_CLOSED

    conn = Connection()
    conn.receive_data(b"5:Hello!")
    with pytest.raises(ValueError):
        conn.next_event()
    assert conn.closed
    assert conn.next_event() == CONNECTION_CLOSED

    conn = Connection()
    conn.receive_data(b"5")
    assert conn.next_event() == NEED_DATA
    conn.receive_data(b"b")
    with pytest.raises(ValueError):
        conn.next_event()
    assert conn.closed

    conn = Connection()
    for c in b"5:Hello":
        conn.receive_data(bytes([c]))
        assert conn.next_event() == NEED_DATA
    conn.receive_data(b":")
    with pytest.raises(ValueError):
        conn.next_event()
    assert conn.closed


#@pytest.mark.parametrize("data", [d[0] for d in DATA_EVENTS], ids=idfn)
@given(binary())
def test_reads(data):
    reader = io.BytesIO(data)
    strm = reads(reader)
    result = b"".join(item for item in strm)
    assert result == data


@pytest.mark.asyncio
@given(binary())
async def test_async_reads(data):
    class Reader:
        async def read(self, size):
            result = self.data[:size]
            self.data = self.data[size:]
            return result
    reader = Reader()
    reader.data = data
    strm = async_reads(reader)
    result = b"".join([item async for item in strm])
    assert result == data


@pytest.mark.parametrize("data, events, error", DATA_EVENTS, ids=idfn)
def test_stream_gen(data, events, error):
    def source(data):
        while data:
            evt, data = data[:4096], data[4096:]
            yield evt
    src = source(data)
    strm = stream(src)
    if error:
        with pytest.raises(error):
            evts = []
            for event in strm:
                evts.append(event)
        assert evts == events
    else:
        assert list(strm) == events


@pytest.mark.parametrize("data, events, error", DATA_EVENTS, ids=idfn)
def test_stream_file(data, events, error):
    reader = io.BytesIO(data)
    strm = stream(reader)
    if error:
        with pytest.raises(error):
            evts = []
            for event in strm:
                evts.append(event)
        assert evts == events
    else:
        assert list(strm) == events


@pytest.mark.asyncio
@pytest.mark.parametrize("data, events, error", DATA_EVENTS, ids=idfn)
async def test_async_stream(data, events, error):
    async def source(data):
        while data:
            evt, data = data[:4096], data[4096:]
            yield evt
    src = source(data)
    strm = async_stream(src)
    if error:
        with pytest.raises(error):
            evts = []
            async for event in strm:
                evts.append(event)
        assert evts == events
    else:
        assert [e async for e in strm] == events

