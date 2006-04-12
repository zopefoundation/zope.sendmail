##############################################################################
#
# Copyright (c) 2001, 2002 Zope Corporation and Contributors.
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
"""mail ZCML Namespace handler

$Id$
"""
__docformat__ = 'restructuredtext'

from zope.component import queryUtility
from zope.component.zcml import handler, proxify, PublicPermission
from zope.configuration.exceptions import ConfigurationError
from zope.security.checker import InterfaceChecker, CheckerPublic

from zope.sendmail.delivery import QueuedMailDelivery, DirectMailDelivery
from zope.sendmail.delivery import QueueProcessorThread
from zope.sendmail.interfaces import IMailer, IMailDelivery
from zope.sendmail.mailer import SMTPMailer


def _assertPermission(permission, interfaces, component):
    if permission is not None:
        if permission == PublicPermission:
            permission = CheckerPublic
        checker = InterfaceChecker(interfaces, permission)

    return proxify(component, checker)
    

def queuedDelivery(_context, permission, queuePath, mailer, name="Mail"):

    def createQueuedDelivery():
        delivery = QueuedMailDelivery(queuePath)
        delivery = _assertPermission(permission, IMailDelivery, delivery)

        handler('registerUtility', delivery, IMailDelivery, name)

        mailerObject = queryUtility(IMailer, mailer)
        if mailerObject is None:
            raise ConfigurationError("Mailer %r is not defined" %mailer)

        thread = QueueProcessorThread()
        thread.setMailer(mailerObject)
        thread.setQueuePath(queuePath)
        thread.start()

    _context.action(
            discriminator = ('delivery', name),
            callable = createQueuedDelivery,
            args = () )


def directDelivery(_context, permission, mailer, name="Mail"):

    def createDirectDelivery():
        mailerObject = queryUtility(IMailer, mailer)
        if mailerObject is None:
            raise ConfigurationError("Mailer %r is not defined" %mailer)

        delivery = DirectMailDelivery(mailerObject)
        delivery = _assertPermission(permission, IMailDelivery, delivery)

        handler('registerUtility', delivery, IMailDelivery, name)

    _context.action(
            discriminator = ('utility', IMailDelivery, name),
            callable = createDirectDelivery,
            args = () )


def smtpMailer(_context, name, hostname="localhost", port="25",
               username=None, password=None):
    _context.action(
        discriminator = ('utility', IMailer, name),
        callable = handler,
        args = ('registerUtility',
                SMTPMailer(hostname, port, username, password), IMailer, name)
        )
