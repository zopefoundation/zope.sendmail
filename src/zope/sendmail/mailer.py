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

"""These are classes which abstract different channels an email
message could be sent out by.

$Id$
"""
__docformat__ = 'restructuredtext'

import socket
from smtplib import SMTP

from zope.interface import implements
from zope.sendmail.interfaces import ISMTPMailer

from Products.MailHost.MailHost import MailHostError

have_ssl = hasattr(socket, 'ssl')

class SMTPMailer(object):

    implements(ISMTPMailer)

    smtp = SMTP

    def __init__(self, hostname='localhost', port=25,
                 username=None, password=None):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password

    def send(self, fromaddr, toaddrs, message):
        connection = self.smtp(self.hostname, str(self.port))

        # send EHLO
        code, response = connection.helo()
        if code < 200 or code >300:
            raise MailHostError('Error sending EHLO to the SMTP server '
                                '(code=%s, response=%s)' % (code, response))

        # encryption support
        if connection.has_extn('starttls') and have_ssl:
            connection.starttls()
            connection.ehlo()

        if connection.does_esmtp: 
            if self.username is not None and self.password is not None:
                connection.login(self.username, self.password)
        elif self.username:
            raise MailHostError('Mailhost does not support ESMTP but a username '
                                'is configured')

        connection.sendmail(fromaddr, toaddrs, message)
        connection.quit()
