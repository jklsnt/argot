import itertools

from flask import Flask, request, abort
from flask_restful import Api, Resource
from marshmallow import Schema, ValidationError, fields
from flask_sock import Sock

import argot
from argot.models import *

from io import StringIO
import sys

from bs4 import BeautifulSoup
import urllib

app = Flask(__name__)
api = Api(app)
sock = Sock(app)
sock.init_app(app)

class PostQuerySchema(Schema):    
    id = fields.UUID(required=True)

class PostSchema(Schema):    
    title = fields.Str()
    link = fields.Url()
    author = fields.Str(required=True)
    # tags = fields.List(fields.Str())

class PostsQuerySchema(Schema):    
    pg = fields.Int()
    # tags = fields.List(fields.Str())
    
    
postq_schema = PostQuerySchema()
    
def assert_task_valid(post_id):
    if len(Post.select().where(Post.id == post_id)) == 0:
        abort(404, message=f"A post with the ID {post_id} does not exist!")

class PostEndpoint(Resource):
    def get(self):
        try: 
            postq_schema.load(request.args)
        except ValidationError:
            return "Type check failed!", 400
        
        assert_task_valid(request.args['id'])        
        p = Post.select().where(Post.id == request.args['id']).get()
        return p.to_dict(), 200

    def post(self):
        try:
            PostSchema().validate(request.args)
        except ValidationError:
            return "Type check failed!", 400

        
        if "title" not in request.args:
            if "link" not in request.args:
                return "Can't guess title.", 400

            soup = urllib.request.urlopen(request.args["link"])
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
            
page_size = 10

class PostListEndpoint(Resource):
    def get(self):
        try:
            PostsQuerySchema().validate(request.args)
        except ValidationError:
            return "Type check failed!", 400

        page = int(request.args["pg"]) if "pg" in request.args else 0                
        ps = Post.select().order_by(Post.posted.desc())
        ps = itertools.islice(ps, page_size*page, page_size*(page+1))
        return [p.to_dict() for p in ps], 200 
    
api.add_resource(PostEndpoint, '/post')
api.add_resource(PostListEndpoint, '/posts')
# api.add_resource(TaskListEndpoint, '/tasks')

if __name__ == '__main__':
    app.run(debug=True)
