
__all__ = ['db']
from pydal import DAL, Field

db = DAL('sqlite://storage.db')

db.define_table('video',
        Field('filename')
    )
db.commit()
