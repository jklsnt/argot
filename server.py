import itertools

from flask import Flask, request, abort
from marshmallow import Schema, ValidationError, fields
from flask_cors import CORS
from flask_login import *

import argot
from argot.models import *

from io import StringIO
import sys

from bs4 import BeautifulSoup
import urllib
from collections import defaultdict

app = Flask(__name__)
app.config["SECRET_KEY"] = "uh idk whats secret"
CORS(app, supports_credentials=True)
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.select().where(User.id == int(user_id)).get()

def ago(x):
    return datetime.now()-x.time

class PostSchema(Schema):
    title = fields.Str(required=True)
    link = fields.Url(required=True)
    content = fields.Str(required=True)
    private = fields.Bool(required=True)
    tags = fields.List(fields.Int(), required=True)

class CommentSchema(Schema):
    post = fields.Int(required=True)
    content = fields.Str(required=True)
    parent = fields.Int()
    private = fields.Bool()

class PostsQuerySchema(Schema):
    pg = fields.Int()

class LoginSchema(Schema):
    nick = fields.Str(required=True)
    password = fields.Str(required=True)

class SignupSchema(Schema):
    nick = fields.Str(required=True)
    password = fields.Str(required=True)
    bio = fields.Str()
    email = fields.Email()

notifs = defaultdict(set)

@app.route("/posts/<post_id>", methods=["GET"])
def get_post(post_id):
    post_id = int(post_id)
    if len(Post.select().where(Post.id == post_id)) == 0:
        return f"A post with the ID {post_id} does not exist!", 404
    p = Post.select().where(Post.id == post_id).get().to_dict()
    cs = Comment.select().where((Comment.post_id == post_id) & (Comment.parent_id == None))
    if not current_user.is_authenticated:
        cs = filter(lambda c: not c.private, cs)
    cs = [c.to_mini_dict() for c in cs]
    p["comments"] = cs

    return p, 200

@app.route("/comments/<comment_id>", methods=["GET"])
def get_comment(comment_id):
    comment_id = int(comment_id)
    if len(Comment.select().where(Comment.id == comment_id)) == 0:
        return f"A comment with the ID {comment_id} does not exist!", 404
    c = Comment.select().where(Comment.id == comment_id).get().to_dict()
    return c.to_flat_dict(), 200

@app.route("/posts/<post_id>", methods=["PUT"])
def update_post(post_id):
    post_id = int(post_id)
    req = request.json
    
    try:
        PostSchema().validate(req)
    except ValidationError:
        return "Type check failed!", 400
    
    if len(Post.select().where(Post.id == post_id)) == 0:
        return f"A post with the ID {post_id} does not exist!", 404
    
    p = Post.select().where(Post.id == post_id).get()
    if "title" in req:
        p.title = req["title"]
    if "link" in req:
        p.link = req["link"]
    if "content" in req:
        p.content = req["content"]
    p.save()

    return "", 200

@app.route("/posts/<post_id>", methods=["DELETE"])
@login_required
def delete_post(post_id):
    post_id = int(post_id)

    if len(Post.select().where(Post.id == post_id)) == 0:
        return f"A post with the ID {post_id} does not exist!", 404

    post = Post.get(Post.id == post_id)
    if post.author_id.id != current_user.id:
        return "Not yours to delete!", 403    

    TagMap.delete().where(TagMap.post_id == post_id).execute()    
    post.delete_instance()
    
    return "", 200

@app.route("/posts", methods=["POST"])
@login_required
def add_post():
    req = request.json

    try:
        PostSchema().validate(req)
    except ValidationError:
        return "Type check failed!", 400

    if "title" not in req or req["title"] == "":
        if "link" not in req:
            return "Can't guess title.", 400

        src = urllib.request.urlopen(req["link"])
        soup = BeautifulSoup(src, "html")
        title = soup.title.string
    else:
        title = req["title"]

    tags = list(set(req["tags"]))
    for tag in tags:
        if len(Tag.select().where(Tag.id == tag)) == 0:
            return f"Tag {tag} doesn't exist.", 404

    p = Post.new(
        req["link"],
        title,
        current_user.id,
        content=req["content"],
        private=req["private"],
    )

    for tag in tags:
        TagMap.create(post_id=p.id, tag_id=tag)
    
    return str(p.id), 200

