CREATE TABLE users (
  id         SERIAL PRIMARY KEY,
  nick       TEXT NOT NULL,
  bio        TEXT,
  email		 TEXT,
  hash       TEXT NOT NULL,
  salt       TEXT NOT NULL
);

CREATE TABLE posts (
  id         SERIAL PRIMARY KEY,
  time       TIMESTAMP NOT NULL,
  title      TEXT NOT NULL,
  link       TEXT,
  author_id  INTEGER NOT NULL,
  content    TEXT,
  private    BOOLEAN,
  FOREIGN KEY(author_id) REFERENCES users(id)
);

CREATE INDEX post_content_idx ON posts USING gin(to_tsvector('english', content));

CREATE TABLE tags (
  id         SERIAL PRIMARY KEY,
  name       TEXT NOT NULL
);

CREATE TABLE tagmaps (
  id         SERIAL PRIMARY KEY,
  post_id    INTEGER NOT NULL,
  tag_id     INTEGER NOT NULL,
  FOREIGN KEY(post_id)   REFERENCES posts(id),
  FOREIGN KEY(tag_id)    REFERENCES tags(id)
);

CREATE TABLE comments (
  id         SERIAL PRIMARY KEY,
  time       TIMESTAMP NOT NULL,
  post_id    INTEGER NOT NULL,
  parent_id  INTEGER,
  author_id  INTEGER NOT NULL,
  content    TEXT NOT NULL,
  private    BOOLEAN,
  FOREIGN KEY(post_id)   REFERENCES posts(id),
  FOREIGN KEY(parent_id) REFERENCES comments(id),
  FOREIGN KEY(author_id) REFERENCES users(id)
);

CREATE INDEX comment_content_idx ON comments USING gin(to_tsvector('english', content));
