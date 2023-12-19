CREATE TABLE users (
  id         INTEGER PRIMARY KEY,
  nick       TEXT NOT NULL,
  bio        TEXT,
  email		 TEXT,
  hash       TEXT NOT NULL,
  salt       TEXT NOT NULL
);

CREATE TABLE posts (
  id         INTEGER PRIMARY KEY,
  time       TIMESTAMP NOT NULL,
  title      TEXT NOT NULL,
  linkk       TEXT,
  author_id  INTEGER NOT NULL,
  content    TEXT,
  FOREIGN KEY(author_id) REFERENCES users(id)
);

CREATE TABLE comments (
  id         INTEGER PRIMARY KEY,
  time       TIMESTAMP NOT NULL,
  post_id    INTEGER NOT NULL,
  parent_id  INTEGER,
  author_id  INTEGER NOT NULL,
  content    TEXT NOT NULL,
  FOREIGN KEY(post_id)   REFERENCES posts(id),
  FOREIGN KEY(parent_id) REFERENCES comments(id),
  FOREIGN KEY(author_id) REFERENCES users(id)
);
