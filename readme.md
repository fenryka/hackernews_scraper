# What is this for

It was an interview question for a job interview I didn't get. Apparently it's over complciated (unfair) and not that well tested (fair, but there is a limit to what I'm going to do in an evening to join your company). I wouldn't use anything here :)

# Dependencies

* Python 2.7

## Python Dependencies

intstall with pip

* pycurl
* validators

## Explanation

I chose pycurl to handle the http api requests as that's what it does

Validators I found after googling to solve the problem of actually validating
a URL without pulling in a large amount of dependencies on something like django

# Running

`./hackernews.py`

use the -h flag to see options and their explanation

# Testing

Tests use the python unittest library

`./hackernews_tests.py`

To run a specific test (for example)

`python -m unittest hackernews_tests.tests.test_errors`

