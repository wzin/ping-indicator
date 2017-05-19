#!/usr/bin/env python


import time
import socket
import signal
import threading
import Queue
import random
import sys

from ping import Ping, is_valid_ip4_address
import conf
import data_exch

sys.path.append('/usr/share/ping-indicator/python/')


PING_FREQUENCY = 1.0  # HZ


def init_signals(daemon):
    """Catch signals to stop daemon before exiting."""

    def signal_action(signum, frame):
        """
        To be executed upon exit signal.
        """
        daemon.quit()
        sys.exit(0)

    # catch signals and handle appropriately
    for sig in [signal.SIGINT, signal.SIGHUP]:
        signal.signal(sig, signal_action)


def make_ping_object(h, ping_id):
    """
    Returns initialized Ping thread
    """
    timeout = min(500, 1000.0 / PING_FREQUENCY if PING_FREQUENCY else 500)
    max_sleep = int(1000.0 / PING_FREQUENCY)
    if not is_valid_ip4_address(h):
        try:
            h = socket.gethostbyname(h)
        except:
            return False
    # print "ping_id = {}\n".format(ping_id)
    return Ping(h, timeout, own_id=ping_id, max_sleep=max_sleep)


class PingThread(threading.Thread):
    def __init__(self, hostname, queue, quit_event, thread_id):
        threading.Thread.__init__(self)
        self.q = queue
        self.hostname = hostname
        self.host = make_ping_object(hostname, thread_id)
        self.quit_event = quit_event
        self.thread_id = thread_id
        self.counter = random.randint(900, 1800)

    def run(self):
        """
        Runs as long as the quit event is not set
        """
        while not self.quit_event.is_set():
            if self.counter < 0:
                self.host = make_ping_object(self.hostname, self.thread_id)
                self.counter = random.randint(900, 1800)
            try:
                delay = self.host.do()
                if delay is None:
                    delay = 10
                    self.q.put((self.hostname, -1))
                else:
                    self.q.put((self.hostname, delay))
            except:
                self.q.put((self.hostname, -1))
                delay = 10
            to_sleep = 1000.0 / PING_FREQUENCY
            to_sleep -= delay
            to_sleep = max(to_sleep, 0)
            self.counter -= 1
            time.sleep(to_sleep / 1000)


class PingIndicatorDaemon:
    def __init__(self, hostnames, user):
        self.hostnames = hostnames
        self.user = user
        self.quit_event = threading.Event()
        self.quit_event.clear()
        self.q = Queue.Queue()
        self.threads = [PingThread(h, self.q, self.quit_event, random.randint(333, 32333)) for h in hostnames]

    def main(self):
        [t.start() for t in self.threads]
        time.sleep(0.200)
        while not self.quit_event.is_set():
            delays = dict([(h, -1) for h in self.hostnames])
            while True:
                try:
                    (host, delay) = self.q.get_nowait()
                    delays[host] = delay
                except Queue.Empty:
                    break
            # if __debug__:
            #     print delays
            self.show_results([(h, delays[h]) for h in self.hostnames])

            to_sleep = (1000.0 / PING_FREQUENCY) if PING_FREQUENCY else 1000
            to_sleep = max(to_sleep, 0)
            # print "going to sleep {} ms ..".format(to_sleep)

            seconds = to_sleep / 1000.0
            # if __debug__:
            #     print seconds
            time.sleep(seconds)

    def show_results(self, delays):
        data = data_exch.Data_Exch(self.user)
        data.write(delays)

    def quit(self):
        self.quit_event.set()


if __name__ == "__main__":
    user = sys.argv[1]

    if len(user) > 0:
        c = conf.Conf(user)
        PING_FREQUENCY = 1000.0 / c.refresh_interval

        daemon = PingIndicatorDaemon(c.servers, user)
        init_signals(daemon)
        daemon.main()
