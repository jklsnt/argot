from datetime import datetime

from peewee import *
from playhouse.postgres_ext import *
import uuid

db = PostgresqlExtDatabase('argot')

class Post(Model):
    id = UUIDField(primary_key=True)
    title = TextField()
    link = TextField()
    author = TextField()
    posted = DateTimeField()
    content = TextField()
    tags = ArrayField(TextField)

    class Meta:
        database = db
        table_name = "posts"

    def new(link, title, author, time=datetime.now(), content=None, tags=None):
        return Post.create(
            id=uuid.uuid4(),
            title=title,
            link=link,
            author=author,
            posted=time,
            content=content,
            tags=[] if tags is None else tags,
        )

    def to_dict(self):
        return {
            "title": self.title,
            "link": self.link,
            "author": self.author,
            "posted": self.posted.timestamp(),
            "content": self.content,
            "tags": self.tags
        }
