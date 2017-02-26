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

        #
        # will deal with closing this once we've inished fetching
        # weather that fetch passes or succeeds
        #
        self.curl = pycurl.Curl()

        self.curl.setopt (self.curl.URL, self.url)
        self.curl.setopt (self.curl.WRITEDATA, self.buf)
        self.curl.setopt (pycurl.CONNECTTIMEOUT, 30)
        self.curl.setopt (pycurl.TIMEOUT, 300)
        self.curl.setopt (pycurl.NOSIGNAL, 1)

    #
    # We can error in one of two ways, either the request was a success
    # but we got nothing back, i.e. we requested something stupid or the
    # physcial request failed. In etiehr case we're goign to return the
    # appropraite error string and let the caller deal with rasing an
    # excpetion unless we're in a state we shouldn't be in in
    #
    def errors (self) :
        try :
            if self.buf and self.buf.getvalue() == "null" :
                return ("Url %s returned no result" % self.url)
        except AttributeError :
            #
            # If we've not been called we won't have a buff so we don't 
            # care one isn't set since any other state will be caught below
            #
            pass

        try :
            return self.error
        except AttributeError :
            #
            # Finally if no error is set on the obejct there aren't any
            # so we're all good to go
            #
            return False


    def json (self) :
        if self.errors() :
            raise ValueError (self.errors())

        #
        # we've already tested for errors we tolerate, if this fails let the
        # exception escape as we want to see how it's maanged to go worng in
        # an unexpted way
        #
        return json.loads (self.buf.getvalue())

    def rtype (self) :
        try :
            return self.json()['type']
        except (ValueError, TypeError, Exception) :
            return None

#-------------------------------------------------------------------------------

class HNews (object) :
    def __init__ (self) :
        self.uri        = 'https://hacker-news.firebaseio.com'
        self.version    = 'v0'
        self.mc         = pycurl.CurlMulti()
        self.timeout    = 1.0

        #
        # The set of URLS to fetch
        #
        self.urls       = [ ]

        #
        # How many concurrent requests we can fire off at any one time in
        # parallel. Basically we make URL requests in batches of max_active
        # so a list of 50 URLS would be fetched in two rounds
        #
        self.max_active = 25

    #
    # Interface for adding url's to the queue we want to fetch when peform
    # is called
    #
    def _add_url (self, what_) :
        self.urls.append (
            HNewsResult ('%s/%s/%s.json' % (self.uri, self.version, what_)))

        #
        # return a convieneince refference to the caller, can be ignored if
        # theyr'e just going to iterate over a collection of restults later
        #
        return self.urls[-1]

    #
    # Synthesise the top 500 stories API url and add it to our list
    #
    def topstories (self) : return self._add_url ('topstories')

    #
    # Sytheises a UTL to fetch info on object 'item' from the API
    #
    def item (self, item) : return self._add_url ('item/%s' % item)

    def __del__ (self) :
        self.mc.close()

    def perform (self) :
        #
        # Just track which handles map to which elements in out URL
        # list as we add them to the mcurl object
        #
        handles = { }
        idx     = 0
        offset  = 0

        while idx + offset < len (self.urls) :
            while idx < self.max_active and idx + offset < len (self.urls) :
                self.urls[offset + idx].activate()
                self.mc.add_handle (self.urls[offset + idx].curl)

                #
                # Keep a mapping between our meta result object and 
                # the curl object we put into the multicurl obj
                # so we can deal with errors and assign them to
                # the proper objects
                #
                handles[self.urls[offset + idx].curl] = idx + offset

                idx+=1

            while True :
                ret, num_handles = self.mc.perform()
                if ret != pycurl.E_CALL_MULTI_PERFORM : break

            #
            # With the state machine kicked off wait for all requests to
            # finish
            #
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

            #
            # unlike g above which is just the curl object b is a tuble of
            # { curl object, erro code, error desc }
            #
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
    ap = argparse.ArgumentParser (description = "Hacker News downloader")

    #
    # Custom value validity checker for the number of posts argument
    # since we explicitly want that to be between 1 and 100
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
    # and don't want i tp actually print out the sotry contents
    #
    ap.add_argument (
        '--silent', '-s',
        action = 'store_true',
        help   = "Supress all output")

    return ap.parse_args()

