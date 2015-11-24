from flask_socketio import SocketIO


NOTI = 'notification'


class MySocket():

    def __init__(self, app, async_mode):
        self.socketio = SocketIO(app, async_mode=async_mode)

    def get_socketio(self):
        return self.socketio

    def noti_emit(self, msg, room=None):
        if room:
            self.socketio.emit(NOTI, {'data': msg}, namespace='/noti', room=room)
        else:
            self.socketio.emit(NOTI, {'data': msg}, namespace='/noti')
