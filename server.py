import socketio
import eventlet
from multiprocessing import Queue

def server(port, q_input, q_output):
    sio = socketio.Server(cors_allowed_origins='*')
    app = socketio.WSGIApp(sio)

    @sio.event
    def connect(sid, environ, auth):
        print('connect ', sid)

    @sio.event
    def disconnect(sid):
        print('disconnect ', sid)

    @sio.event
    def post(sid, data):
        q_input.put(data)
        # print("post")

    @sio.event
    def get(sid):
        if (q_output.qsize() > 0):
            sio.emit("get", q_output.get())
            # print("get")

    eventlet.wsgi.server(eventlet.listen(('', port)), app)

def test(port):
    q = Queue()
    sio = socketio.Server(cors_allowed_origins='*')
    app = socketio.WSGIApp(sio)

    @sio.event
    def connect(sid, environ, auth):
        print('connect ', sid)

    @sio.event
    def disconnect(sid):
        print('disconnect ', sid)

    @sio.event
    def post(sid, data):
        q.put(data)
        # print("post")

    @sio.event
    def get(sid):
        if (q.qsize() > 0):
            sio.emit("get", q.get())
            # print("get")

    eventlet.wsgi.server(eventlet.listen(('', port)), app)
