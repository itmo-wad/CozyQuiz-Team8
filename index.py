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


def getCorrectOrWrong(i, keys):
    if f"correct{i}" in keys:
        return True
    return False


def allowedFile(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def getNextQuestion(room_id):
    questions = list(db.questions.find({"roomId": ObjectId(room_id)}))
    results = db.results.find_one({"roomId": ObjectId(room_id), "user": session['nickname']})
    if results:
        print('results[answers]: ', results['answers'])
        question_id = results['answers'][-1]['questionId']
        for i in range(len(questions)):
            if questions[i]['_id'] == ObjectId(question_id):
                if i + 1 < len(questions):
                    return questions[i + 1]
        return None
    return questions[0]

def checkAnswer(question, answerNumber):
    print('answerNumber', answerNumber)
    print('question: ', question)
    print('answer[0]: ', question['answers'][0])
    print('answer[0][correct]: ', question['answers'][0]['correct'])
    if question['answers'][answerNumber]['correct'] == True:
        return True
    return False

def countAnswers(questionId, answerNumber):
    if db.results.find_one({'answers.questionId': ObjectId(questionId), "answers.answerNumber": answerNumber}) is None:
        return 0
    results = db.results.find({'answers.questionId': ObjectId(questionId), "answers.answerNumber": answerNumber})
    return len(list(results))

@app.route('/')
def home():
    session.pop('nickname', None)
    if 'logged' in session:
        return redirect(url_for('myProfile'))
    return render_template('home.html')

@app.route('/enterQuiz', methods=["GET", "POST"])
def enterQuiz():
    if request.method == "GET":
        username = getLoggedUsername() # logged users will be forced to used their username as nickname
        return render_template("enterQuiz.html", username = username)
    else: #POST
        username = request.form.get("username")
        room_id = request.form.get("room_code") #room id is the same with room code
        # check if room exists
        room = db.rooms.find_one({"_id": ObjectId(room_id)})
        if room == None:
            flash("Unable to join, Room does not exist!")
            return redirect(request.url)
        else:
            # check if nickname exists in the same room
            joined = room['joined']
            if username in joined:
                flash("Nickname already Taken! :(")
                return redirect(request.url)
            else:
                # add nickname to session
                session['nickname'] = username
                # add nickname to the room
                db.rooms.update_one({"_id": ObjectId(room_id)}, {
                                "$set": {"joined": joined + [username]}}) # adds user into joinedUsers array
        return redirect(url_for('answerQuiz', room_id=room_id))

@app.route('/login', methods=["GET", "POST"])
def login():
    session.pop('nickname', None)
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
    session.pop('nickname', None)
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
        db.users.insert_one({"username": username, "password": generate_password_hash(password),
                             "profile_pic": ''})
        flash('Account Created!', 'success')
        return redirect('/')

@app.route('/userQuizzes')
def showUserQuizzes():
    username = getLoggedUsername()
    if username != '':
        quizzes = list(db.rooms.find({"owner" : username}))
        for quiz in quizzes:
            print(quiz['_id'])
        return render_template('userQuizzes.html', quizzes = quizzes) 
    return redirect(url_for('login'))       

@app.route('/createQuizVerification')
def createQuizVerification():
    username = getLoggedUsername()
    if username != '':
        return render_template("createQuizVerification.html")
    return redirect(url_for('login'))

@app.route('/createQuiz')
def createQuiz():
    username = getLoggedUsername()
    if username != '':
        room_info = db.rooms.insert_one({"owner": username})
        room_id = room_info.inserted_id
        session['room_id'] = str(room_id)
        return redirect(url_for('showRoom', room_id=room_id))
    return redirect(url_for('login'))

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
            db.users.update_one({"username": username}, {
                                "$set": {"password": generate_password_hash(newPassword)}})
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
            db.users.update_one({"username": username},
                                {"$set": {"profile_pic": filename}})
            flash('Your profile pic was successfully updated!', 'success')
            return redirect(url_for('myProfile'))
    return render_template("uploadPic.html")


@app.route('/uploads/<filename>')
def uploadedFile(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# show the room with the given id
@app.route('/rooms/<room_id>')
def showRoom(room_id):
    room = db.rooms.find_one({"_id": ObjectId(room_id)})
    if room is None:
        flash('Room not found', 'danger')
        return redirect(url_for('home'))

    questions = db.questions.find({"roomId": ObjectId(room_id)})
    print("questions: ", questions)
    return render_template("room.html", room=room, questions=questions)

@app.route('/rooms/<string:room_id>/questions/new', methods=['POST', 'GET'])
def newQuestion(room_id):
    username = getLoggedUsername()
    if username == '':
        flash('Please, login first', 'danger')
        return redirect(url_for('login'))

    room = db.rooms.find_one({"_id": ObjectId(room_id)})
    if room is None:
        flash('Room not found', 'danger')
        return redirect(url_for('home'))

    if room['owner'] != username:
        flash('You are not the owner of that room', 'danger')
        return redirect(url_for('home'))

    if request.method == 'GET':
        questions = list(db.questions.find({"room_id": ObjectId(room_id)}))
        return render_template('newQuestion.html', questions=questions, room_id=room_id)
    else:
        answers = request.form.getlist('answer')
        question = request.form.get('questionText')
        bgColors = request.form.getlist('answerBgColor')
        txtColors = request.form.getlist('answerTextColor')
        keys = request.form.keys()
        answerList = []
        for i in range(len(answers)):
            answerList.append({'number': i, 'text': answers[i], 'bgColor': bgColors[i], 'textColor': txtColors[i], 'correct': getCorrectOrWrong(i, keys)})
        db.questions.insert_one({'roomId': ObjectId(room_id), 'text': question, 'answers': answerList})
        flash("Quiz question added", "success")
        return redirect(url_for('showRoom', room_id=room_id))

@app.route('/rooms/<string:room_id>/questions/delete/<question_id>', methods=["POST"])
def deleteQuestion(room_id, question_id):
    if request.method == "POST":
        username = getLoggedUsername()
        if username == '':
            flash('Please, login first', 'danger')
            return redirect(url_for('login'))

        room = db.rooms.find_one({"_id": ObjectId(room_id)})
        if room is None:
            flash('Room not found', 'danger')
            return redirect(url_for('home'))
        if room['owner'] != username:
            flash('You are not the owner of that room', 'danger')
            return redirect(url_for('home'))

        if db.questions.delete_one({"_id": ObjectId(question_id)}):
            flash("Question deleted", "success")
            return redirect(url_for('showRoom', room_id=room_id))
        flash('Question not found', 'danger')
        return redirect(url_for('showRoom', room_id=room_id))

@app.route('/answerQuiz/<string:room_id>/', methods=['GET', 'POST'])
def answerQuiz(room_id):
    if 'nickname' not in session:
        flash('Please, join the room first', 'warning')
        return redirect(url_for('home'))

    room = db.rooms.find_one({"_id": ObjectId(room_id)})
    if room is None:
        flash('Room not found', 'danger')
        return redirect(url_for('home'))

    if request.method == 'GET':
        if db.questions.find_one({"roomId": ObjectId(room_id)}) is None:
            flash('No questions in this room', 'danger')
            return redirect(url_for('home'))
        question = getNextQuestion(room_id)
        if question is None:
            flash('You finished your quiz', 'success')
            session.pop('nickname', None)
            return redirect(url_for('results', room_id=room_id))
        return render_template('answerQuiz.html', question=question, room=room)
    else:
        questionId = request.form.get('questionId')
        question = db.questions.find_one({"_id": ObjectId(questionId)})
        answerNumber = request.form.get('answerNumber', type=int)
        result = db.results.find_one({"roomId": ObjectId(room_id), "user": session['nickname']})
        if result is None:
            db.results.insert_one({'roomId': ObjectId(room_id), 'user': session['nickname'],
             'answers': [{'questionId': questionId, 'answerNumber': answerNumber,
             'correct': checkAnswer(question, answerNumber)}]})
        else:
            newAnswersArray = result['answers'] + [{'questionId': questionId,
                                'answerNumber': answerNumber,
                                'correct': checkAnswer(question, answerNumber)}]
            db.results.update_one({"roomId": ObjectId(room_id), "user": session['nickname']},
                                {"$set": {"answers": newAnswersArray}})
        return redirect(url_for('answerQuiz', room_id=room_id))

@app.route('/results/<string:room_id>')
def showResults(room_id):
    room = db.rooms.find_one({"_id": ObjectId(room_id)})
    if room is None:
        flash('Room not found', 'danger')
        return redirect(url_for('home'))

    results = db.results.find_one({"roomId": ObjectId(room_id), "user": session['nickname']})
    if results is None:
        flash('You have not answered any questions yet', 'danger')
        return redirect(url_for('home'))

    rightAnswers = 0
    resultsTemplate = []
    for answer in results['answers']:
        question = db.questions.find_one({"_id": ObjectId(answer['questionId'])})
        answers = []
        for questionAnswer in question['answers']:
            if questionAnswer['correct']:
                if questionAnswer['number'] == answer['answerNumber']:
                    rightAnswers += 1
                answers.append({'text': questionAnswer['text'], 'bgColor': questionAnswer['bgColor'], 'textColor': questionAnswer['textColor'], 'check': True})
            elif questionAnswer['number'] == answer['answerNumber']:
                answers.append({'text': questionAnswer['text'], 'bgColor': questionAnswer['bgColor'], 'textColor': questionAnswer['textColor'], 'check': False})
            else:
                answers.append({'text': questionAnswer['text'], 'bgColor': questionAnswer['bgColor'], 'textColor': questionAnswer['textColor'], 'check': None})
        resultsTemplate.append({'question': question['text'], 'answers': answers})

    score = [rightAnswers, len(list(db.questions.find({"roomId": ObjectId(room_id)})))]
    return render_template('showResults.html', results=resultsTemplate, score=score)

@app.route('/rooms/<string:room_id>/results')
def showRoomResults(room_id):
    username = getLoggedUsername()
    if username == '':
        flash('Please, login first', 'danger')
        return redirect(url_for('login'))

    room = db.rooms.find_one({"_id": ObjectId(room_id)})
    if room is None:
        flash('Room not found', 'danger')
        return redirect(url_for('home'))

    if room['owner'] != username:
        flash('You are not the owner of this room', 'danger')
        return redirect(url_for('home'))

    results = db.results.find({"roomId": ObjectId(room_id)})
    if results is None:
        flash('No results in this room', 'danger')
        return redirect(url_for('home'))

    questions = db.questions.find({"roomId": ObjectId(room_id)})
    if questions is None:
        flash('No questions in this room', 'danger')
        return redirect(url_for('home'))

    questionsTemplate = []
    for question in list(questions):
        answers = []
        for questionAnswer in question['answers']:
            answers.append({'text': questionAnswer['text'], 'bgColor': questionAnswer['bgColor'],
             'textColor': questionAnswer['textColor'], 'check': questionAnswer['correct'], "chooseBy": countAnswers(question['_id'], questionAnswer['number'])})
        questionsTemplate.append({'question': question['text'], 'answers': answers})

    return render_template('showRoomResults.html', results=questionsTemplate)

if __name__ == '__main__':
    db.users.drop()
    # db.questions.drop()
    # db.rooms.drop()
    # db.results.drop()

    db.users.insert_one(
        {"username": "123", "password": generate_password_hash('123'), "profile_pic": '624afbe60c0ab501b81b0517.png'})
    # db.rooms.insert_one({"_id": '1', "owner": '123', "joined": [{"username" : "gabriel"}]})
    # db.rooms.insert_one({"_id": '2', "owner": '123', "joined": [{"username" : "gabriel"}]})
    # db.questions.insert_one({"room": "id of the room","text": 'A question?', "answers": [{"text": 'text for the answer 1', "color": 'hex code for a answer', "correct": True}, {"text": 'text for the answer 2', "color": 'hex code for a answer', "correct": False}]})
    # db.results.insert_one({"user": "a username", "room": "id_room", "answers": [{"question_num": "the question number", "answer": 3, "correct": False, "time": 10}]})
    db.questions.drop()
    db.rooms.drop()
    db.rooms.insert_one({"owner": "123"})
    room = db.rooms.find_one({"owner": "123"})
    print(room)
    db.questions.insert_one(
        {"roomId": room["_id"], "text": "What is the capital of Poland?",
         "answers": [{"number": 0, "text": "Warsaw", "bgColor": "#eeeeee", "textColor": "#212529", "correct": True},
                     {"number": 1, "text": "Helsinki", "bgColor": "#eeeeee", "textColor": "#212529", "correct": False}]})
    db.questions.insert_one(
        {"roomId": room["_id"], "text": "Europe is separated from Africa by which sea?",
         "answers": [{"number": 0, "text": "Mediterranean Sea", "bgColor": "#eeeeee", "textColor": "#212529", "correct": True},
                     {"number": 1, "text": "Bering Sea", "bgColor": "#eeeeee", "textColor": "#212529", "correct": False}]})
    db.questions.insert_one(
        {"roomId": room["_id"], "text": "Which of Shakespeare’s plays is the longest?",
         "answers": [{"number": 0, "text": "Macbeth", "bgColor": "#eeeeee", "textColor": "#212529", "correct": False},
                     {"number": 1, "text": "Hamlet", "bgColor": "#eeeeee", "textColor": "#212529", "correct": True}]})
    db.questions.insert_one(
        {"roomId": room["_id"], "text": "Which nuts give marzipan its distinctive taste?",
         "answers": [{"number": 0, "text": "Walnut", "bgColor": "#eeeeee", "textColor": "#212529", "correct": False},
                     {"number": 1, "text": "Almonds", "bgColor": "#eeeeee", "textColor": "#212529", "correct": True}]})
    db.questions.insert_one(
        {"roomId": room["_id"], "text": "How many bones are in the adult human body?",
         "answers": [{"number": 0, "text": "around 205", "bgColor": "#eeeeee", "textColor": "#212529", "correct": True},
                     {"number": 1, "text": "around 180", "bgColor": "#eeeeee", "textColor": "#212529", "correct": False}]})

    app.run(host='localhost', port=5000, debug=True)
