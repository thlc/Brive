# -*- coding: utf-8 -*-

import os
import errno
import time
import tarfile
import shutil
from StringIO import StringIO

from utils import *


# a helper class for actual backends
class BaseBackend(object):

    def __init__(self, config=None):
        if config:
            self._root_dir = config.get('backend_root_dir', not_null=True)
            # add a trailing slash to root_dir if there isn't any
            self._root_dir += '' if self._root_dir[-1] == os.sep else os.sep

    # can be overriden for more elaborate backends
    def need_to_fetch_contents(self, user, document):
        return True

    # equivalent to *nix's _mkdir -p
    def _mkdir(self, path=''):
        try:
            os.makedirs(self._root_dir + path)
        except OSError as ex:
            if ex.errno == errno.EEXIST:
                pass
            else:
                raise

    def finalize(self):
        pass

    # called to clean up if there was an exception halfway through
    def clean_up(self):
        pass

    # UTC ISO-8601 time
    @staticmethod
    def _get_session_dir_name():
        return time.strftime('%Y-%m-%dT%H%M%SZ', time.gmtime())


# doens't do anything, just say it was asked to save
# mainly for Log.debugging purposes
class DummyBackend(BaseBackend):

    def save(self, user, document):
        print u'Backend save for user {}: {}'.format(user, repr(document))


# simplest backend possible: just download everything
class SimpleBackend(BaseBackend):

    def __init__(self, config):
        super(SimpleBackend, self).__init__(config)
        # create the root directory for this session
        dir_name = BaseBackend._get_session_dir_name()
        self._mkdir(dir_name)
        self._root_dir += dir_name + os.sep
        Log.debug('SimpleBackend loaded')

    def save(self, user, document):
        self._mkdir(user.login)
        prefix = self._root_dir + user.login + os.sep
        for file_name, content in document.contents.items():
            path = prefix + file_name
            Log.debug(u'Writing {}\'s {} to {}'.format(
                user.login, document.title, path
            ))
            f = open(path, 'w')
            f.write(content)
            f.close()

    def clean_up(self):
        Log.verbose(u'Unexpected shutdown, deleting {} folder'
                    .format(self._root_dir))
        shutil.rmtree(self._root_dir)


# also downloads everything, but compresses it
class TarBackend(SimpleBackend):

    def __init__(self, config):
        super(TarBackend, self).__init__(config)
        # get the compression format
        self._format = config.get('backend_compression_format', not_null=True)
        if self._format not in ('gz', 'bz2'):
            raise Exception(
                'The compression format must be either gz or bz2, '
                + u'{} given'.format(format)
            )
        self._tar_files = dict()
        Log.debug('TarBackend loaded')

    def save(self, user, document):
        # create the tarfile if we don't have one for this user yet
        if user.login not in self._tar_files:
            name = self._root_dir + user.login + '.tar.' + self._format
            self._tar_files[user.login] = tarfile.open(
                name, 'w:' + self._format
            )
        tar_file = self._tar_files[user.login]
        for file_name, content in document.contents.items():
            path = user.login + os.sep + file_name
            Log.debug(u'Writing {}\'s {} to {}'.format(
                user.login, document.title, path
            ))
            file_object = StringIO(content)
            tarnfo = tarfile.TarInfo(path)
            tarnfo.size = file_object.len
            tar_file.addfile(tarnfo, file_object)

    def finalize(self):
        Log.debug('Closing tar files')
        for tar_file in self._tar_files.values():
            tar_file.close()

