# -*- coding: utf-8 -*-
#
# This file is part of the python-netstring project
#
# Copyright (c) 2021-2022 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

__version__ = "0.3.0"

END = b','
END_ORD = ord(END)
NEED_DATA = object()
CONNECTION_CLOSED = object()


class Connection:

    def __init__(self):
        self._receive_buffer = b""
        self.closed = False

    @property
    def trailing_data(self):
        """Data that has been received, but not yet processed, represented as
        a tuple with two elements, where the first is a byte-string containing
        the unprocessed data itself, and the second is a bool that is True if
        the receive connection was closed.
        """
        return self._receive_buffer, self.closed

    def send_data(self, event):
        """Convert a high-level event into bytes that can be sent to the peer"""
        return f"{len(event)}:".encode() + event + END

    def receive_data(self, data):
        """Feed network data into the connection instance.

        This does not actually do any processing on the data, just stores
        it. To trigger processing, you have to call `next_event()`

        Feeding the empty bytes effectively closes the receiving end.

        Feeding data on a closed receiving end raises ValueError.
        """
        if data:
            if self.closed:
                raise ValueError("Cannot receive more data: received closed")
            self._receive_buffer += data
        else:
            self.close()

    def next_event(self):
        """Parse the next event out of our receive buffer, update our internal
        state, and return it.

        This is a mutating operation -- think of it like calling :func:`next`
        on an iterator.

        Returns one of three things:
            1) An event object.
            2) The special constant `NEED_DATA`, which indicates that
               you need to read more data from your stream and pass it to
               `receive_data` before this method will be able to return
               any more events.
            3) The special constant `CONNECTION_CLOSED` if we the object
               was closed and no event is available on the buffer

        Raises ValueError or TypeError if the data feed is malformed
        """
        if not self._receive_buffer:
            return CONNECTION_CLOSED if self.closed else NEED_DATA
        try:
            ndig = self._receive_buffer.index(b":")
        except ValueError:
            try:
                int(self._receive_buffer)
            except ValueError:
                self.close()
                raise ValueError("Received data with invalid format")
            return CONNECTION_CLOSED if self.closed else NEED_DATA
        n = int(self._receive_buffer[0:ndig])
        start = ndig + 1
        end = start + n + 1
        if len(self._receive_buffer) < end:
            return CONNECTION_CLOSED if self.closed else NEED_DATA
        result = self._receive_buffer[start:end - 1]
        if self._receive_buffer[end - 1] != END_ORD:
            self.close()
            raise ValueError("Received data with invalid format")
        self._receive_buffer = self._receive_buffer[end:]
        return result

    def close(self):
        self.closed = True
        self._receive_buffer = b""

    def __iter__(self):
        while (event := self.next_event()) not in {CONNECTION_CLOSED, NEED_DATA}:
            yield event


def stream_data(conn, data):
    """Feeds the connection with the given data and yields its events"""
    conn.receive_data(data)
    for event in conn:
        yield event


def reads(reader, size=4096):
    """
    A generator of chunks of data for the given max size.
    Useful to consume from any reader with read(size) method (ex: file like
    object, socket.makefile()) into a generator.

    with open("messages.ns", "rb") as reader:
        for chunk in reads(reader):
            print(f"{chunk = !r}")
    """
    while data := reader.read(size):
        yield data


async def async_reads(reader, size=4096):
    """
    An async generator of chunks of data for the given max size.
    Useful to consume from any async reader with read(size) method (ex: file
    like  object, asyncio.StreamReader) into an async generator.

    with open("messages.ns", "rb") as reader:
        for chunk in reads(reader):
            print(f"{chunk = !r}")
    """
    while data := await reader.read(size):
        yield data


def stream(source):
    """
    Consumes the source yielding its events.
    Source must be iterable. If you intend the source to be a file like
    object, don't pass it directly since file iterators read until the EOL
    character. Instead use the reads() helper. Example:

    with open("messages.ns", "rb") as reader:
        source = reads(reader)
        for event in stream(source):
            print(f"{event = !r}")
    """
    conn = Connection()
    for chunk in source:
        yield from stream_data(conn, chunk)


async def async_stream(source):
    """
    Consumes the source yielding its events.
    Source must be iterable. If you intend the source to be an async reader
    like object (ex: asyncio.StreamReader, aiofile.File), don't pass it
    directly since reader iterators read until the EOL character.
    Instead use the async_reads() helper. Example:

    with open("messages.ns", "rb") as reader:
        source = async_reads(reader)
        for event in stream(source):
            print(f"{event = !r}")
    """
    conn = Connection()
    async for chunk in source:
        for event in stream_data(conn, chunk):
            yield event

