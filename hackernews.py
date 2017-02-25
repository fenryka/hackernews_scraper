#!/usr/bin/python

#-------------------------------------------------------------------------------

import sys
import json
import pycurl
import argparse
import validators

from StringIO import StringIO

#-------------------------------------------------------------------------------

class HNewsResult (object) :
    def __init__ (self, url_) :
        self.url = url_

    def activate (self) :
        self.buf  = StringIO()
        self.curl = pycurl.Curl()

        self.curl.setopt (self.curl.URL, self.url)
        self.curl.setopt (self.curl.WRITEDATA, self.buf)
        self.curl.setopt(pycurl.CONNECTTIMEOUT, 30)
        self.curl.setopt(pycurl.TIMEOUT, 300)
        self.curl.setopt(pycurl.NOSIGNAL, 1)

    def errors (self) :
        try :
            return self.error
        except AttributeError :
            return None

    def json (self) :
        try :
            return json.loads (self.buf.getvalue())
        except :
            return None

    def rtype (self) :
        try :
            return self.json()['type']
        except (ValueError, TypeError) :
            return None

#-------------------------------------------------------------------------------

class HNews (object) :
    def __init__ (self) :
        self.uri        = 'https://hacker-news.firebaseio.com'
        self.version    = 'v0'
        self.mc         = pycurl.CurlMulti()
        self.timeout    = 1.0
        self.urls       = [ ]
        self.max_active = 25

    def _add_url (self, what_) :
        self.urls.append (
            HNewsResult ('%s/%s/%s.json' % (self.uri, self.version, what_)))

        #
        # return a convieneince refference to the caller, can be ignored if
        # theyr'e just going to iterate over a collection of restults later
        #
        return self.urls[-1]

    def topstories (self) : return self._add_url ('topstories')
    def item (self, item) : return self._add_url ('item/%s' % item)

    def __del__ (self) :
        self.mc.close()

    def perform (self) :
        handles = { }
        idx    = 0
        offset = 0

        while idx + offset < len (self.urls) :
            while idx < self.max_active and idx + offset < len (self.urls) :
                self.urls[offset + idx].activate()
                self.mc.add_handle (self.urls[offset + idx].curl)
                handles[self.urls[offset + idx].curl] = idx + offset

                idx+=1

            while True :
                ret, num_handles = self.mc.perform()
                if ret != pycurl.E_CALL_MULTI_PERFORM : break

            while num_handles :
                v = self.mc.select (self.timeout)
                if v == -1 : continue

                while True :
                    ret, num_handles = self.mc.perform()
                    if ret != pycurl.E_CALL_MULTI_PERFORM : break

            _dummy, good, bad = self.mc.info_read()

            for g in good :
                self.mc.remove_handle (g)
                self.urls[handles[g]].curl.close()
                handles.pop (g)

            for b in bad :
                self.mc.remove_handle (b[0])
                self.urls[handles[b[0]]].curl.close()
                self.urls[handles[b[0]]].error = b[2]
                self.urls[handles[b[0]]].buf   = None
                handles.pop (b[0])

            offset += idx
            idx = 0

    def __iter__ (self) :
        return self.urls.__iter__()

#-------------------------------------------------------------------------------

def parseargs() :
    ap = argparse.ArgumentParser (description = "Hacker News dl'er")

    #
    # Custom value calidity checker for the number of posts argument
    # since we exlicitly want that to be between 1 and 100
    #
    class posts_action (argparse.Action) :
        def __call__ (self, parser, namespace, values, option_string = None) :
            if values < 1 or values > 100 :
                parser.error (
                    "Posts must be between 1 and 100".format (option_string))

            setattr (namespace, self.dest, values)

    ap.add_argument (
        '--posts', '-p',
        type    = int,
        default = 100,
        action  = posts_action,
        help    = 'How many stories to grab [between 1 and 100]')

    ap.add_argument (
        '--nlists', '-l',
        type    = int,
        default = 1,
        help    = "How may sub lists to work on")

    #
    # Set weather we treat all child elements of a story object as a 
    # comment or weather we check each one to be sure
    #
    ap.add_argument (
        '--all_kids_are_not_comments', '-k',
        action = 'store_true',
        help   = "If set, will inspect every child object of a story to "
                 "check weather it is a comment object or not. If unset ("
                 "the default) Then all child objects are treated as comments "
                 "and included in the count. The latter is much faster")

    #
    # Just for testing purpoes when you want to time how long things are taking
    #
    ap.add_argument (
        '--silent', '-s',
        action = 'store_true',
        help   = "Supress all output")

    return ap.parse_args()

#-------------------------------------------------------------------------------

def get_items (items_, args_) :
    rtn = []
    mhn = HNews();

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
        item['title']  = story['title'][:256].encode('ascii','replace')
        item['author'] = story['by'][:256]
        item['rank']   = items_[0] + offset

        try :
            item['points'] = story['score']
        except KeyError :
            item['points'] = 0

        try :
            item['uri'] = story['url']
            if not validators.url (item['uri']) :
                item['uri'] = "<INVALID>"
        except KeyError :
            item['uri'] = ""

        try :
            if args_.all_kids_are_not_comments :
                kids = HNews()
                for kid in story['kids'] : kids.item (kid)
                kids.perform()
                item['comments'] = [ 1 if x.rtype() == "comment" else 0 \
                    for x in kids ].count (1)
            else :
                item['comments'] = len (story['kids'])

        except KeyError as e :
            item['comments'] = 0

        rtn.append (item)

    return rtn

#-------------------------------------------------------------------------------

def main() :
    args   = parseargs()
    hnews  = HNews()

    #
    # Firstly, just grab the list of the top 200 stories. There might be a
    # way to trim that down in the API call but I can't see it so just
    # get all 200 and throw away the ones we don't need. It's just one
    # call so it's not like we're really wasting any cycles doing this
    #
    result = hnews.topstories()
    hnews.perform();

    #
    # As above, limit the actual list of posts we want to fetch to the
    # number we've been told to
    #
    if result.errors() :
        print "Error: %s" % result.errors()
        sys.exit (1)

    top = result.json()[:args.posts]

    #
    # how big is each sub list going to be. we could be using sublists
    # to partition off the calls we make
    #
    lsize = args.nlists if args.posts < args.nlists else args.posts / args.nlists

    #
    # split the list into a set of sublists and then iterate over them
    # to pull down the results. Default to one as the library should be able to
    # handle pulling down lots of resuls in parallel but the VM I was testing
    # on struggles (because it was tiny) and this became a good way of letting
    # it actually complete without OOMing   
    #
    sublists   = [(i, top[i:i + lsize]) for i in xrange (0, len (top), lsize)]
    results    = []

    for l in sublists : results.extend (get_items (l, args))
    if not args.silent :
        print json.dumps (results, indent = 3)

#-------------------------------------------------------------------------------

if __name__ == "__main__" :
    main()

#-------------------------------------------------------------------------------

