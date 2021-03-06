# vim:set ff=unix tabstop=4 shiftwidth=4 expandtab:

# Author : Pavel Vitis "blackdaemon"
# Email  : blackdaemon@seznam.cz
#
# Copyright (c) 2010, Pavel Vitis <blackdaemon@seznam.cz>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    1. Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#
#    2. Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
#    3. Neither the name of Enso nor the names of its contributors may
#       be used to endorse or promote products derived from this
#       software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# AUTHORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
# OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

#==============================================================================
# Version history
#
#
#
# 1.0    [blackdaemon] Initial version
#==============================================================================

__author__ = "blackdaemon@seznam.cz"
__module_version__ = __version__ = "1.0"
__updated__ = "2017-03-02"

#==============================================================================
# Imports
#==============================================================================

import locale
import logging
import os
import re
import subprocess
import sys
import time
import urllib2
from contextlib import closing
from datetime import datetime, timedelta

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer as DirectoryChangeObserver

try:
    from iniparse import SafeConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser

from enso.platform import *
from enso.contrib.scriptotron.ensoapi import EnsoApi
from enso.events import EventManager
from enso.quasimode import Quasimode
from enso.contrib.calc.ipgetter import myip
from enso.net import inetcache

#==============================================================================
# Constants
#==============================================================================

CACHED_RATES_TIMEOUT = 60 * 60  # 1 hour

HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.2.12) Gecko/20101028 Firefox/3.6.12',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    #    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-us,en;q=0.5',
}


class Globals(object):
    __slots__ = (
        '__dict__',
        '__weakref__',
        'INI_FILE',
        'HOME_CURRENCY',
    )
    # FIXME: This needs to work on all platforms
    INI_FILE = os.path.expanduser(u"~/.config/enso/cmd_calculate.ini")
    HOME_CURRENCY = None

quasimode = Quasimode.get()

#==============================================================================
# Classes & Functions
#==============================================================================

# FIXME: This needs to work on all platforms
CACHE_DIR = os.path.expanduser(u"~/.cache/enso/cmd_calculate")
if not os.path.isdir(CACHE_DIR):
    os.makedirs(CACHE_DIR)
RATES_FILENAME = os.path.join(CACHE_DIR, "rates.csv")

_dir_monitor = None
_file_changed_event_handler = None

_last_exchangerate_update_check = 0


class ExchangeRates(object):

    class _FileChangedEventHandler(FileSystemEventHandler):

        def __init__(self, filenames=None, callback_func=None):
            assert callback_func is None or callable(callback_func)
            self.callback_func = callback_func
            self.filenames = filenames

        def on_moved(self, event):
            if event.is_directory:
                return
            if self.filenames:
                if event.dest_path in self.filenames:
                    self.run_callback_func(event)
            else:
                self.run_callback_func(event)

        def on_created(self, event):
            if event.is_directory:
                return
            if self.filenames:
                if event.src_path in self.filenames:
                    self.run_callback_func(event)
            else:
                self.run_callback_func(event)

        def run_callback_func(self, event):
            try:
                self.callback_func(event)
            except Exception as e:
                logging.error(e)

    def __init__(self):
        self.exchange_rates = {}
        self.updated_on = 0

        self.parse_rates_file(RATES_FILENAME)

        self._file_changed_event_handler = ExchangeRates._FileChangedEventHandler(
            [RATES_FILENAME],
            self.rates_file_updated
        )
        self._dir_monitor = DirectoryChangeObserver()
        self._dir_monitor.schedule(self._file_changed_event_handler, CACHE_DIR, recursive=False)
        self._dir_monitor.start()

    def rates_file_updated(self, event):
        self.parse_rates_file(RATES_FILENAME)

    def parse_rate(self, ratedef):
        code = None
        try:
            code, rate_s, bid, offer, last_date, last_time = ratedef.strip().split(",")
            _, _ = bid, offer
            symbol = code.strip("\"")[3:6].upper()
            try:
                rate = float(rate_s)
            except ValueError, e:
                logging.warn(
                    "Currency exchange rate returned for code '%s' is not parseable: %s",
                    str(code), rate_s)
                rate = float(0)
            last_date = last_date.strip("\"")
            updated = None
            if last_date != "N/A":
                #last_datetime = "%s %s" % (last_date, last_time)
                #updated = datetime.strptime(last_datetime, "%m/%d/%Y %I:%M%p")

                month, day, year = map(int, last_date.split("/"))
                last_time = last_time.strip("\"")
                if last_time != "N/A":
                    hour, minute = last_time.split(":")
                    hour = int(hour)
                    if minute.endswith("pm"):
                        if hour < 12:
                            hour += 12
                    minute = int(minute[:-2])
                updated = datetime(year, month, day, hour, minute)
            #name = self.exchange_rates.get(symbol, {"name":None})["name"]
            if rate == 0.0:
                logging.warning(
                    "Currency exchange data returned for code '%s' unhandled; empty data received.",
                    code
                )
            return symbol, {
                #"name":name,
                "name": symbol,
                "rate": rate,
                "updated": updated
            }
        except Exception, e:
            logging.error(
                "Currency exchange data returned for code '%s' are not parseable: %s",
                str(code), e)
            return None, None

    def parse_rates_file(self, filename):
        updates = 0
        try:
            with open(filename, "r") as fd:
                for line in fd:
                    symbol, definition = self.parse_rate(line)
                    if symbol and definition:
                        self.exchange_rates[symbol] = definition
                        updates += 1
        except Exception as e:
            logging.error(e)
        else:
            if updates:
                self.updated_on = os.path.getmtime(filename)
                logging.info("Currency exchange rates updated for %d currencies on %s",
                             updates,
                             time.ctime(self.updated_on)
                             )


