from datetime import datetime
import secrets
import hashlib
import string

from peewee import *
from playhouse.postgres_ext import *
from flask_login import UserMixin

# def date_str(dt):
#     """Scuffed func to convert datetime to relative time in natural language.
#     E.g. dt -> '3 hours ago'
#     It's 2:27 AM as I write this so cut me some slack.
#     """    
#     now = datetime.now()
#     diff = now - dt
#     if diff.days != 0:
#         return f"{diff.days} day{'' if diff.days == 1 else 's'} ago"
#     if diff.seconds >= 3600:
#         hours = diff.seconds//3600
#         return f"{hours} hour{'' if hours == 1 else 's'} ago"
#     if diff.seconds >= 60:
#         mins = diff.seconds//60
#         return f"{mins} minute{'' if mins == 1 else 's'} ago"
#     if diff.seconds >= 0:
#         return f"{diff.seconds} second{'' if diff.seconds == 1 else 's'} ago"
#     return "just now" # you don't need microsecond precision.


db = PostgresqlExtDatabase('argot', host="/var/run/postgresql")

class BaseModel(Model):
    class Meta:
        database = db

class User(UserMixin, BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "users"

    id = AutoField(primary_key=True)
    nick = TextField()
    bio = TextField(null=True)
    email = TextField(null=True)
    hash = TextField()
    salt = TextField()

    def new(nick, password, bio=None, email=None):
        alphabet = string.ascii_letters + string.digits
        salt = ''.join(secrets.choice(alphabet) for i in range(8))

        dk = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1)

        return User.create(
            nick=nick,
            hash=dk.hex(),
            salt=salt,
            email=email,
            bio=bio
        )

    def to_dict(self):
        return {
            "nick": self.nick,
            "bio": self.bio
        }

    def __hash__(self):
        return self.id

class Post(BaseModel):
    id = AutoField(primary_key=True)
    title = TextField(null=True)
    link = TextField(null=True)
    author_id = ForeignKeyField(User, backref="posts")
    time = DateTimeField()
    content = TextField(null=True)
    private = BooleanField()

    class Meta(BaseModel.Meta):
        table_name = "posts"

    def new(link, title, author, time=None, content=None, tags=None, private=False):
        return Post.create(
            title=title,
            link=link,
            author_id=author,
            time=time if time is not None else datetime.now(),
            content=content,
            private=private
        )

    def tag_exclude(excl_tags):
        """For handling the case where it's just exclusions."""
        
        excl_posts = Post.select().join(TagMap).join(Tag).where(
            (Post.id == TagMap.post_id) &
            (TagMap.tag_id == Tag.id) &
            (Tag.name << excl_tags)
        ).group_by(Post.id)
        
        posts = Post.select().where(~(Post.id << excl_posts))
        return [p.to_dict() for p in posts]

    def tag_query(tag_names, excl_tags, intersection=False):
        tags = tuple([str(tag) for tag in tag_names])

        excl_posts = Post.select().join(TagMap).join(Tag).where(
            (Post.id == TagMap.post_id) &
            (TagMap.tag_id == Tag.id) &
            (Tag.name << excl_tags)
        ).group_by(Post.id)
                
        posts = Post.select().join(TagMap).join(Tag).where(
            (TagMap.tag_id == Tag.id) &
            (Tag.name << tags) &
            (Post.id == TagMap.post_id) &
            ~(Post.id << excl_posts)
        ).group_by(Post.id)
        if intersection:
            posts = posts.having(fn.Count(Post.id) == len(tags))

        return [p.to_dict() for p in posts]

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "author": self.author_id.nick,
            "time": self.time.timestamp(),
            "content": self.content,
            "num_comments": sum(c.tree_size() for c in self.comments),
            "tags": [t.tag_id.name for t in self.tags],
            "private": self.private
        }

class Tag(BaseModel):
    id = AutoField(primary_key=True)
    name = TextField()

    class Meta(BaseModel.Meta):
        table_name = "tags"

class TagMap(BaseModel):
    id = AutoField(primary_key=True)
    post_id = ForeignKeyField(Post, backref="tags")
    tag_id = ForeignKeyField(Tag, backref="posts")

    class Meta(BaseModel.Meta):
        table_name = "tagmaps"

class Comment(BaseModel):
    id = AutoField(primary_key=True)
    time = DateTimeField()
    post_id = ForeignKeyField(Post, backref="comments")
    parent_id = ForeignKeyField('self', null=True, backref="children")
    author_id = ForeignKeyField(User, backref="comments")
    content = TextField()
    private = BooleanField()

    class Meta(BaseModel.Meta):
        table_name = "comments"

    def new(post, author, content, parent=None, time=None, private=False):
        return Comment.create(
            post_id=post,
            author_id=author,
            content=content,
            parent_id=parent,
            time=time if time is not None else datetime.now(),
            private=private
        )

    def to_flat_dict(self):            
        return {
            "id": self.id,
            "post_id": self.post_id.id,
            "author": self.author_id.nick,
            "time": self.time.timestamp(),
            "content": self.content,
            "private": self.private
        }        
    
    def to_mini_dict(self):
        return {
            "id": self.id,
            "author": self.author_id.nick,
            "time": self.time.timestamp(),
            "content": self.content,
            "children": [c.to_mini_dict() for c in self.children],
            "private": self.private
        }        

    def tree_size(self):
        if len(self.children) == 0:
            return 1
        return sum(c.tree_size() for c in self.children)
            
