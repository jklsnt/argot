CREATE TABLE posts (
  id   	     UUID PRIMARY KEY,
  title	     TEXT NOT NULL,
  link 	     TEXT,
  author     TEXT NOT NULL,
  posted     TIMESTAMP NOT NULL,
  content    TEXT
);
