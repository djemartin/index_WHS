from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, PasswordField, SubmitField, DateField, SelectField
from wtforms.validators import DataRequired, NumberRange


class LoginForm(FlaskForm):
    username = StringField('Nom utilisateur', validators=[DataRequired()])
    submit = SubmitField('Connexion')


class GolfForm(FlaskForm):
    name = StringField('Nom', validators=[DataRequired()])
    course = StringField('Parcours', validators=[DataRequired()])
    par = IntegerField('Par', validators=[DataRequired()])
    tees = StringField('Tees', validators=[DataRequired()])
    slope = IntegerField('Slope', validators=[DataRequired()])
    sss = FloatField('SSS', validators=[DataRequired()])
    submit = SubmitField('Enregistrer')


class TourForm(FlaskForm):
    name = StringField('Nom', validators=[DataRequired()])
    jour = IntegerField('Jour', validators=[DataRequired()])
    date = DateField('Date', validators=[DataRequired()])
    golf = SelectField('Golf', coerce=int, validators=[DataRequired()])
    par = IntegerField('Par', validators=[DataRequired()])
    slope = IntegerField('Slope', validators=[DataRequired()])
    sss = FloatField('SSS', validators=[DataRequired()])
    pcc = IntegerField('PCC', default=0)
    submit = SubmitField('Enregistrer')
