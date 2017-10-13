#!/usr/bin/env python
# -*- coding: utf-8 -*-

from zeroconf import ServiceBrowser, Zeroconf
from ssdp import SSDPFinder, DEVICE_TYPE_ROKU
from dial import DIALFinder
from log import logger

APPLE_NAMESPACE = '_airplay._tcp.local.'
GOOGLE_NAMESPACE = '_googlecast._tcp.local.'
ROKU_ST_NAME = 'roku:ecp'
UPNP_ST_NAME = 'upnp:rootdevice'
FIRETV_MODEL_LIST = ['FireTV', 'FireTV Stick', 'FireTV Edition', 'AFTS', 'AFTT']

MODEL_NAME_UNKNOWN = 'Unknown'


class CastListener(object):
    def __init__(self, namespace, callback):
        self.services = {}
        self.namespace = namespace
        self.callback = callback

    @property
    def count(self):
        return len(self.services)

    @property
    def devices(self):
        return list(self.services.values())

    def remove_service(self, zconf, typ, name):
        self.services.pop(name, None)

    def add_service(self, zconf, typ, name):
        service = None
        tries = 0
        while service is None and tries < 4:
            service = zconf.get_service_info(typ, name)
            tries += 1

        if service:
            host = '.'.join([str(ord(s)) for s in service.address])

            self.services[name] = (host, service.port)
            display_name = name.split('.')[0]

            # detect model
            if typ == GOOGLE_NAMESPACE and 'md' in service.properties:
                # Chromecast case
                model_name = service.properties['md']
                if 'fn' in service.properties:
                    # get friendly name
                    display_name = service.properties['fn']
                    try:
                        unicode(display_name)
                    except UnicodeDecodeError:
                        # get friendly name from ssdp desc xml
                        import urllib2
                        import xml.etree.cElementTree as ET
                        tree = ET.ElementTree(file=urllib2.urlopen('http://{}:8008/ssdp/device-desc.xml'.format(host)))
                        for elem in tree.iter(tag='{urn:schemas-upnp-org:device-1-0}friendlyName'):
                            display_name = elem.text
                            break

            elif typ == APPLE_NAMESPACE and 'model' in service.properties:
                # AppleTV case
                model_name = service.properties['model']
            else:
                model_name = MODEL_NAME_UNKNOWN

            if self.callback is not None:
                self.callback(host, unicode(display_name).encode('utf8'), model_name)


listener = {}
zconf = {}
browser = {}
finder = None
dialFinder = None


def start_discovery(namespace, callback=None):
    global listener, zconf, browser
    try:
        listener[namespace] = CastListener(namespace=namespace, callback=callback)
        zconf[namespace] = Zeroconf()
        browser[namespace] = ServiceBrowser(zconf[namespace], namespace, listener[namespace])
    except:
        logger.exception('')


def cancel_discovery(namespace):
    try:
        if namespace in browser:
            browser[namespace].cancel()
        if namespace in zconf:
            zconf[namespace].close()
    except:
        logger.exception('')


def start_ssdp_discovery(st, device_type=None, callback=None):
    global finder
    finder = SSDPFinder(st, device_type=device_type, callback=callback)
    finder.start()


def cancel_ssdp_discovery():
    global finder
    if finder is not None:
        finder.close()
        finder = None


def start_dial_discovery(st, model_list=None, callback=None):
    global dialFinder
    dialFinder = DIALFinder(st, model_list=model_list, callback=callback)
    dialFinder.start()


def cancel_dial_discovery():
    global dialFinder
    if dialFinder is not None:
        dialFinder.close()
        dialFinder = None


def main():
    def show(host, name, model):
        logger.info('host:{}, name:{}, model:{}'.format(host, name, model))

    import log
    import logging
    log.init_logger(logging.DEBUG)

    logger.info('start finding device')
    start_discovery(namespace=APPLE_NAMESPACE, callback=show)
    start_discovery(namespace=GOOGLE_NAMESPACE, callback=show)
    start_ssdp_discovery(ROKU_ST_NAME, callback=show)
    start_dial_discovery(model_list=FIRETV_MODEL_LIST, callback=show)

    # start_ssdp_discovery(UPNP_ST_NAME, device_type=DEVICE_TYPE_ROKU, callback=show)
    raw_input()
    cancel_discovery(namespace=APPLE_NAMESPACE)
    cancel_discovery(namespace=GOOGLE_NAMESPACE)
    cancel_ssdp_discovery()
    cancel_dial_discovery()


if __name__ == '__main__':
    main()
