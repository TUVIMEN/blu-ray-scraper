#!/usr/bin/env python
# by Dominik Stanisław Suchora <suchora.dominik7@gmail.com>
# License: GNU GPLv3

import os
import sys
import random
import time
import json
import re
from datetime import datetime
from typing import Tuple
from pathlib import Path
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import itertools
import gzip

from reliq import reliq
import requests
from urllib.parse import urljoin


def urljoin_r(ref, url):
    if url is None or len(url) == 0:
        return ""
    return urljoin(ref, url)


def conv_curl_header_to_requests(src: str):
    r = re.search(r"^\s*([A-Za-z0-9_-]+)\s*:(.*)$", src)
    if r is None:
        return None
    return {r[1]: r[2].strip()}


def conv_curl_cookie_to_requests(src: str):
    r = re.search(r"^\s*([A-Za-z0-9_-]+)\s*=(.*)$", src)
    if r is None:
        return None
    return {r[1]: r[2].strip()}


def valid_header(src: str) -> dict:
    r = conv_curl_header_to_requests(src)
    if r is None:
        raise argparse.ArgumentTypeError('Invalid header "{}"'.format(src))
    return r


def valid_cookie(src: str) -> dict:
    r = conv_curl_cookie_to_requests(src)
    if r is None:
        raise argparse.ArgumentTypeError('Invalid cookie "{}"'.format(src))
    return r


def valid_directory(directory: str):
    if os.path.isdir(directory):
        return directory
    else:
        raise argparse.ArgumentTypeError('"{}" is not a directory'.format(directory))


def valid_file(directory: str):
    if os.path.isfile(directory):
        return directory
    else:
        raise argparse.ArgumentTypeError('"{}" is not a file'.format(directory))


class RequestError(Exception):
    pass


def bool_get(obj: dict, name: str, otherwise: bool = False) -> bool:
    x = obj.get(name)
    if x is None:
        return otherwise
    return bool(x)


def int_get(obj: dict, name: str, otherwise: int = 0) -> int:
    x = obj.get(name)
    if x is None:
        return otherwise
    return int(x)


def float_get(obj: dict, name: str, otherwise: float = 0) -> float:
    x = obj.get(name)
    if x is None:
        return otherwise
    return float(x)


def dict_get(obj: dict, name: str) -> dict:
    x = obj.get(name)
    if not isinstance(x, dict):
        return {}
    return x


