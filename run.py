# -*- coding: utf-8 -*-
#!/usr/bin/python
import re
import wykop
import urllib
import urllib2
import datetime
import html2text
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

def get_entries_from_tag(api, tag, lenght = 60, max = 5):
    data={}
    entries = api.tag(tag)
    micro_entries = [(entry['vote_count'], entry) for entry in entries['items'] if entry['type'] == 'entry' and entry['author'] != 'bitcoinbot']

    top_micros = sorted(micro_entries)[::-1][:max]
    top_micros = [ micro[1] for micro in top_micros if micro[0] != 0]

    if len(top_micros) > 0:
        data[tag + "_entry_micros"] = "\nPopularne ostatnio wpisy na mikro z tagu [%s](http://www.wykop.pl/tag/%s): \n" % (tag, tag)

        for micro_entry in top_micros:

            title = html2text.html2text(micro_entry['body'])
            title = re.sub('\n', '. ', title)
            title = re.sub('#', '', title)
            title = re.sub('(\. )+', '. ', title)
            title = re.sub('\ +', ' ', title)

            micro_entry['title'] = title[:lenght] + "..."
            data[tag + "_entry_micros"] += '- ["%(title)s"](%(url)s) [+%(vote_count)s] by @[%(author)s](http://www.wykop.pl/ludzie/%(author)s)\n' % micro_entry

        data[tag + "_entry_micros"] += "\n"

    links = [entry for entry in entries['items'] if entry['type'] == 'link']

    if len(links) > 0:
        data[tag + "_entry_links"] = "\nOstatnio dodane znaleziska na temat %sa:\n" % tag

        for link in links:
            link['title'] = re.sub('#', '', link['title'])
            data[tag + "_entry_links"] += "- [%(title)s](%(url)s) [+%(vote_count)s/-%(report_count)s]\n" % link

        data[tag + "_entry_links"] += "\n"

    return data

def get_prices(trickers):
    data={}
    data["entry_price"] = ""
    for tricker_data in trickers:

        for service in tricker_data["services"]:
            for currency in service["currency"]:
                print service["name"] +  " - " + currency

                cur_fun = service.get("cur_fun", lambda c:c)

                response = _request(service["ticker"], cur_fun(currency))
                t = _parse_json(response)
                last_extractor = service["last_extractor"]

                format_ = "{0:6.%df}" % ( 4 if currency == "BTC" else 2)
                data[service["name"] + '_price_' + currency] = format_.format(last_extractor(t))

                print " -  OK"

        curs = set()
        for service in tricker_data["services"]:
            curs |= set(service['currency'])

        data["entry_price"] += '`  {:10s} '.format("CENY %s" % tricker_data["main_currency"]) + "|"

        for currency in curs:
            data["entry_price"] += '{:>8s} '.format(currency) + "|"
        data["entry_price"] += "`\n"

        data["entry_price"] += "`" + str('-'*(len(curs)*10+14)) +   "`\n"

        for service in tricker_data["services"]:
            data["entry_price"] += '`{:12s} '.format(service["name"]) + "|"
            for currency in curs:
                if service["name"] + '_price_' + currency in data:
                    data["entry_price"] += "{:>8s} ".format(data[service["name"] + '_price_' + currency]) + "|"
                else:
                    data["entry_price"] += "{:>8s} ".format("") + "|"

            data["entry_price"] += '`\n'

        data["entry_price"] += "\n\n"

    data["entry_price"] = data["entry_price"].replace(" ", u"\u00A0")
    return data

def get_fallow_tags(h):
    data = {}
    data["fallow_tags"]="\n\n%s - tag do subskrybcji co 24h (12:00)\n" % generate_sub_tag(h, 24)
    data["fallow_tags"]+= "%s - tag do subskrybcji co 12h (0:00/12:00)\n" % generate_sub_tag(h, 12)
    data["fallow_tags"]+= "%s - tag do subskrybcji co 6h (0/6/12/18)\n" % generate_sub_tag(h, 6)
    data["fallow_tags"]+= "%s - tag do subskrybcji co 3h (0/3/6/9/12/15/18/21)\n" % generate_sub_tag(h, 3)
    data["fallow_tags"]+= "%s - tag do subskrybcji co godzine\n" % generate_sub_tag(h, 1)

    return data

def get_ps():
    return {"ps": "#bitcoinbot\n\nPS. Stworzyl mnie @[noisy](http://www.wykop.pl/ludzie/noisy), do niego prosze kierowac pomysly i sugestie na temat mojego rozwoju."}

def generate_sub_tag(h, arg):
    return "#bitcoinbot%s" % arg if h % arg == 0 else "[bitcoinbot%s](http://www.wykop.pl/tag/bitcoinbot%s/)" % (arg, arg)

APPKEY=""
SECRETKEY=""
LOGIN = ''
ACCOUNTKEY=""

def main():

    api = wykop.WykopAPI(APPKEY, SECRETKEY)
    api.authenticate(LOGIN, ACCOUNTKEY)

    data = {}

    data.update(get_prices(TRICKERS))
    data.update(get_entries_from_tag(api, "bitcoin"))
    data.update(get_ps())
    data.update(get_fallow_tags(datetime.datetime.now().hour))

    entry = ""

    for entry_data in ["bitcoin_entry_links", "bitcoin_entry_micros", "ps"]:
        entry += data[entry_data]

    entry = data["entry_price"] + unidecode(entry)

    print entry
    api.add_entry(entry)
    print "OK!"

if __name__ == '__main__':
    main()

