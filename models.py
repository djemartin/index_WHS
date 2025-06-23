from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin


db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)

    @property
    def doc_id(self):
        """Return id for compatibility with templates expecting doc_id."""
        return self.id


class Golf(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    course = db.Column(db.String(80))
    par = db.Column(db.Integer)
    slope = db.Column(db.Integer)
    sss = db.Column(db.Float)
    tees = db.Column(db.String(20))
    pars = db.Column(db.PickleType)
    hcps = db.Column(db.PickleType)

    @property
    def doc_id(self):
        """Return id for compatibility with templates expecting doc_id."""
        return self.id


class Tour(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    jour = db.Column(db.Integer)
    date = db.Column(db.String(20))
    golf_id = db.Column(db.Integer, db.ForeignKey('golf.id'))
    par = db.Column(db.Integer)
    slope = db.Column(db.Integer)
    sss = db.Column(db.Float)
    pcc = db.Column(db.Integer, default=0)
    pars = db.Column(db.PickleType)
    hcps = db.Column(db.PickleType)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    golf = db.relationship('Golf')
    user = db.relationship('User')

    @property
    def doc_id(self):
        """Return id for compatibility with templates expecting doc_id."""
        return self.id


class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tour_id = db.Column(db.Integer, db.ForeignKey('tour.id'))
    handicap = db.Column(db.Integer)
    holes = db.Column(db.PickleType)

    tour = db.relationship('Tour')

    @property
    def doc_id(self):
        """Return id for compatibility with templates expecting doc_id."""
        return self.id


class Stats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score_id = db.Column(db.Integer, db.ForeignKey('score.id'))
    tour_id = db.Column(db.Integer)
    fairway_hits = db.Column(db.Integer)
    fairway_possible = db.Column(db.Integer)
    gir_hits = db.Column(db.Integer)
    putts_total = db.Column(db.Integer)
    putts_avg = db.Column(db.String(10))