class Session(requests.Session):
    def __init__(self, **kwargs):
        super().__init__()

        self.proxies.update(dict_get(kwargs, "proxies"))
        self.headers.update(dict_get(kwargs, "headers"))
        self.cookies.update(dict_get(kwargs, "cookies"))

        self.timeout = int_get(kwargs, "timeout", 30)
        self.verify = bool_get(kwargs, "verify", True)
        self.allow_redirects = bool_get(kwargs, "allow_redirects", False)

        t = kwargs.get("user_agent")
        self.user_agent = (
            t
            if t is not None
            else "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0"
        )

        self.headers.update(
            {"User-Agent": self.user_agent, "Referer": "https://hdporncomics.com/"}
        )

        self.retries = int_get(kwargs, "retries", 3)
        self.retry_wait = float_get(kwargs, "retry_wait", 60)
        self.wait = float_get(kwargs, "wait")
        self.wait_random = int_get(kwargs, "wait_random")

        self.logger = kwargs.get("logger")

    @staticmethod
    def base(rq: reliq, url: str) -> str:
        ref = url
        u = rq.search(r'[0] head; [0] base href=>[1:] | "%(href)v"')
        if u != "":
            u = urljoin(url, u)
            if u != "":
                ref = u
        return ref

    def r_req_try(self, url: str, method: str, retry: bool = False, **kwargs):
        if not retry:
            if self.wait != 0:
                time.sleep(self.wait)
            if self.wait_random != 0:
                time.sleep(random.randint(0, self.wait_random + 1) / 1000)

        if self.logger is not None:
            print(url, file=self.logger)

        if method == "get":
            return self.get(url, timeout=self.timeout, **kwargs)
        elif method == "post":
            return self.post(url, timeout=self.timeout, **kwargs)
        elif method == "delete":
            return self.delete(url, timeout=self.timeout, **kwargs)
        elif method == "put":
            return self.put(url, timeout=self.timeout, **kwargs)

    def r_req(self, url: str, method: str = "get", **kwargs):
        tries = self.retries
        retry_wait = self.retry_wait

        instant_end_code = [400, 401, 402, 403, 404, 410, 412, 414, 421, 505]

        i = 0
        while True:
            try:
                resp = self.r_req_try(url, method, retry=(i != 0), **kwargs)
            except (
                requests.ConnectTimeout,
                requests.ConnectionError,
                requests.ReadTimeout,
                requests.exceptions.ChunkedEncodingError,
                RequestError,
            ):
                resp = None

            if resp is None or not (
                resp.status_code >= 200 and resp.status_code <= 299
            ):
                if resp is not None and resp.status_code in instant_end_code:
                    raise RequestError(
                        "failed completely {} {}".format(resp.status_code, url)
                    )
                if i >= tries:
                    raise RequestError(
                        "failed {} {}".format(
                            "connection" if resp is None else resp.status_code, url
                        )
                    )
                i += 1
                if retry_wait != 0:
                    time.sleep(retry_wait)
            else:
                return resp

    def get_html(
        self, url: str, return_cookies: bool = False, **kwargs
    ) -> Tuple[reliq, str] | Tuple[reliq, str, dict]:
        resp = self.r_req(url, **kwargs)

        rq = reliq(resp.text)
        ref = self.base(rq, url)

        if return_cookies:
            return (rq, ref, resp.cookies.get_dict())
        return (rq, ref)

    def get_json(self, url: str, **kwargs) -> dict:
        resp = self.r_req(url, **kwargs)
        return resp.json()

    def post_json(self, url: str, **kwargs) -> dict:
        resp = self.r_req(url, method="post", **kwargs)
        return resp.json()

    def delete_json(self, url: str, **kwargs) -> dict:
        resp = self.r_req(url, method="delete", **kwargs)
        return resp.json()

    def put_json(self, url: str, **kwargs) -> dict:
        resp = self.r_req(url, method="put", **kwargs)
        return resp.json()


def createdir(path):
    try:
        os.mkdir(path)
    except FileExistsError:
        pass


