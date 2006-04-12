##############################################################################
#
# Copyright (c) 2003 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Unit tests for zope.sendmail.maildir module

$Id$
"""
import unittest
import stat

from zope.interface.verify import verifyObject


class FakeSocketModule(object):

    def gethostname(self):
        return 'myhostname'

class FakeTimeModule(object):

    _timer = 1234500000

    def time(self):
        return self._timer

    def sleep(self, n):
        self._timer += n

class FakeOsPathModule(object):

    def __init__(self, files, dirs):
        self.files = files
        self.dirs = dirs

    _exists_never_fails = False

    def join(self, *args):
        return '/'.join(args)

    def isdir(self, dir):
        return dir in self.dirs

    def exists(self, p):
        return self._exists_never_fails or p in self.files

class FakeOsModule(object):

    F_OK = 0
    _stat_mode = {
        '/path/to/maildir': stat.S_IFDIR,
        '/path/to/maildir/new': stat.S_IFDIR,
        '/path/to/maildir/new/1': stat.S_IFREG,
        '/path/to/maildir/new/2': stat.S_IFREG,
        '/path/to/maildir/cur': stat.S_IFDIR,
        '/path/to/maildir/cur/1': stat.S_IFREG,
        '/path/to/maildir/cur/2': stat.S_IFREG,
        '/path/to/maildir/tmp': stat.S_IFDIR,
        '/path/to/maildir/tmp/1': stat.S_IFREG,
        '/path/to/maildir/tmp/2': stat.S_IFREG,
        '/path/to/maildir/tmp/1234500000.4242.myhostname': stat.S_IFREG,
        '/path/to/maildir/tmp/1234500001.4242.myhostname': stat.S_IFREG,
        '/path/to/regularfile': stat.S_IFREG,
        '/path/to/emptydirectory': stat.S_IFDIR,
    }
    _listdir = {
        '/path/to/maildir/new': ['1', '2', '.svn'],
        '/path/to/maildir/cur': ['2', '1', '.tmp'],
        '/path/to/maildir/tmp': ['1', '2', '.ignore'],
    }

    path = FakeOsPathModule(_stat_mode, _listdir)

    _made_directories = ()
    _removed_files = ()
    _renamed_files = ()

    def access(self, path, mode):
        return path in self._stat_mode

    def stat(self, path):
        if path in self._stat_mode:
            return (self._stat_mode[path], 0, 0, 1, 0, 0, 0, 0, 0, 0)
        raise OSError('%s does not exist' % path)

    def listdir(self, path):
        return self._listdir.get(path, [])

    def mkdir(self, path):
        self._made_directories += (path, )

    def getpid(self):
        return 4242

    def unlink(self, path):
        self._removed_files += (path, )

    def rename(self, old, new):
        self._renamed_files += ((old, new), )

class FakeFile(object):

    def __init__(self, filename, mode):
        self._filename = filename
        self._mode = mode
        self._written = ''
        self._closed = False

    def close(self):
        self._closed = True

    def write(self, data):
        self._written += data

    def writelines(self, lines):
        self._written += ''.join(lines)

def fake_open(self, filename, mode):
    return FakeFile(filename, mode)


class TestMaildir(unittest.TestCase):

    def setUp(self):
        import zope.sendmail.maildir as maildir_module
        self.maildir_module = maildir_module
        self.old_os_module = maildir_module.os
        self.old_time_module = maildir_module.time
        self.old_socket_module = maildir_module.socket
        maildir_module.os = self.fake_os_module = FakeOsModule()
        maildir_module.time = FakeTimeModule()
        maildir_module.socket = FakeSocketModule()
        maildir_module.MaildirMessageWriter.open = fake_open

    def tearDown(self):
        self.maildir_module.os = self.old_os_module
        self.maildir_module.time = self.old_time_module
        self.maildir_module.socket = self.old_socket_module
        self.maildir_module.MaildirMessageWriter.open = open
        self.fake_os_module._stat_never_fails = False
        self.fake_os_module.path._exists_never_fails = False

    def test_factory(self):
        from zope.sendmail.interfaces import IMaildirFactory, IMaildir
        from zope.sendmail.maildir import Maildir
        verifyObject(IMaildirFactory, Maildir)

        # Case 1: normal maildir
        m = Maildir('/path/to/maildir')
        verifyObject(IMaildir, m)

        # Case 2a: directory does not exist, create = False
        self.assertRaises(ValueError, Maildir, '/path/to/nosuchfolder', False)
        
        # Case 2b: directory does not exist, create = True
        m = Maildir('/path/to/nosuchfolder', True)
        verifyObject(IMaildir, m)
        dirs = list(self.fake_os_module._made_directories)
        dirs.sort()
        self.assertEquals(dirs, ['/path/to/nosuchfolder',
                                 '/path/to/nosuchfolder/cur',
                                 '/path/to/nosuchfolder/new',
                                 '/path/to/nosuchfolder/tmp'])

        # Case 3: it is a file, not a directory
        self.assertRaises(ValueError, Maildir, '/path/to/regularfile', False)
        self.assertRaises(ValueError, Maildir, '/path/to/regularfile', True)

        # Case 4: it is a directory, but not a maildir
        self.assertRaises(ValueError, Maildir, '/path/to/emptydirectory', False)
        self.assertRaises(ValueError, Maildir, '/path/to/emptydirectory', True)

    def test_iteration(self):
        from zope.sendmail.maildir import Maildir
        m = Maildir('/path/to/maildir')
        messages = list(m)
        messages.sort()
        self.assertEquals(messages, ['/path/to/maildir/cur/1',
                                     '/path/to/maildir/cur/2',
                                     '/path/to/maildir/new/1',
                                     '/path/to/maildir/new/2'])

    def test_newMessage(self):
        from zope.sendmail.maildir import Maildir
        from zope.sendmail.interfaces import IMaildirMessageWriter
        m = Maildir('/path/to/maildir')
        fd = m.newMessage()
        verifyObject(IMaildirMessageWriter, fd)
        self.assertEquals(fd._filename,
                          '/path/to/maildir/tmp/1234500002.4242.myhostname')

    def test_newMessage_never_loops(self):
        from zope.sendmail.maildir import Maildir
        from zope.sendmail.interfaces import IMaildirMessageWriter
        self.fake_os_module.path._exists_never_fails = True
        m = Maildir('/path/to/maildir')
        self.assertRaises(RuntimeError, m.newMessage)

    def test_message_writer_and_abort(self):
        from zope.sendmail.maildir import MaildirMessageWriter
        filename1 = '/path/to/maildir/tmp/1234500002.4242.myhostname'
        filename2 = '/path/to/maildir/new/1234500002.4242.myhostname'
        writer = MaildirMessageWriter(filename1, filename2)
        # writer._fd should be a FakeFile instance because we stubbed open()
        self.assertEquals(writer._fd._filename, filename1)
        self.assertEquals(writer._fd._mode, 'w')  # TODO or 'wb'?
        print >> writer, 'fee',
        writer.write(' fie')
        writer.writelines([' foe', ' foo'])
        self.assertEquals(writer._fd._written, 'fee fie foe foo')

        writer.abort()
        self.assertEquals(writer._fd._closed, True)
        self.assert_(filename1 in self.fake_os_module._removed_files)
        # Once aborted, abort does nothing
        self.fake_os_module._removed_files = ()
        writer.abort()
        writer.abort()
        self.assertEquals(self.fake_os_module._removed_files, ())
        # Once aborted, commit fails
        self.assertRaises(RuntimeError, writer.commit)

    def test_message_writer_commit(self):
        from zope.sendmail.maildir import MaildirMessageWriter
        filename1 = '/path/to/maildir/tmp/1234500002.4242.myhostname'
        filename2 = '/path/to/maildir/new/1234500002.4242.myhostname'
        writer = MaildirMessageWriter(filename1, filename2)
        writer.commit()
        self.assertEquals(writer._fd._closed, True)
        self.assert_((filename1, filename2)
                       in self.fake_os_module._renamed_files)
        # Once commited, commit does nothing
        self.fake_os_module._renamed_files = ()
        writer.commit()
        writer.commit()
        self.assertEquals(self.fake_os_module._renamed_files, ())
        # Once commited, abort does nothing
        writer.abort()
        writer.abort()
        self.assertEquals(self.fake_os_module._renamed_files, ())


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestMaildir))
    return suite


if __name__ == '__main__':
    unittest.main()
