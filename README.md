# WHS Golf Tracking Application

This Flask app lets you record golf rounds and scores.
You can also manage information about each golf course.

Key features:
- Full CRUD management for tours with per-hole par values, a day number and a date.
- Manage golf courses (name, course, par, slope, SSS and per-hole pars).
- Input scores for each hole of a tour.
- Quick creation of a tour using "Nouvelle Carte" to jump directly to score entry.
- View, edit and delete existing tours from the home page.
- Statistics for each scorecard are stored in their own TinyDB index.

Install dependencies with:
```
pip install -r requirements.txt
```

Run the app with:
```
python app.py
```