#-------------------------------------------------------------------------------

#
# Takes a list of id's and should return a list of records matching
# each id in that list.
#
# item_ is a tuble where
# item_[0] is the offset rank for the start of the list
# item_[1] is a list of hackerrank story id's
#
# args_ is the command line parameter object
#
def get_items (items_, args_) :
    rtn = []
    mhn = HNews();

    #
    # load the list of items into our multi curl obj
    #
    for item_key in items_[1] : mhn.item (item_key)

    mhn.perform()

    #
    # loop count over the list to determine the ranking. We're assuming
    # that as we were given the top N stories then that list is ordered
    # with the top story being element zero. As we can be given a portion
    # of that list to operate on this will be offset by our offset as 
    # given to the func in items_[0]
    #
    offset = 0;
    for data in mhn :
        offset += 1
        item  = { }

        try :
            story = data.json()
        except ValueError as e:
            #
            # If we failed to read a url create a fake story that indicates
            # this and continue since I think it's better to out put some results
            # rather than exit and produce nothign
            #
            story = {
                'title' : str (e),
                'url'   : 'error',
                'score' : '0',
                'by'    : 'None',
                'kids'  : [ ]
            }
        except Exception as e:
            print "ERROR: %s" % str (e);
            sys.exit (1)

        #
        # Requiremets were these two field should be limitied to 256 
        # characters
        #
        item['title']  = story['title'][:256].encode('ascii','replace')
        item['author'] = story['by'][:256]
        item['rank']   = items_[0] + offset

        try :
            item['points'] = story['score']
        except KeyError :
            item['points'] = 0

        #
        # It's unclear what we're supposed to do if a URL isn't valid
        # given they'e coming from a 3rd party so I'm just going to
        # replace it with some text that makes it clear that's what
        # we've done
        #
        try :
            item['uri'] = story['url']
            if not validators.url (item['uri']) :
                item['uri'] = "<INVALID>"
        except KeyError :
            item['uri'] = ""

        #
        # So, either we can assume all kid elements ofa story are comments
        # or we can't. If we can't then we have to fetch eash one in turn
        # and test it's type, which is going to take a lot logner than
        # simply assumign they are. I'm defaulting it to assuming they all
        # are as that's much faster but a command line switch can be used
        # to force us to check each in turn
        #
        try :
            if args_.all_kids_are_not_comments :
                kids = HNews()
                for kid in story['kids'] : kids.item (kid)
                kids.perform()
                item['comments'] = [ 1 if x.rtype() == "comment" else 0 \
                    for x in kids ].count (1)
            else :
                item['comments'] = len (story['kids'])

        #
        # if there aren't any kids then we've got zero comments regardless
        # of wht assumptions we're making
        #
        except KeyError as e :
            item['comments'] = 0

        rtn.append (item)

    return rtn

#-------------------------------------------------------------------------------

def item_list_to_results (args_, top_results_) :
    if len (top_results_) != args_.posts :
        raise ValueError ("result list size must match post count")
    #
    # how big is each sub list going to be. we could be using sublists
    # to partition off the calls we make
    #
    lsize = args_.nlists if args_.posts < args_.nlists else \
        args_.posts / args_.nlists

    #
    # split the list into a set of sublists and then iterate over them
    # to pull down the results. Default to one as the library should be able to
    # handle pulling down lots of resuls in parallel but the VM I was testing
    # on struggles (because it was tiny) and this became a good way of letting
    # it actually complete without OOMing   
    #
    sublists   = [(i, top_results_[i:i + lsize]) for i in xrange (0, len (top_results_), lsize)]
    results    = []

    for l in sublists : results.extend (get_items (l, args_))

    return results

#-------------------------------------------------------------------------------

def main() :
    args  = parseargs()
    hnews = HNews()

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
        print "ERROR: %s" % result.errors()
        sys.exit (1)

    try :
        top = result.json()[:args.posts]
    except Exception as e :
        print "ERROR: %s" % str (e)
        sys.exit (1)

    results = item_list_to_results (args, top)

    if not args.silent :
        print json.dumps (results, indent = 3)

#-------------------------------------------------------------------------------

if __name__ == "__main__" :
    main()

#-------------------------------------------------------------------------------