class BluRayItem:
    def __init__(self, path, session, alllinks):
        self.ses = session
        self.alllinks = alllinks

        self.workdir = Path(os.path.realpath(path))
        createdir(self.workdir)
        self.links_path = self.workdir / "links"
        # self.raw_path = self.workdir / "raw"
        # createdir(self.raw_path)

        self.links = self.links_load()
        if self.alllinks is not None:
            self.alllinks.update(self.links)

        self.links_save_counter = 0
        self.links_save_boundary = 800

        self.urlvalid_pattern = r"^https?://www\.blu-ray\.com(\?|/|$)"

    def urlvalid(self, url):
        return re.match(self.urlvalid_pattern, url) is not None

    def links_add(self, link, boundary=True):
        if self.alllinks is not None:
            self.alllinks.add(link)
        self.links.add(link)

        if boundary:
            self.links_save_counter += 1
            if self.links_save_counter >= self.links_save_boundary:
                self.links_save_counter = 0
                self.links_save()

    def save_set_to_file(self, sett, fname, conv=str):
        with open(fname, "w") as f:
            for i in sett:
                f.write(conv(i))
                f.write("\n")

    def links_save(self):
        self.save_set_to_file(self.links, self.links_path)

    def save_state(self):
        self.links_save()

    def load_set_from_file(self, fname, conv=str):
        ret = set()
        try:
            with open(fname, "r") as f:
                for i in f:
                    ret.add(conv(i.strip()))
        except FileNotFoundError:
            pass
        return ret

    def links_load(self):
        return self.load_set_from_file(self.links_path)

    def get_id(self, url):
        # for main components returns int, otherwise string
        pass

    def process(self, rq, ref, url, p_id):
        pass

    # def raws_path(self, p_id):
    # return self.raw_path / str(p_id)

    # def raw_exists(self, p_id):
    # return self.file_exists(self.raws_path(p_id), minsize=100)

    # def raw_read(self, p_id):
    # path = self.raws_path(p_id)

    # with open(path, "r") as f:
    # data = f.read()

    # data = data.partition("\n")[2]
    # r = data.partition("\n")
    # ref = r[0]
    # rq = reliq(r[2])

    # return (rq, ref)

    # def raw_save(self, rq, ref, url, p_id):
    # path = self.raws_path(p_id)
    # with open(path, "w") as f:
    # f.write(url)
    # f.write("\n")
    # f.write(ref)
    # f.write("\n")
    # f.write(rq.get_data())

    def add(self, url, p_id):
        self.links_add(url)
        rq, ref = self.ses.get_html(url)
        # self.raw_save(rq, ref, url, p_id)
        return (rq, ref)

    def read(self, p_id):
        path = self.post_path(p_id)
        with open(path, "r") as f:
            return json.load(f)

    def get(self, url, p_id=0, force=False):
        if p_id == 0:
            p_id = self.get_id(url)

        if not force and self.post_exists(p_id):
            return self.read(p_id)

        # if not force and self.raw_exists(p_id):
        # rq, ref = self.raw_read(p_id)
        # else:
        rq, ref = self.add(url, p_id)

        return self.process(rq, ref, url, p_id)

    def file_exists(self, path, minsize=2):
        if not os.path.exists(path):
            return False
        if not os.path.isfile(path):
            return True
        return os.path.getsize(path) >= minsize

    def post_path(self, p_id):
        return self.workdir / str(p_id)

    def post_exists(self, p_id):
        path = self.post_path(p_id)
        return self.file_exists(path, minsize=8)

    def save(self, url, force=False):
        p_id = self.get_id(url)
        if not force and self.post_exists(p_id):
            return False

        r = self.get(url, p_id, force=force)
        path = self.post_path(p_id)
        with open(path, "w") as f:
            json.dump(r, f, separators=(",", ":"))
            f.write("\n")

        return True

    @staticmethod
    def conv_date(date, formats):
        date = date.strip()
        if len(date) == 0:
            return ""
        date = re.sub(r" +", " ", date)

        return datetime.strptime(date, formats).isoformat()


