#!/bin/python3

import argparse
import os.path
from .connection import Connection

def parse():
    parser = argparse.ArgumentParser(prog='bpcsutil.py',
                                     description='Baidu PCS client',
                                     add_help=True)
    def common(sp, human=True, noquiet=False):
        sp.add_argument('-c', action="store", metavar='CONFIG',
                        default=os.path.expanduser('~')+'/.bpcs.conf',
                        help='config file, default=~/.bpcs.conf')
        if human:
            sp.add_argument('-h', action='store_true',
                            help='human readable output')
        sp.add_argument(
            '-v', action='store', default=20, metavar='V', type=int,
            help='verbose level: ' + ('' if noquiet else '0-quiet, ')
            + '10-basic, 20-normal, '
            + '30-verbose, 40-debug')
        sp.add_argument('--help', action='help', help='print help')
    subparser = parser.add_subparsers(dest='comm', help='subcommands')
    subinit = subparser.add_parser('init', add_help=False,
                                   help ='initialize the config file')
    common(subinit, human=False, noquiet=True)
    subinit.add_argument('appname', metavar='APPNAME', help='application name')
    subinit.add_argument('apikey', metavar='APIKEY', help='API key')
    subinit.add_argument('secret', metavar='SECRET', help='API secret key')
    subinfo = subparser.add_parser('info', add_help=False,
                                   help ='get quota info')
    common(subinfo, noquiet=True)
    sublist = subparser.add_parser('list', add_help=False,
                                   help ='list directory/file')
    common(sublist, noquiet=True)
    sublist.add_argument('-l', action='store_true',
                         help='full output')
    sublistsort = sublist.add_mutually_exclusive_group()
    sublistsort.add_argument('-t', action='store_const', dest='sort',
                             const='time', default='name', help='sort by mtime')
    sublistsort.add_argument('-s', action='store_const', dest='sort',
                             const='size', default='name', help='sort by size')
    sublist.add_argument('-d', action='store_const', dest='order',
                         const='desc', default='asc',
                         help='sort in descending order')
    sublist.add_argument('-r', action='store_true',
                         help='recursive')
    sublist.add_argument('path', metavar='PATH', help='path of directory/file')
    subupload = subparser.add_parser('upload', add_help=False,
                                     help ='upload file')
    common(subupload)
    subuploadondup = subupload.add_mutually_exclusive_group()
    subuploadondup.add_argument('-n', action='store_const', dest='ondup',
                                const='newcopy', default=None,
                                help='create new copy on duplication')
    subuploadondup.add_argument('-f', action='store_const', dest='ondup',
                                const='overwrite', default=None,
                                help='overwrite on duplication')
    subupload.add_argument('-s', action='store', dest='start', default=-1,
                           metavar='INDEX', type=int,
                           help='slice the file and start from given chunk')
    subupload.add_argument('src', metavar='SRC', help='source file name')
    subupload.add_argument('dst', metavar='DST', help='destination file name')
    submeta = subparser.add_parser('meta', add_help=False,
                                   help='get meta info of directories/files')
    common(submeta, noquiet=True)
    submeta.add_argument('path', metavar='PATH', nargs='+',
                         help='paths of directories/files')
    args = parser.parse_args()
    if len(vars(args)) <= 1:
        parser.print_usage()
        return None
    else:
        return args

def main():
    args = parse()
    if not args:
        return
    if args.v >= 30:
        print('Arguments: ' + str(args))
    if args.comm == 'init':
        conn = Connection(None, args.h, args.v)
        conn.init(args.c, args.appname, args.apikey, args.secret)
    else:
        conn = Connection(args.c, args.h, args.v)
        if args.comm == 'info':
            conn.info()
        elif args.comm == 'list':
            conn.list(args.path, args.l, args.sort, args.order, args.r)
        elif args.comm == 'upload':
            conn.upload(args.src, args.dst, args.ondup, args.start,)
        elif args.comm == 'meta':
            conn.meta(args.path)
