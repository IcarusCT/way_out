from enum import unique
import pstats
from unicodedata import category
from flask import Flask,render_template,request,redirect,url_for
from flask.helpers import flash
from flask_login import LoginManager,UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import re
from functools import wraps

app = Flask(__name__)

app.config['SECRET_KEY'] = '9OLWxND4o83j4K4iuopO'
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///site.db"
db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    __tablename__= 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(50))
    surname = db.Column(db.String(50))
    password = db.Column(db.String(128))
    posts=db.relationship('Post', backref='owner')
    votes=db.relationship('Vote', backref='owner_vote')
    comments=db.relationship('Comment', backref='owner')
    is_admin = db.Column(db.Boolean,default = False)
    

class Category(db.Model):
    __tablename__= 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)

class Post(db.Model):
    __tablename__= 'post'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer , db.ForeignKey('user.id'))
    content = db.Column(db.Text)
    category = db.Column(db.Integer , db.ForeignKey('category.id'))
    link = db.Column(db.Text)
    link_text = db.Column(db.String(25))
    comments = db.relationship('Comment', backref='post')
    status = db.Column(db.Integer , default = 0)# 0 onaylanmadı | 1 onaylandı | 2 işleme alındı | 3 çözüldü
    # 0 = red
    # 1 = black
    # 2 = yellow
    # 3 = green
    votes=db.relationship('Vote', backref='owner_post')
    created_date = db.Column(db.DateTime,default=datetime.datetime.now)
    def liked(self):
        try:
            for i in self.votes:
                if i.owner_id==current_user.id:
                    return True
            return False
        except:
            return False
    def status_color(self):
        if self.status==0:
            return "red"
        if self.status==1:
            return "black"
        if self.status==2:
            return "yellow"
        if self.status==3:
            return "green"
    def get_category(self):
        return Category.query.filter_by(id=self.category).first().name

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer , db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer , db.ForeignKey('post.id'))
    comment = db.Column(db.String(1000))
    created_date = db.Column(db.DateTime,default=datetime.datetime.now)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer , db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer , db.ForeignKey('post.id'))

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def is_admin(f):
    @wraps(f)
    def wrap(*args, **kwargs):

        if current_user.is_admin:
            return f(*args, **kwargs)
        return "access denied" , 403
    return login_required(wrap)

@app.route('/')
def index():
    return render_template("index.html",posts=Post.query.filter(Post.status >= 1),categorys=Category.query.all())

@app.route('/filter_category/<int:id>')
def filter_category(id):
    return render_template("index.html",posts=Post.query.filter(and_(Post.status >= 1,Post.category==id))[::-1],categorys=Category.query.all())

@app.route('/view_post/<int:id>')
def view_post(id):
    return render_template("view_post.html",post=Post.query.filter_by(id=id).first())

@app.route('/vote_post/<int:id>')
@login_required
def vote_post(id):
    post=Post.query.filter_by(id=id).first()
    if not post:
        return redirect(url_for('index'))
    elif post.status==0:
        return redirect(url_for('index')) 
    for i in Post.query.filter_by(id=id).first().votes:
        if i.owner_id==current_user.id:
            db.session.delete(i)
            db.session.commit()
            return "ok"
    vote=Vote(owner_id=current_user.id,post_id=id)
    db.session.add(vote)
    db.session.commit()
    return "ok"

@app.route('/create_post',methods=['POST','GET'])
@login_required
def create_post():
    if request.method=="POST":
        category = int(request.form.get('category'))
        content = request.form.get('content')
        link = request.form.get('link')
        link_name = request.form.get('link_name')
        status=0
        if current_user.is_admin:
            status=1
        post=Post(owner=current_user,content=content,link=link,link_text=link_name,category=category,status=status)
        db.session.add(post)
        db.session.commit()
        flash("New post has been created. Admin confirmation is expected!","success")
        return redirect(url_for('profile',id=current_user.id))
    return render_template("create_post.html",categorys=Category.query.all())

@app.route('/profile/<int:id>')
def profile(id):
    return render_template("profile.html",user=User.query.filter_by(id=id).first())

@app.route('/login',methods=['POST','GET'])
def login():
    if request.method=="POST":
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            flash("Login Failed!" , category="danger")
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('index'))
    return render_template("login.html")

@app.route('/users')
@is_admin
def users():
    users = User.query.all()
    return render_template("users.html" , title='Users' , users = users )

