# -*- coding: utf-8 -*-
#
# This file is part of the python-netstring project
#
# Copyright (c) 2021 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

__version__ = "0.1.0"

END = b','
END_ORD = ord(END)
NEED_DATA = object()


class NetstringError(Exception):
    pass


class Connection:

    def __init__(self):
        self._receive_buffer = b""
        self._receive_buffer_closed = False

    @property
    def trailing_data(self):
        """Data that has been received, but not yet processed, represented as
        a tuple with two elements, where the first is a byte-string containing
        the unprocessed data itself, and the second is a bool that is True if
        the receive connection was closed.
        """
        return self._receive_buffer, self._receive_buffer_closed

    def send_data(self, event):
        """Convert a high-level event into bytes that can be sent to the peer"""
        return f"{len(event)}:".encode() + event + END

    def receive_data(self, data):
        """Feed network data into the connection instance.

        This does not actually do any processing on the data, just stores
        it. To trigger processing, you have to call `next_event()`

        Feeding the empty bytes effectively closes the receiving end.

        Feeding data on a closed receiving end raises NetstringError.
        """
        if data:
            if self._receive_buffer_closed:
                raise NetstringError("Cannot receive more data: received closed")
            self._receive_buffer += data
        else:
            self.close()

    def next_event(self):
        """Parse the next event out of our receive buffer, update our internal
        state, and return it.

        This is a mutating operation -- think of it like calling :func:`next`
        on an iterator.

        Returns one of two things:
            1) An event object.
            2) The special constant `NEED_DATA`, which indicates that
               you need to read more data from your stream and pass it to
               `receive_data` before this method will be able to return
               any more events.

        Raises ValueError or TypeError if the data feed is malformed
        """
        if not self._receive_buffer:
            return None if self._receive_buffer_closed else NEED_DATA
        try:
            ndig = self._receive_buffer.index(b":")
        except ValueError:
            try:
                int(self._receive_buffer)
            except ValueError:
                self.close()
                raise NetstringError("Received data with invalid format")
            return NEED_DATA
        n = int(self._receive_buffer[0:ndig])
        start = ndig + 1
        end = start + n + 1
        if len(self._receive_buffer) < end:
            return NEED_DATA
        result = self._receive_buffer[start:end - 1]
        if self._receive_buffer[end - 1] != END_ORD:
            self.close()
            raise NetstringError("Received data with invalid format")
        self._receive_buffer = self._receive_buffer[end:]
        return result

    def close(self):
        self._receive_buffer_closed = True
        self._receive_buffer = b""


def stream_data(conn, data):
    """Feeds the connection with the given data and yields its events"""
    conn.receive_data(data)
    while (event := conn.next_event()) not in {None, NEED_DATA}:
        yield event


def stream(reader, size=4096):
    """Consumes the reader yielding its events"""
    conn = Connection()
    while data := reader.read(size):
        yield from stream_data(conn, data)


async def async_stream(reader, size=4096):
    """Consumes the async reader yielding its events"""
    conn = Connection()
    while data := await reader.read(size):
        for event in stream_data(conn, data):
            yield event
