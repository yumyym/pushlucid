from __future__ import with_statement
import time
import os
from sqlite3 import dbapi2 as sqlite3
from hashlib import md5
from datetime import datetime
from contextlib import closing
from flask import Flask, request, session, url_for, redirect, \
     render_template, abort, g, flash
from werkzeug import check_password_hash, generate_password_hash

# configuration
DATABASE = 'lucid.db'
PER_PAGE = 30
DEBUG = True
SECRET_KEY = 'development key'

app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('LUCID_SETTINGS', silent = True)

# global variables

V = ["personally identifying", "sensitive pi", "aggregate/non-pi", "device-specific", "location", "log/usage", "application-specific", "trackers"]
H = ["provide service", "improve service", "filter content", "target ads", "third parties", "merger/acquisition"]
RV = range(0,len(V))
RH = range(0,len(H))

# sqlite3 functions

def connect_db():
    """Returns a new connection to the database."""
    return sqlite3.connect(app.config['DATABASE'])

def init_db():
    """Creates the database tables."""
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql') as f:
            db.cursor().executescript(f.read())
        db.commit()

def query_db(query, args=(), one=False):
    cur = g.db.execute(query, args)
    rv = [dict((cur.description[idx][0], value)
               for idx, value in enumerate(row)) for row in cur.fetchall()]
    return (rv[0] if rv else None) if one else rv

def sqlinsertall():
    command = "insert into entries (title"
    rest = ["compliance","link","parent"]
    for i in RV:
        for j in RH:
            rest.append("q"+str(i)+"_"+str(j))
    for x in rest:
        command = command + ", " + x
    command = command + ")"
    command = command + " values ("
    quests = "?,"*(len(V)*len(H)+3)
    quests = quests + "?)"
    command = command + quests
    return command

def sqlupdatebytitle(title):
    command = "update entries set compliance=?"
    rest = ["link", "parent"]
    for i in RV:
        for j in RH:
            rest.append("q"+str(i)+"_"+str(j))
    for x in rest:
        command = command + ", " + x + "=?"
    command = command + " where title='" + title + "'"
    return command

def fields():
    x = ['compliance','link','parent']
    for i in RV:
        for j in RH:
            x.append("q"+str(i)+"_"+str(j))
    return x

@app.before_request
def before_request():
    """Make sure we are connected to the database each request."""
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'db'):
        g.db.close()

# home page
@app.route('/')
def home():
    return render_template('index.html')

# shows all policies we've documented
@app.route('/showall')
def showall():
    cur = g.db.execute('select title from entries order by id desc')
    entries = [dict(title = row[0]) for row in cur.fetchall()]
    return render_template('show_all.html', entries = entries)

# submit.html should pass to url_for submit()
@app.route('/submit')
def submitin():
    return render_template('submit.html')

@app.route('/guide')
def guide():
    return render_template('guide.html')

@app.route('/upcoming')
def upcoming():
    return render_template('upcoming.html')

# receives input from submit.html, passes either to create or edit
@app.route('/submitting', methods=['POST'])
def submit_form():
    exists = query_db('select * from entries where title = ?', [request.form['title']], True)
    if exists is None:
        return redirect(url_for('create', company=request.form['title']))
    else:
        return redirect(url_for('edit', company=request.form['title']))

# form should pass to writenew
@app.route('/create/<company>')
def create(company):
    return render_template('create.html', company=company, V=V, H=H, RV=RV, RH=RH)

# form should pass to writeold
@app.route('/edit/<company>')
def edit(company):
    query = "select * from entries where title = ?"
    entry = query_db(query, [company], True)
    if entry is None:
        return redirect('/booboo')
    return render_template('edit.html', entry=entry, V=V, H=H, RV=RV, RH=RH)

@app.route('/writenew', methods=['GET','POST'])
def writenew():
    company = request.args.get('company','')
    command = sqlinsertall()
    f = fields()
    y = [request.form[x] for x in f]
    y.insert(0, company)
    g.db.execute(command, y)
    g.db.commit()
    return redirect(url_for('show', company=company))

@app.route('/writeold', methods=['POST'])
def writeold():
    company = request.args.get('company','')
    command = sqlupdatebytitle(company)
    g.db.execute(command, [request.form[x] for x in fields()])
    g.db.commit()
    return redirect(url_for('show', company=company))

@app.route('/show/<company>')
def show(company):
    query = "select * from entries where title = ?"
    entry = query_db(query, [company], True)
    cquery = "select title from entries where parent = ?"
    pquery = "select title from entries where link = ?"
    children = []
    for x in query_db(cquery, [entry['link']]):
        children.append(x['title'])
    parent = query_db(pquery, [entry['parent']], True)
    pname = []
    if not parent is None:
        pname.append(parent['title'])
    if entry is None:
        return redirect('/booboo')
    else:
        return render_template('show.html', entry=entry, children=children, parent=pname, V=V, H=H, RV=RV, RH=RH)

@app.route('/csv/<company>')
def givecsv(company):
    query = "select * from entries where title = ?"
    entry = query_db(query, [company], True)
    if entry is None:
        return redirect('/booboo')
    cols = ",".join(H)
    cols = "type,"+cols
    cols = [cols]
    for i in RV:
        z = [V[i]]
        for j in RH:
            z.append(entry["q"+str(i)+"_"+str(j)])
        cols.append(",".join(z))
    return render_template('csv.html', entry=cols)

# ERROR PAGE HEHEH
@app.route('/booboo')
def booboo():
    return render_template('booboo.html')

if __name__ == '__main__':
    app.run()
