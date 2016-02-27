from flask import Flask, render_template, request, redirect,jsonify, url_for, flash
app = Flask(__name__)

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import User, Organizer, Event, Base

from flask import session as login_session
import random, string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

from datetime import datetime

CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())['web']['client_id']

#Connect to Database and create database session
engine = create_engine('sqlite:///events.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['provider'] = 'google'
    login_session['credentials'] = credentials
    login_session['gplus_id'] = gplus_id
    response = make_response(json.dumps('Successfully connected user', 200))

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = json.loads(answer.text)

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # See if user exists, if it does not make a new one.
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

# Disconnect - Revoke a user's access
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['credentials']
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']

        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have Successfully been logged out.")
        return redirect(url_for('showOrganizers'))
    else:
        flash("You were not logged in to begin with.")
        redirect(url_for('showOrganizers'))


@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Execute HTTP Get to revoke current token
    access_token = credentials.access_token
    print access_token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    if result['status'] == '200':
        # Reset the user's session
        del login_session['credentials']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']

        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        # For whatever reason, the given token was invalid
        response = make_response(json.dumps('Failed to revoke token for the given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response

@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print request.data
    access_token = request.data
    print "access token received = %s " % access_token

    app_id = json.loads(open('fb_client_secrets.json', 'r').read())[
        'web']['app_id']
    app_secret = json.loads(
        open('fb_client_secrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
        app_id, app_secret, access_token)
    print "url = %s" % url
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    print "result = %s" % result
    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.4/me"
    # strip expire tag from access token
    token = result.split("&")[0]


    url = 'https://graph.facebook.com/v2.4/me?%s&fields=name,id,email' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly logout, let's strip out the information before the equals sign in our token
    stored_token = token.split("=")[1]
    login_session['access_token'] = stored_token

    # Get user picture
    url = 'https://graph.facebook.com/v2.4/me/picture?%s&redirect=0&height=200&width=200' % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '

    flash("Now logged in as %s" % login_session['username'])
    return output

@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    url = 'https://graph.facebook.com/%s/permissions' % facebook_id
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    del login_session['username']
    del login_session['email']
    del login_session['picture']
    del login_session['user_id']
    del login_session['facebook_id']
    return "You have been logged out"
###

def createUser(login_session):
    newUser = User(name = login_session['username'], email = login_session['email'], picture = login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email = login_session['email']).one()
    return user.id

def getUserInfo(user_id):
    user = session.query(User).filter_by(id = user_id).one()
    return user

def getUserID(email):
    try:
        user = session.query(User).filter_by(email = email).one()
        return user.id
    except:
        return None

# JSON APIs to view Organizer Information
@app.route('/organizer/<int:organizer_id>/event/JSON')
def organizerEventsJSON(organizer_id):
    organizer = session.query(Organizer).filter_by(id = organizer_id).one()
    events = session.query(Event).filter_by(organizer_id = organizer_id).all()
    return jsonify(Events=[e.serialize for e in events])


@app.route('/organizer/<int:organizer_id>/event/<int:event_id>/JSON')
def eventJSON(organizer_id, event_id):
    event = session.query(Event).filter_by(id = event_id).one()
    return jsonify(event = Event.serialize)


@app.route('/organizer/JSON')
def organizersJSON():
    organizers = session.query(Organizer).all()
    return jsonify(organizers= [o.serialize for o in organizers])


# Show all organizers
@app.route('/')
@app.route('/organizer/')
def showOrganizers():
    organizers = session.query(Organizer).order_by(asc(Organizer.name))
    if 'username' not in login_session:
        return render_template('publicOrganizers.html', organizers = organizers)
    else:
        return render_template('organizers.html', organizers = organizers)
    return render_template('organizers.html', organizers = organizers)

# Create a new organizer
@app.route('/organizer/new/', methods=['GET','POST'])
def newOrganizer():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        organizer_thumbnail_url = request.form['organizer_thumbnail_url']
        if not organizer_thumbnail_url:
            organizer_thumbnail_url = "http://818397471.r.worldcdn.net/wp-content/uploads/2015/01/Dj-Logo-Design-For-Sale.png"
        newOrganizer = Organizer(name = request.form['name'], organizer_thumbnail_url = organizer_thumbnail_url, user_id = login_session['user_id'])
        session.add(newOrganizer)
        flash('New Organizer %s Successfully Created' % newOrganizer.name)
        session.commit()
        return redirect(url_for('showOrganizers'))
    else:
        return render_template('newOrganizer.html')

# Edit an organizer
@app.route('/organizer/<int:organizer_id>/edit/', methods = ['GET', 'POST'])
def editOrganizer(organizer_id):
  editedOrganizer = session.query(Organizer).filter_by(id = organizer_id).one()
  if request.method == 'POST':
      if request.form['name']:
        editedOrganizer.name = request.form['name']
        flash('Organizer Successfully Edited %s' % editedOrganizer.name)
        return redirect(url_for('showOrganizers'))
  else:
    return render_template('editOrganizer.html', organizer = editedOrganizer)


# Delete an organizer
@app.route('/organizer/<int:organizer_id>/delete/', methods = ['GET','POST'])
def deleteOrganizer(organizer_id):
  organizerToDelete = session.query(Organizer).filter_by(id = organizer_id).one()

  if 'username' not in login_session:
      return redirect('/login')
  if organizerToDelete.user_id != login_session['user_id']:
      return "<script>function myFunction() {alert('You are not \
      authorized to delete this organizer. ');}</script> <body onload='myFunction()'>"
  if request.method == 'POST':
    session.delete(organizerToDelete)
    organizerEvents = session.query(Event).filter_by(organizer_id = organizer_id).all()
    for organizerEvent in organizerEvents:
        eventToDelete = session.query(Event).filter_by(id = organizerEvent.id).one()
        session.delete(eventToDelete)

    flash('%s Successfully Deleted' % organizerToDelete.name)
    session.commit()
    return redirect(url_for('showOrganizers', organizer_id = organizer_id))
  else:
    return render_template('deleteOrganizer.html',organizer = organizerToDelete)

# Show an event
@app.route('/organizer/<int:organizer_id>/')
@app.route('/organizer/<int:organizer_id>/event/')
def showEvent(organizer_id):
    organizer = session.query(Organizer).filter_by(id = organizer_id).one()
    creator = getUserInfo(organizer.user_id)
    events = session.query(Event).filter_by(organizer_id = organizer_id).all()
    if 'username' not in login_session or creator.id != login_session['user_id']:
        return render_template('publicEvent.html', events = events, organizer = organizer, creator = creator)
    else:
        return render_template('event.html', events = events, organizer = organizer, creator = creator)
    return render_template('event.html', events = events, organizer = organizer)

# Create a new event
@app.route('/organizer/<int:organizer_id>/event/new/', methods=['GET','POST'])
def newEvent(organizer_id):
  organizer = session.query(Organizer).filter_by(id = organizer_id).one()
  if request.method == 'POST':
      if not 'featured' in request.form:
        featured = 0
      if None or '' in request.form.values():
        flash('Please make sure that you have entered all necessary data for all form fields.')
        return render_template('newEvent.html')

      newEvent = Event(
                    name = request.form['name'],
                    description = request.form['description'],
                    event_url = request.form['event_url'],
                    event_thumbnail_url = request.form['event_thumbnail_url'],
                    ticket_price = request.form['ticket_price'],
                    start_date = datetime.strptime(request.form['start_date'], '%Y-%M-%d'),
                    featured = featured,
                    organizer_id = organizer_id,
                    user_id = organizer.user_id
                    )
      session.add(newEvent)
      session.commit()
      flash('New Event %s Successfully Created' % (newEvent.name))
      return redirect(url_for('showEvent', organizer_id = organizer_id))
  else:
      return render_template('newEvent.html', organizer_id = organizer_id)

# Edit an event
@app.route('/organizer/<int:organizer_id>/event/<int:event_id>/edit', methods=['GET','POST'])
def editEvent(organizer_id, event_id):

    editedEvent = session.query(Event).filter_by(id = event_id).one()
    organizer = session.query(Organizer).filter_by(id = organizer_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedEvent.name = request.form['name']
        if request.form['description']:
            editedEvent.description = request.form['description']
        if request.form['event_url']:
            editedEvent.event_url = request.form['event_url']
        if request.form['event_thumbnail_url']:
            editedEvent.event_thumbnail_url = request.form['event_thumbnail_url']
        if request.form['ticket_price']:
            editedEvent.ticket_price = request.form['ticket_price']
        if request.form['start_date']:
            editedEvent.start_date = datetime.strptime(request.form['start_date'], '%Y-%M-%d')
        if request.form['featured']:
            editedEvent.featured = request.form['featured']

        session.add(editedEvent)
        session.commit()
        flash('Event Successfully Edited')
        return redirect(url_for('showEvent', organizer_id = organizer_id))
    else:
        return render_template('editEvent.html', organizer_id = organizer_id,
                                event_id = event_id, event = editedEvent)

# Delete an event
@app.route('/organizer/<int:organizer_id>/event/<int:event_id>/delete', methods = ['GET','POST'])
def deleteEvent(organizer_id, event_id):
    organizer = session.query(Organizer).filter_by(id = organizer_id).one()
    eventToDelete = session.query(Event).filter_by(id = event_id).one()
    if request.method == 'POST':
        session.delete(eventToDelete)
        session.commit()
        flash('Event Successfully Deleted')
        return redirect(url_for('showEvent', organizer_id = organizer_id))
    else:
        return render_template('deleteEvent.html', event = eventToDelete)

if __name__ == '__main__':
  app.secret_key = 'super_secret_key'
  app.debug = True
  app.run(host = '0.0.0.0', port = 5000)
