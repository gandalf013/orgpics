#!/usr/bin/env python

import logging
import sys
import os
import optparse
import shutil
import itertools

import pyexiv2

DATETIME_KEY = 'Exif.Image.DateTime'
CAMERA_KEY = 'Exif.Image.Model'

def make_unique_filename(name):
    for i in itertools.count():
        test_name = '%s.%d' % (name, i)
        if not os.path.exists(name):
            break

    return test_name

def process_file(filename, options):
    logging.debug('%s...' % filename)
    meta = pyexiv2.ImageMetadata(filename)
    try:
        meta.read()
    except IOError, e:
        logging.warning('error processing %s: %s' % (filename, e))
        return

    try:
        date_time =  meta[DATETIME_KEY].value
    except KeyError:
        logging.warning('%s: no date' % filename)
        date_time = None
    else:
        if isinstance(date_time, str):
            logging.warning('%s: bad date/time: %s' % (filename, date_time))
            date_time = None

    try:
        camera = meta[CAMERA_KEY].value
    except KeyError:
        logging.warning('%s: no camera' % filename)
        camera = None

    base_name = os.path.basename(filename)
    out_dir = options.out_dir
    if camera is not None:
        camera = camera.replace(' ', '_')
        camera = camera.replace(',', '.')
        out_dir = os.path.join(out_dir, camera)

    if date_time is not None:
        date_str = date_time.strftime(options.fmt)
        out_filename = os.path.join(out_dir, date_str, base_name)
    else:
        out_filename = os.path.join(out_dir, 'NoDate', base_name)

    if os.path.exists(out_filename) and not options.overwrite:
        out_filename = make_unique_filename(out_filename)

    out_dir = os.path.dirname(out_filename)
    if not os.path.exists(out_dir):
        logging.info('making directory: %s' % out_dir)
        os.makedirs(out_dir)

    if options.copy:
        func = shutil.copy2
        op = 'copy'
    else:
        func = shutil.move
        op = 'move'

    if not options.dry_run:
        logging.debug('%s %s -> %s' % (op, filename, out_filename))
        func(filename, out_filename)
    else:
        logging.info('%s %s -> %s' % (op, filename, out_filename))

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
                logging.info('ignoring directory %s' % name)
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
    usage = 'usage: %prog [options]'
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-D', '--debug', dest='debug', action='store_true',
            default=False, help='debug')
    parser.add_option('-d', '--out-dir', dest='out_dir', default=None,
            metavar='DIR', help='output directory=DIR')
    parser.add_option('-f', '--fmt', dest='fmt', default='%Y/%m/%d',
            metavar='FMT', help='strftime() format for output directory')
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

    if options.out_dir is None:
        options.out_dir = os.path.join(os.environ['HOME'], 'OrganizedPics')

    setup_logging(options.debug)

    if run(options, args):
        return 1
    else:
        return 0

if __name__ == '__main__':
    sys.exit(main())

# vim:ft=python

