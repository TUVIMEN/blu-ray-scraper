#!/usr/bin/env python

import os
import sys
import tempfile
import json
from pathlib import Path

from biggusdictus import isdict, uint, Or, Isodate, Https, Uri, Url

bluray = __import__("blu-ray")


def intemp(func):
    prev = os.getcwd()

    with tempfile.TemporaryDirectory() as dir:
        os.chdir(dir)

        func()

    os.chdir(prev)


def thing_verify(data):
    isdict(
        data,
        ("parent_link", Or, Https, (str, 0, 0)),
        ("parent_id", uint),
        ("title", str),
        ("country", str),
        ("subtitle", str),
        ("distributor", str),
        ("year1", uint),
        ("year2", uint),
        ("runtime", uint),
        ("release", Or, Isodate, str),
        ("seasons", uint),
        ("rated", str),
        ("cover", Or, Https, (str, 0, 0)),
        (
            "rating",
            dict,
            ("movie", float, 0, 5.0),
            ("video", float, 0, 5.0),
            (None, "video2k", float, 0, 5.0),
            (None, "video4k", float, 0, 5.0),
            ("audio", float, 0, 5.0),
            ("extras", float, 0, 5.0),
            ("overall", float, 0, 5.0),
        ),
        ("list-price", str),
        ("price", str),
        ("sources", list, Https),
        (
            "info",
            dict,
            ("video", list, str),
            ("discs", list, str),
            ("digital", list, str),
            ("packaging", list, str),
            ("playback", list, str),
            ("audio", list, str),
            ("subtitles", list, str),
            (None, "links", list, (Or, Url, (str, 0, 1))),
        ),
        ("url", Https),
        ("id", uint),
        (None, "packaging", list, (dict, ("link", Https), ("date", Isodate))),
        (
            None,
            "region_coding",
            list,
            (
                dict,
                ("avatar", Or, Https, (str, 0, 0)),
                ("user", str, 1),
                ("user_link", Https),
                ("date", Isodate),
                ("rating", uint),
                ("regions", str),
            ),
            0,
            7,
        ),
    )


def main_verify(data):
    isdict(
        data,
        ("cover", Or, Https, (str, 0, 0)),
        ("title", str, 1),
        ("year", uint),
        ("screenshots", list, Https),
        ("watched", uint),
        ("watchlist", uint),
        ("notinterested", uint),
        (
            "appeals",
            list,
            (dict, ("name", str, 1), ("amount", uint)),
        ),
        ("plottags", list, (str, 1)),
        ("studios", list, (dict, ("name", str, 1), ("link", Https))),
        ("distributors", list, (dict, ("name", str, 1), ("link", Https))),
        ("releasedates", list, (dict, ("name", str, 1), ("date", Isodate))),
        (
            "boxoffice",
            list,
            (dict, ("name", str, 1), ("amount", str)),
        ),
        ("country", str),
        ("language", str),
        ("runtime", uint),
        ("rated", str),
        ("technical", str),
        ("fans", uint),
        (
            "collections",
            dict,
            ("blu-ray", uint),
            ("dvd", uint),
            ("digital", uint),
            ("itunes", uint),
            ("prime", uint),
        ),
        ("score", float),
        ("liked", uint),
        (
            "sources",
            list,
            (dict, ("name", str, 1), ("link", Url)),
        ),
        ("id", uint),
        ("url", Https),
        (
            "releases",
            list,
            (
                dict,
                ("name", str),
                ("link", Https),
                ("country", str, 1),
                ("distributor", str),
                ("price", str),
            ),
        ),
    )


def item_test(url):
    def t():
        blur = bluray.BluRay(".", wait=2)
        obj = blur.guess(url)
        assert obj is not None
        p_id = obj.get_id(url)
        assert p_id is not None

        obj.save(url)

        path = obj.workdir / str(p_id)
        data = path.read_text()

        js = json.loads(data)

        if isinstance(obj, bluray.BluRay_Movie):
            main_verify(js)
        else:
            thing_verify(js)

    intemp(t)


def test_posts_1():
    item_test(
        "https://www.blu-ray.com/movies/Tarantino-XX-8-Film-Collection-Blu-ray/55782/#Packaging"
    )


def test_posts_2():
    item_test(
        "https://www.blu-ray.com/movies/Pulp-Fiction-4K-Blu-ray/252780/#Packaging"
    )


def test_posts_3():
    item_test("https://www.blu-ray.com/movies/Pulp-Fiction-Blu-ray/274484/#Packaging")


def test_posts_4():
    item_test(
        "https://www.blu-ray.com/digital/Tarantino-6-Film-Collection-Digital/26486/?retailerid=20#"
    )


def test_posts_5():
    item_test("https://www.blu-ray.com/itunes/Pulp-Fiction-iTunes/1341/")


def test_posts_6():
    item_test(
        "https://www.blu-ray.com/digital/Quentin-Tarantino-5-Movie-Collection-Digital/49213/#"
    )


def test_posts_7():
    item_test("https://www.blu-ray.com/dvd/Pulp-Fiction-DVD/9336/#RegionCoding")


def test_posts_8():
    item_test(
        "https://www.blu-ray.com/movies/Pulp-Fiction-4K-Blu-ray/252780/#RegionCoding"
    )


def test_posts_9():
    item_test(
        "https://www.blu-ray.com/movies/Dreamworks-42-Movie-Collection-Blu-ray/308868/"
    )


def test_posts_10():
    item_test("https://www.blu-ray.com/dvd/Coleccion-Clint-Eastwood-DVD/272457/")


def test_posts_11():
    item_test("https://www.blu-ray.com/itunes/X-Men-11-Movie-Collection-iTunes/186410/")


def test_posts_12():
    item_test(
        "https://www.blu-ray.com/Harry-Potter-and-the-Deathly-Hallows-Part-2/31864/"
    )


def test_posts_13():
    item_test(
        "https://www.blu-ray.com/digital/Columbia-Pictures-100th-Anniversary-Collection-Digital/64883/"
    )


def test_posts_14():
    item_test(
        "https://www.blu-ray.com/uv/Godzilla-vs-Megaguirus-The-G-Annihilation-Strategy-Digital/5402/"
    )


def test_posts_15():
    item_test("https://www.blu-ray.com/prime/Cheaper-by-the-Dozen-2-Prime-Video/11805/")


def test_posts_16():
    item_test(
        "https://www.blu-ray.com/ma/The-Mortal-Instruments-City-of-Bones-Movies-Anywhere/1208/"
    )