class BluRay_Thing(BluRayItem):
    def __init__(self, path, session, alllinks, name):
        super().__init__(path, session, alllinks)

        self.name = name

        self.urlvalid_pattern = (
            r"^https?://www\.blu-ray\.com/"
            + self.name
            + r"/[a-zA-Z0-9_-]+/\d+(/(#.*)?)?$"
        )

    def get_id(self, url):
        r = re.match(
            r"^https?://www\.blu-ray\.com/"
            + self.name
            + r"/[a-zA-Z0-9_-]+/(\d+)(/(#.*)?)?$",
            url,
        )
        if r is None:
            return 0
        return int(r[1])

    @staticmethod
    def trim_info(r):
        r = r.translate(str.maketrans("\t\n", "  ", ""))
        r = r.replace("<br>", "\n")
        return list(
            filter(
                lambda x: x != "",
                map(lambda y: y.strip(), reliq(r).text.strip().split("\n")),
            )
        )

    def get_packaging(self, p_id):
        if self.name != "dvd" and self.name != "movies":
            return []

        url = "https://www.blu-ray.com/{}/movies.php?id={}&action=showpackaging".format(
            self.name, p_id
        )

        rq, ref = self.ses.get_html(url)
        r = rq.json(
            r"""
            .c h3 i@f>"Member uploaded packaging images"; [:3] * ssub@; [0] div self@; a; {
                .link @ | "%(href)v",
                .date @ | "%(title)v" sed "s/^Uploaded //"
            } |
        """
        )["c"]

        for i in r:
            i["link"] = urljoin_r(ref, i["link"])
            i["date"] = self.conv_date(i["date"], "%H:%M:%S %B %d, %Y")
        return r

    def get_region_coding(self, p_id):
        if self.name != "dvd" and self.name != "movies":
            return []

        url = "https://www.blu-ray.com/{}/movies.php?id={}&action=showregioncoding&filter=rating&page=".format(
            self.name, p_id
        )
        rq, ref = self.ses.get_html(url)
        r = rq.json(
            r"""
            .c table l@[0] style; {
                .avatar a href=a>/profile.php?u=; [0] img | "%(src)v",
                [0] h5; {
                    .user @ | "%Di" trim,
                    a parent@; {
                        .user_link @ | "%(href)v",
                        .date [0] * ssub@; font style="color: #aaa" | "%Di" trim,
                        .rating.u [0] img #b>showrating fssub@ | "%(title)v"
                    }
                },
                .regions text@ [1] "Region " | "%DA" trim
            } |
        """
        )["c"]
        for i in r:
            i["avatar"] = urljoin_r(ref, i["avatar"])
            i["user_link"] = urljoin_r(ref, i["user_link"])
            i["date"] = self.conv_date(i["date"], "%b %d, %Y")
        return r

    def get_redirection(self, url):
        time.sleep(0.8)
        resp = self.ses.get(url, allow_redirects=False)
        if resp.status_code != 301:
            return url
        loc = resp.headers.get("Location")
        if loc is None:
            return url
        return urljoin_r(url, loc)

    def clear_redirections(self, arr):
        ret = set()
        for i in set(arr):
            if i.find("/link/click.php?") == -1:
                ret.add(i)
                continue
            print(i)
            ret.add(self.get_redirection(i))
        return list(ret)

    def process(self, rq, ref, url, p_id):
        r = rq.json(
            r"""
            [0] td width=728; {
                [0] a data-globalparentid; {
                    .parent_link @ | "%(href)v",
                    .parent_id.u @ | "%(data-globalparentid)v",
                },
                .title h1 | "%Dt" trim,
                .country [0] img alt width | "%(alt)v",
                .subtitle [0] span .subheadingtitle | "%Dt" trim,
                [0] span .subheading .grey c@[2:]; {
                    .distributor [0] a href=a>?studioid= child@ | "%Dt" trim,
                     a href=a>movies.php?year= child@; {
                        .year1.u [0] @ | "%i",
                        .year2.u [1] @ | "%i",
                     },
                    .runtime.u span #runtime | "%i",
                    .release [0] a href=a>releasedates.php?year= child@ | "%i",
                    .seasons.u text@ " Seasons |" child@ / sed "s/.* [0-9]+ Seasons \|.*/\1/" "E",
                    .rated text@ "| Rated " child@ / sed "s/.*\| Rated ([^|]+) \|.*/\1/" "E" trim
                },
                .cover img #frontimage_overlay | "%(src)v",
                .rating div #bluray_rating; {
                    .movie.n td width=38% i@f>Movie; [1] * ssub@; td width=16% | "%i",
                    .video.n td width=38% i@f>Video; [1] * ssub@; td width=16% | "%i",
                    .video2k.n td width=38% i@f>"Video 2K"; [1] * ssub@; td width=16% | "%i",
                    .video4k.n td width=38% i@f>"Video 4K"; [1] * ssub@; td width=16% | "%i",
                    .audio.n td width=38% i@f>Audio; [1] * ssub@; td width=16% | "%i",
                    .extras.n td width=38% i@f>Extras; [1] * ssub@; td width=16% | "%i",
                    .overall.n td width=38% i@f>Overall; [1] * ssub@; td width=16% | "%i",
                },
                [0] td width=266px; {
                    .list-price [0] strike | "%Dt" trim,
                    .price {
                        [0] b i@"b>Now Only" | "%Dt" trim sed "s/^Now Only //" ||
                        text@ Price: / sed "s/^.*Price: //; s/,.*//" ||
                        a href=a>/link/click.php?p=; [0] b | "%Dt" ||
                        [0] a .pricestyle | "%Dt"
                    } / trim,
                    .sources.a a href=b>"https://" -id ( -href=a>blu-ray.com/ )( href=a>"/link/click.php?" ) | "%(href)v\n",
                },
                .info [0] td width=228px; {
                    .video [0] span .subheading i@f>Video; ( tag@ * )( text@ * ) ssub@ / sed "/^<span class=\"subheading\">/q; p" "n",
                    .discs [0] span .subheading i@f>Discs; ( tag@ * )( text@ * ) ssub@ / sed "/^<span class=\"subheading\">/q; p" "n",
                    .digital [0] span .subheading i@f>Digital; ( tag@ * )( text@ * ) ssub@ / sed "/^<span class=\"subheading\">/q; p" "n",
                    .packaging [0] span .subheading i@f>Packaging; ( tag@ * )( text@ * ) ssub@ / sed "/^<span class=\"subheading\">/q; p" "n",
                    .playback [0] span .subheading i@f>Playback; ( tag@ * )( text@ * ) ssub@ / sed "/^<span class=\"subheading\">/q; s/ *$//; p" "n",
                    .audio.a {
                        div #longaudio; {
                            b child@; {
                                a child@ | "%Dt: ",
                                [1] * ssub@; div self@ | "%Di" sed "s/<br>/\t/g" trim
                            } | echo "" "\n" ||
                            text@ * -f>")" child@ | "%A\n" / sed "s/&nbsp;/ /g" decode sed "s/ ($//; s/.(less)$//; /^$/d"
                        } || div .shortaudio; text@ * child@ | "%DA\n",
                    },
                    .subtitles.a {
                        div #longsubs; {
                            b child@; {
                                a child@ | "%Dt: ",
                                [1] * ssub@; div self@ | "%Di" sed "s/<br>/\t/g" trim
                            } | echo "" "\n" ||
                            text@ * -f>")" child@ | "%A\n" / sed "s/&nbsp;/ /g" decode sed "s/ ($//; s/.(less)$//; /^$/d"
                        } || div .shortsubs; text@ * child@ | "%DA\n",
                    },
                    .links.a h3 i@f>Links; [:1] * ssub@; table self@; a | "%(href)v\n"
                },
            },
        """
        )

        r["url"] = url
        r["id"] = p_id
        r["packaging"] = self.get_packaging(p_id)
        r["region_coding"] = self.get_region_coding(p_id)

        info = r["info"]
        info["video"] = self.trim_info(info["video"])
        info["discs"] = self.trim_info(info["discs"])
        info["digital"] = self.trim_info(info["digital"])
        info["packaging"] = self.trim_info(info["packaging"])
        info["playback"] = self.trim_info(info["playback"])
        info["links"] = self.clear_redirections(info["links"])

        r["release"] = self.conv_date(r["release"], "%b %d, %Y")
        r["parent_link"] = urljoin_r(ref, r["parent_link"])
        r["cover"] = urljoin_r(ref, r["cover"])
        r["sources"] = self.clear_redirections(r["sources"])
        return r


