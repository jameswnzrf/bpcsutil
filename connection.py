#!/bin/python3

import math
import http.client
import baidupcs
import re
import json
import time
import os.path
import hashlib
import requests
from .encode import multipart_encode

class Connection:
    '''Connection with pcs.baidu.com.'''
    conf = None

    def __init__(self, config, human, verbose):
        self.human = human
        self.verbose = verbose # verbose level explained:
        #  0: quiet: Nothing will be printed out;
        # 10: basic: Only critical information;
        # 20: normal: Normal information;
        # 30: verbose: Information only interested in debugging the script;
        # 40: debug: All debug information including those from libraries.
        http.client.HTTPConnection.debuglevel = 1 if verbose >= 40 else 0;
        if config:
            self.load(config)

    class APIException(http.client.HTTPException):
        def __init__(self, status, reason, body):
            self.status = status
            self.reason = reason
            self.body = body
        def __str__(self):
            return str(self.status) + ': ' + self.reason + '\n' + str(self.body)

    def proxyrequest(self, func, *args, raw=False, noset=set(), **kwargs):
        default = lambda name: name not in noset and name not in kwargs
        if default('verify'):
            kwargs['verify'] = True
        if default('timeout'):
            kwargs['timeout'] = 30
        r = func(*args, **kwargs)
        if not raw:
            try:
                rj = r.json()
            except Exception:
                rj = None
            if self.verbose >= 30:
                print('Response: ', rj)
        if r.status_code != requests.codes.ok:
            if rj:
                raise Exception(rj)
            else:
                r.raise_for_status()
        return rj

    def noquiet(self):
        if self.verbose < 10:
            raise Exception('task is incompatible with quiet')

    def init(self, config, appname, appkey, secret):
        self.noquiet()
        res = self.proxyrequest(
            requests.get, 'https://openapi.baidu.com/oauth/2.0/device/code',
            params={
                'client_id': appkey,
                'response_type': 'device_code',
                'scope': 'netdisk',
            })
        print('**** Please open: ', res['verification_url'],
              '\n**** And input: ', res['user_code'],
              '\n**** Press enter when done.')
        input()
        res = self.proxyrequest(
            requests.get,
            'https://openapi.baidu.com/oauth/2.0/token',
            params={
                'grant_type': 'device_token',
                'code': res['device_code'],
                'client_id': appkey,
                'client_secret': secret,
            })
        data = {'name': appname,
                'appkey': appkey,
                'secret': secret,
                'token': res['access_token'],
                'expire': time.time() + res['expires_in'] - 24 * 3600,
                'refresh': res['refresh_token'],}
        with open(config, 'w') as fp:
            fp.write(json.dumps(data))
        self.load(config)

    def load(self, config):
        with open(config, 'r') as fp:
            self.conf = json.loads(fp.read())
        if time.time() > self.conf['expire']:
            if self.verbose >= 30:
                print('Access token expired.')
            res = self.proxyrequest(
                requests.get,
                'https://openapi.baidu.com/oauth/2.0/token',
                params={
                    'grant_type': 'refresh_token',
                    'refresh_token': self.conf['refresh'],
                    'client_id': self.conf['appkey'],
                    'client_secret': self.conf['secret'],
                })
            self.conf['token'] = res['access_token']
            self.conf['expire'] = time.time() + res['expires_in'] - 24 * 3600
            self.conf['refresh'] = res['refresh_token']
            with open(config, 'w') as fp:
                fp.write(json.dumps(self.conf))
        if self.verbose >= 30:
            print('Config: ', self.conf)
        self.pcs = baidupcs.PCS(self.conf['token'])

    @staticmethod
    def humansize(num):
        for x in ['B','KiB','MiB','GiB']:
            if num < 1024.0 and num > -1024.0:
                return "%3.2f%s" % (num, x)
            num /= 1024.0
        return "%3.2f%s" % (num, 'TB')

    @staticmethod
    def humantime(sec):
        now = time.localtime()
        local = time.localtime(sec)
        if time.strftime('%Y', now) == time.strftime('%Y', local):
            if time.strftime('%j', now) == time.strftime('%j', local):
                return time.strftime('%H:%M', local)
            else:
                return time.strftime('%m/%d', local)
        else:
            return time.strftime('%Y-%m-%d', local)

    def info(self):
        self.noquiet()
        res = self.proxyrequest(self.pcs.info)
        if self.human:
            print('Quota: ', Connection.humansize(res['used']),
                  '/', Connection.humansize(res['quota']))
        else:
            print('Quota: ', res['used'], '/', res['quota'])
        return res

    def path(self, relative=None, absolute=None):
        prefix = '/apps/' + self.conf['name']
        if relative and absolute:
            raise Exception('relative and absolute should not coexist')
        if relative:
            path = (prefix
                    + ('/' if len(relative) > 0 and relative[0] != '/' else '')
                    + relative)
            if (re.search('[\\\\?|"><:*]', path) or re.search('[.\s]$', path)
                or re.search('/[.\s]', path) or re.search('[.\s]/', path)
                or len(path) > 1000):
                raise Exception('invalid path: ' + path)
        if absolute:
            path = absolute[len(prefix)+1:]
        return path

    def detail(self, path, ctime, mtime, size,
               md5='-', isdir=None, subdir=None, blocks=[]):
        path = self.path(absolute=path)
        if self.human:
            ctime = Connection.humantime(ctime)
            mtime = Connection.humantime(mtime)
            size = Connection.humansize(size)
        if isdir == 1:
            isdir = 'D'
        elif isdir == 0:
            isdir = 'F'
        else:
            isdir = '-'
        if subdir == 1:
            subdir = 'S'
        elif subdir == 0:
            subdir = 'N'
        else:
            subdir = '-'
        print(path, '\t', ctime, '\t', mtime, '\t', size, '\t', md5, '\t',
              isdir + subdir, '\t', blocks)

    def list(self, path, full, sort, order, recursive):
        self.noquiet()
        res = self.proxyrequest(self.pcs.list_files, self.path(relative=path),
                                by=sort, order=order)
        for item in res['list']:
            if full:
                self.detail(
                    item['path'], item['ctime'], item['mtime'], item['size'],
                    md5=item['md5'], isdir=item['isdir'])
            else:
                print(self.path(absolute=item['path']))
            if recursive and item['isdir']:
                self.list(self.path(absolute=item['path']),
                          full, sort, order, recursive)
        return res

    def upload(self, src, dst, ondup, start):
        piece = 200 * 1024 # minimum piece size, set arbitrarily
        count = 1024 # maximum count of pieces, set by baidu
        total = os.path.getsize(src)
        if piece * count < total:
            piece = math.ceil(total / count)
        else:
            count = math.ceil(total / piece)
        if start >= count:
            raise Exception('invalid start index')
        if self.verbose >= 20:
            print('Size: ' + Connection.humansize(total) + '(' + str(total)
                  + ')' + (' = ' + str(count) + ' * '
                           + Connection.humansize(piece) + '(' + str(piece) +
                           ')' if start >= 0 else ''))
            if start >= 0:
                print('Starting from ', start)
        allmd = hashlib.md5()
        timeout = (total if start < 0 else piece) / (100 * 1024) + 30
        with open(src, 'rb') as fp:
            if start < 0:
                data, headers = multipart_encode({'file':fp})
                res = self.proxyrequest(
                    requests.post, 'https://c.pcs.baidu.com/rest/2.0/pcs/file',
                    data=data, headers=headers, timeout=timeout,
                    params={'method': 'upload',
                            'access_token': self.conf['token'],
                            'path': self.path(relative=dst),
                            'ondup': ondup})
                fp.seek(0)
                while True:
                    chunk = fp.read(piece)
                    if len(chunk) == 0:
                        break
                    allmd.update(chunk)
            elif count == 1:
                chunk = fp.read()
                res = self.proxyrequest(
                    self.pcs.upload, self.path(relative=dst), chunk,
                    ondup=ondup, timeout=timeout)
                allmd.update(chunk)
            else:
                blocks = []
                try:
                    for i in range(0, count):
                        chunk = fp.read(piece)
                        if i < start:
                            allmd.update(chunk)
                        else:
                            res = self.proxyrequest(
                                self.pcs.upload_tmpfile, chunk, timeout=timeout)
                            if res['md5'] != hashlib.md5(chunk).hexdigest():
                                raise Exception('temp file checksum mismatch')
                            allmd.update(chunk)
                            blocks.append(res['md5'])
                            start += 1
                            if self.verbose >= 20:
                                print('Progress: ', start, ' / ', count,
                                      end='\r')
                finally:
                    if self.verbose >= 10 and start < count:
                        print('continue from index ', start)
                res = self.proxyrequest(
                    self.pcs.upload_superfile, self.path(relative=dst), blocks,
                    ondup=ondup)
        if res['md5'] != allmd.hexdigest():
            raise Exception('whole file checksum mismatch: '
                            + allmd.hexdigest() + ' != ' + res['md5'])
        if self.verbose >= 20:
            self.detail(res['path'], res['ctime'], res['mtime'], res['size'],
                        md5=res['md5'])
        return res

    def meta(self, paths):
        self.noquiet()
        paths = [self.path(relative=p) for p in paths]
        res = self.proxyrequest(self.pcs.multi_meta, paths)
        for item in res['list']:
            self.detail(
                item['path'], item['ctime'], item['mtime'], item['size'],
                isdir=item['isdir'], subdir=item['ifhassubdir'],
                blocks=item['block_list'])

