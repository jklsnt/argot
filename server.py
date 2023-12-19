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

app = Flask(__name__)
app.config["SECRET_KEY"] = "uh idk whats secret"
CORS(app)
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.select().where(User.id == int(user_id)).get()

class PostQuerySchema(Schema):    
    id = fields.Int(required=True)

class PostSchema(Schema):    
    title = fields.Str()
    link = fields.Url()
    content = fields.Str()
    # tags = fields.List(fields.Str())

class CommentSchema(Schema):    
    post = fields.Int(required=True)    
    content = fields.Str(required=True)
    parent = fields.Int()
    
class PostsQuerySchema(Schema):    
    pg = fields.Int()

class LoginSchema(Schema):    
    nick = fields.Str(required=True)
    password = fields.Str(required=True)    
    
def assert_post_valid(post_id):
    if len(Post.select().where(Post.id == post_id)) == 0:
        abort(404, message=f"A post with the ID {post_id} does not exist!")

@app.route("/post", methods=["GET"])        
def get_post():
    try: 
        PostQuerySchema().validate(request.args)
    except ValidationError:
        return "Type check failed!", 400

    assert_post_valid(request.args['id'])
    p = Post.select().where(Post.id == request.args['id']).get().to_dict()
    cs = Comment.select().where(Comment.post_id == request.args['id'] and Comment.parent_id == None)
    cs = [c.to_mini_dict() for c in cs]                            
    p["comments"] = cs    

    return p, 200

@app.route("/post", methods=["POST"])
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

    p = Post.new(
        req["link"] if "link" in req else None,
        title,
        current_user.id,
        content=req["content"],
    )

    return str(p.id), 200

@app.route("/comment", methods=["POST"])
@login_required
def add_comment():
    req = request.json

    try: 
        CommentSchema().validate(req)
    except ValidationError:
        return "Type check failed!", 400        

    assert_post_valid(req['post'])

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
    )

    return str(c.id), 200

@app.route("/login", methods=["POST"])
def login():
    req = request.json

    try:
        LoginSchema().validate(req)
    except ValidationError:
        return "Type check failed!", 400        

    # NOTE: assumes no repeat usernames (enforce this?)
    user = User.select().where(User.nick == req["nick"])

    if len(user) == 0:
        return "No such user.", 400
    user = user.get()

    hash = hashlib.scrypt(
        req["password"].encode(), salt=user.salt.encode(), n=16384, r=8, p=1
    ).hex()
    if user.hash != hash:
        return "Invalid password.", 403

    login_user(user)
    return "", 200


@app.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return "", 200
    
page_size = 10

@app.route("/posts", methods=["GET"])
def get_posts():
    try:
        PostsQuerySchema().validate(request.args)
    except ValidationError:
        return "Type check failed!", 400

    page = int(request.args["pg"]) if "pg" in request.args else 0                
    ps = Post.select().order_by(Post.time.desc())
    ps = itertools.islice(ps, page_size*page, page_size*(page+1))
    return [p.to_dict() for p in ps], 200 
    
# api.add_resource(TaskListEndpoint, '/tasks')

if __name__ == '__main__':
    app.run(debug=True)