class BluRay_Movie(BluRayItem):
    def __init__(self, path, session, alllinks):
        super().__init__(path, session, alllinks)

        self.urlvalid_pattern = (
            r"^https?://www\.blu-ray\.com/[a-zA-Z0-9_-]+/\d+(/(#.*)?)?$"
        )

    def get_id(self, url):
        r = re.match(
            r"^https?://www\.blu-ray\.com/[a-zA-Z0-9_-]+/(\d+)(/(#.*)?)?$", url
        )
        if r is None:
            return 0
        return int(r[1])

    def get_releases(self, url):
        rq, ref = self.ses.get_html(url)

        r = json.loads(
            rq.search(
                r"""
            .releases tr; a; {
                .name @ | "%(title)Dv" trim,
                .link @ | "%(href)v",
                .country [0] * spre@; img self@ | "%(title)v",
                [0:1] * ssub@; small self@; {
                    .distributor [0] @ | "%t" trim,
                    .price [1] @ | "%Dt" trim
                }
            } |
        """
            )
        )["releases"]

        for i in r:
            i["link"] = urljoin_r(ref, i["link"])
            self.alllinks.add(i["link"])
        return r

    def process(self, rq, ref, url, p_id):
        r = json.loads(
            rq.search(
                r"""
            .cover [0] img #productimage | "%(src)v",
            [0] h1 .eurostile; {
                .title @ | "%t" trim,
                .year.u [0] font .oswald | "%i"
            },

            // just a few screenshots at main page
            .screenshots.a img src=b>"https://images.static-bluray.com/reviews/" | "%(src)v\n" / sed "s/_tn(\.[a-z]+)$/\1/" "E",
            .watched.u div c@[0] #B>watched1_.* | "%i",
            .watchlist.u div c@[0] #B>watchlist1_.* | "%i",
            .notinterested.u div c@[0] #B>notinterested1_.* | "%i",

            div #content_overview; {
                .appeals div .genreappeal; {
                    .name [0] * c@[0] | "%Dt" trim,
                    .amount.u @ | "%(style)v" / sed "s/.*; width: //"
                } | ,
                .plottags.a div #E>plottagwidget_[0-9]+ title; div .plottaglink; a c@[0] title | "%i\n",
                [0] table .menu; {
                    .studios [0] td .specmenu i@f>Studio; [0] * ssub@; td .specitem self@; a; {
                        .name @ | "%Dt" trim,
                        .link @ | "%(href)v"
                    } | ,
                    .distributors [0] td .specmenu i@f>"Blu-ray distributor"; [0] * ssub@; td .specitem self@; a; {
                        .name @ | "%Dt" trim,
                        .link @ | "%(href)v"
                    } | ,
                    .releasedates [0] td .specmenu i@f>"Release date"; [0] * ssub@; td .specitem self@; img; {
                        .name @ | "%(title)Dv",
                        .date [0] ( textall@ * )( tag@ * )( comment@ * ) ssub@; text@ [0] * self@ / sed "s/&nbsp;//g" trim
                    } | ,
                    .boxoffice [0] td .specmenu i@f>"Box office"; [0] * ssub@; td .specitem self@; span title; {
                        .name @ | "%(title)Dv",
                        .amount @ | "%t" / sed "s/&nbsp;//g" trim
                    } | ,
                    .country [0] td .specmenu i@f>"Country"; [0] * ssub@; td .specitem self@ | "%t" sed "s/&nbsp;//g" trim,
                    .language [0] td .specmenu i@f>"Language"; [0] * ssub@; td .specitem self@ | "%t" trim,
                    .runtime.u [0] td .specmenu i@f>"Runtime"; [0] * ssub@; td .specitem self@ | "%t" trim,
                    .rated [0] td .specmenu i@f>"Rated"; [0] * ssub@; td .specitem self@ | "%t" trim,
                    .technical [0] td .specmenu i@f>"Technical details"; [0] * ssub@; td .specitem self@ | "%t" trim,
                },
                div .cloud; {
                    .fans.u [0] small i@"fans"; [0] * spre@; self@ | "%i",
                    .collections {
                        .blu-ray.u [0] small i@"Blu-ray"; [0] * spre@; self@ | "%i",
                        .dvd.u [0] small i@"DVD"; [0] * spre@; self@ | "%i",
                        .digital.u [0] small i@"Digital"; [0] * spre@; self@ | "%i",
                        .itunes.u [0] small i@"iTunes"; [0] * spre@; self@ | "%i",
                        .prime.u [0] small i@"Prime"; [0] * spre@; self@ | "%i",
                    }
                },
                div #ratingdistribution; [0] td width="40%"; font; {
                    .score.n [0] @ | "%i",
                    .liked.u [1] @ | "%i"
                },
                .sources [0] table width=240 .menu; a c@[0]; {
                    .name @ | "%Dt" trim,
                    .link @ | "%(href)v"
                } |
            }
        """
            )
        )
        r["id"] = p_id
        r["url"] = url
        r["cover"] = urljoin_r(ref, r["cover"])
        for i, img in enumerate(r["screenshots"]):
            r["screenshots"][i] = urljoin_r(ref, img)
        for i in r["studios"]:
            i["link"] = urljoin_r(ref, i["link"])
        for i in r["distributors"]:
            i["link"] = urljoin_r(ref, i["link"])
        for i in r["sources"]:
            i["link"] = urljoin_r(ref, i["link"])
        for i in r["releasedates"]:
            i["date"] = self.conv_date(i["date"], "%b %d, %Y")

        r["releases"] = self.get_releases(
            "https://www.blu-ray.com/products/menu_ajax.php?p={}&c=20&action=showreleasesall".format(
                p_id
            )
        )

        return r