@app.route("/comments", methods=["POST"])
@login_required
def add_comment():
    req = request.json
    try:
        CommentSchema().validate(req)
    except ValidationError:
        return "Type check failed!", 400

    if len(Post.select().where(Post.id == int(req["post"]))) == 0:
        return f"A post with the ID {post_id} does not exist!", 404

    if "parent" in req:
        post = Post.select().where(Post.id == req['post']).get()
        ids = [c.id for c in post.comments]
        if int(req["parent"]) not in ids:
            return f"Can't reply to comment from other post.", 400

    c = Comment.new(
        req["post"],
        current_user.id,
        req["content"],
        parent=req["parent"] if "parent" in req else None,
        private=req["private"] if "private" in req else False,
    )

    if "parent" in req:
        notifs[int(req["parent"])].append(c.id)
    else:
        orig_author = Post.select().where(Post.id == req['post']).get().author_id
        notifs[author_id].append(c.id)

    return str(c.id), 200


@app.route("/inbox", methods=["GET"])
@login_required
def get_inbox():
    return list(notifs[current_user]), 200

@app.route("/inbox/read/<comment_id>", methods=["POST"])
@login_required
def mark_read(comment_id):
    try:
        notifs[current_user].remove(int(comment_id))
        return "", 200
    except KeyError:
        return "Not in inbox!", 404

@app.route("/inbox/size", methods=["GET"])
@login_required
def get_inbox_sz():
    return len(notifs[current_user]), 200

@app.route("/comments/<comment_id>", methods=["PUT"])
@login_required
def update_comment(comment_id):
    req = request.json
    comment_id = int(comment_id)
    
    if "content" not in req:
        return "Need new content.", 400    

    query = Comment.select().where(Comment.id == comment_id)
    if len(query) == 0:
        return f"A comment with the ID {comment_id} does not exist!", 404

    c = query.get()
    c.content = req["content"]
    c.save()
    
    return "", 200

@app.route("/comments/<comment_id>", methods=["DELETE"])
@login_required
def delete_comment(comment_id):
    comment_id = int(comment_id)

    if len(Comment.select().where(Comment.id == comment_id)) == 0:
        return f"A comment with the ID {comment_id} does not exist!", 404

    comment = Comment.get(Comment.id == comment_id)
    if comment.author_id.id != current_user.id:
        return "Not yours to delete!", 403    
    
    comment.content = "[deleted]"
    comment.save()
    
    return "", 200


@app.route("/login", methods=["POST"])
def login():
    req = request.json

    try:
        LoginSchema().validate(req)
    except ValidationError:
        return "Type check failed!", 400

    user = User.select().where(User.nick == req["nick"])

    if len(user) == 0:
        return "No such user.", 400
    user = user.get()

    hash = hashlib.scrypt(
        req["password"].encode(), salt=user.salt.encode(), n=16384, r=8, p=1
    ).hex()
    if user.hash != hash:
        return "Invalid password.", 403

    print(f"Logged in {user.nick}")
    login_user(user)
    return {"nick": user.nick, "id": user.id}, 200

@app.route("/signup", methods=["POST"])
def signup():
    req = request.json

    try:
        SignupSchema().validate(req)
    except ValidationError:
        return "Type check failed!", 400

    user = User.select().where(User.nick == req["nick"])
    if len(user) != 0:
        return f"User with nick '{req['nick']}' already exists!", 400

    # TODO: This is a very scuffed system for enforcing a whitelist.
    whitelist = [l.strip() for l in open("./whitelist").readlines()]
    if req["nick"] not in whitelist:
        return "Not on the whitelist.", 403

    User.new(
        req["nick"], req["password"],
        bio = req["bio"] if "bio" in req else None,
        email = req["email"] if "email" in req else None,
    )
    return "", 200

@app.route("/tags/<name>", methods=["POST"])
@login_required
def add_tag(name):
    name = str(name)
    if not name.isalnum():
        return "Invalid character in tag name.", 400
    if len(Tag.select().where(Tag.name == name)) != 0:
        return "Tag already exists.", 400

    t = Tag.create(name=name)
    return str(t.id), 200

@app.route("/tags", methods=["GET"])
def get_tags():
    out = [{"name": t.name, "id": t.id} for t in Tag.select()]    
    return out, 200

