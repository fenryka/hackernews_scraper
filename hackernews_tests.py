#!/usr/bin/python

#-------------------------------------------------------------------------------

import unittest

from hackernews import HNews, HNewsResult, item_list_to_results

#-------------------------------------------------------------------------------

class fake_args (object) :
    nlists                    = 1
    posts                     = 1
    all_kids_are_not_comments = False

#-------------------------------------------------------------------------------

class tests (unittest.TestCase) :
    def test_url (self) :
        hn  = HNews()
        res = hn.topstories()

        self.assertEqual (res.url,
            'https://hacker-news.firebaseio.com/v0/topstories.json')

        res = hn.item (1)

        self.assertEqual (res.url,
            'https://hacker-news.firebaseio.com/v0/item/1.json')


    def test_perform_item (self) :
        hn  = HNews()
        res = hn.item (1)
        hn.perform()
        item = res.json()

        self.assertTrue ("by" in item)
        self.assertTrue ("descendants" in item)
        self.assertTrue ("id" in item)
        self.assertTrue ("kids" in item)
        self.assertTrue ("score" in item)
        self.assertTrue ("time" in item)
        self.assertTrue ("title" in item)
        self.assertTrue ("type" in item)
        self.assertTrue ("url" in item)

        self.assertEqual (item["by"], "pg")
        self.assertEqual (item["descendants"], 15)
        self.assertEqual (item["id"], 1)
        self.assertEqual (len (item["kids"]), 5)
        self.assertEqual (item["score"], 61)
        self.assertEqual (item["time"], 1160418111)
        self.assertEqual (item["title"], "Y Combinator")
        self.assertEqual (item["type"], "story")
        self.assertEqual (item["url"], "http://ycombinator.com")

    def test_top (self) :
        hn  = HNews()
        res = hn.topstories()
        hn.perform()
        item = res.json()
        self.assertTrue (isinstance (item, list))

        #
        # API docs recon you sohuld get up to 500 so...
        #
        self.assertTrue (len (item) <= 500)


    def test_multi_perform (self) :
        hn  = HNews()

        for x in xrange (1, 6, 1) : hn.item (x)

        self.assertEqual (5, len (hn.urls))

        #
        # Prior to fetchm, objects won't have a buffer
        #
        for x in xrange (0, 5, 1) :
            with self.assertRaises (AttributeError) :
                b = hn.urls[x].buf

        hn.perform()

        self.assertEqual (5, len (hn.urls))

        for x in xrange (0, 5, 1) :
            self.assertFalse (hn.urls[x].errors())
            self.assertEqual (x+1, hn.urls[x].json()["id"])

    def test_multi_perform_2 (self) :
        hn  = HNews()

        #
        # force multiple iterations over the read loop
        #
        hn.max_active = 2

        for x in xrange (1, 6, 1) : hn.item (x)

        self.assertEqual (5, len (hn.urls))
        for x in xrange (0, 5, 1) :
            with self.assertRaises (AttributeError) :
                b = hn.urls[x].buf

        hn.perform()

        self.assertEqual (5, len (hn.urls))

        for x in xrange (0, 5, 1) :
            self.assertEqual (x+1, hn.urls[x].json()["id"])

    def test_multi_perform_3 (self) :
        hn  = HNews()

        #
        # force multiple iterations over the read loop
        #
        hn.max_active = 2

        for x in xrange (1, 6, 1) : hn.item (x)

        self.assertEqual (5, len (hn.urls))
        for x in xrange (0, 5, 1) :
            with self.assertRaises (AttributeError) :
                b = hn.urls[x].buf

        hn.perform()

        #
        # Pretend we failed one of the reads
        #
        hn.urls[2].buf = None

        self.assertEqual (5, len (hn.urls))

        with self.assertRaises (Exception) :
            json = hn.urls[2].json()

        self.assertEqual (None, hn.urls[2].rtype())

    def test_errors (self) :
        hnr = HNewsResult ("https://test.com/url")

        self.assertFalse (hnr.errors())

        hnr.error = "It went bad"

        self.assertTrue (hnr.errors())
        self.assertEqual (hnr.errors(), "It went bad")

    def test_item_fetch (self) :
        #
        # build a fake item list
        #
        top = [x for x in xrange (1, 6, 1)]

        #
        # and a fake args list
        #
        args = fake_args()
        args.posts = 5

        results = item_list_to_results (args, top)
        self.assertEqual (5, len (results))

        #
        # Subdividing the lists should still render the same result
        #
        args.nlists = 3
        results = item_list_to_results (args, top)
        self.assertEqual (5, len (results))

        #
        # without changing the list length whouls throw
        #
        args.nlists = 1
        args.posts  = 1
        with self.assertRaises (ValueError) :
            results = item_list_to_results (args, top)

        #
        # shrinking the list to match should again work
        #
        top = top[:1]
        results = item_list_to_results (args, top)
        self.assertEqual (1, len (results))


    def test_zero_fetch (self) :
        top        = []
        args       = fake_args()
        args.posts = 0

        results = item_list_to_results (args, top)
        self.assertEqual (0, len (results))


    def test_error_result (self) :
        hn  = HNews()
        res = hn.item (1)
        hn.perform()

        res.error = "fake an error"
        res.buf = None

        with self.assertRaises (ValueError) :
            item = res.json()

        #
        # build a fake item list
        #
        top = [x for x in xrange (1, 6, 1)]

        #
        # mark the middle element wit ha garbage id
        #
        top[2]     = "helloo"
        args       = fake_args()
        args.posts = 5

        results    = item_list_to_results (args, top)
        self.assertEqual (5, len (results))


        self.assertEqual ('<INVALID>', results[2]['uri'])
        self.assertEqual ('Url https://hacker-news.firebaseio.com/v0/item/helloo.json '
            'returned no result', results[2]['title'])



#-------------------------------------------------------------------------------

if __name__ == "__main__" :
    suite = unittest.TestLoader().loadTestsFromTestCase (tests)
    unittest.TextTestRunner (verbosity=1).run (suite)

#-------------------------------------------------------------------------------