class BluRay(BluRayItem):
    def __init__(self, path, **kwargs):
        self.ses = Session(
            **kwargs,
        )

        self.workdir = Path(os.path.realpath(path))
        createdir(self.workdir)

        self.links_path = self.workdir / "links"
        self.links = self.links_load()
        self.links_save_counter = 0
        self.links_save_boundary = 800

        self.items = [
            BluRay_Thing(self.workdir / "movies", self.ses, self.links, "movies"),
            BluRay_Thing(self.workdir / "itunes", self.ses, self.links, "itunes"),
            BluRay_Thing(self.workdir / "dvd", self.ses, self.links, "dvd"),
            BluRay_Thing(self.workdir / "uv", self.ses, self.links, "uv"),
            BluRay_Thing(self.workdir / "digital", self.ses, self.links, "digital"),
            BluRay_Thing(self.workdir / "prime", self.ses, self.links, "prime"),
            BluRay_Thing(self.workdir / "ma", self.ses, self.links, "ma"),
            BluRay_Movie(self.workdir / "main", self.ses, self.links),
        ]

    def guess(self, url):
        self.links.add(url)
        for i in self.items:
            if i.urlvalid(url):
                return i
        return None

    def get(self, url, force=False):
        obj = self.guess(url)
        if obj is None:
            return None
        return obj.get(url, force=force)

    def save(self, url, force=False):
        obj = self.guess(url)
        if obj is None:
            return None
        return obj.save(url, force=force)

    def sitemap_load(self):
        try:
            rq, ref = self.ses.get_html("https://www.blu-ray.com/sitemap.xml")
            for i in rq.search(
                r'loc i@E>"/sitemap_(movies|bluraymovies|itunesmovies|dvdmovies|digitalmovies|ma)_" | "%i\n"'
            ).split("\n")[:-1]:
                print(i)
                r = self.ses.get(i)
                rq = reliq(gzip.decompress(r.content))

                for j in rq.search(r'loc | "%i\n"').split("\n")[:-1]:
                    self.links.add(j)
        except Exception as e:
            self.save_state()
            raise e
        self.save_state()

    def saveall(self, force=False):
        try:
            while True:
                saved = 0
                for i in list(self.links):
                    if self.save(i, force) is True:
                        saved += 1

                if saved == 0:
                    break
        except Exception as e:
            self.save_state()
            raise e
        self.save_state()


