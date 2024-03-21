##############################################################################
#
# Copyright (c) 2003 Zope Foundation and Contributors.
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
"""Classes which abstract different channels a message could be sent to.
"""
__docformat__ = 'restructuredtext'

from smtplib import SMTP
from smtplib import SMTP_SSL
from ssl import SSLError
from threading import local

from zope.interface import implementer

from zope.sendmail.interfaces import ISMTPMailer


class _SMTPState(local):
    connection = None
    code = None
    response = None


@implementer(ISMTPMailer)
class SMTPMailer:
    """Implementation of :class:`zope.sendmail.interfaces.ISMTPMailer`."""

    smtp = None

    def __init__(self, hostname='localhost', port=25,
                 username=None, password=None, no_tls=False, force_tls=False,
                 implicit_tls=False):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.force_tls = force_tls
        self.no_tls = no_tls
        self.implicit_tls = implicit_tls
        self._smtp = _SMTPState()
        # this is for backwards compatibility, in case someone has been
        # overrided this class with a custom `smtp` attribute.
        if self.smtp is None:
            self.smtp = SMTP_SSL if self.implicit_tls else SMTP

    def _make_property(name):
        return property(lambda self: getattr(self._smtp, name),
                        lambda self, nv: setattr(self._smtp, name, nv))

    connection = _make_property('connection')
    code = _make_property('code')
    response = _make_property('response')

    del _make_property

    def vote(self, fromaddr, toaddrs, message):
        self.connection = self.smtp(self.hostname, str(self.port))

        code, response = self.connection.ehlo()
        if code < 200 or code >= 300:
            code, response = self.connection.helo()
            if code < 200 or code >= 300:
                raise RuntimeError('Error sending HELO to the SMTP server '
                                   '(code=%s, response=%s)' % (code, response))

        self.code, self.response = code, response

    def _close_connection(self):
        try:
            self.connection.quit()
        except SSLError:
            # something weird happened while quiting
            self.connection.close()
        self.connection = None

    def abort(self):
        if self.connection is None:
            return
        self._close_connection()

    def send(self, fromaddr, toaddrs, message):
        connection = self.connection
        if connection is None:
            self.vote(fromaddr, toaddrs, message)

        connection = self.connection

        # encryption support
        if not self.implicit_tls:
            have_tls = connection.has_extn('starttls')
            if not have_tls and self.force_tls:
                raise RuntimeError('TLS is not available but TLS is required')

            if have_tls and not self.no_tls:
                connection.starttls()
                connection.ehlo()

        if connection.does_esmtp:
            if self.username is not None and self.password is not None:
                username, password = self.username, self.password
                connection.login(username, password)
        elif self.username:
            raise RuntimeError(
                'Mailhost does not support ESMTP but a username is configured')

        try:
            connection.sendmail(fromaddr, toaddrs, message)
        finally:
            self._close_connection()