RATES = ExchangeRates()


complete_currency_re = re.compile(
    r"(.*)(" +
    "|".join(RATES.exchange_rates.keys()) +
    ") (in|to) (" +
    "|".join(RATES.exchange_rates.keys()) +
    ")(.*)",
    re.IGNORECASE)


partial_currency_re = re.compile(
    r"(in|to) (" +
    "|".join(RATES.exchange_rates.keys()) +
    ")(.*)",
    re.IGNORECASE)


def is_supported_currency(iso):
    if not iso:
        return False
    return iso.upper() in RATES.exchange_rates


def guess_home_currency():
    logging.info("Guessing user's local currency")

    ext_ip = None
    try:
        logging.info("Getting external IP address...")
        ext_ip = myip()  # enso.net.get_external_ip()
        logging.info("External IP address: %s", ext_ip)
    except Exception, e:
        logging.error("Error getting external IP address: %s", e)
    else:
        logging.info("Lookup country by IP address...")
        try:
            import ccy
        except ImportError:
            logging.warning("Python-package 'ccy' is not installed. Currency lookup-by-country will not be available.")
        else:
            try:
                import geoip
            except ImportError:
                logging.warning(
                    "Python-package 'pygeoip' is not installed. Currency lookup-by-country will not be available.")
            else:
                try:
                    # TODO: Reasonably cache this
                    c = geoip.lookup_country_code(ext_ip)
                    if c:
                        logging.info("Country by IP: %s", c)
                        logging.info("Lookup currency by country...")
                        curr = ccy.countryccy(c)
                        logging.info("Local currency: %s", curr)
                        return curr
                except Exception, e:
                    logging.error(e)

    # If all above failed, try to query geobytes directly for curency code
    # TODO: Reasonably cache this
    if ext_ip and inetcache.isonline:
        try:
            with closing(urllib2.urlopen(
                    "http://getcitydetails.geobytes.com/GetCityDetails?fqcn=%s"
                    % ext_ip, None, 5)) as resp:
                meta = resp.read()
            r = re.search(r"\"geobytescurrencycode\"\s*:\s*\"([A-Z]{3})\"", meta)
            if r:
                return r.group(1)
        except Exception, e:
            logging.error(e)

    #import ip2country
    # print ip2country.IP2Country(verbose=True).lookup(ext_ip)

    #import whois
    #nic_client = whois.NICClient()
    #flags = whois.NICClient.WHOIS_QUICK
    # print nic_client.whois_lookup({}, ext_ip, flags)

    #import pycountry
    #country = pycountry.countries.get(alpha2=c)
    # print dir(country)

    logging.info("Reading local currency from locale settings...")
    locale.setlocale(locale.LC_ALL, '')
    curr = locale.localeconv()['int_curr_symbol']
    if curr:
        curr = curr.strip()
        logging.info("Local currency: %s", curr)
    else:
        curr = 'EUR'
        logging.info("Setting local currency to default: %s", curr)
    return curr


def get_home_currency():
    if Globals.HOME_CURRENCY is None:
        config = SafeConfigParser()
        config.read(Globals.INI_FILE)
        if config.has_section("defaults") and config.has_option("defaults", "home_currency"):
            hc = config.get("defaults", "home_currency")
        else:
            hc = guess_home_currency()
            if hc:
                set_home_currency(hc)
        Globals.HOME_CURRENCY = hc
    return Globals.HOME_CURRENCY


def set_home_currency(curr):
    Globals.HOME_CURRENCY = curr
    config = SafeConfigParser()
    config.read(Globals.INI_FILE)
    if not config.has_section("defaults"):
        config.add_section("defaults")
    config.set("defaults", "home_currency", curr)
    if not os.path.isdir(os.path.dirname(Globals.INI_FILE)):
        os.makedirs(os.path.dirname(Globals.INI_FILE))
    with open(Globals.INI_FILE, "w") as fp:
        config.write(fp)