def argparser():
    parser = argparse.ArgumentParser(
        description="Tool for getting torrents from 1337x",
        add_help=False,
    )

    parser.add_argument(
        "urls",
        metavar="URL",
        type=str,
        nargs="*",
        help="urls",
    )

    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit",
    )
    parser.add_argument(
        "-d",
        "--directory",
        metavar="DIR",
        type=valid_directory,
        help="Use DIR as working directory",
        default=".",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Exit if anything fails",
    )

    request_set = parser.add_argument_group("Request settings")
    request_set.add_argument(
        "-w",
        "--wait",
        metavar="SECONDS",
        type=float,
        help="Sets waiting time for each request to SECONDS",
    )
    request_set.add_argument(
        "-W",
        "--wait-random",
        metavar="MILISECONDS",
        type=int,
        help="Sets random waiting time for each request to be at max MILISECONDS",
    )
    request_set.add_argument(
        "-r",
        "--retries",
        metavar="NUM",
        type=int,
        help="Sets number of retries for failed request to NUM",
    )
    request_set.add_argument(
        "--retry-wait",
        metavar="SECONDS",
        type=float,
        help="Sets interval between each retry",
    )
    request_set.add_argument(
        "-m",
        "--timeout",
        metavar="SECONDS",
        type=float,
        help="Sets request timeout",
    )
    request_set.add_argument(
        "-k",
        "--insecure",
        action="store_false",
        help="Ignore ssl errors",
    )
    request_set.add_argument(
        "-L",
        "--location",
        action="store_true",
        help="Allow for redirections, can be dangerous if credentials are passed in headers",
    )
    request_set.add_argument(
        "-A",
        "--user-agent",
        metavar="UA",
        type=str,
        help="Sets custom user agent",
    )
    request_set.add_argument(
        "-x",
        "--proxies",
        metavar="DICT",
        type=lambda x: dict(ast.literal_eval(x)),
        help='Set requests proxies dictionary, e.g. -x \'{"http":"127.0.0.1:8080","ftp":"0.0.0.0"}\'',
    )
    request_set.add_argument(
        "-H",
        "--header",
        metavar="HEADER",
        type=valid_header,
        action="append",
        help="Set header, can be used multiple times e.g. -H 'User: Admin' -H 'Pass: 12345'",
    )
    request_set.add_argument(
        "-b",
        "--cookie",
        metavar="COOKIE",
        type=valid_cookie,
        action="append",
        help="Set cookie, can be used multiple times e.g. -b 'auth=8f82ab' -b 'PHPSESSID=qw3r8an829'",
    )

    return parser