@app.route('/delete/<int:id>')
@is_admin
def delete(id):
    user = User.query.filter_by(id=id).first()
    if user and not user.is_admin:
        for vote in user.votes :
            db.session.delete(vote)
        for comment in user.comments :
            db.session.delete(comment)
        for post in user.posts :
            for vote in post.votes :
                db.session.delete(vote)
            for comment in post.comments :
                db.session.delete(comment)
            db.session.delete(post)


        db.session.delete(user)
        db.session.commit()
        flash("User has been removed succesfully!" , category="success")
    else:
        flash("User removel failed!" , category="danger")
    return redirect(url_for("users"))

@app.route('/create_category',methods=['POST','GET'])
@is_admin
def create_category():
    if request.method=="POST":
        category = request.form.get('category')
        c=Category(name=category)
        db.session.add(c)
        db.session.commit()
        return redirect(url_for('create_category'))
    return render_template("create_category.html")

@app.route("/add_comment/<int:id>",methods=["POST"])
@login_required
def add_comment(id):
    post=Post.query.filter_by(id=id).first()
    if not post:
        flash("Post couldn't be found!")
        return redirect(url_for('index'))
    elif post.status==0:
        flash("Post couldn't be found!")
        return redirect(url_for('index')) 
    content = request.form.get('content')
    comment=Comment(owner_id=current_user.id,post_id=id,comment=content)
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('view_post',id=id))

@app.route("/register", methods=["POST","GET"])
def register():
    if request.method=="POST":
        password = generate_password_hash(request.form.get("password"))            
        name = request.form.get("name")
        surname = request.form.get("surname")
        username = request.form.get("username")
        #burada hata varsa asagiya geciyor
        try:
            if len(password) < 4 or len(name) <1 or len(surname) <1 or len(username) <1:
                flash("Please do not use 'space'!" , category="danger") 
                return render_template("register.html")
        except:
            flash("Please do not use 'space'!" , category="danger") 
            return render_template("register.html")
        new_user = User(password=password , name=name , surname=surname , username=username)
        db.session.add(new_user)
        try:
            db.session.commit()
        except:
            flash("An error has been occured.")
            return redirect(url_for("register"))
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/edit_post/<int:id>", methods=["POST","GET"])
@login_required
def edit_post(id):
    if request.method=="POST":
        post=Post.query.filter_by(id=id).first()
        post.category = int(request.form.get('category'))
        post.content = request.form.get('content')
        post.link = request.form.get('link')
        post.link_text = request.form.get('link_name')
        db.session.commit()
        flash("Post has been edited succesfully!","success")
        return redirect(url_for('view_post',id=id))
    post=Post.query.filter_by(id=id).first()
    if not post:
        flash("Post couldn't be found!")
        return redirect(url_for('index')) 
    if current_user.id!=post.owner.id and not current_user.is_admin:
        flash("Post couldn't be found!")
        return redirect(url_for('index')) 
    return render_template("edit_post.html",post=Post.query.filter_by(id=id).first(),categorys=Category.query.all())

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/approve')
@is_admin
def approve():
    return render_template("approve.html",posts=Post.query.filter(Post.status == 0))

@app.route('/approve/<int:id>')
@is_admin
def approved(id):
    post=Post.query.filter_by(id=id).first()
    if not post:
        flash("Post couldn't be found!")
        return redirect(url_for('approve'))
    post.status=1
    db.session.commit()
    return redirect(url_for('approve'))

@app.route('/processing/<int:id>')
@is_admin
def processing(id):
    post=Post.query.filter_by(id=id).first()
    if not post:
        flash("Post couldn't be found!")
        return redirect(url_for('index'))
    post.status=2
    db.session.commit()
    return redirect(url_for('view_post' , id=id))

@app.route('/solved/<int:id>')
@is_admin
def solved(id):
    post=Post.query.filter_by(id=id).first()
    if not post:
        flash("Post couldn't be found!")
        return redirect(url_for('index'))
    post.status=3
    db.session.commit()
    return redirect(url_for('view_post' , id=id)) 


@app.route('/delete_post/<int:id>')
@login_required
def delete_post(id):
    post=Post.query.filter_by(id=id).first()
    if not post:
        flash("Post couldn't be found!")
        return redirect(url_for('index'))
    if not current_user.is_admin and post.owner.id != current_user.id:
        flash("You do not have any authority for this operation!")
        return redirect(url_for('index'))
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == "__main__":
    db.create_all()
    if User.query.filter_by(username = "admin").first()==None:
        admin = User(password=generate_password_hash("password") , name="admin" , surname="admin" , username="admin" , is_admin=True)
        db.session.add(admin)
        db.session.commit()
    app.run(debug=True)