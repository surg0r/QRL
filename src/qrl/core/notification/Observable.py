# coding=utf-8
# Distributed under the MIT software license, see the accompanying
# file LICENSE or http://www.opensource.org/licenses/mit-license.php.

from typing import Callable

from qrl.core.misc import logger
from qrl.core.notification.ObservableEvent import ObservableEvent


class Observable(object):
    """
    This is the Observer pattern, but implemented with composition instead of
    inheritance. This means that instead of inheriting from this class (and
    getting the notify() method), the class that will be observed will have a
    self._observable. Then, the class will take care of calling
    self._observable.notify() whenever something relevant happens to it.

    Other "observer" classes will use Observable.register() to tell the observed
    class  "hey, if you receive this message_type, run my function at ..." When
    the observed class receives a message, it will run notify(), which will
    notify the corresponding observer classes that it received this message.
    """
    def __init__(self, source):
        # FIXME: Add mutexes
        self.source = source
        self._observers = dict()

    @property
    def observers_count(self):
        return len(self._observers)

    def register(self, message_type, func: Callable):
        """
        Other "observer" classes will use Observable.register() to tell the
        observed class  "hey, if you receive this message_type, run my function
        at ...". Then, when the observed class receives a message, it will run
        notify(), which will notify the corresponding observer classes that it
        received this message.

        :param message_type:
        :param func:
        :return:
        """
        # FIXME: Add mutexes
        self._observers.setdefault(message_type, []).append(func)

    def notify(self, message: ObservableEvent, force_delivery=False):
        # FIXME: Add mutexes
        observers = self._observers.get(message.func_name, [])

        if force_delivery and not observers:
            raise RuntimeError("Observer not registered for: %s" % message.func_name)

        for o in observers:
            try:
                o(self.source, message)
            except Exception as e:
                logger.debug("[%s] executing %s", self.source, message)
                logger.exception(e)