def currency(amount, from_curr, to_curr):
    # TODO: Convert following assertions into custom exceptions
    assert from_curr in RATES.exchange_rates, "Unknown source currency code: %s" % from_curr
    assert to_curr in RATES.exchange_rates, "Unknown target currency code: %s" % to_curr

    unknown_rates = []
    result = None
    rate = None
    rate_updated = None

    if from_curr == "EUR":
        if RATES.exchange_rates[to_curr]["rate"] == 0:
            unknown_rates.append(to_curr)
        else:
            rate = RATES.exchange_rates[to_curr]["rate"]
            rate_updated = RATES.exchange_rates[to_curr]["updated"]
            result = rate * amount
    elif to_curr == "EUR":
        if RATES.exchange_rates[from_curr]["rate"] == 0:
            unknown_rates.append(from_curr)
        else:
            rate = 1 / RATES.exchange_rates[from_curr]["rate"]
            rate_updated = RATES.exchange_rates[to_curr]["updated"]
            result = rate * amount
    else:
        # How to correctly calculate this?
        if RATES.exchange_rates[from_curr]["rate"] == 0:
            unknown_rates.append(from_curr)
        if RATES.exchange_rates[to_curr]["rate"] == 0:
            unknown_rates.append(to_curr)
        if not unknown_rates:
            in_eur = amount / RATES.exchange_rates[from_curr]["rate"]
            result = round(RATES.exchange_rates[to_curr]["rate"] * in_eur, 4)
            rate_updated = RATES.exchange_rates[to_curr]["updated"]

    if unknown_rates:
        quasimode.setDidyoumeanHint(
            u"Unknown exchange rate for currency %s"
            % ",".join(unknown_rates))
    #result2 = currency1(amount, from_curr, to_curr)
    # if result2 != result:
    #    print "Currency computed: %f; currency Google: %f" % (result, result2)
    
    rate_updated_str = ""
    if rate_updated:
        if rate_updated.date() == datetime.today().date():
            rate_updated_str = " (updated today %s)" % rate_updated.time().strftime("%H:%M")
        elif rate_updated.date() == datetime.today().date() - timedelta(days=1):
            rate_updated_str = " (updated yesterday %s)" % rate_updated.time().strftime("%H:%M")
        else:
            rate_updated_str = " (updated %s)" % rate_updated.isoformat()
    expr = "%s %s in %s%s" % (  # (rate %s from %s)
        ("%.4f" % amount).rstrip("0").rstrip("."),
        from_curr,  # exchange_rates[from_curr][0],
        to_curr,  # exchange_rates[to_curr][0]
        #("%.4f" % rate).rstrip("0").rstrip("."),
        rate_updated_str,
    )
    """
    suggestions = set(symbol for symbol in RATES.exchange_rates.keys() if symbol.startswith((from_curr[0], to_curr[0])))
    suggestions = suggestions - set((from_curr, to_curr))
    if suggestions:
        quasimode.setDidyoumeanHint(" or ".join(suggestions))
    else:
        quasimode.setDidyoumeanHint(None)
    """
    return result, expr, rate, rate_updated

get_home_currency()


def _get_enso_directory():
    dir_name = os.path.dirname(os.path.realpath(sys.argv[0]))
    if dir_name.endswith("%sscripts" % os.path.sep):
        dir_name = os.path.realpath(os.path.join(dir_name, ".."))
    return dir_name


def tolocale(ustr):
    """Return a locale-encoded bytestring from unicode @ustr"""
    assert isinstance(ustr, unicode)
    enc = locale.getpreferredencoding(do_setlocale=False)
    return ustr.encode(enc)


def argv_to_locale(argv):
    "encode unicode strings in @argv according to the locale encoding"
    return [tolocale(A) if isinstance(A, unicode) else A
            for A in argv]


def spawn_exchangerates_updater():
    global _last_exchangerate_update_check
    
    now = time.time()
    if now - _last_exchangerate_update_check < 5 * 60:
        return 0

    try:
        try:
            if CURRENT_PLATFORM == PLATFORM_NAME_LINUX:
                import gobject
                cmdline = ["python", os.path.join(_get_enso_directory(), "enso", "contrib", "calc", "exchangerates_updater.py")]
                argv = argv_to_locale(cmdline)
                pid = gobject.spawn_async (argv, #working_directory=workdir,
                        flags=gobject.SPAWN_SEARCH_PATH | gobject.SPAWN_STDOUT_TO_DEV_NULL)
                return pid
            else:
                cmdline = ["python.exe", os.path.join(_get_enso_directory(), "enso", "contrib", "calc", "exchangerates_updater.py")]
                pid = subprocess.Popen(cmdline, shell=False, stdout=None).pid  # Only on windows: , creationflags=os.P_NOWAIT
                return pid
        except Exception as e:
            logging.error(e)
    except Exception as e:
        logging.error("Error spawning exchangerates_updater process: %s", e)
        return 0
    finally:
        _last_exchangerate_update_check = now


def on_idle():
    try:
        spawn_exchangerates_updater()
    except Exception as e:
        logging.error(e)


def on_init():
    try:
        spawn_exchangerates_updater()
    except Exception as e:
        logging.error(e)
    finally:
        EventManager.get().removeResponder(on_init)
        EventManager.get().registerResponder(on_idle, "idle")


EventManager.get().registerResponder(on_init, "init")
