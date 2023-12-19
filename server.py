import itertools

from flask import Flask, request, abort
from flask_restful import Api, Resource
from marshmallow import Schema, ValidationError, fields
from flask_sock import Sock
from flask_cors import CORS

import argot
from argot.models import *

from io import StringIO
import sys

from bs4 import BeautifulSoup
import urllib

app = Flask(__name__)
CORS(app)
api = Api(app)
sock = Sock(app)
sock.init_app(app)

class PostQuerySchema(Schema):    
    id = fields.Int(required=True)

class PostSchema(Schema):    
    title = fields.Str()
    link = fields.Url()
    author = fields.Int(required=True)
    content = fields.Str()
    # tags = fields.List(fields.Str())

class CommentSchema(Schema):    
    post = fields.Int(required=True)
    author = fields.Int(required=True)
    parent = fields.Int()
    
class PostsQuerySchema(Schema):    
    pg = fields.Int()
    # tags = fields.List(fields.Str())    
    
postq_schema = PostQuerySchema()
    
def assert_post_valid(post_id):
    if len(Post.select().where(Post.id == post_id)) == 0:
        abort(404, message=f"A post with the ID {post_id} does not exist!")

class PostEndpoint(Resource):
    def get(self):
        try: 
            postq_schema.load(request.args)
        except ValidationError:
            return "Type check failed!", 400
        
        assert_post_valid(request.args['id'])
        p = Post.select().where(Post.id == request.args['id']).get().to_dict()
        cs = Comment.select().where(Comment.post_id == request.args['id'] and Comment.parent_id == None)
        cs = [c.to_mini_dict() for c in cs]                            
        p["comments"] = cs    
        
        return p, 200

    def post(self):
        try:
            PostSchema().validate(request.args)
        except ValidationError:
            return "Type check failed!", 400
        
        if "title" not in request.args or request.args["title"] == "":
            if "link" not in request.args:
                return "Can't guess title.", 400

            src = urllib.request.urlopen(request.args["link"])
            soup = BeautifulSoup(src, "html")
            title = soup.title.string            
        else:
            title = request.args["title"]

        p = Post.new(
            request.args["link"] if "link" in request.args else None,
            title,
            request.args["author"],
            content=request.data,
            # tags=request.args["tags"] if "tags" in request.args else []
        )

        return str(p.id), 200

class CommentEndpoint(Resource):
    def post(self):
        try:
            CommentSchema().validate(request.args)
        except ValidationError:
            return "Type check failed!", 400

        if request.data == "":
            return "C'mon, actually say something.", 400

        assert_post_valid(request.args['post'])
        
        if "parent" in request.args:
            post = Post.select().where(Post.id == request.args['post']).get()
            ids = [c.id for c in post.comments]
            if int(request.args["parent"]) not in ids:
                return f"Can't reply to comment from other post.", 400
        
        c = Comment.new(
            request.args["post"],
            request.args["author"],
            request.data,
            parent=request.args["parent"] if "parent" in request.args else None,
        )

        return str(c.id), 200
    
page_size = 10

class PostListEndpoint(Resource):
    def get(self):
        try:
            PostsQuerySchema().validate(request.args)
        except ValidationError:
            return "Type check failed!", 400

        page = int(request.args["pg"]) if "pg" in request.args else 0                
        ps = Post.select().order_by(Post.time.desc())
        ps = itertools.islice(ps, page_size*page, page_size*(page+1))
        return [p.to_dict() for p in ps], 200 
    
api.add_resource(PostEndpoint, '/post')
api.add_resource(CommentEndpoint, '/comment')
api.add_resource(PostListEndpoint, '/posts')
# api.add_resource(TaskListEndpoint, '/tasks')

if __name__ == '__main__':
    app.run(debug=True)
