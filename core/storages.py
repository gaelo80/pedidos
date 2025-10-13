# core/storages.py
from storages.backends.s3boto3 import S3Boto3Storage

class PrivateMediaStorage(S3Boto3Storage):
    """
    Este almacenamiento personalizado asegura que los archivos de medios (default storage)
    SIEMPRE usen URLs firmadas (pre-signed URLs), ignorando cualquier
    configuración global como AWS_QUERYSTRING_AUTH.
    """
    querystring_auth = True
    default_acl = 'private'