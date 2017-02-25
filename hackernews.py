#!/usr/bin/python

#-------------------------------------------------------------------------------

import sys
import json
import pycurl
import argparse
import itertools

from StringIO              import StringIO
from multiprocessing.dummy import Pool

#-------------------------------------------------------------------------------

class HNews (object) :
    def __init__ (self) :
        self.uri     = 'https://hacker-news.firebaseio.com'
        self.version = 'v0'
        self.curl    = pycurl.Curl()

    def __del__ (self) :
        self.curl.close()

    def _set (self, what_) :
        self.buf = StringIO()
        self.curl.setopt (self.curl.URL, '%s/%s/%s.json' % (self.uri, self.version, what_))
        self.curl.setopt (self.curl.WRITEDATA, self.buf)
        self.curl.setopt(pycurl.CONNECTTIMEOUT, 30)
        self.curl.setopt(pycurl.TIMEOUT, 300)
        self.curl.setopt(pycurl.NOSIGNAL, 1)

    def _get (self) :
        self.curl.perform()
        return json.loads (self.buf.getvalue())

    def topstories (self, get_ = True) :
        self._set ('topstories')
        return self._get() if get_ else None

    def item (self, item_, get_ = True) :
        self._set ('item/%s' % item_);
        return self._get() if get_ else None

    def perform (self) :
        return self._get()

    def close (self) :
        self.curl.close()

    def json (self) :
        return json.loads (self.buf.getvalue())

#-------------------------------------------------------------------------------

class MultiHNews (object) :
    def __init__ (self) :
        self.mcurls  = pycurl.CurlMulti()
        self.curls   = []
        self.timeout = 1.0

    def __del__ (self) :
        print "Tear down"
        for curl in self.curls :
            self.mcurls.remove_handle (curl.curl)
            curl.close()

        self.mcurls.close()

    def item (self, item_) :
        self.curls.append (HNews())
        self.curls[-1].item (item_, False)
        self.mcurls.add_handle (self.curls[-1].curl)

    def perform (self) :
        while True :
            while True :
                ret, num_handles = self.mcurls.perform()
                if ret != pycurl.E_CALL_MULTI_PERFORM : break

            if num_handles == 0 : break;

            v = self.mcurls.select (self.timeout)
            if v == -1 : continue

    def __iter__ (self) :
        return self.curls.__iter__()

#-------------------------------------------------------------------------------

def parseargs() :
    ap = argparse.ArgumentParser (description = "Hacker News dl'er")

    class posts_action (argparse.Action) :
        def __call__ (self, parser, namespace, values, option_string = None) :
            if values < 1 or values > 100 :
                parser.error (
                    "Posts must be between 1 and 100".format (option_string))

            setattr (namespace, self.dest, values)

    ap.add_argument (
        '--posts', '-p',
        type    = int,
        default = 10,
        action  = posts_action,
        help    = 'How many stories to grab [between 1 and 100]')

    ap.add_argument (
        '--tpool', '-t',
        type    = int,
        default = 10,
        help    = "How large a threadpool to use for issue fetch")

    ap.add_argument (
        '--threads', '-T',
        action = 'store_true',
        help   = "If set each subset of results will be fetched in a seperate thread")

    #
    # Set weather we treat all child elements of a story object as a 
    # comment or weather we check each one to be sure
    #
    ap.add_argument (
        '--all_kids_are_comments', '-k',
        action = 'store_true',
        help   = "If set, will treat every child ofa story as a comment")


    return ap.parse_args()

#-------------------------------------------------------------------------------

#
# returned fields will be 
#   kids
#   title
#   url
#   descendants
#   id
#   score
#   time
#   type
#   by
#
# from that we want to map
#   author <- by
#   title
#   uri <- url
#   points <- score
#   ranks <- { from offset }
#   comments <- { calc from kids }
#
def get_items (items_, args_) :
    def kid_is_comment (child) :
        item = HNews().item (child)
        return 1 if item['type'] == "comment" else 0

    rtn = []
    mhn = MultiHNews()

    #
    # load the list of items into our multi curl obj
    #
    for item_key in items_[1] : mhn.item (item_key)

    mhn.perform()

    offset = 0;
    for data in mhn :
        offset += 1
        story = data.json()
        item  = { }
        try :
            item['title']  = story['title']
            item['uri']    = story['url']
            item['author'] = story['by']
            item['rank']   = items_[0] + offset
            item['points'] = story['score']
        except KeyError as e:
            raise e

        try :
            if args_.all_kids_are_comments :
                item['comments'] = len (story['kids'])
            else :
                kids = MultiHNews()
                for kid in story['kids'] : kids.item (kid)
                kids.perform()
                item['comments'] = [ 1 if x.json()['type'] == "comment" else 0 \
                    for x in kids ].count (1)
        except KeyError as e :
            item['comments'] = 0

        rtn.append (item)

    return rtn

#-------------------------------------------------------------------------------

def main() :
    args  = parseargs()
    hnews = HNews()
    top   = hnews.topstories()[:args.posts]
    if args.posts < args.tpool :
        lsize = args.tpool
    else :
        lsize = args.posts / args.tpool

    #
    # split the list into a set of sublists we can farm out to some
    # worker threads, each sublist is actually n object pair mathcing
    # the offset into tthe origional list with the sublist itself
    #
    sublists   = [(i, top[i:i + lsize]) for i in xrange (0, len (top), lsize)]
    results    = []

    if args.threads :
        threadpool = Pool (args.tpool)
        results.extend (threadpool.map (lambda p : get_items (p, args), sublists));
#        print json.dumps (list (itertools.chain.from_iterable (results)), indent=3)
    else :
        for l in sublists : results.extend (get_items (l, args))
#        print json.dumps (results, indent=3)

#-------------------------------------------------------------------------------

if __name__ == "__main__" :
    main()

#-------------------------------------------------------------------------------

