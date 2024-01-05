#!/bin/env python3

import os
import os.path
import re
import stat
import sys
import textwrap
from collections import namedtuple
from pathlib import Path
from pprint import pprint

# https://github.com/libfuse/python-fuse
# https://pypi.org/project/fuse-python/
import fuse
from fuse import Fuse

fuse.fuse_python_api = (0, 2)


class FileHandler:
    # Suffix regex
    #
    # Should have two named groups: r"(?P<prefix>.*)(?P<suffix>\.zip)"
    #
    # Dots from file suffixes are converted to underlines for dir suffixes.
    # Example:
    #   "foo.bar.tar.gz" <-> "foo.bar_tar_gz"
    #   "foo_bar.tAr.GZ" <-> "foo_bar_tAr_GZ"
    # Undefined behavior:
    #   "foobar.tar_gz"
    #   "foobar_tar.gz"
    suffix_regex = None

    @classmethod
    def matches(cls, path):
        path = str(path)
        if match := cls.suffix_regex.fullmatch(path):
            prefix = match.group("prefix")
            suffix = match.group("suffix")
            filename = prefix + suffix.replace("_", ".")
            dirname = prefix + suffix.replace(".", "_")
            return (filename, dirname)
        return None

    @classmethod
    def open(cls, path):
        raise NotImplementedError()


class FileHandlerZip(FileHandler):
    suffix_regex = re.compile(r"(?P<prefix>.*)(?P<suffix>[._](zip|cbz))", re.I)


class FileHandlerTar(FileHandler):
    suffix_regex = re.compile(
        r"""
        (?P<prefix>.*)
        (?P<suffix>
            (
                [._](tar|tgz|tbz2|txz)
                |
                [._]tar[._](gz|bz2|xz)
            )
        )
        """,
        re.I | re.X,
    )

class FileHandlerPassthrough(FileHandler):
    @classmethod
    def matches(cls, path):
        return None


KNOWN_FILE_HANDLERS = [
    FileHandlerZip,
    FileHandlerTar,
]

HandlerForFile = namedtuple("HandlerForFile", ["handler", "filename", "dirname"])


def find_file_handler(path):
    for handler in KNOWN_FILE_HANDLERS:
        if file_and_dir := handler.matches(path):
            (fname, dname) = file_and_dir
            return HandlerForFile(handler, fname, dname)
    return None


HandlerForPart = namedtuple("HandlerForPart", ["fullpath", "part", "handler", "filename", "dirname"])


def find_all_handlers(path_str):
    path = Path(path_str.removeprefix("/"))

    fullpath = Path(".")
    handler_parts = []

    for (i, part) in enumerate(path.parts):
        fullpath = fullpath / part
        if match := find_file_handler(part):
            handler_parts.append(HandlerForPart(
                fullpath, part, match.handler, match.filename, match.dirname
            ))
        else:
            handler_parts.append(HandlerForPart(
                fullpath, part, FileHandlerPassthrough, None, None
            ))

    pprint(handler_parts)
    return handler_parts


class FakeStat(fuse.Stat):
    def __init__(self, is_dir=False, size=0, uid=0, gid=0, mtime=0):
        self.st_mode = stat.S_IFDIR | 0o555 if is_dir else stat.S_IFREG | 0o444
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 2 if is_dir else 1  # We don't support hardlinks.
        self.st_uid = uid
        self.st_gid = gid
        self.st_size = size
        self.st_atime = 0
        self.st_mtime = mtime
        self.st_ctime = mtime

    @classmethod
    def clone_from(cls, stat_result):
        s = cls()
        s.st_mode = stat_result.st_mode
        s.st_ino = stat_result.st_ino
        s.st_dev = stat_result.st_dev
        s.st_nlink = stat_result.st_nlink
        s.st_uid = stat_result.st_uid
        s.st_gid = stat_result.st_gid
        s.st_size = stat_result.st_size
        s.st_atime = stat_result.st_atime
        s.st_mtime = stat_result.st_mtime
        s.st_ctime = stat_result.st_ctime
        return s


class ArchiveExplorer(Fuse):
    def __init__(self, *args, **kw):
        self.src_path = None
        self.path = None
        super().__init__(*args, **kw)

    def init_mount(self, path):
        self.src_path = path
        self.path = Path(path)

    def fsinit(self):
        # chdir is good because it is stable even if the source directory is
        # moved after this program starts running.
        # It also simplifies path manipulation by just using "." as the root.
        os.chdir(self.path)

    def getattr(self, path):
        path = "." + path
        if hff := find_file_handler(path):
            if path == hff.dirname:
                s = os.stat(hff.filename)
                return FakeStat(
                    is_dir=True, uid=s.st_uid, gid=s.st_gid, mtime=s.st_mtime
                )

        # Fallback case:
        s = FakeStat.clone_from(os.lstat(path))
        # Removing the +w permission:
        s.st_mode &= 0xFFFFFFFF ^ 0o222
        return s

    def readlink(self, path):
        path = "." + path
        return os.readlink(path)

    def readdir(self, path, offset):
        path = "." + path
        for item in os.listdir(path):
            yield fuse.Direntry(item)
            if hff := find_file_handler(item):
                yield fuse.Direntry(hff.dirname)

    # def access(self, path, mode):
    #     raise NotImplementedError()

    # def statfs(self):
    #     raise NotImplementedError()


def main():
    server = ArchiveExplorer(
        version="%prog 0.1",
        dash_s_do="setsingle",
        usage=textwrap.dedent(
            """
            fuse-archive-explorer - transparently explore all archive contents

            $ %prog source_dir mount_point

            This tool can mount a directory onto another directory, and it will
            make all archive files available as subdirectories.

            Only read operations are supported.
            It is not possible to write anything to the mounted directory.
            (Feel free to fork this project and implement it yourself!)
            """
        ).strip(),
    )
    server.parse(
        errex=1,  # error exit code
    )
    (options, args) = server.cmdline
    if server.fuse_args.mount_expected():
        if len(args) < 1:
            print("Missing the source directory. (Have you read --help ?)")
            sys.exit(1)
        if len(args) > 1:
            print("Too many arguments. (Have you read --help ?)")
            sys.exit(1)
        path = args[0]
        realpath = os.path.realpath(path, strict=True)  # Throws OSError
        server.init_mount(realpath)

    server.main()


if __name__ == "__main__":
    main()
