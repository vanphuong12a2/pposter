import base64


def make_key(ktype, val):
    return ktype + ':' + str(val)


def allowed_file(filename, exts):
    return '.' in filename and filename.rsplit('.', 1)[1] in exts


def s3_put(conn, bucket, filename, content):
    conn.Object(bucket, filename).put(Body=content)


def s3_get(conn, bucket, filename):
    img_data = conn.Object(bucket, filename).get()
    return base64.encodestring(img_data['Body'].read())


def s3_delete(conn, bucket, filename):
    conn.Object(bucket, filename).delete()
