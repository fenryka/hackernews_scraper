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

    def _get (self, what_) :
        buf = StringIO()
        self.curl.setopt (self.curl.URL, '%s/%s/%s.json' % (self.uri, self.version, what_))
        self.curl.setopt (self.curl.WRITEDATA, buf)
        self.curl.perform()

        return json.loads (buf.getvalue())

    def topstories (self) : return self._get ('topstories')
    def item (self, item_) : return self._get ('item/%s' % item_);

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
set(['author', 'title', 'uri', 'rank', 'points', 'comments'])
def get_items (items_, args_) :
    print "get_items %s" % str(items_)
    def kid_is_comment (child) :
        item = HNews().item (child)
        return 1 if item['type'] == "comment" else 0

    rtn        = []
    hnews      = HNews()
    threadpool = Pool (args_.tpool)

    offset = 1;
    for item_key in items_[1] :
        story            = hnews.item (item_key)
        item             = { }
        item['title']    = story['title']
        item['uri']      = story['url']
        item['author']   = story['by']
        item['rank']     = items_[0] + offset
        item['points']   = story['score']

        try :
#            item['comments'] = threadpool.map (get_comments, story['kids']).count (1)

            item['comments'] = 0
            for kid in story['kids'] :
                if kid_is_comment (kid) : item['comments'] += 1
        except KeyError :
            item['comments'] = 0

        offset += 1

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
    threadpool = Pool (args.tpool)
    results    = []

#    results.extend (threadpool.map (lambda p : get_items (p, args), sublists));
    for l in sublists : results.extend (get_items (l, args))

    print json.dumps (list (itertools.chain.from_iterable (results)), indent=3)

#-------------------------------------------------------------------------------

if __name__ == "__main__" :
    main()

#-------------------------------------------------------------------------------

