from datetime import datetime


def allowed_file(filename, exts):
    return '.' in filename and filename.rsplit('.', 1)[1] in exts


def format_datetime(timestamp):
    """Format a timestamp for display."""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d @ %H:%M')
