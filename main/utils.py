import time
import datetime
import pytz

import numpy


def unitConv(nb, u1, u2):
    powDict = {
        "Y" : 24,
        "Z" : 21,
        "E" : 18,
        "P" : 15,
        "T" : 12,
        "G" : 9,
        "M" : 6,
        "k" : 3,
        "h" : 2,
        "da" : 1,
        "" : 0,
        "d" : -1,
        "c" : -2,
        "m" : -3,
        "µ" : -6, "u" : -6,
        "n" : -9,
        "p" : -12,
        "f" : -15,
        "a" : -18,
        "z" : -21,
        "y" : -24,
    }
    return nb * 10**(powDict[u1[:-1]] - powDict[u2[:-1]])


# function decorator
# print time taken by a function
def time_func(func):
    def wrapper(*args, **kw):
        t1 = time.time()
        res = func(*args, **kw)
        t2 = time.time()
        print("[time] : ", func.__name__, " : ", t2 - t1)
        return res 
    return wrapper


# convert date form timezone tz1 to tz2
def convertTimezone(date, tz1, tz2):
    return pytz.timezone(tz1).localize(date).astimezone(pytz.timezone(tz2))


def isnotnan(a):
    if isinstance(a, float) and numpy.isnan(a):
        return (False)
    else:
        return (True)


def date_inc(date, time):
    ret = datetime.datetime.combine(date.date(), time.time())
    if (ret < date and date - ret > datetime.timedelta(hours=1)):
        ret += datetime.timedelta(days=1)
    return (ret)


