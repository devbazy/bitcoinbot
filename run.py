# -*- coding: utf-8 -*-
#!/usr/bin/python
import re
import wykop
import urllib
import urllib2
import datetime
import html2text
try: import simplejson as json
except ImportError: import json
import contextlib
import time

TRICKERS = [

    {
        "main_currency":"BTC",
        "services":[
            {
                "name":"bitcurex",
                "ticker":"http://%(currency)s.bitcurex.com/data/ticker.json",
                "currency":["PLN", "EUR"],
                "last_extractor" : lambda t, cur=None:t['last'],
            },
            {
                "name":"mtgox",
                "ticker":"http://data.mtgox.com/api/1/BTC%(currency)s/ticker",
                "currency":["PLN", "EUR", "USD"],
                "last_extractor" : lambda t, cur=None: float(t['return']['last']['value']),
            },
            {
                "name":"btcchina",
                "ticker":"https://data.btcchina.com/data/ticker",
                "currency":["CNY"],
                "last_extractor" : lambda t, cur=None: float(t['ticker']['last']),
            },
            {
                "name":"bitstamp",
                "ticker":"https://www.bitstamp.net/api/ticker/",
                "currency":["USD"],
                "last_extractor" : lambda t, cur=None: float(t['last']),
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
                "last_extractor" : lambda t, cur=None:float(t['ticker']['last']),
            },
            {
                "name":"crypto-trade",
                "ticker":"https://www.crypto-trade.com/api/1/ticker/ltc_%(currency)s",
                "currency":["BTC", "EUR", "USD"],
                "cur_fun" : lambda t:t.lower(),
                "last_extractor" : lambda t, cur=None: float(t['data']["last"]),
            },
            {
                "name":"vircurex",
                "ticker":"https://vircurex.com/api/get_highest_bid.json?base=LTC&alt=%(currency)s",
                "currency":["BTC"],#, "EUR", "USD"],
                "last_extractor" : lambda t, cur=None: float(t['value']),
            },
        ]
    },
    {
        "main_currency":"GLD",
        "services":[
            {
                "name":"cryptsy",
                "ticker":"http://pubapi.cryptsy.com/api.php?method=singlemarketdata&marketid=%(currency)s",
                "currency":["BTC", "LTC"],
                "cur_fun" : lambda t: 30 if "BTC"==t else 36,
                "last_extractor" : lambda t, cur=None:float(t['return']['markets']['GLD']['lasttradeprice']),
                "precision":6
            },
            {
                "name":"coinex",
                "ticker":"https://coinex.pw/api/v1/trade_pairs",
                "currency":["BTC", "LTC"],
                "cur_fun" : lambda t: t,
                "last_extractor" : lambda t, cur:float([tt["lastprice"] for tt in t if tt["urlSlug"] == "gld_%s" % cur.lower()][0]/100000000.0),
                "precision":6
            },
        ]
    },
    {
        "main_currency":"FTC",
        "services":[
            {
                "name":"btc-e",
                "ticker":"https://btc-e.com/api/2/ftc_%(currency)s/ticker/",
                "currency":["BTC"],
                "cur_fun" : lambda t:t.lower(),
                "last_extractor" : lambda t, cur=None:float(t['ticker']['last']),
                "precision":5
            },
            {
                "name":"crypto-trade",
                "ticker":"https://www.crypto-trade.com/api/1/ticker/ftc_%(currency)s",
                "currency":["BTC", "USD"],
                "cur_fun" : lambda t:t.lower(),
                "last_extractor" : lambda t, cur=None: float(t['data']["last"]),
                "precision":5
            },
        ]
    }

]

class AttrDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__

def _request(url, currency):

    if "https" in url:
        import httplib

        main_address = "/".join(url.split("/")[:3])
        c = httplib.HTTPSConnection(main_address.replace("https://", ""))
        c.request("GET", (url.replace(main_address,"")) % {"currency": currency})
        response = c.getresponse()
        if response.status != 200:
            return "ERR"
        else:
            return response.read()

    else:
        req = urllib2.Request(url % {"currency": currency})

        try:
            with contextlib.closing(urllib2.urlopen(req)) as f:
                return f.read()
        except Exception, e:
            return "ERR"

def _parse_json(data):
    result = json.loads(data, object_hook=lambda x: AttrDict(x))
    return result

def get_entries_from_tag(api, tag, h, lenght = 60, max = 5):
    data={}
    entries = api.tag(tag)
    micro_entries = [(entry['vote_count'], entry) for entry in entries['items'] if entry['type'] == 'entry' and entry['author'] != 'bitcoinbot']

    top_micros = sorted(micro_entries)[::-1][:max]
    top_micros = [ micro[1] for micro in top_micros if micro[0] != 0]

    if len(top_micros) > 0:
        data[tag + "_entry_micros"] = u"\nPopularne ostatnio wpisy na mikro z tagu [%s](http://www.wykop.pl/tag/%s): \n" % (tag, tag)

        for micro_entry in top_micros:

            title = html2text.html2text(micro_entry['body'])
            for f, r in [('\n', '. '), ('#', ''), ('@', ''), ('(\. )+', '. '), ('\ +', ' '), ('\[', ''),  ('\]', '')]:
                title = re.sub(f, r, title)

            micro_entry['title'] = title[:lenght] + u"..."
            data[tag + "_entry_micros"] += u'- ["%(title)s"](%(url)s) [+%(vote_count)s] by ' % micro_entry
            data[tag + "_entry_micros"] += (u'@%(author)s\n' if h == 12 else u'@[%(author)s](http://www.wykop.pl/ludzie/%(author)s)\n') % micro_entry

        data[tag + "_entry_micros"] += "\n"

    links = [entry for entry in entries['items'] if entry['type'] == 'link']

    if len(links) > 0:
        data[tag + "_entry_links"] = u"\nOstatnio dodane znaleziska na temat %sa:\n" % tag

        for link in links:
            link['title'] = re.sub('#', '', link['title'])
            data[tag + "_entry_links"] += u"- [%(title)s](%(url)s) [+%(vote_count)s/-%(report_count)s]\n" % link

        data[tag + "_entry_links"] += "\n"

    return data

