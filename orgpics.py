#!/usr/bin/env python

import logging
import sys
import os
import optparse
import shutil
import itertools
import hashlib

import pyexiv2

DATETIME_KEYS = (
    'Exif.Photo.DateTimeOriginal',
    'Exif.Image.DateTimeOriginal',
    'Exif.Photo.DateTimeDigitized',
)

RAW_EXTENSIONS = set(['.cr2', '.nef'])

def make_unique_filename(name):
    for i in itertools.count():
        test_name = '%s.%d' % (name, i)
        if not os.path.exists(test_name):
            return test_name

def real_name(path):
    return os.path.abspath(os.path.normpath(path))

def is_raw_file(path):
    _, ext = os.path.splitext(path)
    return ext.lower() in RAW_EXTENSIONS

def same_file(file1, file2, thorough=True):
    s1 = os.stat(file1)
    s2 = os.stat(file2)

    if s1.st_size != s2.st_size:
        return False

    if not thorough:
        return True

    m1 = hashlib.md5()
    m2 = hashlib.md5()
    with open(file1) as fp1:
        m1.update(fp1.read())
    with open(file2) as fp2:
        m2.update(fp2.read())

    return m1.digest() == m2.digest()

def process_file(filename, options):
    logging.debug('%s...', filename)
    try:
        meta = pyexiv2.ImageMetadata(filename)
    except UnicodeDecodeError, e:
        logging.info('bad filename: %s, not processing', filename)
        return

    try:
        meta.read()
    except IOError, e:
        # logging.warning('error processing %s: %s', filename, e)
        return

    for key in DATETIME_KEYS:
        try:
            date_time =  meta[key].value
            if isinstance(date_time, str):
                logging.warning('%s: bad date/time: %s', filename, date_time)
            else:
                break
        except KeyError:
            continue
    else:
        logging.warning('%s: no date', filename)
        date_time = None

    base_name = os.path.basename(filename)
    out_dir = options.out_dir

    if date_time is not None:
        date_str = date_time.strftime(options.fmt)
        out_dir = os.path.join(out_dir, date_str)
    else:
        out_dir = os.path.join(out_dir, 'NoDate')

    is_raw = is_raw_file(filename)
    if is_raw:
        out_dir = os.path.join(out_dir, 'Raw')

    out_filename = os.path.join(out_dir, base_name)

    act = True
    if real_name(out_filename) == real_name(filename):
        logging.info('%s and %s are the same file, nothing to do',
                     out_filename, filename)
        act = False
    elif os.path.exists(out_filename):
        if same_file(out_filename, filename, thorough=False):
            logging.info('ignoring %s, already processed', filename)
            return
        if not options.overwrite:
            out_filename = make_unique_filename(out_filename)

    if not os.path.exists(out_dir):
        logging.info('making directory: %s', out_dir)
        os.makedirs(out_dir)

    if act:
        if options.copy:
            func = shutil.copy2
            op = 'copy'
        else:
            func = shutil.move
            op = 'move'

        if not options.dry_run:
            logging.debug('%s %s -> %s', op, filename, out_filename)
            try:
                func(filename, out_filename)
            except IOError, e:
                logging.info('%s: error: %s', op, e)
        else:
            logging.info('%s %s -> %s', op, filename, out_filename)

def process_dir(dirname, options):
    for root, dirs, files in os.walk(dirname):
        for fname in files:
            filename = os.path.join(root, fname)
            process_file(filename, options)

def run(options, args):
    for name in args:
        if os.path.isdir(name):
            if options.recurse:
                process_dir(name, options)
            else:
                logging.info('ignoring directory %s', name)
        elif os.path.isfile(name):
            process_file(name, options)
        else:
            raise ValueError('invalid argument %s' % name)

    return True

def setup_logging(debug=False):
    if debug:
        lvl = logging.DEBUG
    else:
        lvl = logging.INFO

    logging.basicConfig(format='%(levelname)s: %(message)s')
    logging.getLogger().setLevel(lvl)

def main(args=None):
    usage = 'usage: %prog [options] <path(s)>'
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-D', '--debug', dest='debug', action='store_true',
                      default=False, help='debug')
    parser.add_option('-d', '--out-dir', dest='out_dir', default=None,
                      metavar='DIR', help='output directory=DIR')
    parser.add_option('-f', '--fmt', dest='fmt', default='%Y-%m-%d',
                      metavar='FMT',
                      help='strftime() format for output directory')
    parser.add_option('-r', '--recurse', dest='recurse', action='store_true',
                      default=False, help='recurse directories')
    parser.add_option('-o', '--overwrite', dest='overwrite',
                      action='store_true', default=False,
                      help='overwrite files (default=False: add an extension)')
    parser.add_option('-c', '--copy', dest='copy', action='store_true',
                      default=False, help='copy files instead of moving')
    parser.add_option('-n', '--dry-run', dest='dry_run', action='store_true',
                      default=False, help='dry run')

    options, args = parser.parse_args(args)

    home = os.environ['HOME']
    if options.out_dir is None:
        options.out_dir = os.path.join(home, 'OrganizedPics')

    setup_logging(options.debug)

    if run(options, args):
        return 1
    else:
        return 0

if __name__ == '__main__':
    sys.exit(main())
