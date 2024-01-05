# fuse-archive-explorer

Transparently explore all archive contents.

This repository is in early prototyping state, and it is NON-FUNCTIONAL. This was the result of one rainy afternoon of coding, and it is not usable yet.

## Objective

I wanted to have a FUSE filesystem that transparently decompressed any archives on-the-fly, so I could navigate the archive contents using any tool, just as if those archives were directories.

In other words, I wanted this:

```
$ ls

Before/
After/

$ ls Before

Photos.zip
Report.zip

$ ls After

(empty)

$ fuse-archive-explorer Before After

("Before" directory is now mounted onto "After".)

$ ls After

Photos.zip
Photos_zip/
Report.zip
Report_zip/

$ ls After/Photos_zip/

DSC01234.JPG
DSC01235.JPG

$ mupdf After/Report_zip/2023-Q1/foobar.pdf

(opens the PDF from inside that zipfile)
```

### Requirements

* A directory subtree should be accessible from the mountpoint (i.e. loopback or passthrough).
* Archive files (e.g. `*.zip`) would also be accessible as a directory (e.g. by replacing `.zip` with `_zip`).
    * Undefined behavior if there is already a file or directory with the same name as the new zip-as-directory fake name. This is so rare in the real world that I don't want to bother with it.
* Read-only access.

Optional requirements:

* Support for multiple archive types.
    * ZIP should be supported.
    * Compressed tarballs may be supported.
    * 7z may as well be supported.
    * RAR may be supported, but the licensing is so troublesome that is likely not worth the effort.
* Support for additional extensions for the same kind of archive.
    * ZIP files can be recognized as `*.zip` but also `*.cbz` and others.
    * Tarballs can be `*.tar`, `*.tar.gz`, `*.tgz`, etc.
* Support for detecting archives based on the [file signature](https://en.wikipedia.org/wiki/List_of_file_signatures).
    * May be quite slow, as it requires reading a few bytes on all files.
* Support for non-archive types.
    * It could be nice to be able to extract data from non-archive files. Data that aren't real files.
    * Metadata from multimedia files (audio/video/image).
    * PNG chunks from a PNG file.
    * Still frames from animated GIFs or from animated APNG.
    * Each icon size from a `.ico` file.
    * Streams from a video file (e.g. individual audio tracks, individual subtitles).
    * This is just nice-to-have, and definitely beyond the initial purpose of this repository. But still very cool to have.
* Nested archives may be supported.
    * If `foo.zip` contains `bar.zip`, it would be nice to access the contents through `./foo_zip/bar_zip/contents`.
    * This is rare enough in real-world that I wouldn't bother implementing it at the beginning.
    * There is a large potential for CPU an RAM bottlenecks.
* Write support is an welcome addition.
    * Having write support for the un-archived files would be simple enough to implement and convenient. This way, extracting a single file from inside an archive would be as simple as `cp foo.zip/bar.txt .`
    * Having full write support for the archived files seems like trouble. A lot of work needed, and terrible performance.

## Status of this repository

This is in a very very early stage. I started coding, I can list fake directory entries, and that's all. I haven't implemented anything else.

I certainly need more time to think on how to implement it correctly, and even more time to implement it and make sure it works fine.

For simplicity, I started coding it in Python, using [python-fuse](https://github.com/libfuse/python-fuse). I knew this would be less performant than other languages, but I just wanted to get something done quickly enough. This was supposed to be fun hacky project, not a production one. (Too bad [the Python bindings for FUSE are not well maintained](https://stackoverflow.com/q/52925566).)

This project is not really usable. It's a starting point, and not much else. If you are unsure if you want to try it, then don't. But if you like the idea and want a starting point to start implementing your own FUSE filesystem, then go ahead and take a look at this project. But it's likely you will find better examples elsewhere anyway.
