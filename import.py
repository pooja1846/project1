import csv
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine("postgres://sdbnynywlkbuwj:30693d76441fc30cd14bafc55a06c5d69da7db4f93b5814adfac2c0b9228e792@ec2-3-91-139-25.compute-1.amazonaws.com:5432/dmbdpe144drlf")
db = scoped_session(sessionmaker(bind=engine))

def main():
    f = open("books.csv")
    reader = csv.reader(f)
    for isbn, title, author, year in reader:
        db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
                    {"isbn": isbn, "title": title, "author": author, "year": year })
        print(f"Added book {title}")
    db.commit()

if __name__ == "__main__":
        main()