def cli(argv: list[str]):
    args = argparser().parse_args(argv)

    headers = {}
    cookies = {}
    if args.cookie is not None:
        for i in args.cookie:
            cookies.update(i)

    if args.header is not None:
        for i in args.header:
            headers.update(i)
        cookie = headers.get("Cookie")
        if cookie is not None:
            headers.pop("Cookie")
            for i in cookie.split(";"):
                pair = i.split("=")
                name = pair[0].strip()
                val = None
                if len(pair) > 1:
                    val = pair[1].strip()
                cookies.update({name: val})

    directory = args.directory

    net_settings = {
        "logger": sys.stdout,
        "wait": args.wait,
        "wait_random": args.wait_random,
        "retries": args.retries,
        "retry_wait": args.retry_wait,
        "timeout": args.timeout,
        "location": args.location,
        "user_agent": args.user_agent,
        "verify": args.insecure,
        "proxies": args.proxies,
        "headers": headers,
        "cookies": cookies,
    }

    force = False
    if args.force is True:
        force = True

    blur = BluRay(directory, **net_settings)

    for i in args.urls:
        blur.save(i, force=force)

    if len(args.urls) == 0:
        # blur.sitemap_load()
        blur.saveall(force=force)


cli(sys.argv[1:] if sys.argv[1:] else ["-h"])

# https://www.blu-ray.com/movies/Tarantino-XX-8-Film-Collection-Blu-ray/55782/#Packaging
# https://www.blu-ray.com/movies/Pulp-Fiction-4K-Blu-ray/252780/#Packaging
# https://www.blu-ray.com/movies/Pulp-Fiction-Blu-ray/274484/#Packaging
# https://www.blu-ray.com/digital/Tarantino-6-Film-Collection-Digital/26486/?retailerid=20#
# https://www.blu-ray.com/itunes/Pulp-Fiction-iTunes/1341/
# https://www.blu-ray.com/digital/Quentin-Tarantino-5-Movie-Collection-Digital/49213/#
# https://www.blu-ray.com/dvd/Pulp-Fiction-DVD/9336/#RegionCoding
# https://www.blu-ray.com/movies/Pulp-Fiction-4K-Blu-ray/252780/#RegionCoding
# https://www.blu-ray.com/Pulp-Fiction/19521/#Releases