@app.route("/users/<user_name>", methods=["GET"])
def get_user(user_name):    
    query = User.select().where(User.nick == str(user_name))
    if len(query) == 0:
        return "No such user.", 404
    user = query.get()
    posts = sorted(user.posts, key=ago)
    comments = sorted(user.comments, key=ago)
    if not current_user.is_authenticated:
        posts = filter(lambda p: not p.private, posts)
        comments = filter(lambda c: not c.private, comments)
    
    out = {
        "nick": user.nick,
        "bio": user.bio,
        "posts": [p.to_dict() for p in posts],
        "comments": [c.to_flat_dict() for c in comments],
    }
    
    return out, 200

@app.route("/posts/<post_id>/tags", methods=["PUT"])
@login_required
def add_post_tag(post_id):
    if len(Post.select().where(Post.id == post_id)) == 0:
        return f"A post with the ID {post_id} does not exist!", 404
    if "name" not in request.args:
        return "Need a tag name!", 400
    tag_name = str(request.args["name"])

    tq = Tag.select().where(Tag.name == tag_name)
    if len(tq) == 0:
        return f"A tag with the name {tag_name} does not exist!", 404
    tag = tq.get()

    query = TagMap.select().where(
        (TagMap.post_id == post_id) & (TagMap.tag_id == tag.id)
    )
    if len(query) != 0:
        i = query.get()
        return str(query.get().id), 200

    tm = TagMap.create(post_id=post_id, tag_id=tag.id)
    return str(tm.id), 200

@app.route("/posts/search", methods=["PUT"])
def search_posts():
    term = request.data.decode()    
    posts = Post.select().where(Match(Post.content, term))
    posts_titles = Post.select().where(Match(Post.title, term))
    posts_links = Post.select().where(Match(Post.link, term))
    if not current_user.is_authenticated:
        posts = list(filter(lambda p: not p.private, posts))
        posts_titles = list(filter(lambda p: not p.private, posts_titles))
        posts_links = list(filter(lambda p: not p.private, posts_links))

    posts = list(set(posts+posts_titles+posts_links))    
    posts = sorted(list(posts), key=ago)
    return [p.to_dict() for p in posts], 200

@app.route("/comments/search", methods=["PUT"])
def search_comments():
    term = request.data.decode()    
    cs = Comment.select().where(Match(Comment.content, term))
    if not current_user.is_authenticated:
        cs = filter(lambda c: not c.private, cs)
    cs = sorted(list(cs), key=ago)    
    return [c.to_flat_dict() for c in cs], 200

@app.route("/posts/query", methods=["PUT"])
def query_posts():
    query = request.data.decode()
    intersection = None

    tags = []
    excl = []
    excluding = False
    pos = 0
    # Real gross, I know. I swear it's just a quick hack.
    for i, c in enumerate(query):
        if c == '|' and intersection is None:
            intersection = False
        elif c == '+' and intersection is None:
            intersection = True
        elif c == '+' and intersection == False:
            return "Mixing and matching +/| operators not supported!", 400
        elif c == '|' and intersection == True:
            return "Mixing and matching +/| operators not supported!", 400
        if c in ('|', '+'):            
            tags.append(query[pos:i])
            pos = i + 1
        elif c == '-':
            if excluding: excl.append(query[pos:i])
            else:
                tags.append(query[pos:i])
                excluding = True
            pos = i + 1
    if excluding: excl.append(query[pos:])
    else: tags.append(query[pos:])

    # NOTE: the way the parsing works means that just exclusions
    # should erroneously result in an empty first exclusion tag
    if tags[0] == '':        
        res = Post.tag_exclude(excl)
    else:
        res = Post.tag_query(tags, excl, intersection=intersection)
    return res, 200

@app.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return "", 200

# page_size = 10

@app.route("/posts", methods=["GET"])
def get_posts():
    try:
        PostsQuerySchema().validate(request.args)
    except ValidationError:
        return "Type check failed!", 400

    page = int(request.args["pg"]) if "pg" in request.args else 0
    ps = Post.select().order_by(Post.time.desc())
    # ps = itertools.islice(ps, page_size*page, page_size*(page+1))

    if not current_user.is_authenticated:
        ps = filter(lambda p: not p.private, ps)
    
    return [p.to_dict() for p in ps], 200

if __name__ == '__main__':
    app.run(debug=True)
