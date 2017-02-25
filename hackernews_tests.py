#!/usr/bin/python

#-------------------------------------------------------------------------------

import unittest

from hackernews import HNews, HNewsResult

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
        # API docs recon yo usohuld get up to 500 so...
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

        self.assertEqual (None, hn.urls[2].json())
        self.assertEqual ("Error", hn.urls[2].rtype())

#-------------------------------------------------------------------------------

if __name__ == "__main__" :
    suite = unittest.TestLoader().loadTestsFromTestCase (tests)
    unittest.TextTestRunner (verbosity=1).run (suite)

#-------------------------------------------------------------------------------

