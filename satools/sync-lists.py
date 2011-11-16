#!/usr/bin/python

import attachments
import common
import gzip
import lxml.html
import mailindex
import sys
import thunderbird
import time
import os
import urllib

# TODO: single list update

class DB:
    def __init__(self, path):
        self.entries = set()
        self.readdb(path)

    def readdb(self, path):
        self.entries.clear()
        self.path = path

        with open(self.path, "a+") as f:
            for line in f:
                self.entries.add(line.strip())

    def writedb(self):
        temppath = common.mktemppath(self.path)
    
        with open(temppath, "w") as f:
            for line in sorted(self.entries):
                print >>f, line

        common.rename(temppath, self.path)

    def add(self, entry):
        self.entries.add(entry)
        self.writedb()

    def __contains__(self, entry):
        return entry in self.entries

def isgzip(f):
    bytes = f.read(2)
    f.seek(0)

    return bytes == "\x1F\x8B"

if __name__ == "__main__":
    global config
    config = common.load_config()

    if not config["lists-sync"]:
        print >>sys.stderr, "Please configure lists in $HOME/.satools before running %s." % sys.argv[0]
        sys.exit(1)

    common.mkdirs(config["lists-base"])
    os.chdir(config["lists-base"])

    lock = common.Lock(".lock")
    db = DB(".sync-db")

    now = time.gmtime()

    for line in config["lists-sync"]:
        line = line.split(" ")
        
        url = line[0].rstrip("/")
        _list = url.split("/")[-1]

        credentials = None
        if len(line) == 3:
            credentials = urllib.urlencode(dict(zip(("username", "password"),
                                                    line[1:3])))

        index = common.retrieve_m(url, credentials)
        index_xml = lxml.html.parse(index).getroot()
        index.close()

        for href in index_xml.xpath("//a[substring-after(@href, '.') = 'txt.gz']/@href"):
            tm = time.strptime(href, "%Y-%B.txt.gz")
            path = "%s/%04u/%02u" % (_list, tm.tm_year, tm.tm_mon)

            if tm.tm_year < int(config["lists-start-year"]):
                break

            if not path in db or not os.path.isfile(path):
                common.mkdirs(os.path.split(path)[0])
                f = common.retrieve_tmpfile(url + "/" + href, credentials)
                if isgzip(f):
                    g = gzip.GzipFile(fileobj = f, mode = "r")
                    common.sendfile_disk(g, path)
                    g.close()
                else:
                    common.sendfile_disk(f, path)
                f.close()
                
                common.mkro(path)
                mailindex.index(".", _list, path)
                attachments.extract(path)

            thunderbird.link(path)

            if not (tm.tm_year == now.tm_year and tm.tm_mon == now.tm_mon):
                db.add(path)

    with open(".sync-done", "w") as f:
        pass
