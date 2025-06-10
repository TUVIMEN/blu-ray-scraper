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
import gzip

from reliq import RQ
import requests
import treerequests

reliq = RQ(cached=True)


def valid_directory(directory: str):
    if os.path.isdir(directory):
        return directory
    else:
        raise argparse.ArgumentTypeError('"{}" is not a directory'.format(directory))


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

    def process(self, rq, url, p_id):
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
        rq = self.ses.get_html(url)
        # self.raw_save(rq, ref, url, p_id)
        return rq

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
        rq = self.add(url, p_id)

        return self.process(rq, url, p_id)

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

        rq = self.ses.get_html(url)
        r = rq.json(
            r"""
            .c h3 i@f>"Member uploaded packaging images"; [:3] * ssub@; [0] div self@; a; {
                .link.U @ | "%(href)v",
                .date @ | "%(title)v" sed "s/^Uploaded //"
            } |
        """
        )["c"]

        for i in r:
            i["date"] = self.conv_date(i["date"], "%H:%M:%S %B %d, %Y")
        return r

    def get_region_coding(self, p_id):
        if self.name != "dvd" and self.name != "movies":
            return []

        url = "https://www.blu-ray.com/{}/movies.php?id={}&action=showregioncoding&filter=rating&page=".format(
            self.name, p_id
        )
        rq = self.ses.get_html(url)
        r = rq.json(
            r"""
            .c table l@[0] style; {
                .avatar.U a href=a>/profile.php?u=; [0] img | "%(src)v",
                [0] h5; {
                    .user @ | "%Di" trim,
                    a parent@; {
                        .user_link.U @ | "%(href)v",
                        .date [0] * ssub@; font style="color: #aaa" | "%Di" trim,
                        .rating.u [0] img #b>showrating fssub@ | "%(title)v"
                    }
                },
                .regions text@ [1] "Region " | "%DA" trim
            } |
        """
        )["c"]
        for i in r:
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
        if len(loc) == 0:
            return ""
        return reliq.urljoin(url, loc)

    def clear_redirections(self, arr):
        ret = set()
        for i in set(arr):
            if i.find("/link/click.php?") == -1:
                ret.add(i)
                continue
            print(i)
            ret.add(self.get_redirection(i))
        return list(ret)

    def process(self, rq, url, p_id):
        r = rq.json(
            r"""
            [0] td width=728; {
                [0] a data-globalparentid; {
                    .parent_link.U @ | "%(href)v",
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
                .cover.U img #frontimage_overlay | "%(src)v",
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
        rq = self.ses.get_html(url)

        r = json.loads(
            rq.search(
                r"""
            .releases tr; a; {
                .name @ | "%(title)Dv" trim,
                .link.U @ | "%(href)v",
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
            self.alllinks.add(i["link"])
        return r

    def process(self, rq, url, p_id):
        r = json.loads(
            rq.search(
                r"""
            .cover.U [0] img #productimage | "%(src)v",
            [0] h1 .eurostile; {
                .title @ | "%t" trim,
                .year.u [0] font .oswald | "%i"
            },

            // just a few screenshots at main page
            .screenshots.a.U img src=b>"https://images.static-bluray.com/reviews/" | "%(src)v\n" / sed "s/_tn(\.[a-z]+)$/\1/" "E",
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
                        .link.U @ | "%(href)v"
                    } | ,
                    .distributors [0] td .specmenu i@f>"Blu-ray distributor"; [0] * ssub@; td .specitem self@; a; {
                        .name @ | "%Dt" trim,
                        .link.U @ | "%(href)v"
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
                    .link.U @ | "%(href)v"
                } |
            }
        """
            )
        )
        r["id"] = p_id
        r["url"] = url
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
        self.ses = treerequests.Session(
            requests,
            requests.Session,
            lambda x, y: treerequests.reliq(x, y, obj=reliq),
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
            rq = self.ses.get_html("https://www.blu-ray.com/sitemap.xml")
            for i in rq.search(
                r'loc i@E>"/sitemap_(movies|bluraymovies|itunesmovies|dvdmovies|digitalmovies|ma)_" | "%i\n"'
            ).split("\n")[:-1]:
                r = self.ses.get(i)
                rq = reliq(gzip.decompress(r.content), ref=rq.ref)

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
        description="Tool for scraping blu-ray.com. If no URLs provided scrapes the whole site",
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

    treerequests.args_section(parser)

    return parser


def cli(argv: list[str]):
    args = argparser().parse_args(argv)

    directory = args.directory

    net_settings = {"logger": treerequests.simple_logger(sys.stdout)}

    force = args.force

    blur = BluRay(directory, **net_settings)
    treerequests.args_session(blur.ses, args)

    for i in args.urls:
        blur.save(i, force=force)

    if len(args.urls) == 0:
        blur.sitemap_load()
        blur.saveall(force=force)


cli(sys.argv[1:])

# https://www.blu-ray.com/movies/Tarantino-XX-8-Film-Collection-Blu-ray/55782/#Packaging
# https://www.blu-ray.com/movies/Pulp-Fiction-4K-Blu-ray/252780/#Packaging
# https://www.blu-ray.com/movies/Pulp-Fiction-Blu-ray/274484/#Packaging
# https://www.blu-ray.com/digital/Tarantino-6-Film-Collection-Digital/26486/?retailerid=20#
# https://www.blu-ray.com/itunes/Pulp-Fiction-iTunes/1341/
# https://www.blu-ray.com/digital/Quentin-Tarantino-5-Movie-Collection-Digital/49213/#
# https://www.blu-ray.com/dvd/Pulp-Fiction-DVD/9336/#RegionCoding
# https://www.blu-ray.com/movies/Pulp-Fiction-4K-Blu-ray/252780/#RegionCoding
# https://www.blu-ray.com/Pulp-Fiction/19521/#Releases
