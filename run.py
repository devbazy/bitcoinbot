# -*- coding: utf-8 -*-
#!/usr/bin/python
import re
import wykop
import urllib
import urllib2
import datetime
from unidecode import unidecode
try: import simplejson as json
except ImportError: import json
import contextlib

TRICKERS = [
    {
        "main_currency":"BTC",
        "services":[
            {
                "name":"bitcurex",
                "ticker":"http://%(currency)s.bitcurex.com/data/ticker.json",
                "currency":["PLN", "EUR"],
                "last_extractor" : lambda t:t['last'],
            },
            {
                "name":"mtgox",
                "ticker":"http://data.mtgox.com/api/1/BTC%(currency)s/ticker",
                "currency":["PLN", "EUR", "USD"],
                "last_extractor" : lambda t: float(t['return']['last']['value']),
            },
            {
                "name":"btcchina",
                "ticker":"https://data.btcchina.com/data/ticker",
                "currency":["CNY"],
                "last_extractor" : lambda t: float(t['ticker']['last']),
            },
            {
                "name":"bitstamp",
                "ticker":"https://www.bitstamp.net/api/ticker/",
                "currency":["USD"],
                "last_extractor" : lambda t: float(t['last']),
            },
        ]
    },
    {
        "main_currency":"LTC",
        "services":[
            {
                "name":"btc-e",
                "ticker":"https://btc-e.com/api/2/ltc_%(currency)s/ticker/",
                "currency":["BTC", "EUR", "USD"],
                "cur_fun" : lambda t:t.lower(),
                "last_extractor" : lambda t:float(t['ticker']['last']),
            },
            #{
            #    "name":"vircurex",
            #    #"ticker":"http://vircurex.com/api/get_highest_bid.json?base=LTC&alt=%(currency)s",
            #    "ticker":"http://vircurex.com/api/get_highest_bid.json?base=LTC&alt=USD",
            #    "currency":["BTC", "EUR", "USD"],
            #    "last_extractor" : lambda t: float(t['value']),
            #},
            {
                "name":"crypto-trade",
                "ticker":"https://www.crypto-trade.com/api/1/ticker/ltc_%(currency)s",
                "currency":["BTC", "EUR", "USD"],
                "cur_fun" : lambda t:t.lower(),
                "last_extractor" : lambda t: float(t['data']["last"]),
            },
        ]
    }
]

class AttrDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__

def _request(url, currency):
    req = urllib2.Request(url % {"currency": currency})

    try:
        with contextlib.closing(urllib2.urlopen(req)) as f:
            return f.read()
    except Exception, e:
        print str(e.code)

def _parse_json(data):
    result = json.loads(data, object_hook=lambda x: AttrDict(x))
    return result

def generate_sub_tag(h, arg):
    return "#bitcoinbot%s" % arg if h % arg == 0 else "[bitcoinbot%s](http://www.wykop.pl/tag/bitcoinbot%s/)" % (arg, arg)

APPKEY=""
SECRETKEY=""
LOGIN = ''
ACCOUNTKEY=""

def main():

    api = wykop.WykopAPI(APPKEY, SECRETKEY)
    api.authenticate(LOGIN, ACCOUNTKEY)

    entries = api.tag("bitcoin")
    micro_entries = [(entry['vote_count'], entry) for entry in entries['items'] if entry['type'] == 'entry' and entry['author'] != 'bitcoinbot']

    top_micros = sorted(micro_entries)[::-1][:5]
    top_micros = [ micro[1] for micro in top_micros if micro[0] != 0]

    if len(top_micros) > 0:
        entry_micros = "\nPopularne ostatnio wpisy na mikro z tagu [bitcoin](http://www.wykop.pl/tag/bitcoin):\n"

        for micro_entry in top_micros:
            import html2text
            title = html2text.html2text(micro_entry['body'])
            title = re.sub('\n', '. ', title)
            title = re.sub('#', '', title)
            title = re.sub('(\. )+', '. ', title)
            title = re.sub('\ +', ' ', title)

            micro_entry['title'] = title[:60] + "..."
            entry_micros += '- ["%(title)s"](%(url)s) [+%(vote_count)s] by @[%(author)s](http://www.wykop.pl/ludzie/%(author)s)\n' % micro_entry

        entry_micros += "\n"

    links = [entry for entry in entries['items'] if entry['type'] == 'link']

    entry_links = None

    if len(links) > 0:
        entry_links = "\nOstatnio dodane znaleziska na temat bitcoina:\n"

        for link in links:
            link['title'] = re.sub('#', '', link['title'])
            entry_links += "- [%(title)s](%(url)s) [+%(vote_count)s/-%(report_count)s]\n" % link

        entry_links += "\n"

    data = {}

    entry_price = ""
    for tricker_data in TRICKERS:

        for service in tricker_data["services"]:
            for currency in service["currency"]:
                print service["name"] +  " - " + currency

                cur_fun = service.get("cur_fun", lambda c:c)

                response = _request(service["ticker"], cur_fun(currency))
                t = _parse_json(response)
                last_extractor = service["last_extractor"]

                if currency == "BTC":
                    data[service["name"] + '_price_' + currency] = "{0:6.4f}".format(last_extractor(t))
                else:
                    data[service["name"] + '_price_' + currency] = "{0:6.2f}".format(last_extractor(t))


                print " -  OK"

        curs = set()
        for service in tricker_data["services"]:
            curs |= set(service['currency'])


        entry_price += '`  {:10s} '.format("CENY %s" % tricker_data["main_currency"]) + "|"

        for currency in curs:
            entry_price += '{:>8s} '.format(currency) + "|"
        entry_price += "`\n"

        entry_price += "`" + str('-'*(len(curs)*10+14)) +   "`\n"

        for service in tricker_data["services"]:
            entry_price += '`{:12s} '.format(service["name"]) + "|"
            for currency in curs:
                if service["name"] + '_price_' + currency in data:
                    entry_price += "{:>8s} ".format(data[service["name"] + '_price_' + currency]) + "|"
                else:
                    entry_price += "{:>8s} ".format("") + "|"

            entry_price += '`\n'

        entry_price += "\n\n"

    entry_price = entry_price.replace(" ", u"\u00A0")

    entry = ''

    if entry_links:
        entry += entry_links

    if entry_micros:
        entry += entry_micros

    entry +="#bitcoinbot\n\n"\
            "PS. Stworzyl mnie @[noisy](http://www.wykop.pl/ludzie/noisy), do niego prosze kierowac pomysly i sugestie na temat mojego rozwoju."


    h = datetime.datetime.now().hour

    fallow_tags="\n\n%s - tag do subskrybcji co 24h (12:00)\n" % generate_sub_tag(h, 24)
    fallow_tags+= "%s - tag do subskrybcji co 12h (0:00/12:00)\n" % generate_sub_tag(h, 12)
    fallow_tags+= "%s - tag do subskrybcji co 6h (0/6/12/18)\n" % generate_sub_tag(h, 6)
    fallow_tags+= "%s - tag do subskrybcji co 3h (0/3/6/9/12/15/18/21)\n" % generate_sub_tag(h, 3)
    fallow_tags+= "%s - tag do subskrybcji co godzine\n" % generate_sub_tag(h, 1)

    entry += fallow_tags

    entry = entry_price + unidecode(entry)

    api.add_entry(entry)

    print "OK!"

if __name__ == '__main__':
    main()
