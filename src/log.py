#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @author Veawor Liu
# @copyright (c) 2014 CyberLink Corp. All Rights Reserved.


import ctypes
import logging
import sys
import unittest


class DebugViewLogger(object):
    def __init__(self, old):
        self.old = old
        self.log = ctypes.windll.kernel32.OutputDebugStringW

    def __getattr__(self, name):
        return self.old.__getattr__(name)

    def write(self, text):
        msg = u''
        if isinstance(text, unicode):
            msg = text
        else:
            for l in text.decode('UTF-8').splitlines():
                msg += l + u'\n'
        self.log(msg)


class DummyLogger(object):
    def write(self, text):
        pass


class SingleLevelFilter(logging.Filter):
    def __init__(self, lvl):
        self.lvl = lvl

    def filter(self, record):
        return record.levelno != self.lvl


def init_logger(lvl, filename=None):
    if filename is None:
        sys.stdout = DebugViewLogger(sys.__stdout__)
        sys.stderr = DebugViewLogger(sys.__stderr__)
    else:
        logging.basicConfig(filename=filename)

    formatter = logging.Formatter('[discovery.pyz][%(levelname)s][%(filename)s:%(funcName)s():%(lineno)s] %(message)s ')

    f1 = SingleLevelFilter(logging.CRITICAL)
    f2 = SingleLevelFilter(logging.ERROR)
    f3 = SingleLevelFilter(logging.WARNING)
    f4 = SingleLevelFilter(logging.INFO)
    f5 = SingleLevelFilter(logging.DEBUG)

    h1 = logging.StreamHandler(sys.stdout)
    h1.addFilter(f1)
    h1.addFilter(f2)
    h1.addFilter(f3)
    h1.setFormatter(formatter)

    h2 = logging.StreamHandler(sys.stderr)
    h2.addFilter(f4)
    h2.addFilter(f5)
    h2.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(h1)
    root_logger.addHandler(h2)
    root_logger.setLevel(lvl)


logger = logging.getLogger(__file__)


class UnitTest(unittest.TestCase):
    def setUp(self):
        init_logger(logging.INFO)

    def test_logger(self):
        logger.info('name: %s', '許功蓋')
        logger.info('陶喆')
