#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copy from ssdp.py
"""

import socket
import httplib
import StringIO
import threading
import select

import requests
import zeroconf

from log import logger

XML_NS_UPNP_DEVICE = "{urn:schemas-upnp-org:device-1-0}"
CC_SESSION = requests.Session()
CC_SESSION.headers['content-type'] = 'application/json'
SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900

MODEL_NAME_UNKNOWN = 'Unknown'



class DIALResponse(object):
    class _FakeSocket(StringIO.StringIO):
        def makefile(self, *args, **kw):
            return self

    def __init__(self, response):
        r = httplib.HTTPResponse(self._FakeSocket(response))
        r.begin()
        self.location = r.getheader("location")
        self.usn = r.getheader("usn")
        self.st = r.getheader("st")

    def __repr__(self):
        return "<DIALResponse({location}, {st}, {usn})>".format(
            **self.__dict__)


class DIALFinder(threading.Thread):
    def __init__(self, service, model_list=None, timeout=1, callback=None):
        super(DIALFinder, self).__init__()
        self.stop = threading.Event()
        self.service = service
        self.timeout = timeout
        self.callback = callback
        self.model_list = model_list
        self.device_list = []

    @staticmethod
    def new_socket(bind_port=None):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

        if bind_port is None:
            s.bind(("", 0))
        else:
            s.bind(("", bind_port))

        return s

    def close(self):
        self.stop.set()
        logger.info('waiting for the thread is terminated.')
        self.join()
        logger.info('thread was terminated.')

    def run(self):
        skt = self.new_socket()
        logger.info('opened a socket: %s', skt.fileno())
        bind_port = skt.getsockname()[1]

        group = (SSDP_ADDR, SSDP_PORT)
        message = "\r\n".join(['M-SEARCH * HTTP/1.1',
                               'HOST: {0}:{1}',
                               'MAN: "ssdp:discover"',
                               'ST: {st}',
                               'MX: 5', '', ''])  # yapf:disable

        interfaces = zeroconf.normalize_interface_choice(zeroconf.InterfaceChoice.All, socket.AF_INET)
        for i in interfaces:
            try:
                skt.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                               socket.inet_aton(SSDP_ADDR) + socket.inet_aton(i))
            except socket.error:
                continue

            sock = self.new_socket(bind_port)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(i))
            sock.sendto(message.format(*group, st=self.service), group)
            sock.close()

        while not self.stop.isSet():
            readable, _, _ = select.select([skt], [], [], self.timeout)
            if not readable:
                continue

            logger.info('waiting for dial response...')
            try:
                response = DIALResponse(skt.recv(4096))
            except socket.timeout:
                continue
            logger.info('received dial response.')

            if response and self.callback is not None:
                try:
                    req = CC_SESSION.get(response.location, timeout=30)
                except requests.exceptions.ConnectTimeout:
                    continue
                except requests.exceptions.ConnectionError:
                    continue
                except requests.exceptions.ReadTimeout:
                    continue

                from xml.etree import ElementTree
                status_el = ElementTree.fromstring(req.text.encode("UTF-8"))
                device_info_el = status_el.find(XML_NS_UPNP_DEVICE + "device")
                try:
                    friendly_name = device_info_el.find(XML_NS_UPNP_DEVICE + "friendlyName").text
                except AttributeError:
                    continue

                if "Application-URL" in req.headers:
                    application_url = req.headers.get("Application-URL")
                else:
                    logger.error('Application-URL not exist')
                    continue

                try:
                    model_name = device_info_el.find(XML_NS_UPNP_DEVICE + "modelName").text
                except AttributeError:
                    model_name = MODEL_NAME_UNKNOWN

                # if this device is not target model or already in list, ignore it
                if (self.model_list is not None) and checkModelName(self.model_list, model_name) and (response.usn not in self.device_list):
                    import re
                    host = re.findall('[0-9]+(?:\\.[0-9]+){3}', application_url)[0]
                    port = re.findall('(?::([0-9]+))', application_url)[0]
                    self.callback(host, port, unicode(friendly_name).encode('utf8'), model_name)
                    self.device_list.append(response.usn)
                    logger.info('found FireTV device: %s host:%s port:%s ', friendly_name, host, port)

        logger.info('closing a socket: %s', skt.fileno())
        skt.close()


def checkModelName(model_list=None, model_name=None):
    if (model_name is None or model_list is None):
        return False

    return model_name.startswith(tuple(model_list))
