#!/usr/bin/env python

import logging
import sys
import os
import optparse
import shutil
import itertools
import shlex
import hashlib

import pyexiv2

DATETIME_KEYS = (
    'Exif.Photo.DateTimeOriginal',
    'Exif.Image.DateTimeOriginal',
    'Exif.Photo.DateTimeDigitized',
    # 'Exif.Image.DateTime'
)

CAMERA_KEY = 'Exif.Image.Model'

def make_unique_filename(name):
    for i in itertools.count():
        test_name = '%s.%d' % (name, i)
        if not os.path.exists(test_name):
            return test_name

class CameraDB(dict):
    def __init__(self, options):
        self.options = options
        self.filename = options.cfg_filename
        self.read_db()

    def read_db(self):
        try:
            fp = open(self.filename)
        except IOError, e:
            logging.debug('cannot read db file: %s: %s' % (self.filename, e))
            return

        for i, line in enumerate(fp):
            data = line.strip()
            if not data or data.startswith('#'):
                continue

            tokens = shlex.split(data, comments=True)
            if len(tokens) == 3 and tokens[1] == '=':
                self[tokens[0]] = tokens[2]
            else:
                key, eq, value = data.partition('=')
                if eq != '=':
                    logging.warning('%d: invalid line: %s' % (i+1, line))
                    continue
                value = shlex.split(value, comments=True)[0]
                self[key] = value

        fp.close()

def real_name(path):
    return os.path.abspath(os.path.normpath(path))

def same_file(file1, file2, thorough=True):
    s1 = os.stat(file1)
    s2 = os.stat(file2)
    if (s1.st_size == s2.st_size):
        if thorough:
            m1 = hashlib.md5()
            m2 = hashlib.md5()
            m1.update(open(file1).read())
            m2.update(open(file2).read())
            return m1.digest() == m2.digest()
        else:
            return True
    else:
        return False

def process_file(filename, options, db):
    logging.debug('%s...' % filename)
    try:
        meta = pyexiv2.ImageMetadata(filename)
    except UnicodeDecodeError, e:
        logging.info('bad filename: %s, not processing' % filename)
        return

    try:
        meta.read()
    except IOError, e:
        # logging.warning('error processing %s: %s' % (filename, e))
        return

    for key in DATETIME_KEYS:
        try:
            date_time =  meta[key].value
            if isinstance(date_time, str):
                logging.warning('%s: bad date/time: %s' % (filename, date_time))
            else:
                break
        except KeyError:
            continue
    else:
        logging.warning('%s: no date' % filename)
        date_time = None

    if options.use_camera:
        try:
            camera = meta[CAMERA_KEY].value
        except KeyError:
            logging.warning('%s: no camera' % filename)
            camera = None
    else:
        camera = None

    base_name = os.path.basename(filename)
    out_dir = options.out_dir
    if camera is not None:
        camera = camera.replace(' ', '_')
        camera = camera.replace(',', '.')
        camera = camera.strip('_.')
        if camera in db:
            logging.info('camera %s -> %s' % (camera, db[camera]))
            camera = db[camera]
        out_dir = os.path.join(out_dir, camera)

    if date_time is not None:
        date_str = date_time.strftime(options.fmt)
        out_filename = os.path.join(out_dir, date_str, base_name)
    else:
        out_filename = os.path.join(out_dir, 'NoDate', base_name)

    act = True
    if real_name(out_filename) == real_name(filename):
        logging.info('%s and %s are the same file, nothing to do' %
                (out_filename, filename))
        act = False
    elif os.path.exists(out_filename):
        if same_file(out_filename, filename, thorough=False):
            logging.info('ignoring %s, already processed' % filename)
            return
        if not options.overwrite:
            out_filename = make_unique_filename(out_filename)

    out_dir = os.path.dirname(out_filename)
    if not os.path.exists(out_dir):
        logging.info('making directory: %s' % out_dir)
        os.makedirs(out_dir)

    if act:
        if options.copy:
            func = shutil.copy2
            op = 'copy'
        else:
            func = shutil.move
            op = 'move'

        if not options.dry_run:
            logging.debug('%s %s -> %s' % (op, filename, out_filename))
            try:
                func(filename, out_filename)
            except IOError, e:
                logging.info('%s: error: %s' % (op, e))
        else:
            logging.info('%s %s -> %s' % (op, filename, out_filename))

def process_dir(dirname, options, db):
    for root, dirs, files in os.walk(dirname):
        for fname in files:
            filename = os.path.join(root, fname)
            process_file(filename, options, db)

def run(options, args):
    db = CameraDB(options)
    for name in args:
        if os.path.isdir(name):
            if options.recurse:
                process_dir(name, options, db)
            else:
                logging.info('ignoring directory %s' % name)
        elif os.path.isfile(name):
            process_file(name, options, db)
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
    parser.add_option('-F', '--cfg-file', dest='cfg_filename', default=None,
            metavar='FILE', help='config file')
    parser.add_option('-C', '--no-camera', dest='use_camera',
            action='store_false', default=True,
            help="don't create separate directories for each camera")

    options, args = parser.parse_args(args)

    home = os.environ['HOME']
    if options.out_dir is None:
        options.out_dir = os.path.join(home, 'OrganizedPics')

    if options.cfg_filename is None:
        options.cfg_filename = os.path.join(home, '.camera_db.rc')

    setup_logging(options.debug)

    if run(options, args):
        return 1
    else:
        return 0

if __name__ == '__main__':
    sys.exit(main())

# vim:ft=python

