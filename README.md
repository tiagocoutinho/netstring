# netstring

A pure python library implementation of the
[netstring](http://cr.yp.to/proto/netstrings.txt) encoding with a low memory
footprint.

It is heavily inspired by the [hyper](https://github.com/python-hyper)
philosophy in the sense that it's a "bring-your-own-I/O" library.
It does this by providing a `Connection` object.
