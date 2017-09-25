from flask import Flask, render_template, flash, request, redirect, url_for, session, logging, json
from pymongo import MongoClient
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps
from bson.objectid import ObjectId
import requests

app = Flask(__name__)

#db config, client is connecting to localhost:27017
client = MongoClient('localhost', 27017)
#select which database to use, in this case flaskapp
db = client.flaskapp

# / route displays home page
@app.route('/')
def index():
    return render_template('home.html')

# about route displays the about page
@app.route('/about')
def about():
    return render_template('about.html')

#articles route
@app.route('/articles')
def articles():
    #select collection in flaskapp db
    col = db.articles
    #articles = all the documents in articles collection
    articles = col.find()

    #if there are documents, display articles page and pass it the articles
    #else display articles page and pass a message
    if articles != None:
        return render_template('articles.html', articles=articles)
    else:
        msg = 'No aritcles found'
        return render_template('articles.html', msg=msg)

# specific article route, identified by id
@app.route('/article/<string:id>/')
def article(id):
    # get the collection
    col = db.articles
    # find the article by id
    article = col.find_one({'_id': ObjectId(id)})
    # display article page and pass it the article
    return render_template('article.html', article=article)

#class for RegisterForm for WTForms
class RegisterForm(Form):
    #set up the fields the form will have and validators
    # ie name has to be between 1 amd 15 characters
    name = StringField('Name', [validators.Length(min=1, max=15)])
    username = StringField('Username', [validators.Length(min=4, max=15)])
    email = StringField('Email', [validators.Length(min=6, max=20)])
    #password has validation for length and it must match the confirm password field
    password = PasswordField('Password', [
        validators.Length(min=4, max=15),
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')    
    ])
    confirm = PasswordField('Confirm Password')

# register route to register a new account
@app.route('/register', methods=['GET', 'POST'])
def register():
    # create a form of type RegisterForm
    form = RegisterForm(request.form)
    #if the request is of type POST and the form has been validated
    if request.method == 'POST' and form.validate():
        #set vars here from what has been entered on the form
        name = form.name.data
        email = form.email.data
        username = form.username.data
        #sha256 encrypt the password from the form
        password = sha256_crypt.encrypt(str(form.password.data))

        #get the user collection
        col = db.users
        #create and insert new user document
        user = {'name': name, 'email': email, 'username': username, 'password': password}
        col.insert_one(user)

        #display a message and redirect to login page
        flash('You are now registered', 'success')
        return redirect(url_for('login'))        
    #display the register page when on the register route
    return render_template('register.html', form=form)

# login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    # if request type is POST
    if request.method == 'POST':
        #not using WTForm
        #get the username and password from the form
        username = request.form['username']
        password_candidate = request.form['password']

        # get the collection
        col = db.users
        #find the user on db by the login username entered
        user = col.find_one({'username': username})
        
        #if the username is empty then its not on the db
        if user != None:
            #if user is found, use sha256 lib to verify the password entered by user and password in db
            if sha256_crypt.verify(password_candidate, user['password']):
                #if authenticated, create a session, set loggedin to true and set username in the session
                session['logged_in'] = True
                session['username'] = username
                #display a message and redirect
                flash('You are now logged in', 'success')
                return redirect(url_for('dashboard'))
            else:
                #else user entered wrong password, display login page again
                error = 'Wrong password'
                return render_template('login.html', error=error)
        else:
            #out ifs else here display error that username entered is not registered, display login page
            error = 'Username not found'
            return render_template('login.html', error=error)
    #display login page
    return render_template('login.html')

#check if user is logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        #if logged_in is set in session then user is logged in
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            #else set message and redirect to login page
            flash('Please login', 'danger')
            return redirect(url_for('login'))
    return wrap

#logout route, check if user is logged in by calling the is_logged_in method
@app.route('/logout')
@is_logged_in
def logout():
    #if logging out, clear the session, removing logged_in and username fields
    session.clear()
    #set message and redirect to login page
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))

#dashboard route, check if user is logged in to access this route
@app.route('/dashboard')
@is_logged_in
def dashboard():
    #set the collection in db
    col = db.articles
    #retrieve articles for the user that is logged in
    articles = col.find({'username': session['username']})

    #if there is results display dashboard page and pass it the articles
    if articles != None:
        return render_template('dashboard.html', articles=articles)
    else:
        #else set message and display dashboard
        msg = 'No aritcles found'
        return render_template('dashboard.html', msg=msg)

#class for ArticleForm for WTForms
class ArticleForm(Form):
    #define fields for an article and set validators required
    title = StringField('Title', [validators.Length(min=1, max=150)])
    body = TextAreaField('Body', [validators.Length(min=15)])

#add_article route, check if user is logged in to access this route
@app.route('/add_article', methods=['GET', 'POST'])
@is_logged_in
def add_article():
    #create a form of type WTForm ArticleForm
    form = ArticleForm(request.form)
    #if request is post and form is validated
    if request.method == 'POST' and form.validate():
        #set vars from the form and author from the session
        title = form.title.data
        body = form.body.data
        author = session['username']

        #set the collection
        col = db.articles
        #create article to insert
        article = {'title': title, 'body': body, 'author': author}
        #insert article document
        col.insert_one(article)

        #set message and redirect to dashboard
        flash('Article Created', 'success')
        return redirect(url_for('dashboard'))

    #display the add_article page and pass the form
    return render_template('add_article.html', form=form)

#edit_article route, identified by id, check if user is logged in to access this route 
@app.route('/edit_article/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def edit_article(id):
    #set collection
    col = db.articles
    #retrieve the article by _id
    article = col.find_one({'_id': ObjectId(id)})

    #create a form of type ArticleForm
    form = ArticleForm(request.form)

    #populate form fields which came from db
    form.title.data = article['title']
    form.body.data = article['body']

    #if request is POST and for is validated
    if request.method == 'POST' and form.validate():
        #add updated title and body from html form
        title = request.form['title']
        body = request.form['body']

        #set the collection
        col = db.articles
        #create article document
        article = {'title': title, 'body': body}
        #update the article where _id is the id coming from the route
        col.update_one({'_id': ObjectId(id)}, {"$set": article}, upsert=False)

        #set message and redirect to dashboard
        flash('Article Updated', 'success')
        return redirect(url_for('dashboard'))
    #display the edit_article page and pass the form
    return render_template('edit_article.html', form=form)

#delete article route, identified by id, only accepts POST requests, checks if user is logged in
@app.route('/delete_article/<string:id>', methods=['POST'])
@is_logged_in
def delete_article(id):
    #set the collection
    col = db.articles
    #delete the article document in db by _id, which comes from the route
    col.delete_one({'_id': ObjectId(id)})

    #set message and redirect to dashboard
    flash('Article Deleted', 'success')
    return redirect(url_for('dashboard'))

'''
#random route for testing http method
@app.route('/test')
def get_data():
    response = requests.get('http://localhost:3000/api/genres').content
    data = json.loads(response.decode('utf-8'))
    #return render_template('test.html', data=data)
    return json.dumps(data)
'''

#run the app
if __name__ == '__main__':
    #secret_key for the session
    app.secret_key='secret'
    app.run(debug=True)