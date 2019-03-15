from flask import(Flask, render_template, request, redirect, jsonify,
                  url_for, flash, g, session as login_session)
from sqlalchemy import create_engine, desc
from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker, joinedload
from models import Base, Categories, Items, User
import json
from flask import make_response
import requests
import random
import string
import os
from flask.ext.httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()
# Connect to Database and create database session
engine = create_engine('sqlite:///ItemCatalog.db')
Base.metadata.bind = engine

app = Flask(__name__)
DBSession = sessionmaker(bind=engine)
session = DBSession()
app.secret_key = os.urandom(32)


@app.before_request
def before_request():
    g.user = None
    if 'user' in login_session:
        g.user = login_session['user']


@app.route('/catalog/logup', methods=['GET', 'POST'])
def log_up():
    error_msg = None
    if request.method == 'POST':
        user_name = request.form['user_name']
        password = request.form['password']
        if session.query(User).filter_by(username=user_name).first() is not None:
            error_msg = 'Please try different username.'  # existing user
            # If a user exists redirect to login page
            return render_template('logup.html', error_msg=error_msg)
        user = User(username=user_name)
        user.hash_password(password)
        session.add(user)
        session.commit()
        flash('Welcome, %s!!' % user_name)
        return redirect(url_for('catalog'))
    else:
        return render_template('logup.html')


@app.route('/catalog/login', methods=['GET', 'POST'])
def login():
    error_msg = None
    if request.method == 'POST':
        login_session.pop('user', None)
        user_name = request.form['user_name']
        password = request.form['password']
        user = session.query(User).filter_by(username=user_name).first()
        # Check if the user exists
        if user is not None:
            # Verify the entered password from the form with
            # the user's password in DB
            if not user.verify_password(password):
                error_msg = 'Invalid credentials, try again'
                return render_template('login.html', error_msg=error_msg)
            else:
                login_session['user'] = user_name
                # protected page with add new items,edit,delete
                flash('Welcome, %s!!' % user_name)
                return redirect(url_for('catalog'))
        else:
            error_msg = 'You do not have an account, sign up please.'
            return render_template('logup.html', error_msg=error_msg)
    else:
        return render_template('login.html')


@app.route('/catalog/logout')
def logout():
    flash('logged out, Come back again %s' % login_session['user'])
    login_session.pop('user', None)
    return redirect(url_for('catalog'))


@app.route('/catalog.json')
def catalogJSON():
    categories = DBSession().query(Categories).options(joinedload(Categories.items)).all()
    return jsonify(Catalog=[dict(c.serialize, items=[i.serialize for i in c.items])for c in categories])


@app.route('/catalog', methods=['GET', 'POST'])
def catalog():
    categories = session.query(Categories).all()
    items = session.query(Items).order_by(desc(Items.id)).limit(10).all()
    category_list = []
    if g.user:
        '''
        make a list of dictionary to store the categories
        names and to be able to display the category
        name with each item
        '''
        for c in categories:
            category_list.append(dict(id=c.id, name=c.name))
        return render_template('catalog.html', categories=categories,
                               items=items, category_list=category_list)
    return render_template('public_catalog.html', categories=categories,
                           items=items, category_list=category_list)


@app.route('/catalog/<int:category_id>/items', methods=['GET', 'POST'])
def getItemsOfCategory(category_id):
    items = session.query(Items).filter_by(cat_id=category_id).all()
    category = session.query(Categories).filter_by(id=category_id).one()
    name = category.name
    count = 0
    for item in items:
        count += 1
    if g.user:
        return render_template('items.html', items=items, count=count,
                               name=name)
    return render_template('public_items.html', items=items, count=count,
                           name=name)


@app.route('/catalog/<int:category_id>/<title>')
def getItem(category_id, title):
    item = session.query(Items).filter_by(title=title).one()
    if g.user:
        return render_template('item_description.html', item=item)
    return render_template('public_item_description.html', item=item)


@app.route('/catalog/<title>/edit', methods=['GET', 'POST'])
def editItem(title):
    if g.user:
        getuser = session.query(User).filter_by(username=login_session['user']).first()
        # Check if the user.id == user_id in Items tables to nauthorize change
        item_to_edit = session.query(Items).filter_by(user_id=getuser.id,
                                                      title=title).first()
        if item_to_edit is None:
            flash('Protected, Item cannot be edited.')
            return redirect(url_for('catalog'))
        else:
            categories = session.query(Categories).all()
            if request.method == 'POST':
                if request.form.get('title', False):
                    item_to_edit.title = request.form['title']
                if request.form.get('description', False):
                    item_to_edit.description = request.form['description']
                if request.form.get('id', False):
                    item_to_edit.cat_id = request.form['id']
                session.add(item_to_edit)
                session.commit()
                flash('Item Edited')
                return redirect(url_for('catalog'))
            else:
                return render_template('edit_item.html', item=item_to_edit,
                                       categories=categories)
    return 'Unauthorized Access!'


@app.route('/catalog/<title>/delete', methods=['GET', 'POST'])
def deleteItem(title):
    if g.user:
        getuser = session.query(User).filter_by(username=login_session['user']).first()
        item_to_delete = session.query(Items).filter_by(user_id=getuser.id,
                                                        title=title).first()
        if item_to_delete is None:
            flash('Protected, Item cannot be deleted.')
            return redirect(url_for('catalog'))
        else:
            if request.method == 'POST':
                session.delete(item_to_delete)
                session.commit()
                flash('Item deleted!')
                return redirect(url_for('catalog'))
            else:
                return render_template('deleteItem.html', item=item_to_delete)
    return 'Unauthorized Access!'


@app.route('/catalog/my_items')
def myitems():
    if g.user:
        getuser = session.query(User).filter_by(username=login_session['user']).first()
        items = session.query(Items).filter_by(user_id=getuser.id).all()
        count = 0
        for item in items:
            count += 1
        return render_template('myitems.html', items=items,
                               username=login_session['user'], count=count)
    return 'Unauthorized Access!'


@app.route('/catalog/new_item', methods=['GET', 'POST'])
def newItem():
    if g.user:
        categories = session.query(Categories).all()
        if request.method == 'POST':
            getuser = session.query(User).filter_by(username=login_session['user']).first()
            getuser_id = getuser.id
            new_item = Items(user_id=getuser_id,
                             title=request.form.get('title', False),
                             description=request.form.get('description', False),
                             cat_id=request.form.get('id', False))
            session.add(new_item)
            session.commit()
            flash('New item created!')
            return redirect(url_for('catalog'))
        else:
            return render_template('newItem.html', categories=categories)
    return 'Unauthorized Access!'

'''
#Run this only once, to avoid repetition
#You can Add more Categories
category1 = Categories( name='food')
category2 = Categories( name='clothes')
category3 = Categories( name='sports')
category4 = Categories( name='news')
category5 = Categories( name='stories')
category6 = Categories( name='movies')
session.add(category1)
session.add(category2)
session.add(category3)
session.add(category4)
session.add(category5)
session.add(category6)
session.commit()
'''

if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
