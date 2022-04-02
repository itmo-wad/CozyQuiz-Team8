from flask import Flask, request, render_template, url_for, redirect, flash, session, send_from_directory
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import os
from bson.objectid import ObjectId
from faker import Faker


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


faker = Faker()
client = MongoClient('localhost', 27017)
db = client.cozyQuiz
app = Flask(__name__)
app.secret_key = 'super secret key'
app.config['UPLOAD_FOLDER'] = './upload'
app.config['SECRET_KEY'] = 'super secret key'
auth = HTTPBasicAuth()


def checkPassword(username, password):
    user = db.users.find_one({"username": username})
    if user:
        if check_password_hash(user['password'], password):
            session['logged'] = f"{user['_id']}"
            return True
    return False

def getLoggedUsername():
    if 'logged' in session:
        user = findUserById(session['logged'])
        if user:
            return user['username']
        session.pop('logged', None)
    return ''

def findUserById(id):
    return db.users.find_one(ObjectId(id))

def getProfilePic():
    user = db.users.find_one(ObjectId(session['logged']))
    if user:
        if user['profile_pic'] != '':
            return url_for('uploadedFile', filename=user['profile_pic'])
    return 'static/icon.png'

def allowedFile(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "GET":
        username = getLoggedUsername()
        if username == '':
            return render_template("login.html")
        return redirect(url_for('myProfile'))
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        if checkPassword(username, password):
            return redirect(url_for('myProfile'))
        flash('Login Error', 'danger')
        return redirect(request.url)

@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        if username == '':
            flash('Invalid Username', 'danger')
            return redirect(request.url)
        if db.users.find_one({"username": username}) is not None:
            flash('That Username is taken!', 'danger')
            return redirect(request.url)
        if password == '':
            flash('Invalid Password', 'danger')
            return redirect(request.url)
        db.users.insert_one({"username": username, "password": generate_password_hash(password), "profile_pic": ''})
        flash('Account Created!', 'success')
        return redirect('/')

@app.route('/myProfile')
def myProfile():
    username = getLoggedUsername()
    if username != '':
        return render_template("myProfile.html", username=username, profilePic=getProfilePic())
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    if 'logged' in session:
        session.pop('logged', None)
    return redirect('/')

@app.route('/changePassword', methods=["GET", "POST"])
def changePassword():
    if request.method == "GET":
        return render_template("changePassword.html")
    else:
        username = getLoggedUsername()
        if username == '':
            return redirect(url_for('login'))
        oldPassword = request.form.get("oldPassword")
        newPassword = request.form.get("newPassword")
        if oldPassword == '':
            flash('Invalid Old Password', 'danger')
            return redirect(request.url)
        if newPassword == '':
            flash('Invalid New Password', 'danger')
            return redirect(request.url)
        if checkPassword(username, oldPassword):
            if oldPassword == newPassword:
                flash('New Password must be different from Old Password', 'danger')
                return redirect(request.url)
            db.users.update_one({"username": username}, {"$set": {"password": generate_password_hash(newPassword)}})
            flash('Password Changed', 'success')
            return redirect(url_for('myProfile'))
        flash('Invalid Old Password', 'danger')
        return redirect(request.url)

@app.route('/updateProfilePic', methods=['GET', 'POST'])
def uploadProfilePic():
    username = getLoggedUsername()
    if username == '':
        flash('Please, login first', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if not allowedFile(file.filename):
            flash('Invalid file extension', 'danger')
            return redirect(request.url)
            
        if file and allowedFile(file.filename):
            extension = file.filename.rsplit('.', 1)[1].lower()
            filename = secure_filename(session['logged'] + '.' + extension)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            db.users.update_one({"username": username}, {"$set": {"profile_pic": filename}})
            flash('Your profile pic was successfully updated!', 'success')
            return redirect(url_for('myProfile'))
    return render_template("uploadPic.html")
       
@app.route('/uploads/<filename>')
def uploadedFile(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    db.users.drop()

    db.users.insert_one({"username": "user", "password": generate_password_hash('123'), "profile_pic": ''})
    # db.rooms.insert_one({"owner": 'username of the owner'})
    # db.questions.insert_one({"room": "id of the room","text": 'A question?', "answers": [{"text": 'text for the answer 1', "color": 'hex code for a answer', "correct": True}, {"text": 'text for the answer 2', "color": 'hex code for a answer', "correct": False}]})
    # db.results.insert_one({"user": "a username", "answers": [{"question_num": "the question number", "answer": 3, "correct": False, "time": 10}]})

    app.run(host='localhost', port=5000, debug=True)