def get_prices(trickers):
    data={}
    data["entry_price"] = u""
    for tricker_data in trickers:

        for service in tricker_data["services"]:
            for currency in service["currency"]:
                #print service["name"] +  " - " + tricker_data["main_currency"] + "/" + currency
                label = "_".join([service["name"],tricker_data["main_currency"],currency])
                cur_fun = service.get("cur_fun", lambda c:c)
                response = _request(service["ticker"], cur_fun(currency))

                if response != "ERR":
                    t = _parse_json(response)
                    last_extractor = service["last_extractor"]

                    format_ = "{0:6.%df}" % service.get("precision",(4 if currency == "BTC" else 2))
                    data[label] = format_.format(last_extractor(t, currency)).replace(".", ",")
                else:
                    data[label] = "#ERR#"

                #print data[label]

        curs = set()
        for service in tricker_data["services"]:
            curs |= set(service['currency'])

        data["entry_price"] += u'`  {:10s} '.format(u"CENY %s" % tricker_data["main_currency"]) + u"|"

        for currency in curs:
            data["entry_price"] += u'{:>8s} '.format(currency) + u"|"
        data["entry_price"] += u"`\n"

        data["entry_price"] += u"`" + str('-'*(len(curs)*10+14)) +   u"`\n"

        for service in tricker_data["services"]:
            data["entry_price"] += u'`{:12s} '.format(service["name"]) + u"|"
            for currency in curs:
                label = "_".join([service["name"],tricker_data["main_currency"],currency])
                data["entry_price"] += u"{:>8s} ".format(data.get(label, "")) + u"|"

            data["entry_price"] += u'`\n'

        data["entry_price"] += u"\n\n"

    data["entry_price"] = data["entry_price"].replace(u" ", u"\u00A0")
    return data

def get_fallow_tags(h):
    data = {}
    data["fallow_tags"] = u"\n\n#bitcoinbot - tag do dodawania na [czarną liste](http://www.wykop.pl/ustawienia/czarne-listy/)\n"
    data["fallow_tags"]+= u"%s - tag do subskrybcji co 24h (12:00)\n" % generate_sub_tag(h+12, 24)
    data["fallow_tags"]+= u"%s - tag do subskrybcji co 12h (0:00/12:00)\n" % generate_sub_tag(h, 12)
    data["fallow_tags"]+= u"%s - tag do subskrybcji co 6h (0/6/12/18)\n" % generate_sub_tag(h, 6)
    data["fallow_tags"]+= u"%s - tag do subskrybcji co 3h (0/3/6/9/12/15/18/21)\n" % generate_sub_tag(h, 3)
    data["fallow_tags"]+= u"%s - tag do subskrybcji co godzinę\n" % generate_sub_tag(h, 1)

    return data

def get_ps():
    return {"ps": u"\n\nPS. Stworzył mnie @[noisy](http://www.wykop.pl/ludzie/noisy), do niego prosze kierować pomysły i sugestie na temat mojego rozwoju."}

def get_addresses():
    return {"addresses":u"\n\n**Lubisz bitcoinbota**? \n! Wesprzyj jego rozwój:\n! LTC: LYQPBdu9PHpKnknWgeKy2y3FJEgdmoE94Q\n! FTC: 6gjVfpj6wCskEdHLRdAStLaRsR4LjRBdXr\n! BTC jest zbyt mainstreamowy :P \n! \n! Lista chwały: \n! - możesz być pierwszy :)\n" }

def generate_sub_tag(h, arg):
    return u"#bitcoinbot%s" % arg if h % arg == 0 else u"[bitcoinbot%s](http://www.wykop.pl/tag/bitcoinbot%s/)" % (arg, arg)

APPKEY=""
SECRETKEY=""
LOGIN = ''
ACCOUNTKEY=""

def main():
    start = time.time()

    api = wykop.WykopAPI(APPKEY, SECRETKEY)
    api.authenticate(LOGIN, ACCOUNTKEY)

    data = {}

    h = datetime.datetime.now().hour
    data.update(get_prices(TRICKERS))
    data.update(get_entries_from_tag(api, "bitcoin", h))
    data.update(get_ps())
    data.update(get_fallow_tags(h))
    data.update(get_addresses())

    entry = u""

    for entry_data in ["entry_price", "bitcoin_entry_links", "bitcoin_entry_micros", "ps", "fallow_tags", "addresses"]:
        entry += data.get(entry_data, "")

    entry += u"\nCzas generowania: %.4f s" % (time.time() - start)

    #print entry
    api.add_entry(entry)
    #print "OK!"

if __name__ == '__main__':
    main()

