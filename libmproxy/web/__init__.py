from __future__ import absolute_import, print_function
import collections
import tornado.ioloop
import tornado.httpserver
from .. import controller, flow
from . import app


class Stop(Exception):
    pass


class WebFlowView(flow.FlowView):
    def __init__(self, store):
        super(WebFlowView, self).__init__(store, None)

    def _add(self, f):
        super(WebFlowView, self)._add(f)
        app.ClientConnection.broadcast(
            type="flows",
            cmd="add",
            data=f.get_state(short=True)
        )

    def _update(self, f):
        super(WebFlowView, self)._update(f)
        app.ClientConnection.broadcast(
            type="flows",
            cmd="update",
            data=f.get_state(short=True)
        )

    def _remove(self, f):
        super(WebFlowView, self)._remove(f)
        app.ClientConnection.broadcast(
            type="flows",
            cmd="remove",
            data=f.get_state(short=True)
        )

    def _recalculate(self, flows):
        super(WebFlowView, self)._recalculate(flows)
        app.ClientConnection.broadcast(
            type="flows",
            cmd="reset"
        )


class WebState(flow.State):
    def __init__(self):
        super(WebState, self).__init__()
        self.view._close()
        self.view = WebFlowView(self.flows)

        self._last_event_id = 0
        self.events = collections.deque(maxlen=1000)

    def add_event(self, e, level):
        self._last_event_id += 1
        entry = {
            "id": self._last_event_id,
            "message": e,
            "level": level
        }
        self.events.append(entry)
        app.ClientConnection.broadcast(
            type="events",
            cmd="add",
            data=entry
        )

class Options(object):
    attributes = [
        "app",
        "app_domain",
        "app_ip",
        "anticache",
        "anticomp",
        "client_replay",
        "eventlog",
        "keepserving",
        "kill",
        "intercept",
        "no_server",
        "refresh_server_playback",
        "rfile",
        "scripts",
        "showhost",
        "replacements",
        "rheaders",
        "setheaders",
        "server_replay",
        "stickycookie",
        "stickyauth",
        "stream_large_bodies",
        "verbosity",
        "wfile",
        "nopop",

        "wdebug",
        "wport",
        "wiface",
    ]

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        for i in self.attributes:
            if not hasattr(self, i):
                setattr(self, i, None)


class WebMaster(flow.FlowMaster):
    def __init__(self, server, options):
        self.options = options
        super(WebMaster, self).__init__(server, WebState())
        self.app = app.Application(self.state, self.options.wdebug)

    def tick(self):
        flow.FlowMaster.tick(self, self.masterq, timeout=0)

    def run(self):  # pragma: no cover
        self.server.start_slave(
            controller.Slave,
            controller.Channel(self.masterq, self.should_exit)
        )
        iol = tornado.ioloop.IOLoop.instance()

        http_server = tornado.httpserver.HTTPServer(self.app)
        http_server.listen(self.options.wport)

        tornado.ioloop.PeriodicCallback(self.tick, 5).start()
        try:
            iol.start()
        except (Stop, KeyboardInterrupt):
            self.shutdown()

    def handle_request(self, f):
        super(WebMaster, self).handle_request(f)
        if f:
            f.reply()
        return f

    def handle_response(self, f):
        super(WebMaster, self).handle_response(f)
        if f:
            f.reply()
        return f

    def add_event(self, e, level="info"):
        super(WebMaster, self).add_event(e, level)
        self.state.add_event(e, level)