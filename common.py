def make_key(ktype, val):
    return ktype + ':' + str(val)


def allowed_file(filename, exts):
    return '.' in filename and filename.rsplit('.', 1)[1] in exts
