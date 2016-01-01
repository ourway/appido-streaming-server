
__all__ = ['db']
from pydal import DAL, Field
import datetime
import uuid

now = datetime.datetime.now

def getUUID():
    return uuid.uuid4().hex


db = DAL('sqlite://storage.db', lazy_tables = True, migrate=True,
         check_reserved=['postgres', 'postgres_nonreserved', 'oracle',
                         'mysql', 'mssql'], pool_size=32)



db.define_table('auth_user',
        Field('uuid', required=True, length=32, default=getUUID),
        Field('first_name', required=True),
        Field('last_name', required=True),
        Field('email', required=True, unique=True),
        Field('cellphone', unique=True),
        Field('notification_emails', 'list:string', default=[]),
        Field('email_activation_token', required=True, length=32,
              default=getUUID),
            )

db.define_table('media',
        Field('original_filename', length=128),
        Field('filename', length=128),
        Field('title', length=128),
        Field('uploader', db.auth_user, required=True),
    )


db.commit()
