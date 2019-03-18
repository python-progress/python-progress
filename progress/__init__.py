# Copyright (c) 2012 Giorgos Verigakis <verigak@gmail.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from __future__ import division, print_function

from collections import deque
from datetime import timedelta
from math import ceil
from sys import stderr
from time import time


__version__ = '1.5'

HIDE_CURSOR = '\x1b[?25l'
SHOW_CURSOR = '\x1b[?25h'


class _Window(object):
    max_seconds = 2
    max_items = None

    def __init__(self, max_seconds=2, max_items=None):
        self.max_seconds = max_seconds
        self.max_items = max_items

        stamp = time()
        self.last = stamp - 0.001
        self.counter = 0
        self.deque = deque()
        self.next(0, stamp)

    def pop(self):
        item = self.deque.popleft()
        self.counter -= item[1]

    def clean(self):
        if self.max_items:
            while len(self.deque) > self.max_items:
                self.pop()
        while len(self.deque) > 2 and self.last - self.deque[0][0] > float(self.max_seconds):
            self.pop()

    def next(self, n, t):
        self.clean()
        self.deque.append((self.last, n))
        self.last = t
        self.counter += n

    @property
    def avg(self):
        return self.counter / (self.last - self.deque[0][0])


class Infinite(object):
    file = stderr
    # Maximum number of next() calls to be held in Simple Moving Average
    # window structure (in memory), default is unlimited.
    sma_window_seconds = 2
    sma_window = None
    check_tty = True
    hide_cursor = True

    def __init__(self, message='', **kwargs):
        self.index = 0
        self.start_ts = time()
        self.window = _Window(self.sma_window_seconds, self.sma_window)
        for key, val in kwargs.items():
            setattr(self, key, val)

        self._width = 0
        self.message = message

        if self.file and self.is_tty():
            if self.hide_cursor:
                print(HIDE_CURSOR, end='', file=self.file)
            print(self.message, end='', file=self.file)
            self.file.flush()

    def __getitem__(self, key):
        if key.startswith('_'):
            return None
        return getattr(self, key, None)

    @property
    def elapsed(self):
        return int(time() - self.start_ts)

    @property
    def avg(self):
        speed = self.window.avg
        if speed:
            return 1/speed
        return 3600 # better constant?

    @property
    def elapsed_td(self):
        return timedelta(seconds=self.elapsed)

    def update(self):
        pass

    def start(self):
        pass

    def clearln(self):
        if self.file and self.is_tty():
            print('\r\x1b[K', end='', file=self.file)

    def write(self, s):
        if self.file and self.is_tty():
            line = self.message + s.ljust(self._width)
            print('\r' + line, end='', file=self.file)
            self._width = max(self._width, len(s))
            self.file.flush()

    def writeln(self, line):
        if self.file and self.is_tty():
            self.clearln()
            print(line, end='', file=self.file)
            self.file.flush()

    def finish(self):
        if self.file and self.is_tty():
            print(file=self.file)
            if self.hide_cursor:
                print(SHOW_CURSOR, end='', file=self.file)

    def is_tty(self):
        return self.file.isatty() if self.check_tty else True

    def next(self, n=1):
        self.window.next(n, time())
        self.index = self.index + n
        self.update()

    def iter(self, it):
        with self:
            for x in it:
                yield x
                self.next()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish()


class Progress(Infinite):
    def __init__(self, *args, **kwargs):
        super(Progress, self).__init__(*args, **kwargs)
        self.max = kwargs.get('max', 100)

    @property
    def eta(self):
        return int(ceil(self.avg * self.remaining))

    @property
    def eta_td(self):
        return timedelta(seconds=self.eta)

    @property
    def percent(self):
        return self.progress * 100

    @property
    def progress(self):
        return min(1, self.index / self.max)

    @property
    def remaining(self):
        return max(self.max - self.index, 0)

    def start(self):
        self.update()

    def goto(self, index):
        incr = index - self.index
        self.next(incr)

    def iter(self, it):
        try:
            self.max = len(it)
        except TypeError:
            pass

        with self:
            for x in it:
                yield x
                self.next()
